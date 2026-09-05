import os
import io
import json
import base64
import uuid
import re
import time
from typing import Dict, Any, List, Optional
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
    generate_custom_template_docx_bytes
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
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data: https: ws: wss:; "
        "upgrade-insecure-requests; object-src 'none'; "
        "frame-ancestors 'self' https://*.github.dev https://*.app.github.dev;"
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

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
    transcription_provider: Optional[str] = "groq"
    transcription_api_key: Optional[str] = ""
    transcription_model: Optional[str] = "whisper-large-v3-turbo"
    transcription_base_url: Optional[str] = ""
    summarization_provider: Optional[str] = "gemini"
    summarization_api_key: Optional[str] = ""
    summarization_model: Optional[str] = "gemini-3.5-flash"
    summarization_base_url: Optional[str] = ""
    groq_api_key: Optional[str] = ""
    gemini_api_key: Optional[str] = ""
    openai_api_key: Optional[str] = ""
    anthropic_api_key: Optional[str] = ""
    model_config = ConfigDict(extra="ignore")

class TestEnginePayload(BaseModel):
    test_type: str = "both"  # "stt", "llm", or "both"
    stt_provider: Optional[str] = None
    stt_api_key: Optional[str] = None
    stt_model: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    base_url: Optional[str] = None
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
        updated = save_api_settings_to_disk(payload.model_dump())
        return JSONResponse(content={"status": "success", "settings": updated, "message": "API settings saved successfully."})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/test_engine")
def test_engine_endpoint(payload: TestEnginePayload):
    """
    Actively tests STT transcription and/or LLM summarization endpoints.
    Returns live latency (ms), HTTP status, and diagnostic health report.
    """
    cfg = load_api_settings_from_disk()
    results: Dict[str, Any] = {"status": "success"}

    # Test STT Transcription Engine if requested
    if payload.test_type in ["stt", "both"]:
        stt_prov = payload.stt_provider or cfg.get("transcription_provider") or "groq"
        stt_key = payload.stt_api_key or cfg.get(f"{stt_prov}_api_key") or cfg.get("transcription_api_key") or ""
        stt_mod = payload.stt_model or cfg.get("transcription_model") or ("whisper-large-v3-turbo" if stt_prov == "groq" else "gemini-3.5-flash")
        stt_res = test_transcription_engine(
            provider=stt_prov,
            api_key=stt_key,
            model_name=stt_mod,
            base_url=payload.base_url or cfg.get("transcription_base_url") or ""
        )
        results["stt"] = stt_res
        if not stt_res.get("success"):
            results["status"] = "partial" if payload.test_type == "both" else "error"

    # Test LLM Summarization Engine if requested
    if payload.test_type in ["llm", "both"]:
        llm_prov = payload.llm_provider or cfg.get("summarization_provider") or "gemini"
        llm_key = payload.llm_api_key or cfg.get(f"{llm_prov}_api_key") or cfg.get("summarization_api_key") or ""
        llm_mod = payload.llm_model or cfg.get("summarization_model") or ("gemini-3.5-flash" if llm_prov == "gemini" else "llama-3.3-70b-versatile")
        llm_res = test_summarization_engine(
            provider=llm_prov,
            api_key=llm_key,
            model_name=llm_mod,
            base_url=payload.base_url or cfg.get("summarization_base_url") or ""
        )
        results["llm"] = llm_res
        if not llm_res.get("success"):
            results["status"] = "partial" if (payload.test_type == "both" and results.get("stt", {}).get("success")) else "error"

    return JSONResponse(content=results)

@app.get("/api/env_keys")
@app.post("/api/env_keys")
def get_env_keys_endpoint():
    """Reports detected AI API environment variables safely."""
    groq_env = bool(os.getenv("GROQ_API_KEY"))
    gemini_env = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    openai_env = bool(os.getenv("OPENAI_API_KEY"))
    anthropic_env = bool(os.getenv("ANTHROPIC_API_KEY"))
    base_dir = os.path.dirname(os.path.abspath(__file__))
    groq_file = os.path.exists(os.path.join(base_dir, "GroqAPI.txt"))
    return JSONResponse(content={
        "status": "success",
        "env_keys": {
            "GROQ_API_KEY": {
                "configured": bool(groq_env or groq_file),
                "preview": "Set in GroqAPI.txt / ENV" if (groq_env or groq_file) else "Not configured"
            },
            "GEMINI_API_KEY": {
                "configured": bool(gemini_env),
                "preview": "Set in environment" if gemini_env else "Not configured"
            },
            "OPENAI_API_KEY": {
                "configured": bool(openai_env),
                "preview": "Set in environment" if openai_env else "Not configured"
            },
            "ANTHROPIC_API_KEY": {
                "configured": bool(anthropic_env),
                "preview": "Set in environment" if anthropic_env else "Not configured"
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
    res = verify_ai_api_key(payload.provider, payload.api_key or "", payload.base_url or "")
    is_valid = bool(res.get("valid", False) or res.get("success", False))
    return JSONResponse(content={
        "status": "success" if is_valid else "error",
        "valid": is_valid,
        "success": is_valid,
        "message": res.get("message", "Key verified.") if is_valid else res.get("message", "Verification failed."),
        "latency_ms": res.get("latency_ms")
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
    try:
        media_bytes = None
        mime_type = "audio/mp3"
        all_audio_chunks = []
        detected_formats = []
        
        # Collect all uploaded files (single file + multi-part files list)
        upload_list: List[UploadFile] = []
        if file:
            upload_list.append(file)
        if files:
            for f in files:
                if f and f.filename:
                    upload_list.append(f)
                    
        for uploaded in upload_list:
            clean_filename = os.path.basename(uploaded.filename or "upload_audio.mp3")
            content = await uploaded.read()
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail=f"File {clean_filename} exceeds 1GB limit.")
                
            proc_res = process_uploaded_media(
                media_bytes=content,
                filename=clean_filename,
                content_type=uploaded.content_type or ""
            )
            
            fmt = proc_res.get("format_detected", "")
            if fmt and fmt not in detected_formats:
                detected_formats.append(fmt)
                
            if proc_res.get("type") == "text":
                extracted = proc_res.get("text", "")
                text_content = f"{text_content}\n\n{extracted}".strip() if text_content else extracted
            elif proc_res.get("type") in ["image_ocr", "pdf_ocr"]:
                media_bytes = proc_res.get("media_bytes")
                mime_type = proc_res.get("mime_type", "image/jpeg")
                if proc_res.get("text"):
                    extracted = proc_res.get("text")
                    text_content = f"{text_content}\n\n{extracted}".strip() if text_content else extracted
            else:
                chunks = proc_res.get("audio_chunks", [])
                single_audio = proc_res.get("audio_bytes")
                if chunks:
                    all_audio_chunks.extend(chunks)
                elif single_audio:
                    all_audio_chunks.append(single_audio)
                mime_type = proc_res.get("mime_type", "audio/mp3")

        detected_format_str = ", ".join(detected_formats) if detected_formats else ""
        
        # If single chunk and no multi-chunk list, assign media_bytes (unless already set by vision)
        if not media_bytes and len(all_audio_chunks) == 1:
            media_bytes = all_audio_chunks[0]
            audio_chunks_param = None
        elif len(all_audio_chunks) > 1:
            media_bytes = None
            audio_chunks_param = all_audio_chunks
        else:
            audio_chunks_param = None

        template_schema = get_template_by_id(template_id) if template_id else None

        result = process_ai_request(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            transcription_provider=transcription_provider or "",
            transcription_api_key=transcription_api_key or "",
            transcription_model=transcription_model or model_name,
            summarization_provider=summarization_provider or "",
            summarization_api_key=summarization_api_key or "",
            summarization_model=summarization_model or model_name,
            media_bytes=media_bytes,
            mime_type=mime_type,
            text_content=text_content,
            org_context=org_context,
            custom_skills=custom_skills,
            audio_chunks=audio_chunks_param,
            template_schema=template_schema
        )
        if detected_format_str and isinstance(result, dict):
            result["detected_format"] = detected_format_str
            
        return JSONResponse(content={"status": "success", "data": result})
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    try:
        template_schema = get_template_by_id(template_id) if template_id else None
        res = process_ai_request(
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
        return JSONResponse(content={"status": "success", "data": res})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        
        result = process_ai_request(
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
    return JSONResponse(content={"status": "success", "report": report})

@app.websocket("/ws/live_transcribe")
async def websocket_live_transcribe(websocket: WebSocket):
    """Real-time streaming WebSocket endpoint for microphone transcription."""
    await websocket.accept()
    session_config = {
        "api_key": "",
        "provider": "gemini",
        "language": "auto",
        "model_name": "gemini-3.5-flash-lite"
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
                session_config["model_name"] = data.get("model_name", "gemini-3.5-flash-lite").strip()
                
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

# Mount Static/Frontend
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
elif os.path.exists(STATIC_LEGACY):
    app.mount("/", StaticFiles(directory=STATIC_LEGACY, html=True), name="static")

def ensure_ssl_certificates(cert_path: str, key_path: str) -> bool:
    """Generates self-signed SSL cert and key for HTTPS if missing."""
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return True
    try:
        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u'BD'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'EASD Eminence'),
            x509.NameAttribute(NameOID.COMMON_NAME, u'localhost'),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.now(datetime.timezone.utc)
        ).not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u'localhost'),
                x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
            ]),
            critical=False,
        ).sign(key, hashes.SHA256())

        with open(key_path, 'wb') as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(cert_path, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return True
    except Exception as e:
        print(f"[SSL Certificate Warning] {e}")
        return False

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

def open_browser_after_delay(url: str, delay: float = 1.0):
    import time
    import threading
    import webbrowser
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    import sys
    port = find_available_port(8000)
    is_cloud_env = os.getenv("CODESPACES") == "true" or os.getenv("DEVCONTAINER") == "true" or os.getenv("HOST") == "0.0.0.0"
    server_host = os.getenv("HOST", "0.0.0.0" if is_cloud_env else "127.0.0.1")
    
    cert_path = os.path.join(BASE_DIR, "cert.pem")
    key_path = os.path.join(BASE_DIR, "key.pem")
    
    # By default, localhost runs on clean HTTP, which W3C and Firefox natively treat as a Secure Context
    # (full mic/speech access enabled with ZERO 'risky self-signed cert' warnings in Firefox).
    # If explicitly requested via CLI flag --https or ENABLE_HTTPS=true, enable HTTPS.
    explicit_https = "--https" in sys.argv or os.getenv("ENABLE_HTTPS", "false").lower() in ["1", "true", "yes"]
    use_https = explicit_https and not is_cloud_env and ensure_ssl_certificates(cert_path, key_path)
    
    proto = "https" if use_https else "http"
    url = f"{proto}://localhost:{port}/"
    print("\n========================================================")
    print(f"  [ONLINE SECURE {proto.upper()}] EASD Meeting Assistant running at: {url}")
    print(f"  [BIND HOST] {server_host}:{port}")
    if not use_https:
        print("  [NOTE] Running clean HTTP on localhost (W3C Secure Context compliant - zero browser warnings in Firefox/Chrome)")
        print("  [TIP] To run with HTTPS/SSL, start with: python app.py --https")
    print("========================================================\n")
    if os.getenv("CODESPACES") != "true" and os.getenv("NO_BROWSER") != "true":
        open_browser_after_delay(url, delay=0.8)
    
    if use_https:
        uvicorn.run(app, host=server_host, port=port, log_level="info", ssl_certfile=cert_path, ssl_keyfile=key_path)
    else:
        uvicorn.run(app, host=server_host, port=port, log_level="info")
