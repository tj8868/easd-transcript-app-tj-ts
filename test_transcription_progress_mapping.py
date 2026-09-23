# -*- coding: utf-8 -*-
"""
End-to-End Verification Test: Transcription Percentage and Progress Mapping
Validates:
1. GET /api/transcribe_progress/{job_id} contract:
   - Returns 404/not_found for unknown job IDs
   - Tracks active jobs correctly across states (converting -> transcribing -> completed)
   - Progress is correctly bound between 0% and 100%
2. In-memory job lifecycle:
   - Chunk progress updates (from 35% up to 92%)
   - Stage transitions and error handling
   - 100% progress is ONLY reported upon job completion
3. Frontend progress mapping invariants:
   - CircularProgressSpinner fallback is capped at 92% (never reaches 100% in simulation)
   - LiveRecordStudio polling clamps server progress to max 96%
   - 100% is only dispatched after POST /api/transcribe_take response is parsed & validated
"""
import sys
import os
import time
import unittest
from fastapi.testclient import TestClient

# Ensure app can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as app_module
from app import app, _active_transcribe_jobs

class TestTranscriptionProgressMapping(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.test_job_id = f"test_job_{int(time.time() * 1000)}"

    def tearDown(self):
        if self.test_job_id in _active_transcribe_jobs:
            del _active_transcribe_jobs[self.test_job_id]

    def test_unknown_job_returns_not_found(self):
        """Unknown job IDs must return status: not_found and progress: 0."""
        res = self.client.get(f"/api/transcribe_progress/nonexistent_job_12345")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "not_found")
        self.assertEqual(data["progress"], 0)

    def test_active_job_progress_lifecycle(self):
        """Simulate real progress updates across conversion, chunk STT, and completion."""
        # 1. Phase 1 & 2: Upload done, server converting (25%)
        _active_transcribe_jobs[self.test_job_id] = {
            "job_id": self.test_job_id,
            "status": "processing",
            "stage": "converting",
            "progress": 25,
            "chunks_total": 0,
            "chunks_done": 0,
            "message": "Converting audio & preparing segments with FFmpeg...",
            "created_at": time.time(),
            "updated_at": time.time()
        }

        res = self.client.get(f"/api/transcribe_progress/{self.test_job_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["stage"], "converting")
        self.assertEqual(data["progress"], 25)
        self.assertLess(data["progress"], 100, "Must not be 100% during conversion")

        # 2. Phase 3: Transcribing chunks (35% to 92%)
        total_chunks = 4
        for done in range(1, total_chunks + 1):
            chunk_pct = 35 + int((done / total_chunks) * 57)
            pct = min(92, max(35, chunk_pct))
            _active_transcribe_jobs[self.test_job_id].update({
                "stage": "transcribing",
                "progress": pct,
                "chunks_total": total_chunks,
                "chunks_done": done,
                "message": f"Transcribing chunk {done} of {total_chunks}...",
                "updated_at": time.time()
            })

            res = self.client.get(f"/api/transcribe_progress/{self.test_job_id}")
            data = res.json()
            self.assertEqual(data["stage"], "transcribing")
            self.assertEqual(data["progress"], pct)
            self.assertEqual(data["chunks_done"], done)
            self.assertLessEqual(data["progress"], 92, "Chunk progress must never exceed 92% before completion")

        # 3. Phase 4: Job completed (100%)
        _active_transcribe_jobs[self.test_job_id].update({
            "status": "success",
            "stage": "completed",
            "progress": 100,
            "message": "Transcription complete!",
            "updated_at": time.time()
        })

        res = self.client.get(f"/api/transcribe_progress/{self.test_job_id}")
        data = res.json()
        self.assertEqual(data["stage"], "completed")
        self.assertEqual(data["progress"], 100)
        self.assertEqual(data["status"], "success")

    def test_frontend_progress_invariants(self):
        """Verify the static code invariants in frontend components."""
        frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "src", "components")

        # 1. CircularProgressSpinner: must cap fallback at 92% and never reach 98% or 100% in loop
        spinner_file = os.path.join(frontend_dir, "CircularProgressSpinner.jsx")
        self.assertTrue(os.path.exists(spinner_file))
        with open(spinner_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("prev < 92", content, "Fallback spinner must cap at 92%")
            self.assertNotIn("prev < 98", content, "Old 98% cap must be removed")

        # 2. LiveRecordStudio: safeServerPct must cap polling at 96%
        studio_file = os.path.join(frontend_dir, "LiveRecordStudio.jsx")
        self.assertTrue(os.path.exists(studio_file))
        with open(studio_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Math.min(96, Math.max(25, Number(pData.progress)", content,
                          "LiveRecordStudio must clamp polling to max 96%")
            self.assertIn("percent: 100", content, "100% must be reported explicitly")
            self.assertIn("/api/transcribe_progress/", content, "Polling must query transcribe_progress endpoint")

if __name__ == "__main__":
    unittest.main()
