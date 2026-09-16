import os
import sys
from fastapi.testclient import TestClient
from app import app
import local_whisper_engine

def test_seamless_whisper_fallback():
    print("=== Testing Seamless Local Whisper Fallback on Gemini Failure ===")
    client = TestClient(app)

    # Inspect host RAM specs
    specs = local_whisper_engine.get_system_ram_specs()
    print(f"1. Host System RAM Specs: {specs}")
    opt_model = local_whisper_engine.select_optimal_model_name()
    print(f"2. Dynamically Selected Optimal Model: {opt_model}")
    assert opt_model in ["tiny", "base", "small"]

    # Read authentic audio test file
    audio_path = os.path.join(os.path.dirname(__file__), "test_slice2.mp3")
    assert os.path.exists(audio_path), "test_slice2.mp3 not found"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    # 3. Test /api/transcribe_take with an invalid key to simulate Gemini 403 / permission denied / failure
    print("3. Testing /api/transcribe_take with failing/denied Gemini key...")
    resp = client.post(
        "/api/transcribe_take",
        data={
            "provider": "gemini",
            "api_key": "AQ.SIMULATED_403_PERMISSION_DENIED_KEY",
            "model_name": "gemini-3.5-transcribe",
            "language": "auto"
        },
        files={"file": ("test_slice2.mp3", audio_bytes, "audio/mp3")}
    )

    print(f"   HTTP Status: {resp.status_code}")
    assert resp.status_code == 200, f"Expected 200 with seamless fallback, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print(f"   Response Status: {data.get('status')}")
    print(f"   Transcript Length: {len(data.get('transcript', ''))}")
    print(f"   Detected Language: {data.get('language')}")
    print(f"   Sample Transcript Snippet: {data.get('transcript', '')[:120]}...")
    assert data.get("status") == "success"
    assert len(data.get("transcript", "").strip()) > 0, "Transcript should not be empty, fallback must succeed!"
    print("   [PASSED] /api/transcribe_take seamlessly transcribed audio via local Whisper fallback!")

    # 4. Test /api/transcribe_and_summarize with failing/denied Gemini key
    print("4. Testing /api/transcribe_and_summarize with failing/denied Gemini key...")
    summ_resp = client.post(
        "/api/transcribe_and_summarize",
        data={
            "provider": "gemini",
            "api_key": "AQ.SIMULATED_403_PERMISSION_DENIED_KEY",
            "model_name": "gemini-3.7-flash",
            "transcription_provider": "gemini",
            "transcription_api_key": "AQ.SIMULATED_403_PERMISSION_DENIED_KEY",
            "transcription_model": "gemini-3.5-transcribe",
            "text_content": ""
        },
        files={"file": ("test_slice2.mp3", audio_bytes, "audio/mp3")}
    )
    print(f"   HTTP Status: {summ_resp.status_code}")
    assert summ_resp.status_code == 200, f"Expected 200, got {summ_resp.status_code}: {summ_resp.text}"
    summ_data = summ_resp.json()
    assert summ_data.get("status") == "success"
    doc_data = summ_data.get("data", {})
    assert "bangla_transcript" in doc_data or "title" in doc_data
    print("   [PASSED] /api/transcribe_and_summarize seamlessly handled fallback without breaking!")

    print("\nALL SEAMLESS FALLBACK TESTS PASSED!")

if __name__ == "__main__":
    test_seamless_whisper_fallback()
