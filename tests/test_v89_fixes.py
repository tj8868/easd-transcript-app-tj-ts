"""v8.9 regression tests: translation, speaker labels, timestamps, attendance, summarize status."""
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import numpy as np

import transcript_translator as tt
import speaker_diarization as sd
import stt_pipeline


def _fake_caller(mapping):
    def call(system, user):
        items = json.loads(user)["items"]
        return json.dumps({"items": [mapping.get(i, "EN:" + i) for i in items]}, ensure_ascii=False)
    return call


def test_translate_keeps_prefixes_and_skips_target_lines(monkeypatch):
    monkeypatch.setattr(tt, "_make_caller", lambda *a, **k: (_fake_caller({}), "fake"))
    src = "[00:01] Speaker 1: আজকের মিটিং শুরু\n[00:05] Speaker 2: Already English.\n[01:02:03] Speaker 3: বাজেট ok"
    res = tt.translate_transcript(src, "en", "gemini", "k")
    lines = res["text"].splitlines()
    assert res["status"] == "success"
    assert lines[0] == "[00:01] Speaker 1: EN:আজকের মিটিং শুরু"
    assert lines[1] == "[00:05] Speaker 2: Already English."      # untouched, not sent
    assert lines[2].startswith("[01:02:03] Speaker 3: EN:")


def test_translate_misaligned_batch_falls_back_per_line(monkeypatch):
    calls = {"n": 0}

    def call(system, user):
        calls["n"] += 1
        items = json.loads(user)["items"]
        if len(items) > 1:
            return json.dumps({"items": ["only one"]})
        return json.dumps({"items": ["ok:" + items[0]]})
    monkeypatch.setattr(tt, "_make_caller", lambda *a, **k: (call, "fake"))
    res = tt.translate_transcript("[00:01] Speaker 1: এক\n[00:02] Speaker 1: দুই", "en", "gemini", "k")
    assert res["status"] == "success" and "ok:এক" in res["text"] and "ok:দুই" in res["text"]


def test_translate_bad_target():
    assert tt.translate_transcript("x", "fr")["status"] == "error"


def test_cluster_cannot_link_keeps_chunk_speakers_apart():
    e = np.array([[1, 0, 0], [1, 0.01, 0], [0, 1, 0]], dtype=np.float32)
    # rows 0 and 1 are the same voice but the same chunk said they differ
    labels = sd.cluster_embeddings(e, threshold=0.5, cannot_link=[0, 0, 1])
    assert labels[0] != labels[1]


def test_missing_word_timings_do_not_reset_to_zero():
    class W:
        def __init__(self, s): self.start_offset = s
    class AT:
        def __init__(self, t, w): self.text, self.speaker_label, self.words = t, "spk_1", w
    class P:
        def __init__(self, at): self.audio_transcription, self.text = at, None
    class C:
        def __init__(self, parts): self.content = type("x", (), {"parts": parts})
    resp = type("R", (), {"candidates": [C([P(AT("a", [W("65s")])), P(AT("b", []))])]})
    lines = stt_pipeline._lines_from_transcribe_response(resp)
    assert lines[1].startswith("[01:05]"), lines


def test_attendance_common_surname_alone_is_not_enough():
    from ai_providers import match_attendance_list
    present = [r["name"] for r in match_attendance_list([], "Mr Hossain and Ms Islam joined") if r["participation"] == "Yes"]
    assert present == []


def test_summarize_reports_error_status(monkeypatch):
    from fastapi.testclient import TestClient
    import app as app_module
    monkeypatch.setattr(app_module, "process_ai_request", lambda **kw: {"status": "error", "error": "boom"})
    r = TestClient(app_module.app).post("/api/summarize_transcript", data={"transcript": "[00:00] Speaker 1: hi"})
    assert r.json()["status"] == "error" and r.json()["detail"] == "boom"


def test_cors_rejects_foreign_origin():
    from fastapi.testclient import TestClient
    import app as app_module
    c = TestClient(app_module.app)
    evil = c.get("/api/settings", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in evil.headers}
    ok = c.get("/api/settings", headers={"Origin": "http://localhost:8000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8000"
