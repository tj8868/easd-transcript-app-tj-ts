"""
WhisperX & Pyannote Speaker Diarization Engine
=============================================
Provides state-of-the-art speech-to-text with neural acoustic speaker diarization.

Features:
1. Pyannote Community Diarization Pipeline ('pyannote/speaker-diarization-community-1')
2. WhisperX End-to-End Pipeline (Faster-Whisper + Alignment + Pyannote Diarization)
3. Hybrid Overlap Matcher: Merges Pyannote speaker turns with faster-whisper transcripts.
4. Memory-optimized for Windows CPU (INT8, multi-threading limits, garbage collection).
"""

import os
import sys
import gc
import json
import logging
import argparse
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger("whisperx_diarization")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def get_optimal_device() -> str:
    """Detect CUDA GPU or fallback to CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def check_diarization_prerequisites() -> Dict[str, bool]:
    """Check availability of torch, pyannote, and whisperx."""
    status = {
        "torch": False,
        "torchaudio": False,
        "pyannote_audio": False,
        "whisperx": False,
        "cuda_available": False
    }
    try:
        import torch
        status["torch"] = True
        status["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        pass

    try:
        import torchaudio
        status["torchaudio"] = True
    except ImportError:
        pass

    try:
        import pyannote.audio
        status["pyannote_audio"] = True
    except ImportError:
        pass

    try:
        import whisperx
        status["whisperx"] = True
    except ImportError:
        pass

    return status


# =====================================================================
# 1. Standalone Pyannote Diarization Pipeline
# =====================================================================

def run_pyannote_diarization(
    audio_path: str,
    hf_token: str,
    pipeline_model: str = "pyannote/speaker-diarization-community-1",
    device: Optional[str] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run the Pyannote Speaker Diarization Community Pipeline on an audio file.

    Args:
        audio_path: Path to audio file (wav, mp3, etc.)
        hf_token: Hugging Face user access token (with read permissions)
        pipeline_model: 'pyannote/speaker-diarization-community-1' or 'pyannote/speaker-diarization-3.1'
        device: 'cuda' or 'cpu' (auto-detected if None)
        min_speakers: Minimum number of speakers if known
        max_speakers: Maximum number of speakers if known

    Returns:
        Dict containing speaker turns, timeline, and unique speakers.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if not hf_token or not hf_token.strip():
        raise ValueError("A valid Hugging Face access token is required for Pyannote Diarization.")

    clean_token = hf_token.strip()
    os.environ["HF_TOKEN"] = clean_token

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as e:
        raise ImportError(
            f"PyTorch or pyannote.audio is not installed: {e}\n"
            "Install with: pip install torch torchaudio pyannote.audio"
        )

    resolved_device = device or get_optimal_device()
    logger.info(f"Initializing Pyannote pipeline '{pipeline_model}' on {resolved_device}...")

    # Load pretrained pipeline with Hugging Face Token
    try:
        pipeline = Pipeline.from_pretrained(
            pipeline_model,
            token=clean_token
        )
    except TypeError:
        # Backward compatibility with older pyannote.audio use_auth_token argument
        pipeline = Pipeline.from_pretrained(
            pipeline_model,
            use_auth_token=clean_token
        )

    if pipeline is None:
        raise RuntimeError(
            f"Failed to load pipeline '{pipeline_model}'. Please check your Hugging Face token "
            "and ensure you have accepted user conditions at: "
            f"https://huggingface.co/{pipeline_model} and https://huggingface.co/pyannote/segmentation-3.0"
        )

    pipeline.to(torch.device(resolved_device))

    logger.info(f"Running diarization on '{audio_path}'...")
    params = {}
    if min_speakers is not None:
        params["min_speakers"] = int(min_speakers)
    if max_speakers is not None:
        params["max_speakers"] = int(max_speakers)

    output = pipeline(audio_path, **params)

    # Parse speaker turns
    turns: List[Dict[str, Any]] = []
    speakers_set = set()

    # Handle output format
    if hasattr(output, "speaker_diarization"):
        # Pyannote community wrapper format
        for turn, speaker in output.speaker_diarization:
            turns.append({
                "start": round(float(turn.start), 3),
                "end": round(float(turn.end), 3),
                "speaker": str(speaker)
            })
            speakers_set.add(str(speaker))
    elif hasattr(output, "itertracks"):
        # Standard pyannote.core.Annotation format
        for turn, _, speaker in output.itertracks(yield_label=True):
            turns.append({
                "start": round(float(turn.start), 3),
                "end": round(float(turn.end), 3),
                "speaker": str(speaker)
            })
            speakers_set.add(str(speaker))
    else:
        logger.warning("Unrecognized pyannote output structure; attempting iteration")
        try:
            for item in output:
                turns.append({
                    "start": round(float(item[0].start), 3),
                    "end": round(float(item[0].end), 3),
                    "speaker": str(item[1])
                })
                speakers_set.add(str(item[1]))
        except Exception as err:
            logger.error(f"Could not parse pyannote output: {err}")

    logger.info(f"Diarization complete. Found {len(turns)} turns across {len(speakers_set)} speakers.")

    return {
        "status": "success",
        "audio_path": audio_path,
        "pipeline": pipeline_model,
        "device": resolved_device,
        "turns_count": len(turns),
        "speakers": sorted(list(speakers_set)),
        "speaker_turns": turns
    }


# =====================================================================
# 2. End-to-End WhisperX Diarization Pipeline
# =====================================================================

def run_whisperx_pipeline(
    audio_path: str,
    hf_token: str,
    model_name: str = "small",
    language: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    batch_size: int = 4,
    diarize_model_name: str = "pyannote/speaker-diarization-community-1",
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run complete WhisperX ASR + Forced Alignment + Pyannote Diarization.

    Workflow:
    1. Whisper batched ASR transcription (faster-whisper)
    2. Phoneme-level alignment via wav2vec2 for exact word timestamps
    3. Speaker diarization via Pyannote pipeline with Hugging Face Token
    4. Speaker assignment to words and segments
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if not hf_token or not hf_token.strip():
        raise ValueError("A valid Hugging Face access token is required for WhisperX diarization.")

    clean_token = hf_token.strip()

    try:
        import torch
        import whisperx
    except ImportError as e:
        raise ImportError(
            f"whisperx is not installed: {e}\n"
            "Install with: pip install torch torchaudio whisperx"
        )

    resolved_device = device or get_optimal_device()
    if compute_type is None:
        compute_type = "float16" if resolved_device == "cuda" else "int8"

    logger.info(f"WhisperX starting: device={resolved_device}, compute_type={compute_type}, model={model_name}")

    # 1. Transcribe with Whisper
    logger.info(f"Step 1/4: Transcribing with Whisper model '{model_name}'...")
    asr_model = whisperx.load_model(
        model_name,
        device=resolved_device,
        compute_type=compute_type,
        language=language
    )
    audio = whisperx.load_audio(audio_path)
    asr_result = asr_model.transcribe(audio, batch_size=batch_size)
    detected_lang = asr_result.get("language", language or "en")
    logger.info(f"Step 1/4 done. Detected language: '{detected_lang}', {len(asr_result.get('segments', []))} segments.")

    # Free ASR model VRAM/RAM before alignment and diarization
    del asr_model
    gc.collect()
    if resolved_device == "cuda":
        torch.cuda.empty_cache()

    # 2. Phoneme Alignment for exact word timestamps
    aligned_result = asr_result
    try:
        logger.info(f"Step 2/4: Aligning audio for language '{detected_lang}'...")
        align_model, metadata = whisperx.load_align_model(
            language_code=detected_lang,
            device=resolved_device
        )
        aligned_result = whisperx.align(
            asr_result["segments"],
            align_model,
            metadata,
            audio,
            resolved_device,
            return_char_alignments=False
        )
        del align_model
        gc.collect()
        if resolved_device == "cuda":
            torch.cuda.empty_cache()
        logger.info("Step 2/4 done. Forced alignment succeeded.")
    except Exception as align_err:
        logger.warning(f"Step 2/4 skipped (alignment unavailable for language '{detected_lang}'): {align_err}")

    # 3. Speaker Diarization with Pyannote Pipeline
    logger.info(f"Step 3/4: Diarizing speakers via '{diarize_model_name}'...")
    try:
        diarize_pipeline = whisperx.DiarizationPipeline(
            model_name=diarize_model_name,
            use_auth_token=clean_token,
            device=resolved_device
        )
    except Exception as e:
        # Fallback to standard pyannote/speaker-diarization-3.1 if community-1 isn't supported by current whisperx version
        logger.warning(f"Could not load '{diarize_model_name}' directly in whisperx: {e}. Trying fallback 'pyannote/speaker-diarization-3.1'...")
        diarize_pipeline = whisperx.DiarizationPipeline(
            model_name="pyannote/speaker-diarization-3.1",
            use_auth_token=clean_token,
            device=resolved_device
        )

    diarize_kwargs = {}
    if min_speakers is not None:
        diarize_kwargs["min_speakers"] = int(min_speakers)
    if max_speakers is not None:
        diarize_kwargs["max_speakers"] = int(max_speakers)

    diarize_segments = diarize_pipeline(audio, **diarize_kwargs)
    logger.info(f"Step 3/4 done. Extracted speaker intervals.")

    # 4. Assign Speakers to Words and Segments
    logger.info("Step 4/4: Assigning speaker labels to transcription segments...")
    final_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)

    # Format transcript with timestamps and speakers
    formatted_lines = []
    raw_text_parts = []
    segments_data = []

    for seg in final_result.get("segments", []):
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        speaker = seg.get("speaker", "SPEAKER_UNKNOWN")
        text = seg.get("text", "").strip()
        if not text:
            continue

        m = int(start // 60)
        s = int(start % 60)
        time_tag = f"[{m:02d}:{s:02d}]"
        line = f"{time_tag} {speaker}: {text}"
        formatted_lines.append(line)
        raw_text_parts.append(text)
        segments_data.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "speaker": speaker,
            "text": text,
            "timestamp": time_tag
        })

    raw_transcript = "\n".join(formatted_lines)
    clean_text = " ".join(raw_text_parts)

    return {
        "status": "success",
        "provider": "whisperx",
        "model": model_name,
        "language": detected_lang,
        "text": raw_transcript,
        "raw_transcript": raw_transcript,
        "clean_text": clean_text,
        "segments": segments_data,
        "segments_count": len(segments_data)
    }


# =====================================================================
# 3. Hybrid Alignment: Match Pyannote Turns to Whisper Segments
# =====================================================================

def merge_whisper_segments_with_pyannote(
    whisper_segments: List[Dict[str, Any]],
    diarization_turns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Takes segments from faster-whisper (or any ASR) and assigns speakers
    from Pyannote acoustic turns based on maximum temporal overlap.
    """
    if not diarization_turns:
        return whisper_segments

    assigned_segments = []

    for seg in whisper_segments:
        s_start = seg.get("start", 0.0)
        s_end = seg.get("end", s_start + 1.0)
        seg_duration = max(0.001, s_end - s_start)

        # Find best overlapping speaker turn
        best_speaker = None
        max_overlap = 0.0

        for turn in diarization_turns:
            t_start = turn["start"]
            t_end = turn["end"]
            overlap_start = max(s_start, t_start)
            overlap_end = min(s_end, t_end)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = turn["speaker"]

        # If no strict overlap, find closest turn
        if not best_speaker and diarization_turns:
            closest_turn = min(diarization_turns, key=lambda t: abs(t["start"] - s_start))
            best_speaker = closest_turn["speaker"]

        updated_seg = dict(seg)
        updated_seg["speaker"] = best_speaker or "SPEAKER_00"

        # Update formatted timestamp string if present
        m = int(s_start // 60)
        s = int(s_start % 60)
        updated_seg["timestamp"] = f"[{m:02d}:{s:02d}]"
        assigned_segments.append(updated_seg)

    return assigned_segments


# =====================================================================
# 4. Token Resolution & Engine Testing
# =====================================================================

def get_huggingface_token(explicit_token: Optional[str] = None) -> str:
    """Resolves Hugging Face token from parameter, env variables, key files, or disk settings."""
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    # Check environment variables
    for env_var in ["HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"]:
        val = os.getenv(env_var)
        if val and val.strip():
            return val.strip()

    # Check key files in root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in ["HuggingFaceAPI.txt", "HF_TOKEN.txt", "hf_token.txt"]:
        fpath = os.path.join(base_dir, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    tok = f.read().strip()
                    if tok:
                        return tok
            except Exception:
                pass

    # Check api_settings.json
    settings_path = os.path.join(base_dir, "api_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("hf_token"):
                    return str(data["hf_token"]).strip()
        except Exception:
            pass

    return ""


def test_whisperx_engine(
    hf_token: Optional[str] = None,
    diarize_model_name: str = "pyannote/speaker-diarization-community-1"
) -> Dict[str, Any]:
    """Tests Hugging Face token against whoami-v2 and reports status of WhisperX prerequisites."""
    token = get_huggingface_token(hf_token)
    prereqs = check_diarization_prerequisites()

    if not token:
        return {
            "status": "warning",
            "valid": False,
            "message": "Hugging Face token is missing. Please set HF_TOKEN in .env, HuggingFaceAPI.txt, or Settings.",
            "prerequisites": prereqs,
            "user": None
        }

    try:
        import httpx
        with httpx.Client(timeout=8.0) as client:
            r = client.get("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {token}"})
            if r.status_code == 200:
                user_info = r.json()
                username = user_info.get("name", "User")
                return {
                    "status": "success",
                    "valid": True,
                    "message": f"Hugging Face token authenticated ({username}). WhisperX engine ready.",
                    "user": username,
                    "prerequisites": prereqs,
                    "pipeline": diarize_model_name
                }
            else:
                return {
                    "status": "error",
                    "valid": False,
                    "message": f"Hugging Face token rejected (HTTP {r.status_code}). Check token permissions.",
                    "prerequisites": prereqs,
                    "user": None
                }
    except Exception as e:
        return {
            "status": "error",
            "valid": False,
            "message": f"Hugging Face connection check failed: {str(e)}",
            "prerequisites": prereqs,
            "user": None
        }


def transcribe_with_diarization(
    audio_path: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    hf_token: Optional[str] = None,
    whisper_model_name: str = "small",
    language: Optional[str] = None,
    diarize_model_name: str = "pyannote/speaker-diarization-community-1",
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
) -> Dict[str, Any]:
    """
    High-level speech transcription with neural speaker diarization.
    Accepts either an audio filepath or raw audio bytes.
    Uses WhisperX if available, with robust fallback to local faster-whisper + Pyannote merge.
    """
    import tempfile
    temp_file = None
    resolved_path = audio_path

    try:
        if audio_bytes and not resolved_path:
            # Write to a temp WAV file
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_file.write(audio_bytes)
            temp_file.flush()
            temp_file.close()
            resolved_path = temp_file.name

        if not resolved_path or not os.path.isfile(resolved_path):
            return {
                "status": "error",
                "text": "",
                "raw_transcript": "",
                "clean_text": "",
                "message": "No valid audio provided."
            }

        token = get_huggingface_token(hf_token)
        prereqs = check_diarization_prerequisites()

        # Strategy A: Try WhisperX end-to-end pipeline if whisperx is installed and token exists
        if prereqs.get("whisperx") and token:
            try:
                return run_whisperx_pipeline(
                    audio_path=resolved_path,
                    hf_token=token,
                    model_name=whisper_model_name,
                    language=language,
                    diarize_model_name=diarize_model_name,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
            except Exception as wx_err:
                logger.warning(f"WhisperX pipeline encountered error: {wx_err}. Falling back to faster-whisper + Pyannote.")

        # Strategy B: Run local faster-whisper transcription first
        import local_whisper_engine
        whisper_res = local_whisper_engine.transcribe_local_audio(
            media_input=resolved_path,
            language=language or "auto",
            beam_size=2,
            temperature=0.0
        )

        segments = whisper_res.get("segments", [])

        # If we have HF token and pyannote.audio, run Pyannote diarization and merge
        if token and prereqs.get("pyannote_audio"):
            try:
                diar_res = run_pyannote_diarization(
                    audio_path=resolved_path,
                    hf_token=token,
                    pipeline_model=diarize_model_name,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
                turns = diar_res.get("speaker_turns", [])
                if turns and segments:
                    merged_segments = merge_whisper_segments_with_pyannote(segments, turns)
                    lines = []
                    clean_parts = []
                    for s in merged_segments:
                        spk = s.get("speaker", "Speaker 1")
                        txt = s.get("text", "").strip()
                        ts = s.get("timestamp") or f"[{int(s.get('start', 0)//60):02d}:{int(s.get('start', 0)%60):02d}]"
                        if txt:
                            lines.append(f"{ts} {spk}: {txt}")
                            clean_parts.append(txt)

                    raw_t = "\n".join(lines)
                    return {
                        "status": "success",
                        "provider": "whisperx",
                        "model": diarize_model_name,
                        "language": whisper_res.get("detected_language", "bn"),
                        "text": raw_t,
                        "raw_transcript": raw_t,
                        "clean_text": " ".join(clean_parts),
                        "segments": merged_segments
                    }
            except Exception as diar_err:
                logger.warning(f"Pyannote diarization failed: {diar_err}. Returning faster-whisper transcript.")

        # If no HF token or diarization failed, return whisper result
        return {
            "status": "success",
            "provider": "whisperx_fallback",
            "model": whisper_model_name,
            "language": whisper_res.get("detected_language", "bn"),
            "text": whisper_res.get("raw_transcript") or whisper_res.get("clean_text", ""),
            "raw_transcript": whisper_res.get("raw_transcript", ""),
            "clean_text": whisper_res.get("clean_text", ""),
            "segments": segments
        }

    finally:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except Exception:
                pass


# =====================================================================
# CLI Entry Point
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="WhisperX & Pyannote Speaker Diarization CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--audio", required=True, help="Path to audio file (wav, mp3, etc.)")
    parser.add_argument("--hf_token", default=os.getenv("HF_TOKEN"), help="Hugging Face User Access Token")
    parser.add_argument("--mode", choices=["whisperx", "pyannote"], default="whisperx",
                        help="Choose 'whisperx' for full ASR + diarization, or 'pyannote' for diarization only")
    parser.add_argument("--model", default="small", help="Whisper model size (small, base, medium, large-v3)")
    parser.add_argument("--pipeline", default="pyannote/speaker-diarization-community-1",
                        help="Pyannote Hugging Face pipeline model")
    parser.add_argument("--device", default=None, help="Device to use ('cpu' or 'cuda')")
    parser.add_argument("--min_speakers", type=int, default=None, help="Minimum expected speakers")
    parser.add_argument("--max_speakers", type=int, default=None, help="Maximum expected speakers")
    parser.add_argument("--output", default=None, help="Optional output JSON or TXT file path")

    args = parser.parse_args()

    if not args.hf_token:
        print("ERROR: Hugging Face token is missing.")
        print("Provide via --hf_token <token> or set HF_TOKEN environment variable.")
        sys.exit(1)

    print(f"Checking environment prerequisites...")
    prereqs = check_diarization_prerequisites()
    print("Prerequisites status:", json.dumps(prereqs, indent=2))

    if args.mode == "pyannote":
        print(f"\n--- Running Pyannote Diarization Pipeline on {args.audio} ---")
        res = run_pyannote_diarization(
            audio_path=args.audio,
            hf_token=args.hf_token,
            pipeline_model=args.pipeline,
            device=args.device,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers
        )
        print("\nPredicted Speaker Diarization:")
        for turn in res["speaker_turns"]:
            print(f"{turn['speaker']} speaks between t={turn['start']:.3f}s and t={turn['end']:.3f}s")
    else:
        print(f"\n--- Running WhisperX Pipeline (ASR + Diarization) on {args.audio} ---")
        res = run_whisperx_pipeline(
            audio_path=args.audio,
            hf_token=args.hf_token,
            model_name=args.model,
            device=args.device,
            diarize_model_name=args.pipeline,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers
        )
        print("\n--- Diarized Transcription ---")
        print(res["raw_transcript"])

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            if args.output.endswith(".json"):
                json.dump(res, f, indent=2, ensure_ascii=False)
            else:
                f.write(res.get("raw_transcript", str(res)))
        print(f"\nSaved results to {args.output}")


if __name__ == "__main__":
    main()
