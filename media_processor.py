import os
import re
import sys
import shutil
import tempfile
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Any, Optional
from ocr_engine import (
    extract_pdf_content,
    preprocess_image_for_ocr,
    optimize_ocr_text,
    perform_local_ocr,
    is_tesseract_available
)

# Supported extensions mapping
VIDEO_EXTENSIONS = {
    ".hevc", ".h265", ".265", ".mp4", ".mkv", ".mov", ".avi", ".webm",
    ".flv", ".wmv", ".m4v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2",
    ".ogv", ".vob", ".mxf", ".rm", ".rmvb", ".asf", ".divx", ".xvid", ".prores",
    ".qt", ".f4v", ".webm"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma",
    ".amr", ".awb", ".ac3", ".eac3", ".aiff", ".aif", ".alac", ".ape",
    ".caf", ".dts", ".pcm", ".spx", ".mka", ".oga", ".mid", ".midi"
}

DOCUMENT_EXTENSIONS = {
    ".docx", ".doc", ".txt", ".md", ".srt", ".vtt", ".rtf", ".csv", ".tsv", ".json",
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".heic"
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".heic"
}

PDF_EXTENSIONS = {".pdf"}

# Maximum chunk size for API uploads (20 MB safe limit to stay well below 25MB Groq / OpenAI limits)
MAX_CHUNK_BYTES = 20 * 1024 * 1024

def find_ffmpeg_binary() -> Optional[str]:
    """Finds the ffmpeg executable in system PATH or common local paths."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    
    # Check common Windows paths
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-*\bin\ffmpeg.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-*\bin\ffmpeg.EXE"),
    ]
    for c in candidates:
        if "*" in c:
            import glob
            matches = glob.glob(c)
            if matches and os.path.isfile(matches[0]):
                return matches[0]
        elif os.path.isfile(c):
            return c
    return None

def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    """Extracts text from a DOCX file using python-docx or raw XML zip parsing as fallback."""
    try:
        import docx
        import io
        doc = docx.Document(io.BytesIO(docx_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    paragraphs.append(row_text)
        if paragraphs:
            return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"[DOCX python-docx parser notice] {e}, trying zip xml fallback...")

    # Direct XML extraction fallback
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for p in tree.iterfind('.//w:p', namespaces):
                texts = [node.text for node in p.iterfind('.//w:t', namespaces) if node.text]
                if texts:
                    paragraphs.append(''.join(texts).strip())
            return "\n\n".join([p for p in paragraphs if p])
    except Exception as e2:
        print(f"[DOCX XML parsing error] {e2}")
        return ""

def parse_subtitle_file(text: str) -> str:
    """Strips timestamps, sequence numbers, and formatting tags from SRT/VTT files."""
    lines = text.splitlines()
    clean_lines = []
    timestamp_pattern = re.compile(r'(?:\d{1,2}:)?\d{2}:\d{2}[\.,]\d{3}\s*-->\s*(?:\d{1,2}:)?\d{2}:\d{2}[\.,]\d{3}')
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("WEBVTT") or s.startswith("NOTE") or s.startswith("STYLE"):
            continue
        if s.isdigit():
            continue
        if timestamp_pattern.search(s):
            continue
        # Strip html tags e.g. <v Speaker> or <i>
        s = re.sub(r'<[^>]+>', '', s).strip()
        if s:
            clean_lines.append(s)
            
    return "\n".join(clean_lines)

def convert_media_to_speech_audio(
    input_file_path: str,
    output_audio_path: str,
    ffmpeg_bin: str
) -> bool:
    """
    Transcodes any video/audio file (including HEVC/H.265, iPhone MOV/M4A/AAC/ALAC/CAF,
    ProRes, H.264, MKV, MP4, WebM, FLAC, AMR, WAV, etc.) into speech-optimized 16kHz mono MP3 (48-64kbps CBR).
    """
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", input_file_path,
        "-vn",                   # Drop video stream
        "-ac", "1",              # Convert to mono
        "-ar", "16000",          # 16kHz sample rate (Whisper & Gemini optimal)
        "-c:a", "libmp3lame",    # High quality MP3 codec
        "-b:a", "48k",           # 48kbps bitrate (~0.35 MB per minute)
        output_audio_path
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return res.returncode == 0 and os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0
    except Exception as e:
        print(f"[FFmpeg conversion error] {e}")
        return False

def split_audio_into_chunks(
    audio_path: str,
    ffmpeg_bin: str,
    segment_time_seconds: int = 600
) -> List[str]:
    """
    Splits long audio into sequential chunks (default 10 mins each)
    to comfortably fit under API payload and timeout limits.
    """
    temp_dir = os.path.dirname(audio_path)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_pattern = os.path.join(temp_dir, f"{base_name}_chunk_%03d.mp3")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(segment_time_seconds),
        "-c", "copy",
        output_pattern
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        # Find generated chunks
        chunks = []
        idx = 0
        while True:
            chunk_file = os.path.join(temp_dir, f"{base_name}_chunk_{idx:03d}.mp3")
            if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 0:
                chunks.append(chunk_file)
                idx += 1
            else:
                break
        return chunks if chunks else [audio_path]
    except Exception as e:
        print(f"[FFmpeg audio chunking error] {e}")
        return [audio_path]

def normalize_audio_chunk_for_stt(chunk_bytes: bytes, mime_type: str = "audio/webm") -> Tuple[Optional[bytes], str]:
    """
    Normalizes a standalone audio recording chunk or streaming slice
    into a valid 16kHz mono MP3 file with complete headers.
    Ensures Groq Whisper and Gemini STT never receive corrupt/headerless containers.
    """
    if not chunk_bytes or len(chunk_bytes) < 64:
        return None, mime_type
        
    ffmpeg_bin = find_ffmpeg_binary()
    if not ffmpeg_bin:
        return chunk_bytes, mime_type
        
    ext = ".webm"
    if "mp4" in mime_type or "m4a" in mime_type or "aac" in mime_type:
        ext = ".mp4"
    elif "wav" in mime_type:
        ext = ".wav"
    elif "ogg" in mime_type or "opus" in mime_type:
        ext = ".ogg"
        
    with tempfile.TemporaryDirectory() as temp_dir:
        in_path = os.path.join(temp_dir, f"raw_chunk{ext}")
        out_path = os.path.join(temp_dir, "normalized_chunk.mp3")
        
        with open(in_path, "wb") as f:
            f.write(chunk_bytes)
            
        success = convert_media_to_speech_audio(in_path, out_path, ffmpeg_bin)
        if success and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            with open(out_path, "rb") as out_f:
                return out_f.read(), "audio/mp3"
                
    return chunk_bytes, mime_type

def process_uploaded_media(
    media_bytes: bytes,
    filename: str,
    content_type: str = ""
) -> Dict[str, Any]:
    """
    Universal media processor:
    Accepts ANY file payload (HEVC/H.265 video, Apple iPhone MOV / ProRes / M4A / AAC / ALAC / CAF,
    H.264, MP4, MKV, WebM, TS, FLAC, AMR, DOCX, SRT, VTT, TXT, MD, etc.).
    
    Returns:
    {
        "type": "text" | "audio_single" | "audio_chunks",
        "text": str (if text/document),
        "audio_bytes": bytes (if single chunk),
        "mime_type": "audio/mp3" | "audio/wav" etc,
        "audio_chunks": List[bytes] (if multi-chunk),
        "format_detected": str
    }
    """
    clean_name = os.path.basename(filename).strip()
    _, ext = os.path.splitext(clean_name.lower())
    
    # 1. Check Document / Subtitle Formats
    if ext in [".docx", ".doc"]:
        extracted_text = extract_text_from_docx_bytes(media_bytes)
        return {
            "type": "text",
            "text": extracted_text,
            "format_detected": "DOCX Document",
            "audio_bytes": None,
            "mime_type": "text/plain",
            "audio_chunks": []
        }
        
    if ext in [".srt", ".vtt"]:
        raw_text = ""
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                raw_text = media_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        clean_text = parse_subtitle_file(raw_text)
        return {
            "type": "text",
            "text": clean_text,
            "format_detected": "Subtitle / Caption Transcript",
            "audio_bytes": None,
            "mime_type": "text/plain",
            "audio_chunks": []
        }
        
    if ext in [".txt", ".md", ".rtf", ".csv", ".tsv", ".json"] or content_type.startswith("text/"):
        raw_text = ""
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                raw_text = media_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        return {
            "type": "text",
            "text": raw_text,
            "format_detected": "Text Document",
            "media_bytes": None,
            "audio_bytes": None,
            "mime_type": "text/plain",
            "audio_chunks": []
        }

    # 2. Check PDF Documents
    if ext == ".pdf" or content_type == "application/pdf":
        pdf_info = extract_pdf_content(media_bytes)
        if not pdf_info["is_scanned"] and len(pdf_info["text"]) >= 60:
            return {
                "type": "text",
                "text": pdf_info["text"],
                "format_detected": f"PDF Document ({pdf_info['page_count']} Pages - Digital Text)",
                "media_bytes": media_bytes,
                "audio_bytes": None,
                "mime_type": "text/plain",
                "audio_chunks": []
            }
        else:
            return {
                "type": "pdf_ocr",
                "text": pdf_info.get("text", ""),
                "format_detected": f"Scanned PDF ({pdf_info['page_count']} Pages - Vision OCR)",
                "media_bytes": media_bytes,
                "audio_bytes": None,
                "mime_type": "application/pdf",
                "audio_chunks": []
            }

    # 3. Check Images for OCR (Photos, Scans, Whiteboards)
    if ext in IMAGE_EXTENSIONS or content_type.startswith("image/"):
        opt_bytes, opt_mime = preprocess_image_for_ocr(media_bytes)
        local_text = perform_local_ocr(opt_bytes) if is_tesseract_available() else ""
        return {
            "type": "image_ocr",
            "text": local_text,
            "format_detected": f"Image Document ({ext.upper().lstrip('.')} - Multimodal OCR)",
            "media_bytes": opt_bytes,
            "audio_bytes": None,
            "mime_type": opt_mime,
            "audio_chunks": []
        }

    # 2. Universal Audio & Video Processing with FFmpeg
    ffmpeg_bin = find_ffmpeg_binary()
    detected_format = f"{ext.upper().lstrip('.')} Media" if ext else "Media File"
    
    if ext in [".hevc", ".h265", ".265"]:
        detected_format = "HEVC / H.265 High Efficiency Video"
    elif ext in [".mov", ".qt"]:
        detected_format = "Apple QuickTime (MOV / ProRes / HEVC)"
    elif ext in [".m4a", ".aac", ".alac", ".caf", ".aif", ".aiff"]:
        detected_format = "Apple / iPhone Audio Recording (M4A / AAC / ALAC / CAF)"
    elif ext in [".mp4", ".m4v"]:
        detected_format = "MP4 / H.264 / HEVC Video"
    elif ext in [".mkv"]:
        detected_format = "Matroska (MKV) Video/Audio"
    elif ext in [".webm"]:
        detected_format = "WebM Audio/Video Stream"
    elif ext in [".ts", ".mts", ".m2ts"]:
        detected_format = "MPEG Transport Stream (TS / HEVC)"
    elif ext in [".amr", ".awb", ".3gp"]:
        detected_format = "Mobile Audio Recording (AMR / 3GP)"
    elif ext in [".flac", ".wav", ".mp3", ".ogg", ".opus", ".wma"]:
        detected_format = f"{ext.upper().lstrip('.')} Audio"

    if ffmpeg_bin:
        # Determine appropriate input extension for temp file
        safe_ext = ext if ext else (".mp4" if "video" in content_type else ".mp3")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_input = os.path.join(temp_dir, f"input_media{safe_ext}")
            temp_output = os.path.join(temp_dir, "speech_normalized.mp3")

            with open(temp_input, "wb") as f:
                f.write(media_bytes)

            success = convert_media_to_speech_audio(temp_input, temp_output, ffmpeg_bin)
            if success and os.path.exists(temp_output):
                output_size = os.path.getsize(temp_output)
                
                # Check if multi-chunk splitting is needed (> MAX_CHUNK_BYTES)
                if output_size > MAX_CHUNK_BYTES:
                    chunk_paths = split_audio_into_chunks(temp_output, ffmpeg_bin, segment_time_seconds=600)
                    chunks_bytes = []
                    for cp in chunk_paths:
                        with open(cp, "rb") as cf:
                            chunks_bytes.append(cf.read())
                    return {
                        "type": "audio_chunks",
                        "text": "",
                        "format_detected": detected_format,
                        "audio_bytes": None,
                        "mime_type": "audio/mp3",
                        "audio_chunks": chunks_bytes
                    }
                else:
                    with open(temp_output, "rb") as out_f:
                        audio_data = out_f.read()
                    return {
                        "type": "audio_single",
                        "text": "",
                        "format_detected": detected_format,
                        "audio_bytes": audio_data,
                        "mime_type": "audio/mp3",
                        "audio_chunks": [audio_data]
                    }

    # 3. Fallback if FFmpeg is not available
    return {
        "type": "audio_single",
        "text": "",
        "format_detected": detected_format,
        "audio_bytes": media_bytes,
        "mime_type": content_type or "audio/webm",
        "audio_chunks": [media_bytes]
    }
