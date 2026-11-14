"""
speaker_diarization.py - voice-based speaker labelling for transcripts (v8.9).

Replaces the old "flip Speaker 1/2 on every 1.6 s pause" heuristic with real, fully local
speaker recognition:

  1. For every utterance, compute a voice fingerprint ("speaker embedding") with the
     WeSpeaker ResNet34 neural model (models/wespeaker_resnet34_LM.onnx, 26 MB, runs on CPU
     through onnxruntime - no internet, no API key, no torch). It is downloaded once
     automatically; if it is missing and cannot be downloaded, a lighter MFCC fingerprint
     (numpy only) is used instead.
  2. Agglomerative clustering (average linkage, cosine distance) until the closest two
     clusters are further apart than the threshold for the active backend.
  3. Number speakers in order of first appearance: Speaker 1, Speaker 2, ...

Two entry points:
  - diarize_wav_segments(wav_path, segments)    -> per-utterance labels (local Whisper)
  - unify_chunk_speakers(chunk_texts, chunk_wavs) -> consistent labels across chunks
    (Gemini/Whisper chunked transcripts, where every chunk numbers speakers from 1 again)

Everything fails soft: on any error the caller keeps the labels it already had.
"""
import os
import re
import wave
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from diag_logging import get_logger

log = get_logger("diarization")

SAMPLE_RATE = 16000
DIARIZATION_ENABLED = os.environ.get("EASD_DIARIZATION", "on").lower() not in ("0", "off", "false", "no")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NEURAL_MODEL_PATH = os.path.join(BASE_DIR, "models", "wespeaker_resnet34_LM.onnx")
NEURAL_MODEL_URL = ("https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/"
                    "voxceleb_resnet34_LM.onnx")
# Cosine distance above which two clusters are treated as different people (per backend;
# EASD_DIARIZATION_THRESHOLD overrides whichever backend is active).
_THRESHOLDS = {"neural": 0.55, "mfcc": 0.9}
_THRESHOLD_OVERRIDE = os.environ.get("EASD_DIARIZATION_THRESHOLD")
MAX_SPEAKERS = int(os.environ.get("EASD_DIARIZATION_MAX_SPEAKERS", "10"))
MIN_SEGMENT_SEC = 0.8        # shorter utterances are labelled by nearest cluster, not clustered
MAX_GROUP_AUDIO_SEC = 90.0   # cap of audio used per (chunk, speaker) group in unify_chunk_speakers

_TS_LINE_RE = re.compile(r"^\[(\d{1,3}):(\d{2})(?::(\d{2}))?\]\s*(?:Speaker\s*(\w+)\s*:)?\s*(.*)$")


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------
def read_wav_pcm16k(path: str) -> np.ndarray:
    """Reads a 16 kHz mono 16-bit WAV into float32 [-1, 1]."""
    with wave.open(path, "rb") as wf:
        if wf.getframerate() != SAMPLE_RATE or wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError("expected 16 kHz mono 16-bit WAV")
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _mel_filterbank(n_filters: int = 40, n_fft: int = 512, sr: int = SAMPLE_RATE) -> np.ndarray:
    def hz_to_mel(h):
        return 2595.0 * np.log10(1.0 + h / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(60.0), hz_to_mel(sr / 2), n_filters + 2)
    bins = np.floor((n_fft + 1) * mel_to_hz(mels) / sr).astype(int)
    fb = np.zeros((n_filters, n_fft // 2 + 1), dtype=np.float32)
    for i in range(1, n_filters + 1):
        lo, mid, hi = bins[i - 1], bins[i], bins[i + 1]
        if mid > lo:
            fb[i - 1, lo:mid] = (np.arange(lo, mid) - lo) / (mid - lo)
        if hi > mid:
            fb[i - 1, mid:hi] = (hi - np.arange(mid, hi)) / (hi - mid)
    return fb


_FB = _mel_filterbank()
_N_MFCC = 20
_DCT = np.cos(np.pi / 40 * (np.arange(40)[None, :] + 0.5) * np.arange(_N_MFCC)[:, None]).astype(np.float32)


def _mfcc_embedding(samples: np.ndarray) -> Optional[np.ndarray]:
    """Mean+std of MFCC 1..19 over voiced frames. None when there is too little speech."""
    if samples is None or len(samples) < int(0.3 * SAMPLE_RATE):
        return None
    x = np.append(samples[0], samples[1:] - 0.97 * samples[:-1])
    frame, hop = 400, 160
    n_frames = 1 + (len(x) - frame) // hop
    if n_frames < 20:
        return None
    idx = np.arange(frame)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = x[idx] * np.hamming(frame).astype(np.float32)
    power = (np.abs(np.fft.rfft(frames, n=512)) ** 2) / 512.0
    energy = np.log(power.sum(axis=1) + 1e-10)
    voiced = energy > (np.percentile(energy, 95) - 6.0)   # keep frames within ~26 dB of the loud ones
    if voiced.sum() < 15:
        return None
    logmel = np.log(power[voiced] @ _FB.T + 1e-10)
    mfcc = logmel @ _DCT.T                                   # (frames, 20)
    mfcc = mfcc[:, 1:]                                       # drop c0 (loudness)
    return np.concatenate([mfcc.mean(axis=0), mfcc.std(axis=0)]).astype(np.float32)


# ---------------------------------------------------------------------------
# Neural speaker embedding (WeSpeaker ResNet34, ONNX)
# ---------------------------------------------------------------------------
def _kaldi_mel_filterbank(n_filters: int = 80, n_fft: int = 512,
                          sr: int = SAMPLE_RATE) -> np.ndarray:
    """Kaldi mel triangles at FFT frequencies, with a 20 Hz lower cutoff.

    Kaldi evaluates triangle slopes in mel space without rounding their edges
    to FFT bins, and excludes the Nyquist bin from the filterbank.
    """
    mel_low = 1127.0 * np.log1p(20.0 / 700.0)
    mel_high = 1127.0 * np.log1p((sr / 2) / 700.0)
    edges = np.linspace(mel_low, mel_high, n_filters + 2)
    fft_mels = 1127.0 * np.log1p(np.arange(n_fft // 2 + 1) * (sr / n_fft) / 700.0)
    left, centre, right = edges[:-2, None], edges[1:-1, None], edges[2:, None]
    rising = (fft_mels[None, :] - left) / (centre - left)
    falling = (right - fft_mels[None, :]) / (right - centre)
    bank = np.maximum(0.0, np.minimum(rising, falling)).astype(np.float32)
    bank[:, -1] = 0.0
    return bank


_neural_state: Dict[str, Any] = {"session": None, "failed": False}
_FB80 = _kaldi_mel_filterbank()
_NEURAL_WINDOW = np.hamming(400).astype(np.float32)


def _ensure_neural_model() -> Optional[str]:
    if os.path.exists(NEURAL_MODEL_PATH) and os.path.getsize(NEURAL_MODEL_PATH) > 1_000_000:
        return NEURAL_MODEL_PATH
    if os.environ.get("EASD_DIARIZATION_NO_DOWNLOAD") == "1":
        return None
    try:
        import httpx
        os.makedirs(os.path.dirname(NEURAL_MODEL_PATH), exist_ok=True)
        tmp = NEURAL_MODEL_PATH + ".part"
        log.info("downloading speaker model (26 MB, one time) from %s", NEURAL_MODEL_URL)
        with httpx.stream("GET", NEURAL_MODEL_URL, follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for block in r.iter_bytes(1 << 20):
                    f.write(block)
        os.replace(tmp, NEURAL_MODEL_PATH)
        return NEURAL_MODEL_PATH
    except Exception as e:
        log.warning("speaker model download failed (%s) - using MFCC voice fingerprints", e)
        return None


# Fastest first. Only providers this onnxruntime build actually has are used:
#   NVIDIA (onnxruntime-gpu)      -> TensorRT / CUDA
#   Any GPU on Windows            -> DirectML (onnxruntime-directml)
#   Apple Silicon / Mac           -> CoreML
#   AMD on Linux / Intel          -> ROCm / MIGraphX / OpenVINO
_PROVIDER_PREFERENCE = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "ROCMExecutionProvider",
                        "MIGraphXExecutionProvider", "DmlExecutionProvider", "CoreMLExecutionProvider",
                        "OpenVINOExecutionProvider", "CPUExecutionProvider"]


def _pick_providers(available: List[str]) -> List[str]:
    forced = os.environ.get("EASD_DIARIZATION_DEVICE", "").lower()
    if forced == "cpu":
        return ["CPUExecutionProvider"]
    chosen = [p for p in _PROVIDER_PREFERENCE if p in available]
    if "TensorrtExecutionProvider" in chosen and "CUDAExecutionProvider" not in chosen:
        chosen.remove("TensorrtExecutionProvider")  # TensorRT without CUDA libs cannot start
    return chosen or ["CPUExecutionProvider"]


def speaker_model_status() -> Dict[str, Any]:
    sess = _neural_session()
    return {"backend": "neural" if sess is not None else "mfcc",
            "device": _neural_state.get("device", "cpu-numpy"),
            "model": os.path.basename(NEURAL_MODEL_PATH) if sess is not None else None}


def _try_openvino_gpu(path: str) -> None:
    """onnxruntime found no GPU provider: if OpenVINO sees an Intel GPU (Iris Xe / Arc / Core
    Ultra), compile the same ONNX model for it there."""
    if os.environ.get("EASD_DIARIZATION_DEVICE", "").lower() == "cpu":
        return
    try:
        import openvino as ov
        core = ov.Core()
        device = os.environ.get("EASD_OV_DEVICE") or next((d for d in core.available_devices if d.startswith("GPU")), None)
        if not device or device.upper() == "CPU":
            return
        cache = os.path.join(BASE_DIR, "models", ".ov_cache")
        os.makedirs(cache, exist_ok=True)
        core.set_property({"CACHE_DIR": cache})
        model = core.read_model(path)
        model.reshape({"feats": ov.PartialShape([1, -1, 80])})
        _neural_state["ov_model"] = core.compile_model(model, device)
        _neural_state["device"] = f"OpenVINO:{device}"
    except Exception as e:
        log.info("OpenVINO GPU not used for speaker model (%s)", e)


def _neural_session():
    if _neural_state["session"] is not None or _neural_state["failed"]:
        return _neural_state["session"]
    try:
        path = _ensure_neural_model()
        if not path:
            raise RuntimeError("model file not available")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
        providers = _pick_providers(ort.get_available_providers())
        # OpenVINO EP: target the Intel iGPU (Iris Xe / Arc / Core Ultra) rather than its CPU default.
        provider_cfg = [(p, {"device_type": os.environ.get("EASD_OV_DEVICE", "GPU")}) if p == "OpenVINOExecutionProvider"
                        else p for p in providers]
        try:
            sess = ort.InferenceSession(path, sess_options=opts, providers=provider_cfg)
        except Exception as e:
            log.warning("speaker model GPU init failed (%s) - using CPU", e)
            sess = ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])
        _neural_state["session"] = sess
        _neural_state["device"] = sess.get_providers()[0]
        if _neural_state["device"] == "CPUExecutionProvider":
            _try_openvino_gpu(path)
        log.info("speaker model loaded: %s on %s", os.path.basename(path), _neural_state["device"])
    except Exception as e:
        _neural_state["failed"] = True
        log.warning("neural speaker model unavailable (%s) - using MFCC voice fingerprints", e)
    return _neural_state["session"]


def _kaldi_fbank(samples: np.ndarray) -> Optional[np.ndarray]:
    """WeSpeaker's 80-bin Kaldi fbank, with utterance mean normalisation.

    Uses 16 kHz PCM scaling, 25 ms frames / 10 ms hops, snipped edges,
    per-frame DC removal, 0.97 pre-emphasis, a Hamming window, 512-point
    power spectra, and no inference-time dithering or energy coefficient.
    """
    x = samples.astype(np.float32) * 32768.0
    frame, hop = 400, 160
    n_frames = 1 + (len(x) - frame) // hop
    if n_frames < 50:
        return None
    idx = np.arange(frame)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = x[idx]
    frames = frames - frames.mean(axis=1, keepdims=True)
    previous = np.concatenate([frames[:, :1], frames[:, :-1]], axis=1)
    frames = frames - 0.97 * previous
    power = np.abs(np.fft.rfft(frames * _NEURAL_WINDOW, n=512)) ** 2
    feats = np.log(np.maximum(power @ _FB80.T, 1.1920929e-07))
    return (feats - feats.mean(axis=0)).astype(np.float32)


def _neural_embedding(samples: np.ndarray) -> Optional[np.ndarray]:
    sess = _neural_session()
    if sess is None:
        return None
    feats = _kaldi_fbank(samples)
    if feats is None:
        return None
    if _neural_state.get("ov_model") is not None:
        out = _neural_state["ov_model"]({"feats": feats[None, :, :]})[0][0]
    else:
        out = sess.run(None, {"feats": feats[None, :, :]})[0][0]
    return np.asarray(out, dtype=np.float32)


def active_backend() -> str:
    return "neural" if _neural_session() is not None else "mfcc"


def _threshold() -> float:
    if _THRESHOLD_OVERRIDE:
        return float(_THRESHOLD_OVERRIDE)
    return _THRESHOLDS[active_backend()]


def voice_embedding(samples: np.ndarray) -> Optional[np.ndarray]:
    """Speaker embedding of an audio span with the active backend (neural, else MFCC)."""
    if samples is None or len(samples) < int(0.5 * SAMPLE_RATE):
        return None
    if active_backend() == "neural":
        return _neural_embedding(samples)
    return _mfcc_embedding(samples)


def _normalise(embs: np.ndarray) -> np.ndarray:
    """Neural embeddings: plain L2. MFCC: session-level normalisation then L2 (centering only
    when there are enough samples for the mean to describe the room, not one speaker)."""
    e = embs.copy()
    if active_backend() == "neural":
        return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
    if len(e) >= 4:
        e = (e - e.mean(axis=0)) / (e.std(axis=0) + 1e-6)
    else:
        e = e / (np.abs(e).max(axis=0) + 1e-6)
    return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
def cluster_embeddings(embs: np.ndarray, threshold: Optional[float] = None,
                       max_speakers: int = MAX_SPEAKERS,
                       cannot_link: Optional[Sequence[Any]] = None) -> List[int]:
    """
    Average-linkage agglomerative clustering on cosine distance, with a cluster-distance matrix
    updated by the Lance-Williams rule (O(n^2) per merge, no Python pair loops).
    cannot_link[i] is a group key (e.g. chunk index); items sharing a key are never merged
    (used when a chunk's own diarization already said they are different people).
    Returns a cluster id per row.
    """
    n = len(embs)
    if n < 2:
        return [0] * n
    threshold = _threshold() if threshold is None else threshold
    e = _normalise(embs)
    dist = (1.0 - e @ e.T).astype(np.float64)
    if cannot_link is not None:
        keys = np.asarray(cannot_link, dtype=object)
        dist[keys[:, None] == keys[None, :]] = np.inf
    np.fill_diagonal(dist, np.inf)
    size = np.ones(n)
    labels = np.arange(n)
    alive = n
    while alive > 1:
        a, b = np.unravel_index(np.argmin(dist), dist.shape)
        d = dist[a, b]
        if not np.isfinite(d) or (d > threshold and alive <= max_speakers):
            break
        merged = (size[a] * dist[a] + size[b] * dist[b]) / (size[a] + size[b])
        merged[np.isinf(dist[a]) | np.isinf(dist[b])] = np.inf   # cannot-link and dead rows stay blocked
        dist[a], dist[:, a] = merged, merged
        dist[a, a] = np.inf
        dist[b], dist[:, b] = np.inf, np.inf
        size[a] += size[b]
        labels[labels == b] = a
        alive -= 1
    return np.unique(labels, return_inverse=True)[1].tolist()


def _first_appearance_numbering(labels: List[int]) -> List[int]:
    order: Dict[int, int] = {}
    out = []
    for lab in labels:
        if lab not in order:
            order[lab] = len(order) + 1
        out.append(order[lab])
    return out


# ---------------------------------------------------------------------------
# 1. Per-utterance diarization of one WAV (local Whisper path)
# ---------------------------------------------------------------------------
def diarize_wav_segments(wav_path: str, segments: List[Dict[str, Any]]) -> Optional[List[int]]:
    """
    segments: [{"start": sec, "end": sec}, ...] relative to wav_path.
    Returns a 1-based speaker number per segment, or None if diarization could not run
    (caller keeps its existing labels).
    """
    if not DIARIZATION_ENABLED or not segments:
        return None
    try:
        audio = read_wav_pcm16k(wav_path)
        # Embed every segment once; only those >= MIN_SEGMENT_SEC take part in clustering.
        embs = [voice_embedding(audio[max(0, int(s["start"] * SAMPLE_RATE)):int(s["end"] * SAMPLE_RATE)])
                for s in segments]
        good = [i for i, e in enumerate(embs)
                if e is not None and segments[i]["end"] - segments[i]["start"] >= MIN_SEGMENT_SEC]
        if len(good) < 2:
            return [1] * len(segments)
        good_labels = np.array(cluster_embeddings(np.stack([embs[i] for i in good])))
        labels_full: List[Optional[int]] = [None] * len(segments)
        for i, lab in zip(good, good_labels):
            labels_full[i] = int(lab)
        # Short utterances: nearest cluster centroid if they could be embedded, else previous speaker.
        short = [i for i, e in enumerate(embs) if labels_full[i] is None and e is not None]
        if short:
            normed = _normalise(np.stack([embs[i] for i in good + short]))
            centroids = np.stack([normed[:len(good)][good_labels == c].mean(axis=0) for c in range(good_labels.max() + 1)])
            for i, v in zip(short, normed[len(good):]):
                labels_full[i] = int(np.argmax(centroids @ v))
        for i in range(len(segments)):
            if labels_full[i] is None:
                labels_full[i] = labels_full[i - 1] if i else int(good_labels[0])
        numbered = _first_appearance_numbering([int(l) for l in labels_full])
        log.info("diarized %d utterances -> %d speaker(s) [backend=%s]", len(segments), len(set(numbered)),
                 active_backend())
        return numbered
    except Exception as e:
        log.warning("diarization skipped (%s: %s) - keeping previous speaker labels", type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# 2. Cross-chunk speaker unification (chunked Gemini / Whisper transcripts)
# ---------------------------------------------------------------------------
def _parse_line(line: str) -> Optional[Tuple[float, Optional[str], str]]:
    m = _TS_LINE_RE.match(line.strip())
    if not m:
        return None
    if m.group(3) is not None:
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    else:
        sec = int(m.group(1)) * 60 + int(m.group(2))
    return float(sec), m.group(4), m.group(5)


def unify_chunk_speakers(chunk_texts: List[Optional[str]], chunk_wavs: List[Optional[str]],
                         chunk_durations: List[float]) -> List[Optional[str]]:
    """
    chunk_texts[i]: transcript of chunk i with chunk-LOCAL timestamps and chunk-local
    "Speaker N" labels (every chunk starts counting from 1). chunk_wavs[i]: 16 kHz mono WAV
    of that chunk (None if unavailable). Returns the texts with globally consistent labels.

    Each (chunk, local speaker) pair becomes one voice sample (all of that speaker's audio in
    the chunk); samples are clustered across chunks with a cannot-link rule so two speakers
    the chunk already separated are never merged. Returns the input unchanged on any failure.
    """
    if not DIARIZATION_ENABLED:
        return chunk_texts
    ok_idx = [i for i, t in enumerate(chunk_texts) if t]
    if len(ok_idx) < 2:
        return chunk_texts
    try:
        group_keys: List[Tuple[int, str]] = []
        group_embs: List[np.ndarray] = []
        for i in ok_idx:
            wav = chunk_wavs[i] if i < len(chunk_wavs) else None
            if not wav or not os.path.exists(wav):
                continue
            audio = read_wav_pcm16k(wav)
            parsed = [_parse_line(l) for l in chunk_texts[i].splitlines()]
            parsed = [p for p in parsed if p and p[1]]
            spans: Dict[str, List[Tuple[float, float]]] = {}
            for k, (sec, spk, _txt) in enumerate(parsed):
                end = parsed[k + 1][0] if k + 1 < len(parsed) else chunk_durations[i]
                end = min(max(end, sec + 1.0), sec + 30.0)
                spans.setdefault(spk, []).append((sec, end))
            for spk, sp in spans.items():
                pieces, total = [], 0.0
                for s, e in sp:
                    if total >= MAX_GROUP_AUDIO_SEC:
                        break
                    a, b = int(s * SAMPLE_RATE), min(len(audio), int(e * SAMPLE_RATE))
                    if b > a:
                        pieces.append(audio[a:b])
                        total += (b - a) / SAMPLE_RATE
                emb = voice_embedding(np.concatenate(pieces)) if pieces else None
                if emb is not None:
                    group_keys.append((i, spk))
                    group_embs.append(emb)

        if len(group_embs) < 2:
            return chunk_texts
        labels = cluster_embeddings(np.stack(group_embs), cannot_link=[k[0] for k in group_keys])
        # Global numbering by first appearance (chunk order, then local speaker order).
        order = sorted(range(len(group_keys)), key=lambda g: (group_keys[g][0], str(group_keys[g][1]).zfill(4)))
        numbering: Dict[int, int] = {}
        for g in order:
            numbering.setdefault(labels[g], len(numbering) + 1)
        mapping = {group_keys[g]: numbering[labels[g]] for g in range(len(group_keys))}
        # Speakers with no usable audio get a fresh number rather than colliding with someone else.
        next_free = len(numbering) + 1

        out: List[Optional[str]] = list(chunk_texts)
        for i in ok_idx:
            new_lines = []
            for line in chunk_texts[i].splitlines():
                p = _parse_line(line)
                if p and p[1]:
                    key = (i, p[1])
                    if key not in mapping:
                        mapping[key] = next_free
                        next_free += 1
                    line = re.sub(r"Speaker\s*\w+\s*:", f"Speaker {mapping[key]}:", line, count=1)
                new_lines.append(line)
            out[i] = "\n".join(new_lines)
        log.info("unified speakers across %d chunks: %d local labels -> %d speaker(s)",
                 len(ok_idx), len(group_keys), len(numbering))
        return out
    except Exception as e:
        log.warning("cross-chunk speaker unification skipped (%s: %s)", type(e).__name__, e)
        return chunk_texts
