"""
v8.3 regression tests for the long-audio pipeline (no network needed).

Gemini is replaced by a FAKE transport that returns real google-genai response
objects, so the actual parsing / retry / fallback / assembly code is exercised.

Run:  python test_long_audio_pipeline.py [path\\to\\long_recording.m4a]
"""
import io
import json
import os
import sys
import time
import wave
import struct
import math
import hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("EASD_GEMINI_BACKOFF_BASE_SEC", "0.01")
os.environ.setdefault("EASD_GEMINI_STAGGER_SEC", "0")

from google.genai import types, errors  # noqa: E402
import stt_pipeline  # noqa: E402
import media_processor  # noqa: E402

stt_pipeline.GEMINI_BACKOFF_BASE_SEC = 0.01
stt_pipeline.GEMINI_STAGGER_SEC = 0.0

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (f"  -> {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------- fake Gemini
def transcribe_response(lines):
    parts = []
    for i, (sec, spk, txt) in enumerate(lines):
        parts.append(types.Part(audio_transcription=types.Transcription(
            text=txt, speaker_label=spk, words=[types.WordInfo(word=txt.split()[0], start_offset=f"{sec:.3f}s")])))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts),
                                                                      finish_reason="STOP")])


def text_response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)]), finish_reason="STOP")])


class FakeModels:
    def __init__(self, behaviour):
        self.behaviour = behaviour  # fn(chunk_no, model, call_no, contents) -> response | raises
        self.calls = {}

    def generate_content(self, model, contents, config=None):
        blob = None
        for c in (contents if isinstance(contents, list) else [contents]):
            if isinstance(c, types.Part) and c.inline_data:
                blob = c.inline_data.data
        key = (CHUNK_ID.get(hashlib.md5(blob).hexdigest()) if blob else None, model)
        self.calls[key] = self.calls.get(key, 0) + 1
        return self.behaviour(key[0], model, self.calls[key], contents)


class FakeClient:
    def __init__(self, behaviour):
        self.models = FakeModels(behaviour)


CHUNK_ID = {}


def register_chunks(chunks):
    CHUNK_ID.clear()
    for i, c in enumerate(chunks):
        CHUNK_ID[hashlib.md5(c).hexdigest()] = i + 1


def install(behaviour, whisper_ok=False):
    client = FakeClient(behaviour)
    stt_pipeline._gemini_client = lambda key: client
    if whisper_ok:
        stt_pipeline.whisper_transcribe_bytes = lambda audio, language="auto", mime_type="", ctx="", **kw: {
            "ok": True, "text": "[00:05] Speaker 1: whisper fallback text", "provider": "local_whisper", "error": ""}
    else:
        stt_pipeline.whisper_transcribe_bytes = lambda audio, language="auto", mime_type="", ctx="", **kw: {
            "ok": False, "text": "", "provider": "local_whisper",
            "error": "Local Whisper model not installed (download failed: 403 Forbidden)"}
    return client


def ok_lines(chunk_no):
    return [(12.5, "spk_1", f"chunk {chunk_no} opening remarks by the chair"),
            (95.0, "spk_2", f"chunk {chunk_no} response from the programme lead"),
            (430.2, "spk_1", f"chunk {chunk_no} decision recorded")]


def err(code, status, msg):
    return errors.APIError(code, {"error": {"code": code, "status": status, "message": msg}})


# ---------------------------------------------------------------- helpers
def make_tone_wav(seconds=3):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / 16000)))
                               for i in range(16000 * seconds)))
    return buf.getvalue()


def main(recording):
    print(f"\n=== 1. Ingest + 16 kHz mono + chunking: {os.path.basename(recording)}")
    t0 = time.time()
    proc = media_processor.process_uploaded_media(filename=os.path.basename(recording), file_path=recording)
    chunks, durs = proc["audio_chunks"], proc["chunk_durations"]
    check("audio decoded", proc["type"] in ("audio_chunks", "audio_single"), proc.get("error"))
    check("multiple 10-min chunks", len(chunks) >= 2, len(chunks))
    check("durations sum to file length (+-2s)", abs(sum(durs) - proc["total_duration_sec"]) < 2,
          f"{sum(durs)} vs {proc['total_duration_sec']}")
    check("every chunk under Gemini inline limit", all(len(c) < stt_pipeline.GEMINI_INLINE_MAX_BYTES for c in chunks))
    print(f"     {len(chunks)} chunks, durations={[round(d,1) for d in durs]} ({time.time()-t0:.1f}s)")
    register_chunks(chunks)
    n = len(chunks)

    print("\n=== 2. All chunks OK (transcribe mode, speaker labels 'spk_N')")
    install(lambda c, m, k, contents: transcribe_response(ok_lines(c)))
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="fake")
    lines = r["transcript"].splitlines()
    check("status success", r["status"] == "success", r["message"])
    check("3 lines per chunk", len(lines) == 3 * n, len(lines))
    check("speakers distinguished (not all Speaker 1)", any("Speaker 2:" in l for l in lines))
    def ts_sec(line):
        m = stt_pipeline._TS_RE.match(line)
        return (int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))) if m.group(3) else int(m.group(1))*60+int(m.group(2))
    check("timestamps offset by real chunk starts (+-1s)", abs(ts_sec(lines[3]) - (durs[0] + 12.5)) <= 1, f"{lines[3][:12]} vs {durs[0]+12.5}")
    check("model timestamps past chunk end are clamped (no overlap into next chunk)",
          ts_sec(lines[-1]) <= sum(durs) and ts_sec(lines[-1]) >= sum(durs[:-1]), f"{lines[-1][:12]} vs total {sum(durs)}")
    ts = [stt_pipeline._TS_RE.match(l) for l in lines]
    secs = [(int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))) if m.group(3) else int(m.group(1))*60+int(m.group(2)) for m in ts]
    check("timestamps never go backwards", all(b >= a for a, b in zip(secs, secs[1:])), secs)
    check("chunk order preserved", all(f"chunk {i+1}" in lines[3*i] for i in range(n)))

    print("\n=== 3. Rate limit: 429 twice on every chunk, then OK (retry + backoff)")
    def flaky(c, m, k, contents):
        if k <= 2:
            raise err(429, "RESOURCE_EXHAUSTED", "Resource has been exhausted (e.g. check quota).")
        return transcribe_response(ok_lines(c))
    client = install(flaky)
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="fake")
    check("recovers to success", r["status"] == "success", r["errors"])
    check("each chunk called 3 times", all(v == 3 for v in client.models.calls.values()), client.models.calls)

    print("\n=== 4. Chunk 3 permanently fails on both Gemini models, Whisper unavailable -> partial")
    def c3_bad(c, m, k, contents):
        if c == 3:
            raise err(400, "INVALID_ARGUMENT", "Request contains an invalid argument.")
        return transcribe_response(ok_lines(c))
    install(c3_bad)
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="fake")
    check("status partial", r["status"] == "partial", r["status"])
    check("other chunks kept", sum(1 for l in r["transcript"].splitlines() if "TRANSCRIPT GAP" not in l) == 3 * (n - 1))
    check("gap marker for 20:00-30:00", "TRANSCRIPT GAP 20:00-30:00" in r["transcript"], r["transcript"][:300])
    check("error names chunk + range + reason",
          any(e.startswith(f"Chunk 3 of {n} (20:00-30:00) failed:") and "400" in e and "Whisper" in e for e in r["errors"]), r["errors"])
    print("     " + r["errors"][0][:200])

    print("\n=== 5. Transcribe model 404 -> prompt-mode fallback model succeeds")
    def no_model(c, m, k, contents):
        if "transcribe" in m:
            raise err(404, "NOT_FOUND", f"models/{m} is not found for API version v1beta")
        return text_response("```\n[00:10] Speaker 1: fallback model line one\n[02:00] Speaker 2: line two\n```")
    install(no_model)
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="fake")
    check("status success via fallback model", r["status"] == "success", r["errors"])
    check("markdown fences stripped", "```" not in r["transcript"])

    print("\n=== 6. Bad API key (401) -> no pointless retries; Whisper fallback used")
    client = install(lambda c, m, k, contents: (_ for _ in ()).throw(err(401, "UNAUTHENTICATED", "API key not valid.")), whisper_ok=True)
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="bad")
    check("status success via whisper", r["status"] == "success" and r["providers_used"] == ["local_whisper"], r)
    check("401 not retried / other models skipped", all(v == 1 for v in client.models.calls.values()) and
          all("transcribe" in k[1] for k in client.models.calls), client.models.calls)

    print("\n=== 7. Everything fails -> explicit error, empty transcript, real reason")
    install(lambda c, m, k, contents: (_ for _ in ()).throw(err(503, "UNAVAILABLE", "The model is overloaded.")))
    r = stt_pipeline.transcribe_chunks(chunks, durs, api_key="fake")
    check("status error", r["status"] == "error")
    check("no fabricated text", r["transcript"] == "")
    check("reason surfaced", "503" in r["message"], r["message"])

    print("\n=== 8. No API key -> clear message, whisper attempted")
    install(lambda *a: transcribe_response([]))
    r = stt_pipeline.transcribe_chunks(chunks[:1], durs[:1], api_key="")
    check("says key missing", "No Gemini API key" in r["message"], r["message"])

    print("\n=== 9. Empty Gemini response is a failure with finish_reason, not silent")
    install(lambda c, m, k, contents: types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="SAFETY")]))
    r = stt_pipeline.transcribe_chunks(chunks[:1], durs[:1], api_key="fake")
    check("empty -> error with finish_reason", r["status"] == "error" and "SAFETY" in r["message"], r["message"])

    # ----------------------------------------------------------- API level
    print("\n=== 10. /api/transcribe_take end-to-end (real file, fake Gemini)")
    from fastapi.testclient import TestClient
    import app as app_module
    install(c3_bad)
    tc = TestClient(app_module.app)
    with open(recording, "rb") as f:
        resp = tc.post("/api/transcribe_take", files={"file": (os.path.basename(recording), f, "audio/mp4")},
                       data={"provider": "gemini", "api_key": "fake", "model_name": "gemini-3.5-transcribe", "language": "auto"})
    body = resp.json()
    check("HTTP 200", resp.status_code == 200)
    check("status partial + chunk error surfaced", body["status"] == "partial" and body["errors"] and "Chunk 3" in body["errors"][0], body.get("errors"))
    check("transcript returned (not empty)", len(body["transcript"]) > 100)

    print("\n=== 11. Short single-chunk upload (regression)")
    install(lambda c, m, k, contents: transcribe_response([(1.0, "spk_1", "short clip words")]))
    resp = tc.post("/api/transcribe_take", files={"file": ("short.wav", make_tone_wav(3), "audio/wav")},
                   data={"provider": "gemini", "api_key": "fake"})
    body = resp.json()
    check("short clip success", body["status"] == "success" and "short clip words" in body["transcript"], body)

    print("\n=== 12. Unsupported / corrupt media -> clear error")
    resp = tc.post("/api/transcribe_take", files={"file": ("broken.m4a", b"\x00" * 5000, "audio/mp4")},
                   data={"provider": "gemini", "api_key": "fake"})
    body = resp.json()
    check("corrupt file -> status error with FFmpeg reason", body["status"] == "error" and "decode" in body["message"].lower(), body["message"])

    print("\n=== 13. Template fill (/api/summarize_transcript) with fake LLM")
    import ai_providers
    transcript = "[00:12] Speaker 1: Today is 15 September 2026, meeting at 11:00 AM.\n[00:30] Speaker 2: Decision: the donor brief is approved."
    good_json = json.dumps({"detected_language": "en", "bangla_transcript": "বাংলা", "english_transcript": "English",
                            "summary": {"title": "Weekly Review", "location": "", "date": "15 September 2026", "time": "11:00 AM",
                                        "agendas": ["1. Donor brief"],
                                        "discussions": [{"sn": "1", "topic": "Followup from previous meeting", "details": "• • item"},
                                                        {"sn": "2", "topic": "Action items", "details": "• a"},
                                                        {"sn": "3", "topic": "Task Assignments", "details": "• b"},
                                                        {"sn": "4", "topic": "Meeting Decisions", "details": "• Donor brief approved"}],
                                        "decisions": "• Donor brief approved", "present_members": []},
                            "raw_transcript": "LLM REWRITE THAT MUST NOT REPLACE THE SOURCE"})
    fake_llm = FakeClient(lambda c, m, k, contents: text_response(good_json))
    stt_pipeline._gemini_client = lambda key: fake_llm
    resp = tc.post("/api/summarize_transcript", data={"transcript": transcript, "api_key": "fake",
                                                       "template_id": "easd_default_minutes"})
    d = resp.json()["data"]
    check("template filled from LLM", d.get("summary_source") == "llm" and d["summary"]["date"] == "15 September 2026", d.get("warning"))
    check("source transcript preserved (not LLM rewrite)", d["raw_transcript"] == transcript)
    check("double bullets cleaned", "• •" not in d["summary"]["discussions"][0]["details"])
    check("agenda numbering stripped", d["summary"]["agendas"] == ["Donor brief"], d["summary"]["agendas"])
    check("4 discussion rows", len(d["summary"]["discussions"]) == 4)

    print("\n=== 14. Truncated LLM JSON -> compact retry succeeds")
    fake_llm = FakeClient(lambda c, m, k, contents: text_response(good_json[:120]) if "600 words" not in str(contents) else text_response(good_json))
    stt_pipeline._gemini_client = lambda key: fake_llm
    d = tc.post("/api/summarize_transcript", data={"transcript": transcript, "api_key": "fake"}).json()["data"]
    check("recovered on compact pass", d.get("summary_source") == "llm", d.get("warning"))

    print("\n=== 15. LLM down -> offline extraction, NO invented content, warning explains why")
    fake_llm = FakeClient(lambda c, m, k, contents: (_ for _ in ()).throw(err(403, "PERMISSION_DENIED", "API key not valid")))
    stt_pipeline._gemini_client = lambda key: fake_llm
    d = tc.post("/api/summarize_transcript", data={"transcript": transcript, "api_key": "bad",
                                                   "template_id": "easd_default_minutes"}).json()["data"]
    s = d["summary"]
    check("offline source flagged", d.get("summary_source") == "offline_extraction")
    check("warning gives real reason", "API key" in d.get("warning", ""), d.get("warning"))
    check("date extracted from transcript (not 29 August)", s["date"] == "15 September 2026", s["date"])
    check("no fabricated boilerplate", "Formally approved active programmatic" not in json.dumps(s))
    check("decision row uses transcript text", "donor brief is approved" in s["discussions"][3]["details"].lower(), s["discussions"])
    for tid in ["blog_article", "news_press_release", "journal_academic", "bangladesh_govt_nothi"]:
        d = tc.post("/api/summarize_transcript", data={"transcript": transcript, "api_key": "bad", "template_id": tid}).json()["data"]
        blob = json.dumps(d["summary"], ensure_ascii=False)
        check(f"{tid}: offline fill has no sample content", "Talukder" not in blob and "28.3%" not in blob and "500,000" not in blob and "কাদের" not in blob)

    print("\n=== 16. Full pipeline /api/transcribe_and_summarize: total STT failure -> error, no fake minutes")
    install(lambda c, m, k, contents: (_ for _ in ()).throw(err(429, "RESOURCE_EXHAUSTED", "quota")))
    with open(recording, "rb") as f:
        body = tc.post("/api/transcribe_and_summarize", files={"file": (os.path.basename(recording), f, "audio/mp4")},
                       data={"api_key": "fake", "template_id": "easd_default_minutes"}).json()
    check("status error", body["status"] == "error", body.get("status"))
    check("no placeholder minutes", "Weekly Strategic, Programmatic and Presentation Review Meeting discussion" not in json.dumps(body))
    check("reason mentions quota", "quota" in (body.get("detail") or "").lower(), body.get("detail"))

    print("\n=== 17. Full pipeline: partial STT -> minutes + warning + gaps")
    def both(c, m, k, contents):
        if any(isinstance(x, str) and "JSON" in x for x in (contents if isinstance(contents, list) else [contents])):
            return text_response(good_json)
        return c3_bad(c, m, k, contents)
    install(both)
    with open(recording, "rb") as f:
        body = tc.post("/api/transcribe_and_summarize", files={"file": (os.path.basename(recording), f, "audio/mp4")},
                       data={"api_key": "fake", "template_id": "easd_default_minutes"}).json()
    d = body.get("data", {})
    check("status success with stt partial", body["status"] == "success" and d.get("stt", {}).get("status") == "partial", body.get("detail"))
    check("warning mentions missing audio", "could not be transcribed" in d.get("warning", ""), d.get("warning"))
    check("transcript contains gap marker", "TRANSCRIPT GAP" in d.get("raw_transcript", ""))

    print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", *FAIL, sep="\n  - ")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    rec = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "Recording", "Meeting minutes 15Sep2026.m4a")
    if not os.path.isfile(rec):
        print(f"Recording not found: {rec}")
        sys.exit(2)
    sys.exit(main(rec))
