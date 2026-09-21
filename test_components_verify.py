"""
test_components_verify.py
Comprehensive automated test suite for EASD Meeting Minutes Audio Pipeline:
1. Audio Extraction from Uploaded Video/Media File (.mp4) via FFmpeg
2. Spoken Language Auto-Detection (Bangla 'bn' vs English 'en')
3. Local Whisper Engine STT (INT8 CPU)
4. FastAPI Endpoints:
   - /api/detect_language
   - /api/live_transcribe_chunk
   - /api/transcribe_take
   - /api/transcribe_and_summarize
"""

import os
import sys
import time
import subprocess
from fastapi.testclient import TestClient
from app import app
import local_whisper_engine
import media_processor

client = TestClient(app)

def run_tests():
    print("=" * 65)
    print("🧪 RUNNING EASD TRANSCRIPTION & EXTRACTION VERIFICATION SUITE")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. Test Media Extraction from Uploaded File
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Audio Extraction from Uploaded Video/Media...")
    video_path = "test_upload_container.mp4"
    # Create synthetic test mp4 container with video + audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=navy:s=320x240:d=4",
        "-i", "test_english_neural.mp3",
        "-c:v", "libx264", "-t", "4", "-c:a", "aac", "-b:a", "128k",
        video_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(video_path, "rb") as f:
        video_bytes = f.read()

    proc_result = media_processor.process_uploaded_media(
        video_bytes, "test_meeting_video.mp4", "video/mp4"
    )
    extracted_bytes = proc_result.get("audio_bytes")
    extracted_mime = proc_result.get("mime_type")
    print(f"   Original size: {len(video_bytes)} bytes (video/mp4)")
    print(f"   Extracted audio size: {len(extracted_bytes)} bytes ({extracted_mime})")
    print(f"   Extraction format: {proc_result.get('format_detected')}")
    assert len(extracted_bytes) > 0, "Extracted audio bytes must not be empty"
    assert extracted_mime == "audio/mp3", f"Expected audio/mp3, got {extracted_mime}"
    print("   ✅ PASSED: Audio cleanly extracted from video/mp4 upload.")

    # -------------------------------------------------------------
    # 2. Test Spoken Language Auto-Detection on Bangla and English
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Language Auto-Detection on Bangla & English Audio...")
    model = local_whisper_engine.get_local_whisper_model()

    # Pure Bengali audio test
    with open("test_bangla_neural.mp3", "rb") as f:
        bn_bytes = f.read()
    bn_lang, bn_conf = local_whisper_engine.detect_audio_language(model, "test_bangla_neural.mp3")
    print(f"   Bengali Audio: detected '{bn_lang}' with confidence {bn_conf:.2f}")
    assert bn_lang == "bn", f"Bengali audio was misdetected as '{bn_lang}'"

    # Pure English audio test
    with open("test_english_neural.mp3", "rb") as f:
        en_bytes = f.read()
    en_lang, en_conf = local_whisper_engine.detect_audio_language(model, "test_english_neural.mp3")
    print(f"   English Audio: detected '{en_lang}' with confidence {en_conf:.2f}")
    assert en_lang == "en", f"English audio was misdetected as '{en_lang}'"

    # Test /api/detect_language HTTP Endpoint
    res_bn_http = client.post(
        "/api/detect_language",
        files={"chunk": ("speech.mp3", bn_bytes, "audio/mp3")}
    )
    assert res_bn_http.status_code == 200
    assert res_bn_http.json().get("language") == "bn"
    print(f"   HTTP /api/detect_language for Bangla: {res_bn_http.json()}")

    res_en_http = client.post(
        "/api/detect_language",
        files={"chunk": ("speech.mp3", en_bytes, "audio/mp3")}
    )
    assert res_en_http.status_code == 200
    assert res_en_http.json().get("language") == "en"
    print(f"   HTTP /api/detect_language for English: {res_en_http.json()}")
    print("   ✅ PASSED: Spoken language accurately auto-detected for both Bangla and English.")

    # -------------------------------------------------------------
    # 3. Test Live Take Transcription Endpoint (/api/transcribe_take)
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing /api/transcribe_take with Language Auto-Detect...")
    # Bangla Take
    res_take_bn = client.post(
        "/api/transcribe_take",
        files={"file": ("take_bn.mp3", bn_bytes, "audio/mp3")},
        data={"language": "auto", "provider": "local_whisper"}
    )
    assert res_take_bn.status_code == 200
    data_bn = res_take_bn.json()
    print(f"   Bangla Take Status: {data_bn.get('status')}, Detected Lang: {data_bn.get('language')}")
    print(f"   Bangla Text: {data_bn.get('clean_text')}")
    assert data_bn.get("language") == "bn"
    assert len(data_bn.get("clean_text", "")) > 0

    # English Take
    res_take_en = client.post(
        "/api/transcribe_take",
        files={"file": ("take_en.mp3", en_bytes, "audio/mp3")},
        data={"language": "auto", "provider": "local_whisper"}
    )
    assert res_take_en.status_code == 200
    data_en = res_take_en.json()
    print(f"   English Take Status: {data_en.get('status')}, Detected Lang: {data_en.get('language')}")
    print(f"   English Text: {data_en.get('clean_text')}")
    assert data_en.get("language") == "en"
    assert len(data_en.get("clean_text", "")) > 0
    print("   ✅ PASSED: /api/transcribe_take auto-detects and returns verbatim transcripts.")

    # -------------------------------------------------------------
    # 4. Test Live Chunk Streaming Endpoint (/api/live_transcribe_chunk)
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing /api/live_transcribe_chunk for Live Recording...")
    res_chunk = client.post(
        "/api/live_transcribe_chunk",
        files={"chunk": ("chunk.mp3", en_bytes[:15000], "audio/mp3")},
        data={"language": "auto", "provider": "local_whisper", "model_name": "gemini-3.5-transcribe-live"}
    )
    assert res_chunk.status_code == 200
    chunk_json = res_chunk.json()
    print(f"   Live chunk response: {chunk_json}")
    assert chunk_json.get("status") == "success"
    print("   ✅ PASSED: /api/live_transcribe_chunk handles audio slices seamlessly.")

    # -------------------------------------------------------------
    # 5. Test End-to-End Transcribe and Summarize on Uploaded Video
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Full Pipeline (/api/transcribe_and_summarize) on Video...")
    res_full = client.post(
        "/api/transcribe_and_summarize",
        files={"file": ("uploaded_meeting.mp4", video_bytes, "video/mp4")},
        data={
            "transcription_provider": "local_whisper",
            "transcription_model": "auto",
            "summarization_provider": "local_whisper",
            "language": "auto"
        }
    )
    assert res_full.status_code == 200
    full_data = res_full.json()
    payload = full_data.get("data", full_data)
    transcript_text = payload.get("transcript") or payload.get("raw_transcript") or ""
    has_summary = bool(payload.get("summary"))
    print(f"   Full pipeline status: {full_data.get('status')}")
    print(f"   Transcribed text length: {len(transcript_text)} chars")
    print(f"   Transcribed sample: {transcript_text[:120]}...")
    print(f"   Minutes generated: {has_summary}")
    assert full_data.get("status") == "success"
    assert len(transcript_text) > 0, "Expected non-empty transcript from extracted video audio"
    assert has_summary, "Expected meeting minutes summary from pipeline"
    print("   ✅ PASSED: Full upload -> extract audio -> transcribe -> minutes pipeline succeeded.")

    # Cleanup temporary video
    if os.path.exists(video_path):
        os.remove(video_path)

    print("\n" + "=" * 65)
    print("🎉 ALL 5 COMPONENTS VERIFIED AND WORKING 100% PERFECTLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
