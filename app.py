import sys
import os
import subprocess
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Automatic Virtual Environment Hand-off:
# If app.py is clicked or executed directly using system Python rather than .venv,
# automatically re-execute inside the project's dedicated virtual environment (.venv)
venv_py = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
venv_pyw = os.path.join(BASE_DIR, ".venv", "Scripts", "pythonw.exe")

current_exe = os.path.abspath(sys.executable).lower()
is_in_venv = False
for vp in [venv_py, venv_pyw]:
    if os.path.isfile(vp) and current_exe == os.path.abspath(vp).lower():
        is_in_venv = True
        break

if not is_in_venv:
    has_console = sys.stdout is not None and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    if has_console and os.path.isfile(venv_py):
        cmd = [venv_py, os.path.abspath(__file__)] + sys.argv[1:]
        try:
            sys.exit(subprocess.call(cmd, cwd=BASE_DIR))
        except Exception:
            pass
    target_py = venv_pyw if os.path.isfile(venv_pyw) else (venv_py if os.path.isfile(venv_py) else None)
    if target_py:
        cmd = [target_py, os.path.abspath(__file__)] + sys.argv[1:]
        subprocess.Popen(cmd, cwd=BASE_DIR)
        sys.exit(0)

# Ensure sys.stdout and sys.stderr are valid streams under pythonw (GUI mode)
# When pythonw runs without a console, sys.stdout and sys.stderr are None, which causes uvicorn logging to crash on isatty()
if sys.stdout is None:
    try:
        sys.stdout = open(os.path.join(BASE_DIR, "app_service.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

if sys.stderr is None:
    try:
        sys.stderr = open(os.path.join(BASE_DIR, "app_service.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import json
import base64
import uuid
import re
import time
import asyncio
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from document_engine import generate_meeting_minutes_docx_bytes, DEFAULT_MEMBERS
from template_engine import (
    load_saved_templates,
    get_template_by_id,
    get_document_types,
    analyze_and_generalize_docx,
    save_custom_template,
    delete_custom_template,
    generate_custom_template_docx_bytes,
    get_template_json_schema,
    get_template_json_example
)
from skills_engine import (
    load_saved_skills,
    save_custom_skill,
    delete_custom_skill
)
from ai_providers import (
    process_ai_request,
    verify_ai_api_key,
    get_default_api_key_from_disk,
    live_transcribe_audio_chunk,
    detect_text_language,
    load_api_settings_from_disk,
    save_api_settings_to_disk,
    test_transcription_engine,
    test_summarization_engine
)
from gdrive_service import upload_docx_to_gdrive
from media_processor import process_uploaded_media
from ocr_engine import (
    preprocess_image_for_ocr,
    extract_pdf_content,
    optimize_ocr_text,
    perform_local_ocr,
    perform_ai_vision_ocr,
    is_tesseract_available
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "EASD Meeting minutes - Template.docx")
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
STATIC_LEGACY = os.path.join(BASE_DIR, "static")

MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1024 MB (1 GB) for high-resolution HEVC/H.265 videos


def _save_upload_limited(uploaded: "UploadFile", suffix: str) -> str:
    """Stream an upload to a temp file, aborting as soon as it exceeds MAX_UPLOAD_SIZE (1 GB)."""
    written = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        while True:
            block = uploaded.file.read(1024 * 1024)
            if not block:
                break
            written += len(block)
            if written > MAX_UPLOAD_SIZE:
                tmp.close()
                os.remove(tmp.name)
                raise HTTPException(status_code=413, detail=(
                    f"File {os.path.basename(uploaded.filename or '')} is larger than the 1 GB limit."))
            tmp.write(block)
    finally:
        if not tmp.closed:
            tmp.close()
    return tmp.name


app = FastAPI(
    title="EASD Meeting Minutes AI Security Hub",
    description="High-Speed & Secure Cross-Platform Meeting Assistant",
    version="2.0.0"
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Check if request is actually over HTTPS
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    if is_https:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data: https: ws: wss:; "
            "upgrade-insecure-requests; object-src 'none'; "
            "frame-ancestors 'self' https://*.github.dev https://*.app.github.dev;"
        )
    else:
        # On clean HTTP / localhost / 127.0.0.1, explicitly reset cached HSTS and allow HTTP
        # to prevent browsers from forcing HTTPS on port 8000 (which triggers ERR_SSL_PROTOCOL_ERROR / Network Error)
        response.headers["Strict-Transport-Security"] = "max-age=0"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data: http: https: ws: wss:; "
            "object-src 'none'; "
            "frame-ancestors 'self' https://*.github.dev https://*.app.github.dev;"
        )
    
    # Ensure index.html and root page never get cached stale by browsers/PWA
    req_path = request.url.path or ""
    if req_path in ["", "/", "/index.html"] or req_path.endswith((".html", ".json")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def app_startup_warmup():
    try:
        import local_whisper_engine
        local_whisper_engine.warm_up_local_whisper_in_background()
    except Exception as e:
        print(f"[Whisper Startup Event] {e}")

class DiscussionItem(BaseModel):
    sn: Optional[str] = "1"
    topic: Optional[str] = "Discussion Point"
    details: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class AttendanceItem(BaseModel):
    serial: Optional[str] = "1"
    name: Optional[str] = "Member"
    participation: Optional[str] = "Yes"
    model_config = ConfigDict(extra="ignore")

class MeetingDocPayload(BaseModel):
    title: Optional[str] = "Weekly Strategic, Programmatic and Presentation Review Meeting"
    location: Optional[str] = "Eminence, Mohakhali, DOHS"
    date: Optional[str] = "29 August, 2026"
    time: Optional[str] = "11:00 AM - 01:00 PM"
    agendas: Optional[List[str]] = []
    discussions: Optional[List[DiscussionItem]] = []
    decisions: Optional[str] = ""
    attendance: Optional[List[AttendanceItem]] = []
    transcript: Optional[str] = ""
    bangla_transcript: Optional[str] = ""
    english_transcript: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class CustomDocxPayload(BaseModel):
    template_id: Optional[str] = "easd_default_minutes"
    doc_data: Dict[str, Any]
    model_config = ConfigDict(extra="ignore")

class GDriveUploadPayload(BaseModel):
    doc_data: MeetingDocPayload
    access_token: str = Field(..., min_length=10, max_length=2048)
    folder_name: Optional[str] = "EASD - meeting minutes"

class VerifyKeyPayload(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class ApiSettingsPayload(BaseModel):
    transcription_provider: Optional[str] = "gemini"
    transcription_model: Optional[str] = "gemini-3.5-transcribe"
    summarization_provider: Optional[str] = "gemini"
    summarization_model: Optional[str] = "gemini-3.8-flash"
    gemini_api_key: Optional[str] = ""
    local_whisper_model: Optional[str] = "auto"
    gemini_live_model: Optional[str] = "models/gemini-3.5-transcribe-live"
    # v8.5: OpenAI-compatible custom endpoint (OpenRouter / DeepSeek / Ollama / LM Studio)
    custom_api_base_url: Optional[str] = ""
    custom_api_key: Optional[str] = ""
    custom_api_model: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class TestEnginePayload(BaseModel):
    test_type: str = "both"  # "stt", "llm", or "both"
    stt_provider: Optional[str] = "gemini"
    stt_api_key: Optional[str] = None
    stt_model: Optional[str] = "gemini-3.5-transcribe"
    llm_provider: Optional[str] = "gemini"
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = "gemini-3.8-flash"
    base_url: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class DeleteTemplatePayload(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=128)
    model_config = ConfigDict(extra="ignore")

class SaveTemplatePayload(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    doc_type: Optional[str] = "custom"
    description: Optional[str] = ""
    category: Optional[str] = "Custom Templates"
    docx_filename: Optional[str] = ""
    context: Optional[str] = ""
    rules: Optional[str] = ""
    requirements: Optional[str] = ""
    fields: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    sections: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tables: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    ai_system_prompt: Optional[str] = ""
    save_as_new: Optional[bool] = False
    model_config = ConfigDict(extra="ignore")

@app.get("/api/default_config")
def get_default_config():
    """Returns preconfigured default key/provider from disk if present."""
    cfg = get_default_api_key_from_disk()
    return JSONResponse(content=cfg)

@app.post("/api/default_config")
def post_default_config():
    """Secure POST variant for retrieving default config."""
    cfg = get_default_api_key_from_disk()
    return JSONResponse(content=cfg)

@app.get("/api/settings")
def get_settings_endpoint():
    """Returns persistent AI configuration and model routing settings from disk."""
    settings = load_api_settings_from_disk()
    return JSONResponse(content={"status": "success", "settings": settings})

@app.post("/api/settings")
def save_settings_endpoint(payload: ApiSettingsPayload):
    """Saves persistent AI configuration, model choices, and API keys to disk."""
    try:
        # exclude_unset: saving one section must not reset the others (e.g. wipe the Gemini key)
        updated = save_api_settings_to_disk(payload.model_dump(exclude_unset=True))
        return JSONResponse(content={"status": "success", "settings": updated, "message": "API settings saved successfully."})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/test_engine")
def test_engine_endpoint(payload: TestEnginePayload):
    """
    Actively tests STT transcription and/or LLM summarization endpoints.
    Returns live latency (ms), HTTP status, and diagnostic health report.
    """
    from diag_logging import bind_job_id
    cfg = load_api_settings_from_disk()
    results: Dict[str, Any] = {"status": "success", "log_id": bind_job_id()}

    # Test STT Transcription Engine if requested
    if payload.test_type in ["stt", "both"]:
        stt_prov = payload.stt_provider or cfg.get("transcription_provider") or "gemini"
        stt_key = payload.stt_api_key or cfg.get("gemini_api_key") or ""
        stt_mod = payload.stt_model or cfg.get("transcription_model") or "gemini-3.5-transcribe"

        stt_res = test_transcription_engine(
            provider=stt_prov,
            api_key=stt_key,
            model_name=stt_mod
        )
        results["stt"] = stt_res
        if not stt_res.get("success"):
            results["status"] = "partial" if payload.test_type == "both" else "error"

    # Test LLM Summarization Engine if requested
    if payload.test_type in ["llm", "both"]:
        llm_prov = payload.llm_provider or cfg.get("summarization_provider") or "gemini"
        if llm_prov.lower() in ("openai_compatible", "custom", "openai", "openrouter"):
            llm_key = payload.llm_api_key or cfg.get("custom_api_key") or ""
            llm_mod = payload.llm_model or cfg.get("custom_api_model") or ""
        else:
            llm_key = payload.llm_api_key or cfg.get("gemini_api_key") or ""
            llm_mod = payload.llm_model or cfg.get("summarization_model") or "gemini-3.8-flash"

        llm_res = test_summarization_engine(
            provider=llm_prov,
            api_key=llm_key,
            model_name=llm_mod,
            base_url=payload.base_url or ""
        )
        results["llm"] = llm_res
        if not llm_res.get("success"):
            results["status"] = "partial" if (payload.test_type == "both" and results.get("stt", {}).get("success")) else "error"

    return JSONResponse(content=results)

@app.get("/api/env_keys")
@app.post("/api/env_keys")
def get_env_keys_endpoint():
    """Reports detected AI API environment variables safely."""
    gemini_env = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gemini_file = False
    gem_path = os.path.join(base_dir, "GeminiAPI.txt")
    if os.path.exists(gem_path):
        try:
            with open(gem_path, "r", encoding="utf-8") as f:
                for line in f:
                    c = line.split("#")[0].strip()
                    if c and (c.startswith("AIzaSy") or c.startswith("AQ.")):
                        gemini_file = True
                        break
        except Exception:
            pass

    return JSONResponse(content={
        "status": "success",
        "env_keys": {
            "GEMINI_API_KEY": {
                "configured": bool(gemini_env or gemini_file),
                "preview": "Set in GeminiAPI.txt / ENV" if (gemini_env or gemini_file) else "Not configured"
            }
        }
    })

@app.get("/api/document_types")
def get_document_types_endpoint():
    """Returns all registered document types."""
    return JSONResponse(content={"status": "success", "document_types": get_document_types()})

@app.post("/api/document_types")
def post_document_types_endpoint():
    """Secure POST endpoint returning all registered document types."""
    return JSONResponse(content={"status": "success", "document_types": get_document_types()})

@app.get("/api/template_members")
def get_template_members():
    return {"members": DEFAULT_MEMBERS}

@app.post("/api/template_members")
def post_template_members():
    return {"members": DEFAULT_MEMBERS}

@app.get("/api/templates")
def get_templates():
    """Returns all available document templates (built-in and custom generated)."""
    templates = load_saved_templates()
    return JSONResponse(content={"status": "success", "templates": templates})

@app.post("/api/templates")
def post_templates():
    """Secure POST endpoint returning all available document templates."""
    templates = load_saved_templates()
    return JSONResponse(content={"status": "success", "templates": templates})

@app.get("/api/template_schema")
@app.post("/api/template_schema")
def get_template_schema_endpoint(template_id: Optional[str] = None):
    """Returns the official JSON schema and illustrative example payload for a specified template."""
    target_tpl = get_template_by_id(template_id) if template_id else None
    if not target_tpl:
        all_tpls = load_saved_templates()
        target_tpl = all_tpls[0] if all_tpls else None
        
    if not target_tpl:
        raise HTTPException(status_code=404, detail="Template not found")
        
    schema = get_template_json_schema(target_tpl)
    example = get_template_json_example(target_tpl)
    return JSONResponse(content={
        "status": "success",
        "template_id": target_tpl.get("id"),
        "name": target_tpl.get("name"),
        "doc_type": target_tpl.get("doc_type"),
        "json_schema": schema,
        "json_example": example
    })

@app.post("/api/generalize_template")
async def generalize_template_endpoint(
    file: UploadFile = File(...),
    doc_type: str = Form("custom")
):
    """Uploads any .docx document file and generalizes it into an AI template schema."""
    try:
        clean_fn = os.path.basename(file.filename or "uploaded_template.docx")
        clean_fn = re.sub(r'[^a-zA-Z0-9_\-\. ]', '_', clean_fn)
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Template file exceeds 50MB limit.")
            
        tpl = analyze_and_generalize_docx(content, clean_fn, doc_type=doc_type)
        return JSONResponse(content={"status": "success", "template": tpl})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to generalize template: {str(e)}")

@app.post("/api/save_template")
async def save_template_endpoint(payload: SaveTemplatePayload):
    """Saves or updates a custom template schema with strict validation."""
    try:
        data = payload.model_dump()
        save_as_new = data.pop("save_as_new", False)
        saved = save_custom_template(data, save_as_new=save_as_new)
        return JSONResponse(content={"status": "success", "template": saved})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/delete_template")
def delete_template_endpoint(payload: DeleteTemplatePayload):
    """Secure POST endpoint to delete a custom template schema."""
    ok = delete_custom_template(payload.template_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot delete default or non-existent template.")
    return JSONResponse(content={"status": "success", "message": "Template deleted."})

class SaveSkillPayload(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = "Custom"
    description: Optional[str] = ""
    prompt: str = Field(..., min_length=1)
    is_builtin: Optional[bool] = False
    model_config = ConfigDict(extra="ignore")

class DeleteSkillPayload(BaseModel):
    skill_id: str = Field(..., min_length=1, max_length=128)
    model_config = ConfigDict(extra="ignore")

@app.get("/api/skills")
def get_skills():
    """Returns all available skills (presets + saved custom skills)."""
    skills = load_saved_skills()
    return JSONResponse(content={"status": "success", "skills": skills})

@app.post("/api/skills")
def post_skills():
    """Secure POST endpoint returning all available skills from persistent storage."""
    skills = load_saved_skills()
    return JSONResponse(content={"status": "success", "skills": skills})

@app.post("/api/save_skill")
def save_skill_endpoint(payload: SaveSkillPayload):
    """Saves or updates a custom AI skill to persistent disk storage."""
    try:
        saved = save_custom_skill(payload.model_dump())
        return JSONResponse(content={"status": "success", "skill": saved})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/delete_skill")
def delete_skill_endpoint(payload: DeleteSkillPayload):
    """Deletes a custom AI skill from persistent disk storage."""
    ok = delete_custom_skill(payload.skill_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot delete built-in or non-existent skill.")
    return JSONResponse(content={"status": "success", "message": "Skill deleted."})

@app.post("/api/verify_key")
@app.post("/api/verify_api_key")
def verify_key_endpoint(payload: VerifyKeyPayload):
    """Verifies whether an API key or custom endpoint is active and valid."""
    from diag_logging import bind_job_id
    log_id = bind_job_id()
    res = verify_ai_api_key(payload.provider, payload.api_key or "", payload.base_url or "")
    is_valid = bool(res.get("valid", False) or res.get("success", False))
    return JSONResponse(content={
        "status": "success" if is_valid else "error",
        "valid": is_valid,
        "success": is_valid,
        "message": res.get("message", "Key verified.") if is_valid else res.get("message", "Verification failed."),
        "latency_ms": res.get("latency_ms"),
        "log_id": log_id
    })

@app.post("/api/transcribe_and_summarize")
async def transcribe_and_summarize(
    provider: str = Form("gemini"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model_name: str = Form(""),
    transcription_provider: Optional[str] = Form(None),
    transcription_api_key: Optional[str] = Form(None),
    transcription_model: Optional[str] = Form(None),
    summarization_provider: Optional[str] = Form(None),
    summarization_api_key: Optional[str] = Form(None),
    summarization_model: Optional[str] = Form(None),
    org_context: str = Form(""),
    custom_skills: str = Form(""),
    template_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    text_content: str = Form("")
):
    """Full pipeline: ingest -> 16 kHz mono -> STT -> template JSON. Never returns fabricated content."""
    from diag_logging import get_logger, bind_job_id
    _log = get_logger("api.transcribe_and_summarize")
    job = bind_job_id()  # correlation id: every log line of this request carries [job=<id>]
    t0 = time.time()
    temp_files_to_cleanup: List[str] = []
    template_schema = None
    try:
        media_bytes = None
        mime_type = "audio/mp3"
        audio_segments: List[Dict[str, Any]] = []
        detected_formats: List[str] = []
        ingest_errors: List[str] = []

        upload_list: List[UploadFile] = []
        if file and file.filename:
            upload_list.append(file)
        for f in (files or []):
            if f and f.filename:
                upload_list.append(f)

        for uploaded in upload_list:
            clean_filename = os.path.basename(uploaded.filename or "upload_audio.mp3")
            _, ext = os.path.splitext(clean_filename.lower())
            tmp_path = _save_upload_limited(uploaded, ext or ".mp4")
            temp_files_to_cleanup.append(tmp_path)
            _log.info("[job %s] ingest %r (%.2f MB)", job, clean_filename, os.path.getsize(tmp_path) / 1048576)

            proc_res = await asyncio.to_thread(
                process_uploaded_media, media_bytes=None, filename=clean_filename,
                content_type=uploaded.content_type or "", file_path=tmp_path
            )
            fmt = proc_res.get("format_detected", "")
            if fmt and fmt not in detected_formats:
                detected_formats.append(fmt)
            ptype = proc_res.get("type")
            if ptype == "error":
                ingest_errors.append(f"{clean_filename}: {proc_res.get('error')}")
            elif ptype == "text":
                extracted = proc_res.get("text", "")
                text_content = f"{text_content}\n\n{extracted}".strip() if text_content else extracted
            elif ptype in ["image_ocr", "pdf_ocr"]:
                media_bytes = proc_res.get("media_bytes")
                mime_type = proc_res.get("mime_type", "image/jpeg")
                if proc_res.get("text"):
                    extracted = proc_res.get("text")
                    text_content = f"{text_content}\n\n{extracted}".strip() if text_content else extracted
            else:
                chunks = proc_res.get("audio_chunks") or ([proc_res["audio_bytes"]] if proc_res.get("audio_bytes") else [])
                if chunks:
                    audio_segments.append({"name": clean_filename, "chunks": chunks,
                                           "durations": proc_res.get("chunk_durations"),
                                           "mime_type": proc_res.get("mime_type", "audio/mp3")})

        if ingest_errors and not audio_segments and not text_content.strip() and not media_bytes:
            return JSONResponse(content={"status": "error", "detail": " | ".join(ingest_errors), "errors": ingest_errors})

        template_schema = get_template_by_id(template_id) if template_id else None
        result = await asyncio.to_thread(
            process_ai_request,
            provider=provider, api_key=api_key, base_url=base_url, model_name=model_name,
            transcription_provider=transcription_provider or "",
            transcription_api_key=transcription_api_key or "",
            transcription_model=transcription_model or model_name,
            summarization_provider=summarization_provider or "",
            summarization_api_key=summarization_api_key or "",
            summarization_model=summarization_model or model_name,
            media_bytes=media_bytes if (media_bytes and mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf")) else None,
            mime_type=mime_type, text_content=text_content, org_context=org_context,
            custom_skills=custom_skills, template_schema=template_schema,
            audio_segments=audio_segments or None
        )
        if isinstance(result, dict):
            if detected_formats:
                result["detected_format"] = ", ".join(detected_formats)
            if ingest_errors:
                result["warning"] = ("; ".join(ingest_errors) + (". " + result["warning"] if result.get("warning") else ""))
            if result.get("status") == "error":
                _log.error("[job %s] FAILED after %.1fs: %s", job, time.time() - t0, result.get("error"))
                result["log_id"] = job
                return JSONResponse(content={"status": "error", "detail": result.get("error"), "data": result,
                                             "log_id": job})
        _log.info("[job %s] done in %.1fs source=%s stt=%s", job, time.time() - t0,
                  result.get("summary_source"), (result.get("stt") or {}).get("status"))
        result["log_id"] = job
        return JSONResponse(content={"status": "success", "data": result, "log_id": job})

    except HTTPException:
        raise
    except Exception as e:
        _log.exception("[job %s] unhandled error after %.1fs: %s", job, time.time() - t0, e)
        return JSONResponse(status_code=500, content={
            "status": "error", "log_id": job,
            "detail": f"Processing failed because of an unexpected server error (reference {job})."})
    finally:
        for tf in temp_files_to_cleanup:
            if tf and os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception:
                    pass

@app.post("/api/summarize_transcript")
async def summarize_transcript_endpoint(
    transcript: str = Form(...),
    provider: str = Form("gemini"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model_name: str = Form(""),
    summarization_provider: Optional[str] = Form(None),
    summarization_api_key: Optional[str] = Form(None),
    summarization_model: Optional[str] = Form(None),
    org_context: str = Form(""),
    custom_skills: str = Form(""),
    template_id: Optional[str] = Form(None)
):
    """Summarizes raw or edited transcript into structured template fields using specified model."""
    from diag_logging import get_logger, bind_job_id, redact_key
    _slog = get_logger("api.summarize_transcript")
    job = bind_job_id()  # correlation id on every log line; returned as "log_id"
    t0 = time.time()
    template_schema = None
    if not (transcript or "").strip():
        return JSONResponse(content={"status": "error", "log_id": job,
                                     "detail": "The transcript is empty - transcribe or paste text first."})
    _slog.info("REQUEST provider=%s summarization_provider=%s model=%s base_url=%s key=%s template=%s transcript_chars=%d",
               provider, summarization_provider, summarization_model or model_name, base_url or "-",
               redact_key(summarization_api_key or api_key), template_id, len(transcript))
    try:
        template_schema = get_template_by_id(template_id) if template_id else None
        res = await asyncio.to_thread(
            process_ai_request,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model_name=summarization_model or model_name,
            summarization_provider=summarization_provider or provider,
            summarization_api_key=summarization_api_key or api_key,
            summarization_model=summarization_model or model_name,
            text_content=transcript,
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )
        res["log_id"] = job
        _slog.info("DONE in %.1fs source=%s model=%s warning=%s", time.time() - t0, res.get("summary_source"),
                   res.get("model"), bool(res.get("warning")))
        return JSONResponse(content={"status": "success", "data": res, "log_id": job})
    except Exception as e:
        _slog.exception("summarize_transcript failed after %.1fs: %s", time.time() - t0, e)
        try:
            fallback = deep_semantic_synthesis(transcript, custom_skills, org_context, template_schema)
            fallback["warning"] = (f"The AI model could not fill the template because of an unexpected error. Fields "
                                   f"were filled offline only with text found in the transcript - please review before "
                                   f"exporting. (reference {job})")
            fallback["log_id"] = job
            return JSONResponse(content={"status": "success", "data": fallback, "log_id": job})
        except Exception:
            _slog.exception("offline fallback also failed")
            return JSONResponse(status_code=500, content={
                "status": "error", "log_id": job,
                "detail": f"Could not fill the template because of an unexpected server error (reference {job})."})

@app.post("/api/ocr_extract_and_optimize")
async def ocr_extract_and_optimize_endpoint(
    provider: str = Form("gemini"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model_name: str = Form(""),
    template_id: Optional[str] = Form(None),
    org_context: str = Form(""),
    custom_skills: str = Form(""),
    file: Optional[UploadFile] = File(None),
    base64_image: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None)
):
    """
    Dedicated OCR, Information Extraction & Optimization Pipeline:
    1. Ingests scanned document, photo, whiteboard snapshot, or clipboard base64.
    2. Executes image preprocessing, AI vision OCR or local Tesseract OCR.
    3. Cleans, normalizes, and repairs OCR anomalies.
    4. Extracts structured data matching target template schema.
    5. Returns both cleaned verbatim OCR text and structured report data ready for DOCX generation.
    """
    try:
        image_bytes = None
        mime_type = "image/jpeg"
        detected_text = raw_text or ""

        if file and file.filename:
            content = await file.read()
            clean_filename = os.path.basename(file.filename)
            proc_res = process_uploaded_media(
                media_bytes=content,
                filename=clean_filename,
                content_type=file.content_type or ""
            )
            if proc_res.get("type") in ["image_ocr", "pdf_ocr"]:
                image_bytes = proc_res.get("media_bytes")
                mime_type = proc_res.get("mime_type", "image/jpeg")
                if proc_res.get("text"):
                    detected_text = proc_res.get("text")
            elif proc_res.get("type") == "text":
                detected_text = proc_res.get("text", "")
        elif base64_image:
            if "," in base64_image:
                header, data_str = base64_image.split(",", 1)
                if "image/png" in header:
                    mime_type = "image/png"
                elif "image/webp" in header:
                    mime_type = "image/webp"
                elif "application/pdf" in header:
                    mime_type = "application/pdf"
            else:
                data_str = base64_image
            raw_b = base64.b64decode(data_str)
            image_bytes, mime_type = preprocess_image_for_ocr(raw_b)

        if not image_bytes and not detected_text:
            raise HTTPException(status_code=400, detail="No document, image, or text provided for OCR.")

        if detected_text:
            detected_text = optimize_ocr_text(detected_text)

        template_schema = get_template_by_id(template_id) if template_id else None
        
        result = await asyncio.to_thread(
            process_ai_request,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            transcription_model=model_name,
            summarization_model=model_name,
            media_bytes=image_bytes,
            mime_type=mime_type,
            text_content=detected_text,
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )

        return JSONResponse(content={
            "status": "success",
            "ocr_text": detected_text or result.get("bangla_transcript", "") or result.get("english_transcript", ""),
            "data": result
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/system_audit")
async def system_audit_endpoint():
    """Returns the daily operational, security, setup, and app-building audit report."""
    cfg = load_api_settings_from_disk()
    report = {
        "status": "HEALTHY",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "transcription_provider": cfg.get("transcription_provider"),
        "transcription_model": cfg.get("transcription_model"),
        "summarization_provider": cfg.get("summarization_provider"),
        "summarization_model": cfg.get("summarization_model"),
        "official_template": "EASD Meeting minutes - Template.docx",
        "template_status": "Loaded and verified" if os.path.exists(TEMPLATE_PATH) else "Missing",
        "security_context": "W3C Secure Context compliant (Localhost / HTTPS ready)"
    }
    # Developer diagnostics (not shown in the UI): which Whisper model would run and on what device
    try:
        import local_whisper_engine
        requested = cfg.get("local_whisper_model") or "auto"
        chosen, source = local_whisper_engine.resolve_whisper_model_choice(requested)
        engine = local_whisper_engine.get_engine_status()
        report["local_whisper"] = {
            "requested_model": requested,
            "resolved_model": chosen,
            "resolution": source,
            "resolved_path": local_whisper_engine.get_model_path(chosen),
            "weights_present": local_whisper_engine._model_has_weights(local_whisper_engine.get_model_path(chosen)),
            "status": engine.get("status"),
            "loaded": engine.get("is_loaded"),
            "device": engine.get("device"),
            "cuda_devices": engine.get("cuda_devices"),
            "threads": engine.get("threads"),
            "load_error": engine.get("error"),
            "vad_parameters": local_whisper_engine.WHISPER_VAD_PARAMETERS,
            "ram": local_whisper_engine.get_system_ram_specs(),
        }
    except Exception as e:
        report["local_whisper"] = {"status": "unavailable", "error": f"{type(e).__name__}: {e}"}
    # v8.5: OpenAI-compatible custom endpoint reachability (GET {base_url}/models, 5s timeout)
    if cfg.get("custom_api_base_url"):
        from ai_providers import ping_openai_compatible
        ping = ping_openai_compatible(timeout=5.0)
        report["custom_api"] = {
            "base_url": cfg.get("custom_api_base_url"),
            "model": cfg.get("custom_api_model"),
            "key_present": bool(cfg.get("custom_api_key")),
            "active_for_summarization": cfg.get("summarization_provider") == "openai_compatible",
            "reachable": ping.get("success"),
            "status_code": ping.get("status_code"),
            "model_listed": ping.get("model_listed"),
            "latency_ms": ping.get("latency_ms"),
            "message": ping.get("message"),
        }
    else:
        report["custom_api"] = {"configured": False}
    report["log_file"] = __import__("diag_logging").LOG_FILE_PATH
    return JSONResponse(content={"status": "success", "report": report})

@app.websocket("/ws/live_transcribe")
async def websocket_live_transcribe(websocket: WebSocket):
    """Real-time streaming WebSocket endpoint for microphone transcription."""
    await websocket.accept()
    session_config = {
        "api_key": "",
        "provider": "gemini",
        "language": "auto",
        "model_name": "gemini-3.5-transcribe-live"
    }
    
    try:
        while True:
            raw_msg = await websocket.receive_text()
            data = json.loads(raw_msg)
            event_type = data.get("type", "")
            
            if event_type == "config":
                session_config["api_key"] = data.get("api_key", "").strip()
                session_config["provider"] = data.get("provider", "gemini").strip()
                session_config["language"] = data.get("language", "auto").strip()
                session_config["model_name"] = data.get("model_name", "gemini-3.5-transcribe-live").strip()
                
                if not session_config["api_key"]:
                    disk_cfg = get_default_api_key_from_disk()
                    session_config["api_key"] = disk_cfg.get("api_key", "")
                    
                await websocket.send_json({
                    "type": "status",
                    "status": "ready",
                    "message": "Live transcription session active and ready."
                })
                
            elif event_type == "audio_chunk":
                audio_b64 = data.get("audio_data", "")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    mime = data.get("mime_type", "audio/webm")
                    
                    res = live_transcribe_audio_chunk(
                        media_bytes=audio_bytes,
                        api_key=session_config["api_key"],
                        provider=session_config["provider"],
                        model_name=session_config["model_name"],
                        mime_type=mime,
                        language=session_config["language"]
                    )
                    
                    if res.get("text"):
                        await websocket.send_json({
                            "type": "transcript",
                            "text": res["text"],
                            "language": res.get("language", "bn"),
                            "is_final": data.get("is_final", False)
                        })
                        
            elif event_type == "stop":
                await websocket.send_json({
                    "type": "status",
                    "status": "stopped",
                    "message": "Live transcription session ended."
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

@app.post("/api/live_transcribe_chunk")
async def live_transcribe_chunk_endpoint(
    chunk: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    provider: str = Form("gemini"),
    api_key: str = Form(""),
    model_name: str = Form("gemini-3.5-transcribe-live"),
    language: str = Form("auto")
):
    """
    HTTP streaming endpoint for live audio slices during recording.
    Transcribes the audio slice in real-time and returns text with language.
    """
    from diag_logging import get_logger, bind_job_id
    log_id = bind_job_id()
    try:
        uploaded = chunk or file
        if not uploaded:
            raise HTTPException(status_code=400, detail="No audio chunk provided")
        content = await uploaded.read()
        if len(content) < 32:
            return JSONResponse(content={"status": "success", "text": "", "language": "auto"})
            
        mime = uploaded.content_type or "audio/webm"
        cfg = load_api_settings_from_disk()
        chosen_prov = (provider or cfg.get("transcription_provider") or "gemini").lower()
        
        # Clean API key resolution
        clean_key = api_key.strip() if api_key else ""
        if chosen_prov == "gemini":
            if not clean_key or clean_key.startswith(("hf_", "gsk_")):
                clean_key = cfg.get("gemini_api_key") or cfg.get("transcription_api_key") or get_default_api_key_from_disk().get("api_key", "")
                if clean_key.startswith(("hf_", "gsk_")):
                    clean_key = get_default_api_key_from_disk().get("api_key", "")

        res = live_transcribe_audio_chunk(
            media_bytes=content,
            api_key=clean_key,
            provider=chosen_prov,
            model_name=model_name or "gemini-3.5-transcribe-live",
            mime_type=mime,
            language=language or "auto"
        )
        import local_whisper_engine
        cleaned_chunk = local_whisper_engine.sanitize_whisper_text(res.get("text", ""))
        return JSONResponse(content={"status": "success", "text": cleaned_chunk, "language": res.get("language", "auto"),
                                     "log_id": log_id})
    except Exception as e:
        get_logger("api.live_transcribe_chunk").error("live chunk failed: %s", e, exc_info=True)
        return JSONResponse(content={"status": "error", "text": "", "log_id": log_id,
                                     "detail": f"Live transcription of this slice failed (reference {log_id})."},
                            status_code=200)

@app.post("/api/detect_language")
async def detect_language_endpoint(
    chunk: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Sub-second acoustic language detection between Bengali ('bn') and English ('en').
    Evaluates audio slice and returns detected language with confidence.
    """
    try:
        uploaded = chunk or file
        if not uploaded:
            return JSONResponse(content={"status": "error", "language": "auto", "confidence": 0.0})
        content = await uploaded.read()
        if len(content) < 32:
            return JSONResponse(content={"status": "success", "language": "bn", "confidence": 0.5})

        import local_whisper_engine
        opt_m, _src = local_whisper_engine.resolve_whisper_model_choice(
            load_api_settings_from_disk().get("local_whisper_model"))
        model = local_whisper_engine.get_local_whisper_model(opt_m)
        temp_wav = local_whisper_engine.convert_to_wav_pcm16k(content, input_hint="webm")
        try:
            lang, conf = local_whisper_engine.detect_bilingual_audio_language(model, temp_wav)
            return JSONResponse(content={"status": "success", "language": lang, "confidence": conf})
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass
    except Exception as e:
        from diag_logging import get_logger, current_job_id
        get_logger("api.detect_language").error("detect_language failed: %s", e, exc_info=True)
        return JSONResponse(content={"status": "error", "language": "auto", "confidence": 0.0,
                                     "detail": "Language detection is unavailable right now.",
                                     "job_id": current_job_id()})

_active_transcribe_jobs: Dict[str, Dict[str, Any]] = {}

@app.get("/api/transcribe_progress/{job_id}")
async def get_transcribe_progress_endpoint(job_id: str):
    job = _active_transcribe_jobs.get(job_id)
    if not job:
        return JSONResponse(content={"status": "not_found", "progress": 0, "message": ""})
    return JSONResponse(content=job)

@app.post("/api/transcribe_take")
async def transcribe_take_endpoint(
    file: UploadFile = File(...),
    provider: str = Form("gemini"),
    api_key: str = Form(""),
    model_name: str = Form("gemini-3.5-transcribe"),
    language: str = Form("auto"),
    job_id: Optional[str] = Form(None)
):
    """
    Transcribe one recorded take or uploaded media file (up to 1 GB).
    Pipeline: stream to disk -> FFmpeg 16 kHz mono MP3 -> 10-min chunks -> STT per chunk.

    Response (always JSON):
      status      "success" | "partial" | "error"
      transcript  combined text; failed ranges appear as '[MM:SS] ⚠ TRANSCRIPT GAP ...' lines
      message     one-line human summary
      errors      ["Chunk 3 of 5 (20:00-30:00) failed: <reason>", ...]
      missing_ranges, chunks, language, duration_sec
    """
    from diag_logging import get_logger, bind_job_id
    from ai_providers import transcribe_audio_chunks_detailed, detect_text_language
    _tlog = get_logger("api.transcribe_take")
    _job = bind_job_id()  # correlation id for app_service.log; returned to the client as "log_id"
    clean_job_id = (job_id or "").strip() or f"job_{_job}"
    _t0 = time.time()
    uploaded_tmp_path = None

    _active_transcribe_jobs[clean_job_id] = {
        "job_id": clean_job_id,
        "status": "processing",
        "stage": "converting",
        "progress": 25,
        "chunks_total": 0,
        "chunks_done": 0,
        "message": "File received. Converting audio & preparing segments with FFmpeg...",
        "created_at": _t0,
        "updated_at": _t0
    }

    def _err(msg: str, **extra):
        _tlog.error("[job %s] ERROR after %.1fs: %s", _job, time.time() - _t0, msg)
        _active_transcribe_jobs[clean_job_id] = {
            "job_id": clean_job_id,
            "status": "error",
            "stage": "failed",
            "progress": 0,
            "message": msg,
            "updated_at": time.time()
        }
        body = {"status": "error", "transcript": "", "raw_transcript": "", "clean_text": "", "text": "",
                "language": "auto", "message": msg, "errors": [msg], "missing_ranges": [], "chunks": [],
                "log_id": _job}
        body.update(extra)
        return JSONResponse(content=body)

    try:
        clean_filename = os.path.basename(file.filename or "take_audio.webm")
        _, ext = os.path.splitext(clean_filename.lower())
        uploaded_tmp_path = _save_upload_limited(file, ext or ".mp4")
        upload_size = os.path.getsize(uploaded_tmp_path)
        _tlog.info("[job %s] REQUEST file=%r content_type=%r size=%.2f MB provider=%s model=%s language=%s api_key_from_ui=%s job_id=%s",
                   _job, clean_filename, file.content_type, upload_size / 1048576, provider, model_name, language, bool(api_key), clean_job_id)
        if upload_size < 32:
            return _err(f"{clean_filename} is empty.")

        proc_res = await asyncio.to_thread(
            process_uploaded_media, media_bytes=None, filename=clean_filename,
            content_type=file.content_type or "", file_path=uploaded_tmp_path
        )
        res_type = proc_res.get("type", "audio_single")

        if res_type == "error":
            return _err(proc_res.get("error") or "Could not read this file.")

        if res_type in ["text", "image_ocr", "pdf_ocr"]:
            extracted_text = proc_res.get("text", "")
            if not extracted_text.strip():
                return _err(f"No text could be extracted from {clean_filename}.")
            lang_d = detect_text_language(extracted_text)
            _active_transcribe_jobs[clean_job_id] = {
                "job_id": clean_job_id,
                "status": "success",
                "stage": "completed",
                "progress": 100,
                "message": f"Extracted text from {clean_filename}.",
                "updated_at": time.time()
            }
            return JSONResponse(content={"status": "success", "transcript": extracted_text, "raw_transcript": extracted_text,
                                         "clean_text": extracted_text, "text": extracted_text, "language": lang_d,
                                         "message": f"Extracted text from {clean_filename}.", "errors": [],
                                         "missing_ranges": [], "chunks": []})

        chunks = proc_res.get("audio_chunks") or ([proc_res["audio_bytes"]] if proc_res.get("audio_bytes") else [])
        n_chunks = len(chunks)
        _active_transcribe_jobs[clean_job_id].update({
            "stage": "transcribing",
            "progress": 35,
            "chunks_total": n_chunks,
            "chunks_done": 0,
            "duration_sec": proc_res.get("total_duration_sec"),
            "message": f"Transcribing audio ({n_chunks} chunk{'s' if n_chunks > 1 else ''})...",
            "updated_at": time.time()
        })

        def _on_chunk_progress(info: Dict[str, Any]):
            done = info.get("chunks_done", 0)
            total = info.get("chunks_total", n_chunks or 1)
            chunk_range = info.get("last_chunk_range", "")
            chunk_pct = 35 + int((done / max(1, total)) * 57)
            pct = min(92, max(35, chunk_pct))
            msg = f"Transcribing chunk {done} of {total} ({chunk_range})..." if chunk_range else f"Transcribing chunk {done} of {total}..."
            if clean_job_id in _active_transcribe_jobs:
                _active_transcribe_jobs[clean_job_id].update({
                    "stage": "transcribing",
                    "progress": pct,
                    "chunks_total": total,
                    "chunks_done": done,
                    "message": msg,
                    "updated_at": time.time()
                })

        res = await asyncio.to_thread(
            transcribe_audio_chunks_detailed,
            chunks=chunks, provider=provider, api_key=api_key, model_name=model_name, language=language,
            mime_type=proc_res.get("mime_type", "audio/mp3"),
            segment_time_sec=proc_res.get("chunk_duration_sec", 600),
            chunk_durations=proc_res.get("chunk_durations"), label=f"job {_job}",
            on_progress=_on_chunk_progress
        )
        transcript = res.get("transcript", "")
        _tlog.log(20 if res["status"] == "success" else 40,
                  "[job %s] RESPONSE after %.1fs: status=%s chunks=%d transcript_chars=%d errors=%s",
                  _job, time.time() - _t0, res["status"], len(chunks), len(transcript), res.get("errors"))

        _active_transcribe_jobs[clean_job_id].update({
            "status": res["status"],
            "stage": "completed",
            "progress": 100,
            "message": "Transcription complete!",
            "updated_at": time.time()
        })

        return JSONResponse(content={
            "status": res["status"],
            "transcript": transcript, "raw_transcript": transcript, "clean_text": transcript, "text": transcript,
            "language": res.get("language", "auto"),
            "message": res.get("message", ""),
            "errors": res.get("errors", []),
            "missing_ranges": res.get("missing_ranges", []),
            "chunks": res.get("chunks", []),
            "providers_used": res.get("providers_used", []),
            "duration_sec": proc_res.get("total_duration_sec"),
            "job_id": clean_job_id,
            "log_id": _job
        })

    except HTTPException as he:
        return _err(str(he.detail))
    except Exception as e:
        _tlog.exception("[job %s] unhandled exception: %s", _job, e)
        return _err(f"Unexpected server error while transcribing (reference {_job}).")
    finally:
        now = time.time()
        expired = [k for k, v in _active_transcribe_jobs.items() if now - v.get("updated_at", now) > 600]
        for k in expired:
            _active_transcribe_jobs.pop(k, None)
        if uploaded_tmp_path and os.path.exists(uploaded_tmp_path):
            try:
                os.remove(uploaded_tmp_path)
            except Exception:
                pass

@app.post("/api/generate_docx")
async def generate_docx(payload: MeetingDocPayload):
    try:
        data_dict = payload.model_dump()
        docx_bytes = generate_meeting_minutes_docx_bytes(data_dict, TEMPLATE_PATH)
        
        # Build filename: EASD-Meeting Minutes-DDMonthYY.docx
        date_str = payload.date or ""
        date_match = re.match(r'(\d{1,2})\s*([A-Za-z]+),?\s*(\d{4})', date_str)
        if date_match:
            day = date_match.group(1)
            month = date_match.group(2)
            year = date_match.group(3)[-2:]
            date_part = f"{day}{month}{year}"
        else:
            date_part = date_str.replace(" ", "").replace(",", "").replace("/", "-")
        
        filename = f"EASD-Meeting Minutes-{date_part}.docx"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate_custom_docx")
async def generate_custom_docx_endpoint(payload: CustomDocxPayload):
    """Generates and streams a .docx document for any custom generalized template."""
    try:
        t_id = payload.template_id or "easd_default_minutes"
        t_info = get_template_by_id(t_id)
        
        if t_id == "easd_default_minutes":
            docx_bytes = generate_meeting_minutes_docx_bytes(payload.doc_data, TEMPLATE_PATH)
        else:
            docx_bytes = generate_custom_template_docx_bytes(t_info, payload.doc_data)
            
        tpl_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', t_info.get("name", "Document")).strip('_')[:30]
        date_str = payload.doc_data.get("date", "")
        date_part = re.sub(r'[^a-zA-Z0-9]', '', date_str) or "Report"
        
        filename = f"{tpl_name}-{date_part}.docx"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload_gdrive")
async def upload_gdrive(payload: GDriveUploadPayload):
    try:
        data_dict = payload.doc_data.model_dump()
        docx_bytes = generate_meeting_minutes_docx_bytes(data_dict, TEMPLATE_PATH)
        
        date_str = payload.doc_data.date or ""
        date_match = re.match(r'(\d{1,2})\s*([A-Za-z]+),?\s*(\d{4})', date_str)
        if date_match:
            day = date_match.group(1)
            month = date_match.group(2)
            year = date_match.group(3)[-2:]
            date_part = f"{day}{month}{year}"
        else:
            date_part = date_str.replace(" ", "").replace(",", "").replace("/", "-")
        
        file_name = f"EASD-Meeting Minutes-{date_part}.docx"
        
        gdrive_res = upload_docx_to_gdrive(
            file_bytes=docx_bytes,
            file_name=file_name,
            access_token=payload.access_token,
            folder_name=payload.folder_name or "EASD - meeting minutes"
        )
        
        return JSONResponse(content={"status": "success", "gdrive": gdrive_res})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CloudImportPayload(BaseModel):
    url: str
    provider: Optional[str] = "auto"

@app.post("/api/import_cloud_file")
async def import_cloud_file(payload: CloudImportPayload):
    import requests
    from urllib.parse import unquote, urlparse
    
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Empty URL provided.")

    direct_url = url
    target_provider = payload.provider or "auto"
    
    # 1. Google Drive
    gdrive_match = re.search(r'drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([a-zA-Z0-9_-]+)', url)
    if gdrive_match:
        fid = gdrive_match.group(1)
        direct_url = f"https://drive.google.com/uc?export=download&id={fid}"
        target_provider = "gdrive"
        
    # 2. Dropbox
    elif "dropbox.com" in url:
        target_provider = "dropbox"
        if "dl=0" in url:
            direct_url = url.replace("dl=0", "dl=1")
        elif "?" in url:
            direct_url = url + "&dl=1"
        else:
            direct_url = url + "?dl=1"
            
    # 3. OneDrive
    elif any(k in url for k in ["1drv.ms", "onedrive.live.com", "sharepoint.com"]):
        target_provider = "onedrive"
        try:
            b64 = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            direct_url = f"https://api.onedrive.com/v1.0/shares/u!{b64}/root/content"
        except Exception:
            direct_url = url + ("&download=1" if "?" in url else "?download=1")

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = session.get(direct_url, headers=headers, stream=True, timeout=60, allow_redirects=True)
        
        # Check for Google Drive large-file virus confirmation token
        if target_provider == "gdrive" and "confirm=" not in direct_url:
            confirm_token = None
            for k, v in resp.cookies.items():
                if k.startswith("download_warning"):
                    confirm_token = v
                    break
            if confirm_token:
                confirm_url = f"{direct_url}&confirm={confirm_token}"
                resp = session.get(confirm_url, headers=headers, stream=True, timeout=60, allow_redirects=True)
            elif "Google Drive - Virus scan warning" in resp.text[:2000]:
                match = re.search(r'confirm=([0-9A-Za-z_]+)', resp.text)
                if match:
                    confirm_url = f"{direct_url}&confirm={match.group(1)}"
                    resp = session.get(confirm_url, headers=headers, stream=True, timeout=60, allow_redirects=True)

        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch cloud file (Status {resp.status_code}). Ensure link has public sharing enabled."
            )

        # Extract filename
        filename = None
        cd = resp.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd, re.IGNORECASE)
            if fn_match:
                filename = unquote(fn_match.group(1).strip())
        
        if not filename:
            path_part = urlparse(url).path
            base_name = os.path.basename(path_part)
            if base_name and "." in base_name:
                filename = unquote(base_name)
            else:
                content_type = resp.headers.get("Content-Type", "")
                ext = ".mp3"
                if "wav" in content_type: ext = ".wav"
                elif "mp4" in content_type: ext = ".mp4"
                elif "m4a" in content_type: ext = ".m4a"
                elif "pdf" in content_type: ext = ".pdf"
                elif "word" in content_type or "docx" in content_type: ext = ".docx"
                filename = f"{target_provider}_recording_{int(time.time())}{ext}"

        media_type = resp.headers.get("Content-Type", "application/octet-stream")
        
        def iterfile():
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-File-Name": filename,
                "Access-Control-Expose-Headers": "Content-Disposition, X-File-Name"
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cloud download error: {str(exc)}")

# Mount Static/Frontend
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
elif os.path.exists(STATIC_LEGACY):
    app.mount("/", StaticFiles(directory=STATIC_LEGACY, html=True), name="static")

def find_available_port(start_port: int = 8000, max_tries: int = 20) -> int:
    import socket
    for p in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', p))
                return p
            except OSError:
                continue
    return start_port

def is_server_already_running(port: int = 8000) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/default_config")
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False

def open_native_app_window(url: str, delay: float = 0.5):
    """
    Launches a dedicated, clean desktop application window using Chromium app mode.
    Removes address bars, tabs, and browser clutter to look and feel like a normal desktop app.
    Provides guaranteed fallback to the default system browser via Windows shell if needed.
    """
    import time
    import threading
    import subprocess
    import shutil
    import webbrowser
    import os
    import urllib.request

    def _launcher():
        # 1. Wait until server is listening and responding with 200 before launching browser
        start = time.time()
        while time.time() - start < 10.0:
            try:
                test_url = f"{url.rstrip('/')}/api/default_config"
                req = urllib.request.Request(test_url)
                with urllib.request.urlopen(req, timeout=0.4) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.2)

        # Brief delay to allow FastAPI static mounts to settle
        time.sleep(max(0.1, delay))

        # Candidate paths for native Chromium app mode
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            shutil.which("msedge.exe") or "",
            shutil.which("chrome.exe") or ""
        ]

        opened = False
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                try:
                    cmd = [candidate, f"--app={url}"]
                    subprocess.Popen(cmd)
                    time.sleep(0.5)
                    opened = True
                    break
                except Exception:
                    continue

        # Reliable fallback: Windows native shell launch or Python webbrowser
        if not opened:
            try:
                os.startfile(url)
            except Exception:
                try:
                    webbrowser.open(url, new=2)
                except Exception:
                    pass

    t = threading.Thread(target=_launcher, daemon=False)
    t.start()
    return t

if __name__ == "__main__":
    import uvicorn
    import sys

    # If server is already running, open the application window and exit
    if is_server_already_running(8000):
        print("EASD Meeting Assistant is already running. Opening application window...")
        t = open_native_app_window("http://localhost:8000/", delay=0.1)
        t.join(timeout=2.0)
        sys.exit(0)

    port = find_available_port(8000)
    server_host = os.getenv("HOST", "127.0.0.1")
    url = f"http://localhost:{port}/"
    print(f"Starting EASD Meeting Assistant at: {url}")

    # Launch dedicated native desktop app window
    if os.getenv("NO_BROWSER") != "true" and os.getenv("CODESPACES") != "true":
        open_native_app_window(url, delay=1.0)

    # Run server
    uvicorn.run(app, host=server_host, port=port, log_level="info")


