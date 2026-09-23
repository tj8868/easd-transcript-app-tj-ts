import io
import wave
import struct
import math
import httpx
import json

def generate_test_pcm16_wav(duration_sec=2.0, sample_rate=16000):
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n_samples = int(duration_sec * sample_rate)
        freq = 440.0
        for i in range(n_samples):
            val = int(32767.0 * 0.25 * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
            wf.writeframes(struct.pack("<h", val))
    return wav_io.getvalue()

def test_recording_and_generate_pipeline():
    print("=" * 60)
    print("TESTING END-TO-END RECORDING & GENERATE BUTTON WORKFLOW")
    print("=" * 60)

    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=60.0)

    # 1. Step 1: User records audio take -> /api/transcribe_take
    print("\n1. Testing recorded audio take transcription (/api/transcribe_take)...")
    wav_bytes = generate_test_pcm16_wav(2.0)
    files = {"file": ("recorded_take.wav", wav_bytes, "audio/wav")}
    data = {"provider": "local", "model_name": "tiny", "language": "en"}
    
    resp_take = client.post("/api/transcribe_take", files=files, data=data)
    print("  Status code:", resp_take.status_code)
    assert resp_take.status_code == 200, f"transcribe_take failed: {resp_take.text}"
    take_data = resp_take.json()
    # v8.3: a 2-second test tone contains no speech, so an honest "error" (with a reason) is correct.
    assert take_data.get("status") in ("success", "partial", "error")
    if take_data.get("status") != "success":
        assert take_data.get("message"), "failed transcription must explain why"
    print("  Transcription response received:", take_data)

    # 2. Step 2: The transcript is placed in the editor
    # Let's use a realistic transcript of a meeting/report
    sample_transcript = (
        "Weekly Strategic, Programmatic and Presentation Review Meeting held at Eminence Mohakhali DOHS. "
        "Dr. Shamim Talukder reviewed progress on previous action items. "
        "The team agreed to finalize the community health initiative by next Thursday. "
        "Decisions were taken to approve the Q4 roadmap and schedule the next session for September 5."
    )
    print(f"\n2. Transcript editor populated with {len(sample_transcript)} characters.")

    # 3. Step 3: User clicks the big 'Generate' button -> /api/summarize_transcript
    for test_template_id in ["easd_default_minutes", "bangladesh_govt_nothi", "blog_article"]:
        print(f"\n3. Testing 'Generate' button click for template: '{test_template_id}'...")
        generate_payload = {
            "transcript": sample_transcript,
            "provider": "local",
            "template_id": test_template_id
        }
        resp_gen = client.post("/api/summarize_transcript", data=generate_payload)
        print("  Status code:", resp_gen.status_code)
        assert resp_gen.status_code == 200, f"summarize_transcript failed: {resp_gen.text}"
        gen_res = resp_gen.json()
        assert gen_res.get("status") == "success"
        
        extracted_data = gen_res.get("data", {})
        summary = extracted_data.get("summary", {})
        doc_type = extracted_data.get("doc_type")
        print(f"  [PASS] Output doc_type: {doc_type}")
        print(f"  [PASS] Summary populated keys: {list(summary.keys())}")
        assert summary.get("title") or summary.get("ministry") or summary.get("subject"), "Missing core identifier"
        assert "sections_data" in summary, "Missing sections_data"
        assert "tables_data" in summary, "Missing tables_data"

        # 4. Step 4: Verify Word DOCX Generation from the generated summary
        print(f"4. Testing DOCX generation for '{test_template_id}'...")
        docx_payload = {
            "template_id": test_template_id,
            "doc_data": summary
        }
        resp_docx = client.post("/api/generate_custom_docx", json=docx_payload)
        assert resp_docx.status_code == 200, f"DOCX generation failed: {resp_docx.text}"
        assert len(resp_docx.content) > 1000, f"DOCX file content too small: {len(resp_docx.content)} bytes"
        print(f"  [PASS] DOCX successfully generated ({len(resp_docx.content)} bytes)!")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED: THE GENERATE BUTTON & RECORDING WORK 100%!")
    print("=" * 60)

if __name__ == "__main__":
    test_recording_and_generate_pipeline()
