"""
Transcription Module Application Server
Provides FastAPI endpoints and WebSocket streaming for:
- Live Record transcription
- Batch Upload processing
- Hardware profile & automatic engine selection (Faster-Whisper INT8 vs Whisper-Turbo)
- Single Customizable API Integration
- Speaker Diarization & Timestamps
"""

import os
import sys
import uuid
import json
import asyncio
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from orchestrator import TranscriptionOrchestrator
from config import load_settings, save_settings

app = FastAPI(
    title="Universal Transcription Module",
    description="Dedicated Speech-to-Text engine with Live Record, Batch Processing, Diarization & Custom API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = TranscriptionOrchestrator.get_instance()

# Static Files for Web UI
STATIC_DIR = os.path.join(_BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

class SettingsPayload(BaseModel):
    default_mode: Optional[str] = "auto"
    language: Optional[str] = "auto"
    enable_diarization: Optional[bool] = True
    enable_timestamps: Optional[bool] = True

class CustomApiPayload(BaseModel):
    enabled: bool = False
    name: str = "Custom API"
    provider_type: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""
    model_name: str = "whisper-large-v3-turbo"
    custom_headers: Optional[dict] = {}

@app.get("/api/status")
async def get_system_status():
    return orchestrator.get_system_status()

@app.post("/api/settings")
async def update_settings(payload: SettingsPayload):
    updated = save_settings(payload.model_dump())
    orchestrator.settings = updated
    return {"status": "success", "settings": updated}

# --- Single Custom API Endpoints ---
@app.get("/api/custom_api")
async def get_custom_api():
    return orchestrator.get_custom_api_config()

@app.post("/api/custom_api")
async def save_custom_api(payload: CustomApiPayload):
    saved = orchestrator.update_custom_api_config(payload.model_dump())
    return {"status": "success", "config": saved}

@app.post("/api/custom_api/test")
async def test_custom_api():
    res = orchestrator.test_custom_api()
    return res

# --- Live Recording Endpoints (Record Button) ---
@app.post("/api/live/start")
async def live_start(session_id: Optional[str] = Form(None), language: str = Form("auto")):
    sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
    return orchestrator.start_live_session(sid, language=language)

@app.post("/api/live/chunk")
async def live_chunk(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    is_final: bool = Form(False)
):
    audio_bytes = await file.read()
    res = orchestrator.process_live_chunk(
        session_id=session_id,
        audio_bytes=audio_bytes,
        mime_type=file.content_type or "audio/webm",
        is_final=is_final
    )
    return res

@app.post("/api/live/stop")
async def live_stop(session_id: str = Form(...)):
    return orchestrator.stop_live_session(session_id)

@app.websocket("/ws/live")
async def websocket_live_record(websocket: WebSocket):
    """Low-latency WebSocket streaming for microphone audio chunks."""
    await websocket.accept()
    session_id = f"ws_{uuid.uuid4().hex[:8]}"
    orchestrator.start_live_session(session_id)

    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            event = data.get("type", "")

            if event == "config":
                lang = data.get("language", "auto")
                orchestrator.start_live_session(session_id, language=lang)
                await websocket.send_json({"type": "ready", "session_id": session_id})

            elif event == "audio_chunk":
                import base64
                audio_b64 = data.get("audio_data", "")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    mime = data.get("mime_type", "audio/webm")
                    res = orchestrator.process_live_chunk(
                        session_id=session_id,
                        audio_bytes=audio_bytes,
                        mime_type=mime,
                        is_final=data.get("is_final", False)
                    )
                    if res.get("text"):
                        await websocket.send_json({
                            "type": "transcript",
                            "text": res["text"],
                            "formatted_transcript": res.get("formatted_transcript"),
                            "segments": res.get("segments", [])
                        })

            elif event == "stop":
                summary = orchestrator.stop_live_session(session_id)
                await websocket.send_json({
                    "type": "completed",
                    "summary": summary
                })
                break

    except WebSocketDisconnect:
        orchestrator.stop_live_session(session_id)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

# --- Batch Processing Endpoints (Upload Button) ---
@app.post("/api/batch/upload")
async def batch_upload(
    file: UploadFile = File(...),
    language: str = Form("auto")
):
    """Uploads an audio/video file and queues batch transcription."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    filename = file.filename or "upload_audio.mp3"
    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".mp3"

    temp_dir = os.path.join(_BASE_DIR, "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, f"{job_id}{ext}")

    content = await file.read()
    with open(temp_file, "wb") as f:
        f.write(content)

    # Launch processing in background thread
    def run_worker():
        try:
            orchestrator.process_batch_upload(job_id, temp_file, filename, language=language)
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    asyncio.create_task(asyncio.to_thread(run_worker))

    return {
        "status": "queued",
        "job_id": job_id,
        "filename": filename,
        "message": f"File '{filename}' queued for batch transcription."
    }

@app.get("/api/batch/status/{job_id}")
async def batch_status(job_id: str):
    return orchestrator.get_batch_job_status(job_id)

# Mount static files
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    cfg = load_settings()
    host = cfg.get("server_host", "127.0.0.1")
    port = int(cfg.get("server_port", 8085))
    print(f"Starting Universal Transcription Module at http://{host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=False)
