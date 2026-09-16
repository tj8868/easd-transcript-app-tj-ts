import sys
import os
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import local_whisper_engine
from app import app
from fastapi.testclient import TestClient

def test_anti_hallucination():
    print("=== 1. Testing sanitize_whisper_text on User-Reported Hallucination Strings ===")

    # Case 1: Syllable repetition loop with trailing replacement character
    user_string_1 = "বালোনা কার্যবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবিবি\ufffd"
    clean_1 = local_whisper_engine.sanitize_whisper_text(user_string_1)
    print(f"Original 1: {user_string_1[:60]}... (length {len(user_string_1)})")
    print(f"Cleaned 1:  {repr(clean_1)}")
    assert "বালোনা কার্য" in clean_1, "Genuine speech must be preserved"
    assert "বিবিবিবিবিবি" not in clean_1, "Repetition loop must be collapsed"
    assert "\ufffd" not in clean_1, "Replacement character must be removed"
    print("✓ Passed Case 1: Repetition loop cleanly collapsed while preserving speech!\n")

    # Case 2: Tibetan symbol hallucination loop from silence
    user_string_2 = "༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ ༼ \ufffd"
    clean_2 = local_whisper_engine.sanitize_whisper_text(user_string_2)
    print(f"Original 2: {user_string_2[:60]}... (length {len(user_string_2)})")
    print(f"Cleaned 2:  {repr(clean_2)}")
    assert clean_2 == "", "Pure Tibetan symbol hallucination must be 100% eliminated"
    print("✓ Passed Case 2: Pure hallucination completely discarded (returns empty string)!\n")

    # Case 3: Bengali single-token repetition ('নানানানানা...')
    user_string_3 = "আলোনানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানানান"
    clean_3 = local_whisper_engine.sanitize_whisper_text(user_string_3)
    print(f"Original 3: {user_string_3[:60]}... (length {len(user_string_3)})")
    print(f"Cleaned 3:  {repr(clean_3)}")
    assert "নানানানানানা" not in clean_3, "Loop must be collapsed"
    print("✓ Passed Case 3: Bengali syllable loop collapsed!\n")

    # Case 4: Normal English and Bengali authentic speech (must be preserved verbatim)
    normal_bn = "ড. শামীম তালুকদার আজকের মিটিং পরিচালনা করবেন।"
    normal_en = "We reviewed the quarterly action items and project milestones."
    assert local_whisper_engine.sanitize_whisper_text(normal_bn) == normal_bn
    assert local_whisper_engine.sanitize_whisper_text(normal_en) == normal_en
    print("✓ Passed Case 4: Authentic Bengali and English speech preserved verbatim!\n")

    print("=== 2. Testing RAM Specs & Model Selection Logic ===")
    specs = local_whisper_engine.get_system_ram_specs()
    print(f"Host System RAM: {specs}")
    opt_model = local_whisper_engine.select_optimal_model_name()
    print(f"Selected Optimal Model: '{opt_model}'")
    # On an 8GB machine, it should select 'small'
    assert opt_model in ["small", "base", "tiny"], f"Invalid model: {opt_model}"
    print("✓ Passed RAM Specs test!\n")

    print("=== 3. Testing Local Whisper Engine Transcription on test_slice2.mp3 ===")
    audio_path = os.path.join(os.path.dirname(__file__), "test_slice2.mp3")
    res = local_whisper_engine.transcribe_local_audio(
        media_input=audio_path,
        language="bn",
        beam_size=2,
        temperature=0.0
    )
    print(f"Transcription status: {res.get('status')}")
    print(f"Raw transcript: {repr(res.get('raw_transcript'))}")
    print(f"Clean text: {repr(res.get('clean_text'))}")
    assert "༼" not in res.get("raw_transcript", ""), "No Tibetan symbols allowed"
    assert "\ufffd" not in res.get("raw_transcript", ""), "No replacement characters allowed"
    print("✓ Passed local Whisper transcription test!\n")

    print("=== 4. Testing /api/transcribe_take Endpoint Integration ===")
    client = TestClient(app)
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    resp = client.post(
        "/api/transcribe_take",
        data={
            "provider": "local_whisper",
            "model_name": "small",
            "language": "bn"
        },
        files={"file": ("test_slice2.mp3", audio_bytes, "audio/mp3")}
    )
    assert resp.status_code == 200
    resp_data = resp.json()
    t = resp_data.get("transcript", "")
    print(f"Endpoint returned transcript: {repr(t)}")
    assert "༼" not in t, "No Tibetan symbols in endpoint response"
    assert "\ufffd" not in t, "No replacement characters in endpoint response"
    print("✓ Passed endpoint integration test!\n")

    print("=======================================================")
    print(" ALL ANTI-HALLUCINATION & ANTI-REPETITION TESTS PASSED! ")
    print("=======================================================")

if __name__ == "__main__":
    test_anti_hallucination()
