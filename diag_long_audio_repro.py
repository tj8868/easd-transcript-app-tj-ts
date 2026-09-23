"""
Reproduce the long-audio transcription path end-to-end and capture per-chunk logs.

Runs POST /api/transcribe_take IN-PROCESS (FastAPI TestClient) against app.app,
exactly as the "Initial Transcript" upload flow does, then prints the response
summary plus every log line written during the run.

Usage (from the app folder, inside the app's .venv):
    .venv\\Scripts\\python.exe diag_long_audio_repro.py "C:\\path\\to\\long_meeting.m4a"
    .venv\\Scripts\\python.exe diag_long_audio_repro.py long.mp3 --provider gemini --api-key AIza...
    .venv\\Scripts\\python.exe diag_long_audio_repro.py long.mp3 --provider local_whisper

If --api-key is omitted, the key saved in the app settings is used (same as the UI
when the key field is empty). Full logs also go to app_service.log next to app.py.
"""
import argparse
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--model", default="gemini-3.5-transcribe")
    ap.add_argument("--language", default="auto")
    args = ap.parse_args()

    import diag_logging
    log_path = diag_logging.LOG_FILE_PATH
    start_offset = os.path.getsize(log_path) if os.path.exists(log_path) else 0

    from fastapi.testclient import TestClient
    import app as app_module

    client = TestClient(app_module.app)
    t0 = time.time()
    with open(args.audio, "rb") as f:
        resp = client.post(
            "/api/transcribe_take",
            files={"file": (os.path.basename(args.audio), f, "application/octet-stream")},
            data={"provider": args.provider, "api_key": args.api_key,
                  "model_name": args.model, "language": args.language},
        )
    elapsed = time.time() - t0

    try:
        body = resp.json()
    except Exception:
        body = {"_raw": resp.text[:2000]}
    transcript = body.get("transcript") or ""

    print("\n" + "=" * 100)
    print(f"HTTP {resp.status_code} in {elapsed:.1f}s | status={body.get('status')} | "
          f"transcript_chars={len(transcript)} | language={body.get('language')}")
    extra = {k: v for k, v in body.items() if k not in ("transcript", "raw_transcript", "clean_text", "text")}
    print("Other response fields:", json.dumps(extra, ensure_ascii=False)[:3000])
    print("Transcript head:", (transcript[:400] or "<EMPTY>").replace("\n", " | "))
    print("=" * 100)
    print(f"LOG LINES WRITTEN DURING THIS RUN ({log_path}):")
    with open(log_path, "r", encoding="utf-8", errors="replace") as lf:
        lf.seek(start_offset)
        run_log = lf.read()
    print(run_log)
    out = os.path.join(BASE_DIR, f"diag_run_{time.strftime('%Y%m%d_%H%M%S')}.log")
    with open(out, "w", encoding="utf-8") as of:
        of.write(run_log)
    print(f"(Saved this run's log excerpt to {out})")


if __name__ == "__main__":
    main()
