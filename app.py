import os
import io
import json
import base64
import uuid
import re
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
    detect_text_language
)
from gdrive_service import upload_docx_to_gdrive
from media_processor import process_uploaded_media

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "EASD Meeting minutes - Template-DDMonthYY.docx")
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
    api_key: str
    base_url: Optional[str] = ""

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
def verify_key_endpoint(payload: VerifyKeyPayload):
    """Verifies whether an API key is active and valid."""
    res = verify_ai_api_key(payload.provider, payload.api_key, payload.base_url or "")
    return JSONResponse(content=res)

@app.post("/api/transcribe_and_summarize")
async def transcribe_and_summarize(
    provider: str = Form("groq"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model_name: str = Form(""),
    transcription_model: str = Form(""),
    summarization_model: str = Form(""),
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
            else:
                chunks = proc_res.get("audio_chunks", [])
                single_audio = proc_res.get("audio_bytes")
                if chunks:
                    all_audio_chunks.extend(chunks)
                elif single_audio:
                    all_audio_chunks.append(single_audio)
                mime_type = proc_res.get("mime_type", "audio/mp3")

        detected_format_str = ", ".join(detected_formats) if detected_formats else ""
        
        # If single chunk and no multi-chunk list, assign media_bytes
        if len(all_audio_chunks) == 1:
            media_bytes = all_audio_chunks[0]
            audio_chunks_param = None
        else:
            media_bytes = None
            audio_chunks_param = all_audio_chunks if all_audio_chunks else None

        template_schema = get_template_by_id(template_id) if template_id else None

        result = process_ai_request(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            transcription_model=transcription_model or model_name,
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
    provider: str = Form("groq"),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model_name: str = Form(""),
    summarization_model: str = Form(""),
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
            summarization_model=summarization_model or model_name,
            text_content=transcript,
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )
        return JSONResponse(content={"status": "success", "data": res})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    port = find_available_port(8000)
    is_cloud_env = os.getenv("CODESPACES") == "true" or os.getenv("DEVCONTAINER") == "true" or os.getenv("HOST") == "0.0.0.0"
    server_host = os.getenv("HOST", "0.0.0.0" if is_cloud_env else "127.0.0.1")
    
    cert_path = os.path.join(BASE_DIR, "cert.pem")
    key_path = os.path.join(BASE_DIR, "key.pem")
    # In cloud/Codespaces environments, the platform terminates SSL at the edge, so uvicorn must run HTTP internally
    use_https = False if is_cloud_env else ensure_ssl_certificates(cert_path, key_path)
    
    proto = "https" if use_https else "http"
    url = f"{proto}://localhost:{port}/"
    print("\n========================================================")
    print(f"  [ONLINE SECURE {proto.upper()}] EASD Meeting Assistant running at: {url}")
    print(f"  [BIND HOST] {server_host}:{port}")
    print("========================================================\n")
    if os.getenv("CODESPACES") != "true":
        open_browser_after_delay(url, delay=0.8)
    
    if use_https:
        uvicorn.run(app, host=server_host, port=port, log_level="info", ssl_certfile=cert_path, ssl_keyfile=key_path)
    else:
        uvicorn.run(app, host=server_host, port=port, log_level="info")
