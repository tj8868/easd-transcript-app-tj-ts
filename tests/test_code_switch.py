"""
v9.0 tests: Bangla/English switching for whisper-bengaliai
(docs/designs/bilingual_local_transcription.md).

What is real and what is simulated
----------------------------------
* transcribe_local_audio(), the stretch splitter, the detector rule, the run planner, the model
  download/registry code and the fail-soft paths are the REAL production code.
* Whisper models are fakes, and Silero VAD is replaced by an energy detector: the test audio is
  pure tones (300 Hz = English, 700 Hz = Bangla) that Silero does not treat as speech.
* No model is downloaded: huggingface_hub.snapshot_download is replaced where it is exercised.
"""
import math
import os
import wave
from unittest.mock import patch

import numpy as np
import pytest

import local_whisper_engine as lwe

SR = 16000
TONE = {"en": 300.0, "bn": 700.0}
TEXT = {"en": "We agreed the next steps.", "bn": "আমরা পরবর্তী পদক্ষেপ ঠিক করেছি।"}
GIBBERISH = "বিবিবিবি ఈ సమావేశంలో"


# ----------------------------------------------------------------------------- audio helpers
def tone_audio(pieces):
    """pieces: [(kind, seconds)] with kind 'en', 'bn', 'silence' or 'quiet' (very low tone)."""
    out = []
    for kind, secs in pieces:
        n = int(secs * SR)
        t = np.arange(n) / SR
        if kind == "silence":
            out.append(np.zeros(n, dtype=np.float32))
        elif kind == "quiet":
            out.append((0.02 * np.sin(2 * math.pi * TONE["bn"] * t)).astype(np.float32))
        else:
            out.append((0.3 * np.sin(2 * math.pi * TONE[kind] * t)).astype(np.float32))
    return np.concatenate(out)


def write_wav(path, pieces):
    audio = tone_audio(pieces)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    return str(path)


def dominant_language(audio):
    if len(audio) == 0 or float(np.abs(audio).mean()) < 1e-3:
        return None
    spec = np.abs(np.fft.rfft(audio[:SR * 5]))
    freq = np.fft.rfftfreq(min(len(audio), SR * 5), 1 / SR)[int(np.argmax(spec))]
    return "en" if abs(freq - TONE["en"]) < abs(freq - TONE["bn"]) else "bn"


def fake_vad(audio, vad_options=None, sampling_rate=SR, **kw):
    """Energy VAD with Silero's output shape: frames above 0.01 RMS are speech; gaps shorter
    than min_silence_duration_ms are bridged."""
    frame = int(0.01 * sampling_rate)
    n = len(audio) // frame
    if n == 0:
        return []
    rms = np.sqrt(np.square(audio[:n * frame]).reshape(n, frame).mean(axis=1))
    speech = rms > 0.01
    min_gap = int((vad_options.min_silence_duration_ms if vad_options else 1000) / 10)
    spans, start, gap = [], None, 0
    for i, s in enumerate(speech):
        if s:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                spans.append({"start": start * frame, "end": (i - gap + 1) * frame})
                start, gap = None, 0
    if start is not None:
        spans.append({"start": start * frame, "end": (n - gap) * frame})
    return spans


# ----------------------------------------------------------------------------- fake models
class Seg:
    def __init__(self, start, end, text, avg_logprob=-0.2):
        self.start, self.end, self.text = start, end, text
        self.avg_logprob, self.no_speech_prob, self.compression_ratio = avg_logprob, 0.02, 1.3


class Info:
    def __init__(self, language):
        self.language, self.language_probability = language, 0.9


class FakeModel:
    """kind 'bn' = whisper-bengaliai, 'en' = small.en. Writes the right text only when asked to
    decode audio in its true language; records every call."""

    def __init__(self, kind, fail=False):
        self.kind, self.fail, self.calls = kind, fail, []

    def detect_language(self, audio=None, **kw):
        lang = dominant_language(audio)
        probs = [("en", 0.8), ("bn", 0.1), ("hi", 0.1)] if lang == "en" else [("hi", 0.5), ("bn", 0.4), ("en", 0.1)]
        return probs[0][0], probs[0][1], probs

    def transcribe(self, audio, language=None, initial_prompt=None, **kw):
        import faster_whisper
        self.calls.append({"language": language, "prompt": initial_prompt})
        if self.fail:
            raise RuntimeError("decoder crashed")
        data = faster_whisper.decode_audio(audio) if isinstance(audio, str) else audio
        segs = []
        for start in range(0, len(data), SR * 10):
            window = data[start:start + SR * 10]
            true_lang = dominant_language(window)
            if true_lang is None:
                continue
            s, e = start / SR, (start + len(window)) / SR
            ok = (language or true_lang) == true_lang and (self.kind == true_lang)
            # unique per window: the engine drops consecutive identical lines as duplicates
            segs.append(Seg(s, e, f"{TEXT[true_lang]} ({start // SR})" if ok else f"{GIBBERISH} {start // SR}",
                            -0.2 if ok else -1.7))
        return iter(segs), Info(language or "en")


# ----------------------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    """Isolated model folders, empty caches, switching settings at their defaults."""
    aux = {k: (str(tmp_path / "models" / os.path.basename(d)), repo) for k, (d, repo) in lwe._AUX_MODELS.items()}
    monkeypatch.setattr(lwe, "_AUX_MODELS", aux)
    monkeypatch.setattr(lwe, "_AUX_DOWNLOAD_FAILED", {})
    monkeypatch.setattr(lwe, "_LOCAL_MODELS", {})
    for name in ("EASD_CS_DETECTOR", "EASD_CS_MIN_PAUSE_SEC", "EASD_CS_MAX_STRETCH_SEC", "EASD_CS_MIN_LID_SEC",
                 "EASD_CS_EN_THRESHOLD", "EASD_CS_MIN_FREE_MB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EASD_CODE_SWITCH", "0")
    yield


def install_fake_weights(kind):
    folder = lwe._AUX_MODELS[kind][0]
    os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, "model.bin"), "wb").close()
    return folder


def run_engine(path, bn_model, en_model=None, detector=None, language=None, code_switch=True, ready=True):
    """transcribe_local_audio with fake models; switching models injected through _load_aux_model."""
    aux = {"en": en_model, "tiny": detector, "base": detector}
    with patch.object(lwe, "get_local_whisper_model", return_value=bn_model), \
         patch.object(lwe, "resolve_whisper_model_choice", return_value=("bengaliai", "auto")), \
         patch.object(lwe, "_load_aux_model", side_effect=lambda k: aux.get(k)) as load_aux, \
         patch.object(lwe, "_code_switch_ready", return_value=(ready, "" if ready else "test: not ready")), \
         patch("faster_whisper.vad.get_speech_timestamps", side_effect=fake_vad), \
         patch("speaker_diarization.diarize_wav_segments", return_value=None), \
         patch("local_llm_engine.release_for_transcription", return_value=False):
        res = lwe.transcribe_local_audio(path, language=language, mime_type="audio/wav", beam_size=1,
                                         code_switch=code_switch)
    return res, load_aux


# ----------------------------------------------------------------------------- splitter
def test_splitter_splits_at_pauses_and_bridges_short_gaps(monkeypatch):
    audio = tone_audio([("bn", 5), ("silence", 1), ("en", 4), ("silence", 0.3), ("en", 3)])
    with patch("faster_whisper.vad.get_speech_timestamps", side_effect=fake_vad):
        st = lwe._split_speech_stretches(audio)
    assert len(st) == 2, st
    assert st[0][0] == pytest.approx(0, abs=0.05) and st[0][1] == pytest.approx(5, abs=0.05)
    assert st[1][0] == pytest.approx(6, abs=0.05) and st[1][1] == pytest.approx(13.3, abs=0.05)


def test_splitter_joins_a_stretch_split_by_the_vad_block_edge():
    # Silero runs on 30 s blocks and re-detects speech ~0.7 s into the next block
    def vad(audio, vad_options=None, sampling_rate=SR, **kw):
        n = len(audio) / SR
        return [{"start": int(24 * SR), "end": len(audio)}] if n == 30 else [{"start": int(0.7 * SR), "end": int(5 * SR)}]
    with patch("faster_whisper.vad.get_speech_timestamps", side_effect=vad):
        st = lwe._split_speech_stretches(np.zeros(SR * 40, dtype=np.float32))
    assert st == [(24.0, 35.0)], st


def test_splitter_caps_long_stretches_at_quiet_points():
    # 70 s of continuous speech with two quiet dips (still "speech" for the VAD)
    audio = tone_audio([("bn", 22), ("quiet", 0.3), ("bn", 23), ("quiet", 0.3), ("bn", 24.4)])
    with patch("faster_whisper.vad.get_speech_timestamps", side_effect=fake_vad):
        st = lwe._split_speech_stretches(audio)
    assert all(e - s <= 30.0 + 1e-6 for s, e in st), st
    assert len(st) >= 3, st
    assert st[0][1] == pytest.approx(22.15, abs=0.2)  # cut inside the first quiet dip
    assert st[0][0] == pytest.approx(0, abs=0.05) and st[-1][1] == pytest.approx(70, abs=0.05)


# ----------------------------------------------------------------------------- detector rule
class Probs:
    def __init__(self, probs):
        self.probs = probs

    def detect_language(self, audio=None, **kw):
        return self.probs[0][0], self.probs[0][1], self.probs


@pytest.mark.parametrize("probs,expect", [
    ([("en", 0.55), ("bn", 0.45)], "bn"),               # below the 0.6 English threshold
    ([("en", 0.65), ("bn", 0.35)], "en"),
    ([("en", 0.5), ("hi", 0.3), ("bn", 0.2)], "bn"),    # Hindi counts as Bangla: p(en) = 0.5
    ([("te", 0.9), ("en", 0.08), ("bn", 0.02)], "en"),  # only bn/en compete: p(en) = 0.8
    ([("te", 0.9)], "bn"),                              # no bn/en mass at all -> Bangla
])
def test_stretch_language_rule(probs, expect):
    lang, _ = lwe._stretch_language(Probs(probs), np.zeros(SR, dtype=np.float32))
    assert lang == expect


def test_en_threshold_is_read_at_call_time(monkeypatch):
    monkeypatch.setenv("EASD_CS_EN_THRESHOLD", "0.5")
    assert lwe._stretch_language(Probs([("en", 0.55), ("bn", 0.45)]), np.zeros(SR))[0] == "en"


# ----------------------------------------------------------------------------- run planning
def test_runs_smooth_short_stretches_and_cover_the_slice(tmp_path):
    # en 4 s | pause | en 1 s (too short to judge) | pause | en 4 s | pause | bn 5 s | tail silence
    path = write_wav(tmp_path / "s.wav", [("en", 4), ("silence", 1), ("en", 1), ("silence", 1), ("en", 4),
                                          ("silence", 1), ("bn", 5), ("silence", 2)])
    with patch("faster_whisper.vad.get_speech_timestamps", side_effect=fake_vad):
        runs = lwe._plan_bilingual_runs(FakeModel("bn"), path, 19.0, "[t]")
    assert [r[2] for r in runs] == ["en", "bn"], runs
    assert runs[0][0] == 0.0
    assert runs[0][0] + runs[0][1] == pytest.approx(runs[1][0])         # no gap, no overlap
    assert runs[1][0] + runs[1][1] == pytest.approx(19.0)                # ends at the slice end
    assert 11.0 <= runs[1][0] <= 12.0                                    # boundary inside the pause


def test_only_short_stretches_stay_bangla(tmp_path):
    path = write_wav(tmp_path / "s.wav", [("en", 1), ("silence", 1), ("en", 1), ("silence", 1)])
    with patch("faster_whisper.vad.get_speech_timestamps", side_effect=fake_vad):
        runs = lwe._plan_bilingual_runs(FakeModel("bn"), path, 4.0, "[t]")
    assert runs == [(0.0, 4.0, "bn")]


# ----------------------------------------------------------------------------- end to end
MIXED = [("bn", 20), ("silence", 1), ("en", 20), ("silence", 1), ("bn", 20)]


def test_runs_are_routed_to_the_right_model(tmp_path, monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    bn, en = FakeModel("bn"), FakeModel("en")
    res, _ = run_engine(write_wav(tmp_path / "m.wav", MIXED), bn, en, detector=FakeModel("bn"))
    assert res["status"] == "success"
    assert en.calls == [{"language": "en", "prompt": lwe._EN_PROMPT}]
    assert [c["language"] for c in bn.calls] == ["bn", "bn"] and all(c["prompt"] is None for c in bn.calls)
    lines = res["raw_transcript"].splitlines()
    # the fake writes one line per 10 s window of each run (a ~21 s English run -> 3 windows)
    assert sum(TEXT["en"] in l for l in lines) >= 2 and sum(TEXT["bn"] in l for l in lines) >= 4
    assert GIBBERISH not in res["raw_transcript"]
    assert all(l.startswith("[") and "] Speaker 1: " in l for l in lines)
    first_en = next(l for l in lines if TEXT["en"] in l)
    assert first_en.startswith("[00:2"), first_en       # absolute time, not run-relative
    assert res["model"].endswith("+small.en")
    assert res["slice_languages"] == ["bn+en"]


def test_switch_off_is_todays_behaviour(tmp_path):
    bn = FakeModel("bn")
    res, load_aux = run_engine(write_wav(tmp_path / "m.wav", MIXED), bn, FakeModel("en"), FakeModel("bn"))
    load_aux.assert_not_called()
    assert [c["language"] for c in bn.calls] == ["bn"]
    assert GIBBERISH in res["raw_transcript"] or TEXT["en"] not in res["raw_transcript"]


def test_not_ready_gives_identical_transcript_to_switch_off(tmp_path, monkeypatch):
    path = write_wav(tmp_path / "m.wav", MIXED)
    off, _ = run_engine(path, FakeModel("bn"))
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    not_ready, load_aux = run_engine(path, FakeModel("bn"), FakeModel("en"), FakeModel("bn"), ready=False)
    load_aux.assert_not_called()
    assert not_ready["raw_transcript"] == off["raw_transcript"]


def test_english_decode_error_falls_back_to_bangla(tmp_path, monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    bn, en = FakeModel("bn"), FakeModel("en", fail=True)
    res, _ = run_engine(write_wav(tmp_path / "m.wav", MIXED), bn, en, FakeModel("bn"))
    assert res["status"] == "success"
    assert len(en.calls) == 1
    assert [c["language"] for c in bn.calls] == ["bn", "bn", "bn"]  # the English run re-decoded as Bangla
    assert not res["model"].endswith("+small.en")


def test_planner_error_falls_back_to_one_bangla_run(tmp_path, monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    bn, en = FakeModel("bn"), FakeModel("en")
    with patch.object(lwe, "_plan_bilingual_runs", side_effect=RuntimeError("vad broke")):
        res, _ = run_engine(write_wav(tmp_path / "m.wav", MIXED), bn, en, FakeModel("bn"))
    assert res["status"] == "success"
    assert [c["language"] for c in bn.calls] == ["bn"] and en.calls == []


def test_live_preview_and_forced_language_never_load_extra_models(tmp_path, monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    path = write_wav(tmp_path / "m.wav", MIXED)
    _, load_aux = run_engine(path, FakeModel("bn"), FakeModel("en"), FakeModel("bn"), code_switch=False)
    load_aux.assert_not_called()
    _, load_aux = run_engine(path, FakeModel("bn"), FakeModel("en"), FakeModel("bn"), language="bn")
    load_aux.assert_not_called()


def test_detector_can_be_the_bangla_model(tmp_path, monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    monkeypatch.setenv("EASD_CS_DETECTOR", "bengaliai")
    bn, en = FakeModel("bn"), FakeModel("en")
    res, load_aux = run_engine(write_wav(tmp_path / "m.wav", MIXED), bn, en, detector=None)
    assert [c.args[0] for c in load_aux.call_args_list] == ["en"]
    assert sum(TEXT["en"] in l for l in res["raw_transcript"].splitlines()) >= 2
    assert GIBBERISH not in res["raw_transcript"]


# ----------------------------------------------------------------------------- readiness
def test_ready_needs_setting_models_and_ram(monkeypatch):
    assert lwe._code_switch_ready() == (False, "EASD_CODE_SWITCH is off")
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    ok, why = lwe._code_switch_ready()
    assert not ok and "whisper-small.en is not installed" in why
    install_fake_weights("en")
    ok, why = lwe._code_switch_ready()
    assert not ok and "whisper-tiny is not installed" in why
    install_fake_weights("tiny")
    with patch.object(lwe, "get_system_ram_specs", return_value={"available_ram_gb": 0.5}):
        ok, why = lwe._code_switch_ready()
    assert not ok and "RAM" in why
    with patch.object(lwe, "get_system_ram_specs", return_value={"available_ram_gb": 3.0}):
        assert lwe._code_switch_ready() == (True, "")


def test_partial_folder_does_not_count_as_installed(monkeypatch):
    monkeypatch.setenv("EASD_CODE_SWITCH", "1")
    folder = lwe._AUX_MODELS["en"][0] + ".partial"
    os.makedirs(folder)
    open(os.path.join(folder, "model.bin"), "wb").close()
    assert not lwe._code_switch_ready()[0]
    assert lwe.code_switch_status()["english_model"]["installed"] is False


# ----------------------------------------------------------------------------- one-time download
def test_installed_model_makes_no_network_call():
    install_fake_weights("en")
    with patch("huggingface_hub.snapshot_download") as dl:
        assert lwe.ensure_aux_model("en") is True
    dl.assert_not_called()


def test_download_installs_via_partial_folder():
    def fake_download(repo, local_dir=None, **kw):
        assert local_dir.endswith(".partial")
        os.makedirs(local_dir, exist_ok=True)
        open(os.path.join(local_dir, "model.bin"), "wb").close()
    with patch("huggingface_hub.snapshot_download", side_effect=fake_download) as dl:
        assert lwe.ensure_aux_model("en") is True
        assert lwe.ensure_aux_model("en") is True  # second call: already installed
    assert dl.call_count == 1
    final = lwe._AUX_MODELS["en"][0]
    assert os.path.isfile(os.path.join(final, "model.bin")) and not os.path.exists(final + ".partial")


def test_failed_download_is_not_installed_and_not_retried():
    with patch("huggingface_hub.snapshot_download", side_effect=OSError("no internet")) as dl:
        assert lwe.ensure_aux_model("en") is False
        assert lwe.ensure_aux_model("en") is False
    assert dl.call_count == 1
    assert not os.path.exists(lwe._AUX_MODELS["en"][0])
    assert "no internet" in lwe._AUX_DOWNLOAD_FAILED["en"]


def test_download_without_weights_is_not_installed():
    with patch("huggingface_hub.snapshot_download", side_effect=lambda repo, local_dir=None, **kw: os.makedirs(local_dir)):
        assert lwe.ensure_aux_model("tiny") is False
    assert not lwe._model_has_weights(lwe._AUX_MODELS["tiny"][0])


def test_ensure_code_switch_models_skips_detector_download_for_bengaliai(monkeypatch):
    monkeypatch.setenv("EASD_CS_DETECTOR", "bengaliai")
    install_fake_weights("en")
    assert lwe.ensure_code_switch_models() == {"en": True}
