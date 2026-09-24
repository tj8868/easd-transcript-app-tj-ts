"""
v8.4 tests: local Whisper language detection, per-slice language, VAD and hallucination filtering.

Run: python test_whisper_language_and_vad.py

What is real and what is simulated
----------------------------------
* sanitize_whisper_text(), detect_audio_language_detail(), transcribe_local_audio() and the
  Silero VAD cross-check are the REAL production code.
* The Whisper acoustic model is replaced by FakeWhisperModel (no model weights are needed).
  Test audio encodes its "language" as a tone (300 Hz = English, 700 Hz = Bangla); the fake
  detector returns the probability distributions that caused the v8.3 bug, and the fake
  decoder returns foreign-script gibberish with low log-probability whenever it is forced
  to decode audio in the wrong language - the failure mode seen on real small/medium models.
* The VAD section uses the real Silero model shipped with faster-whisper; with a real
  recording available (Recording/*.m4a, or EASD_TEST_RECORDING=<path>) it also checks
  real speech after a long silent + noisy stretch.
"""
import glob
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from unittest.mock import patch

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import local_whisper_engine as lwe
import whisper_hallucination_fixtures as fx

SR = 16000
TONE = {"en": 300.0, "bn": 700.0}
PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (f"  -> {detail}" if detail and not cond else ""))


# ----------------------------------------------------------------------------- audio helpers
def write_wav(path, pieces):
    """pieces: list of (kind, seconds) where kind is 'en', 'bn' or 'silence'."""
    samples = []
    for kind, secs in pieces:
        n = int(secs * SR)
        if kind == "silence":
            samples.append(np.zeros(n, dtype=np.float32))
        else:
            t = np.arange(n) / SR
            samples.append((0.3 * np.sin(2 * math.pi * TONE[kind] * t)).astype(np.float32))
    audio = np.concatenate(samples)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    return path


def dominant_language(audio):
    """'en' / 'bn' / None(silence) for an audio window, from its dominant tone."""
    if len(audio) == 0 or float(np.abs(audio).mean()) < 1e-3:
        return None
    spec = np.abs(np.fft.rfft(audio[:SR * 5]))
    freq = np.fft.rfftfreq(min(len(audio), SR * 5), 1 / SR)[int(np.argmax(spec))]
    return "en" if abs(freq - TONE["en"]) < abs(freq - TONE["bn"]) else "bn"


# ----------------------------------------------------------------------------- fake model
class Seg:
    def __init__(self, start, end, text, avg_logprob, no_speech_prob=0.02, compression_ratio=1.3):
        self.start, self.end, self.text = start, end, text
        self.avg_logprob, self.no_speech_prob, self.compression_ratio = avg_logprob, no_speech_prob, compression_ratio


class Info:
    def __init__(self, language):
        self.language, self.language_probability = language, 0.9


CORRECT = {"en": "We reviewed the field data and agreed the next steps.",
           "bn": "আমরা মাঠের তথ্য পর্যালোচনা করেছি এবং পরবর্তী পদক্ষেপ ঠিক করেছি\u0964"}
# What small/medium produced on English audio forced to 'bn' (script soup, low confidence)
GIBBERISH = ["বিবিবিবি কার্যক্রম আলোচনা হলো", "ఈ సమావేశంలో మేము", "आज की बैठक में", "ಸಭೆಯಲ್ಲಿ ನಾವು"]


class FakeWhisperModel:
    """Stands in for faster_whisper.WhisperModel; see module docstring."""

    def __init__(self):
        self.transcribe_calls = []

    def detect_language(self, audio=None, **kwargs):
        lang = dominant_language(audio)
        langs_present = {dominant_language(audio[i:i + SR * 5]) for i in range(0, len(audio), SR * 5)} - {None}
        if langs_present == {"en", "bn"}:
            probs = [("bn", 0.50), ("en", 0.40), ("hi", 0.05), ("te", 0.02)]
        elif lang == "en":  # noisy English: Bengali ~12% -> v8.3 forced 'bn'
            probs = [("en", 0.70), ("bn", 0.12), ("hi", 0.06), ("te", 0.04), ("kn", 0.03)]
        elif lang == "bn":  # Bangla misranked as Hindi
            probs = [("hi", 0.42), ("bn", 0.38), ("ne", 0.08), ("en", 0.05)]
        else:
            probs = [("en", 0.20), ("bn", 0.15), ("te", 0.10)]
        return probs[0][0], probs[0][1], probs

    def transcribe(self, audio, language=None, vad_filter=False, **kwargs):
        import faster_whisper
        data = faster_whisper.decode_audio(audio) if isinstance(audio, str) else audio
        self.transcribe_calls.append({"language": language, "vad_filter": vad_filter})
        segs, i = [], 0
        for start in range(0, len(data), SR * 10):
            window = data[start:start + SR * 10]
            true_lang = dominant_language(window)
            s, e = start / SR, (start + len(window)) / SR
            if true_lang is None:
                if not vad_filter:  # Whisper hallucinates on silence when VAD is off
                    segs.append(Seg(s, e, "Thank you. Thank you. Thank you. Thank you.", -0.9,
                                    no_speech_prob=0.5, compression_ratio=2.6))
                continue
            decode_lang = language or true_lang
            if decode_lang == true_lang:
                segs.append(Seg(s, e, f"{CORRECT[true_lang]} ({int(start / SR)})", -0.25))
            else:
                segs.append(Seg(s, e, GIBBERISH[i % len(GIBBERISH)], -0.95 if i % 2 else -1.7))
                i += 1
        return iter(segs), Info(language or "en")


def run_engine(path, fake):
    lwe._LOCAL_MODELS.clear()
    lwe._LOCAL_MODELS[os.path.join(lwe._BASE_DIR, "models", "whisper-small")] = fake
    with patch.object(lwe, "get_local_whisper_model", return_value=fake):
        return lwe.transcribe_local_audio(path, language=None, model_name="small", mime_type="audio/wav", beam_size=1)


def has_foreign_script(text):
    """Indic script other than Bengali (the shared danda marks U+0964/U+0965 don't count)."""
    return any("\u0900" <= ch <= "\u0D7F" and not ("\u0980" <= ch <= "\u09FF") and ch not in "\u0964\u0965"
               for ch in text)


# ----------------------------------------------------------------------------- tests
def test_sanitizer_fixtures():
    print("\n=== 1. sanitize_whisper_text() against whisper_hallucination_fixtures ===")
    for case in fx.ALL_SANITIZER_CASES:
        ok, out = fx.check_sanitizer_case(lwe.sanitize_whisper_text, case)
        check(f"{case['name']} (lang={case['language']})", ok, repr(out))


def test_language_resolution():
    print("\n=== 2. detect_audio_language_detail() on real-world detector distributions ===")

    class M:
        def __init__(self, p):
            self.p = p

        def detect_language(self, audio=None, **kw):
            return self.p[0][0], self.p[0][1], self.p

    for d in fx.DETECTOR_DISTRIBUTIONS:
        r = lwe.detect_audio_language_detail(M(d["probs"]), np.zeros(SR * 5, dtype=np.float32), _ctx=f"[{d['name']}]")
        check(f"{d['name']} -> {d['expect']} (ambiguous={d['expect_ambiguous']})",
              r["language"] == d["expect"] and r["ambiguous"] == d["expect_ambiguous"],
              f"got {r['language']} ambiguous={r['ambiguous']}")
    lang, conf = lwe.detect_audio_language(M([]), np.zeros(SR, dtype=np.float32))
    check("detector failure -> 'auto' (let Whisper decide), never a forced 'bn'", lang == "auto", lang)


def test_end_to_end_english(tmp):
    print("\n=== 3. All-English 7-minute recording (3 slices) ===")
    path = write_wav(os.path.join(tmp, "english.wav"), [("en", 420)])
    fake = FakeWhisperModel()
    res = run_engine(path, fake)
    text = res["raw_transcript"]
    check("every slice decoded as English", res["slice_languages"] == ["en", "en", "en"], res["slice_languages"])
    check("no Bangla / Devanagari / Telugu / Kannada anywhere",
          not has_foreign_script(text) and not any("\u0980" <= c <= "\u09FF" for c in text), text[:200])
    check("all 42 English segments kept", text.count(CORRECT["en"]) == 42, text.count(CORRECT["en"]))
    return text


def test_end_to_end_code_switched(tmp):
    print("\n=== 4. Mixed Bangla/English recording (language changes between and inside slices) ===")
    pieces = [("bn", 180), ("en", 180), ("bn", 60), ("en", 60), ("bn", 60)]
    path = write_wav(os.path.join(tmp, "mixed.wav"), pieces)
    fake = FakeWhisperModel()
    res = run_engine(path, fake)
    lines = res["raw_transcript"].splitlines()
    check("slice languages follow the audio", res["slice_languages"] == ["bn", "en", "bn+en"], res["slice_languages"])
    check("Bangla parts decoded as Bangla", sum(CORRECT["bn"] in l for l in lines) == 30,
          sum(CORRECT["bn"] in l for l in lines))
    check("English parts decoded as English", sum(CORRECT["en"] in l for l in lines) == 24,
          sum(CORRECT["en"] in l for l in lines))
    check("no Devanagari/Telugu/Kannada gibberish", not has_foreign_script(res["raw_transcript"]))
    first_en = next(l for l in lines if CORRECT["en"] in l)
    check("timestamps stay aligned across slices (first English line at 03:00)", first_en.startswith("[03:00]"), first_en)


def test_end_to_end_silence(tmp):
    print("\n=== 5. Long silent stretch (VAD on) ===")
    path = write_wav(os.path.join(tmp, "silence.wav"), [("en", 30), ("silence", 150), ("en", 30)])
    fake = FakeWhisperModel()
    res = run_engine(path, fake)
    check("VAD enabled for the slice", all(c["vad_filter"] for c in fake.transcribe_calls), fake.transcribe_calls)
    check("no repeating-loop hallucination in the silent stretch", "Thank you" not in res["raw_transcript"])
    check("speech on both sides kept", res["raw_transcript"].count(CORRECT["en"]) == 6)


def test_vad_real_silero(tmp):
    print("\n=== 6. Real Silero VAD: speech after 150s of silence + noise ===")
    rec = os.environ.get("EASD_TEST_RECORDING") or next(iter(sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Recording", "*.m4a")))), "")
    ffmpeg = shutil.which("ffmpeg")
    if not rec or not os.path.isfile(rec) or not ffmpeg:
        print("  [SKIP] no real recording (put one in Recording/ or set EASD_TEST_RECORDING) or no ffmpeg")
        return

    def run(*args):
        subprocess.run([ffmpeg, "-loglevel", "error", "-y", *args], check=True)

    sp1, sp2, mix = (os.path.join(tmp, f) for f in ("sp1.wav", "sp2.wav", "mix.wav"))
    run("-ss", "300", "-t", "30", "-i", rec, "-ac", "1", "-ar", "16000", sp1)
    run("-ss", "900", "-t", "30", "-i", rec, "-ac", "1", "-ar", "16000", sp2)
    run("-i", sp1, "-f", "lavfi", "-t", "60", "-i", "anullsrc=r=16000:cl=mono",
        "-f", "lavfi", "-t", "60", "-i", "anoisesrc=r=16000:color=pink:amplitude=0.03",
        "-f", "lavfi", "-t", "30", "-i", "anoisesrc=r=16000:color=brown:amplitude=0.08", "-i", sp2,
        "-filter_complex", "[0][1][2][3][4]concat=n=5:v=0:a=1", "-ac", "1", "-ar", "16000", mix)
    import faster_whisper
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    audio = faster_whisper.decode_audio(mix)
    spans = get_speech_timestamps(audio, VadOptions(**lwe.WHISPER_VAD_PARAMETERS))
    def cov(a, b):
        return sum(max(0.0, min(t["end"] / SR, b) - max(t["start"] / SR, a)) for t in spans)
    print(f"     speech flagged: 0-30s={cov(0, 30):.1f}s, silence 30-90s={cov(30, 90):.1f}s, "
          f"noise 90-180s={cov(90, 180):.1f}s, speech 180-210s={cov(180, 210):.1f}s")
    check("silence/noise stretch not treated as speech (<2s)", cov(30, 180) < 2.0)
    whole_slice_missed = cov(180, 210) < 5.0
    check("cross-check disables VAD when the whole-slice pass drops later speech",
          lwe._vad_is_reliable_for(mix, "[test mix]") is (not whole_slice_missed))
    check("cross-check keeps VAD on for clean speech", lwe._vad_is_reliable_for(sp1, "[test sp1]") is True)


def test_model_choice():
    print("\n=== 7. Model selection respects explicit choice; medium usable on 8GB ===")
    check("explicit 'medium' respected", lwe.resolve_whisper_model_choice("medium") == ("medium", "explicit"))
    check("'whisper-small' respected", lwe.resolve_whisper_model_choice("whisper-small") == ("small", "explicit"))
    with patch.object(lwe, "select_optimal_model_name", return_value="base"):
        check("'auto' falls through to automatic", lwe.resolve_whisper_model_choice("auto") == ("base", "auto"))
    with patch.object(lwe, "get_system_ram_specs",
                      return_value={"total_ram_gb": 7.9, "available_ram_gb": 3.1, "is_low_ram": False}), \
            patch.object(lwe, "_model_has_weights", side_effect=lambda d: True):
        check("8GB box with 3.1GB free and medium weights -> medium", lwe.select_optimal_model_name() == "medium")
    with patch.object(lwe, "get_system_ram_specs",
                      return_value={"total_ram_gb": 7.9, "available_ram_gb": 1.2, "is_low_ram": False}), \
            patch.object(lwe, "_model_has_weights", side_effect=lambda d: True):
        check("8GB box with only 1.2GB free -> small (and a warning is logged)", lwe.select_optimal_model_name() == "small")

    import stt_pipeline
    seen = {}

    def fake_whisper(audio, language="auto", mime_type="", ctx="", model_name=""):
        seen["model_name"] = model_name
        return {"ok": True, "text": "[00:01] Speaker 1: hello", "provider": "local_whisper", "error": ""}

    with patch.object(stt_pipeline, "whisper_transcribe_bytes", side_effect=fake_whisper):
        import ai_providers
        ai_providers.transcribe_audio_chunks_detailed([b"x" * 4096], provider="local_whisper", model_name="medium")
    check("stt pipeline forwards the explicitly chosen model to Local Whisper", seen.get("model_name") == "medium", seen)


if __name__ == "__main__":
    tmpdir = tempfile.mkdtemp(prefix="easd_v84_")
    try:
        test_sanitizer_fixtures()
        test_language_resolution()
        test_end_to_end_english(tmpdir)
        test_end_to_end_code_switched(tmpdir)
        test_end_to_end_silence(tmpdir)
        test_vad_real_silero(tmpdir)
        test_model_choice()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nRESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", *FAILED, sep="\n  - ")
    sys.exit(1 if FAILED else 0)
