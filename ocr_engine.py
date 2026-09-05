"""
ocr_engine.py - Universal OCR, Document Extraction & Optimization Engine
Supports:
  - Images: PNG, JPEG, WEBP, BMP, TIFF, HEIC
  - Documents: PDF (Digital text extraction + Scanned page OCR)
  - Multimodal AI Vision: Google Gemini (gemini-2.5-flash, gemini-3.5-flash-lite, gemini-3.7-flash)
  - OpenAI Vision: gpt-4o, gpt-4o-mini
  - Local Fallback: pytesseract with auto-discovery & Pillow image pre-processing
  - OCR Post-Processing: Error repair, Bengali ligature fixes, bullet standardization
"""

import os
import io
import re
import base64
import shutil
import logging
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

logger = logging.getLogger("ocr_engine")

# Image extensions supported
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.heic'}
PDF_EXTENSIONS = {'.pdf'}

def find_tesseract_binary() -> Optional[str]:
    """Auto-detects Tesseract OCR executable on Windows, Linux, and macOS."""
    which_tess = shutil.which("tesseract")
    if which_tess:
        return which_tess

    # Check environment variable
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # Common Windows installation locations
    candidate_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        r"D:\Program Files\Tesseract-OCR\tesseract.exe",
        r"E:\Program Files\Tesseract-OCR\tesseract.exe"
    ]
    for p in candidate_paths:
        if os.path.isfile(p):
            return p

    # Common Linux / macOS paths
    unix_paths = ["/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]
    for p in unix_paths:
        if os.path.isfile(p):
            return p

    return None

def is_tesseract_available() -> bool:
    """Checks whether local Tesseract OCR is available."""
    tess_bin = find_tesseract_binary()
    if tess_bin:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_bin
            return True
        except Exception:
            return False
    return False

def preprocess_image_for_ocr(image_bytes: bytes, max_dimension: int = 3000) -> Tuple[bytes, str]:
    """
    Optimizes an input image for OCR:
      1. Corrects orientation based on EXIF metadata (mobile phone photos).
      2. Converts RGBA / Palette images to clean RGB.
      3. Enhances contrast and applies mild unsharp mask for faint handwriting/ink.
      4. Normalizes resolution if image exceeds max_dimension to avoid memory/API limits.
    Returns (optimized_bytes, mime_type).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # 1. EXIF Auto-orientation
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        # 2. Color mode normalization
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # 3. Resize if too large
        w, h = image.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 4. Enhance contrast and sharpness for OCR readability
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.25)
        
        sharpener = ImageEnhance.Sharpness(image)
        image = sharpener.enhance(1.15)

        out_buf = io.BytesIO()
        image.save(out_buf, format="JPEG", quality=92, optimize=True)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning(f"Image preprocessing warning: {e}. Returning original bytes.")
        return image_bytes, "image/jpeg"

def extract_pdf_content(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts text and detects if PDF is digital or scanned.
    Returns:
      {
        "is_scanned": bool,
        "page_count": int,
        "text": str,
        "extracted_images": List[bytes]
      }
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        page_texts = []
        extracted_images = []

        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                page_texts.append(f"--- Page {idx + 1} ---\n{txt.strip()}")
            
            # Check for embedded images if text is minimal
            if len(txt.strip()) < 30 and len(extracted_images) < 10:
                try:
                    for img_obj in page.images:
                        extracted_images.append(img_obj.data)
                        if len(extracted_images) >= 10:
                            break
                except Exception:
                    pass

        full_text = "\n\n".join(page_texts).strip()
        # If average characters per page is less than 40, classify as scanned PDF
        is_scanned = (len(full_text) / max(1, page_count)) < 40

        return {
            "is_scanned": is_scanned,
            "page_count": page_count,
            "text": full_text,
            "extracted_images": extracted_images
        }
    except Exception as e:
        logger.warning(f"PDF extraction error: {e}")
        return {
            "is_scanned": True,
            "page_count": 1,
            "text": "",
            "extracted_images": []
        }

def optimize_ocr_text(raw_text: str) -> str:
    """
    Cleans, optimizes, and repairs common OCR anomalies:
      - Strips spurious isolated punctuation tokens (| | |, ~~~, ___)
      - Unifies bullet points to standard '• '
      - Fixes broken Bengali conjunct spacing (e.g. ক র তে -> করতে)
      - Collapses excessive blank lines and trailing spaces
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Clean bullet points: normalize *, -, o, +, digits followed by paren
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        
        # Replace leading bullet markers with standard •
        bullet_match = re.match(r'^[\*\-\+o•▪►]\s*(.*)$', stripped)
        if bullet_match and len(bullet_match.group(1)) > 0:
            cleaned_lines.append(f"• {bullet_match.group(1).strip()}")
            continue

        num_bullet_match = re.match(r'^\d+[\.\)]\s*(.*)$', stripped)
        if num_bullet_match and len(num_bullet_match.group(1)) > 0:
            cleaned_lines.append(f"• {num_bullet_match.group(1).strip()}")
            continue

        # Strip noisy OCR scanner lines and artifact tokens (e.g., '-------', '_______', '======', '| | | | ~~~')
        if len(stripped) >= 4 and not re.search(r'[a-zA-Z0-9\u0980-\u09FF]', stripped):
            continue

        cleaned_lines.append(stripped)

    joined = "\n".join(cleaned_lines)
    
    # 2. Collapse 3+ consecutive newlines to 2
    joined = re.sub(r'\n{3,}', '\n\n', joined)

    # 3. Fix common Bengali OCR spacing artifacts where hasant/matras get disconnected
    joined = re.sub(r'([\u0980-\u09FF])\s+([\u09BE-\u09CD])', r'\1\2', joined)
    joined = re.sub(r'([\u0980-\u09FF]\u09CD)\s+([\u0980-\u09FF])', r'\1\2', joined)

    # 4. Repair intra-word letter spacing where words are delimited by multi-spaces
    repaired_lines = []
    for line in joined.splitlines():
        if "  " in line and re.search(r'[\u0980-\u09FF]', line):
            words = []
            for word_chunk in re.split(r'\s{2,}', line):
                tokens = [t for t in word_chunk.split(' ') if t]
                if len(tokens) > 1 and all(len(t) <= 4 and re.search(r'[\u0980-\u09FF]', t) for t in tokens):
                    words.append(''.join(tokens))
                else:
                    words.append(word_chunk)
            repaired_lines.append(" ".join(words))
        else:
            repaired_lines.append(line)
    joined = "\n".join(repaired_lines)

    return joined.strip()

def perform_local_ocr(image_bytes: bytes, lang: str = "eng+ben") -> str:
    """
    Runs local Tesseract OCR on preprocessed image bytes.
    Gracefully falls back to 'eng' if Bengali language pack is not installed.
    """
    tess_bin = find_tesseract_binary()
    if not tess_bin:
        logger.info("Local Tesseract binary not found on system.")
        return ""

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = tess_bin
        
        optimized_bytes, _ = preprocess_image_for_ocr(image_bytes)
        img = Image.open(io.BytesIO(optimized_bytes))

        # Try specified language pack
        try:
            raw_text = pytesseract.image_to_string(img, lang=lang)
        except Exception:
            # Fallback to standard English
            raw_text = pytesseract.image_to_string(img, lang="eng")

        return optimize_ocr_text(raw_text)
    except Exception as e:
        logger.warning(f"Local Tesseract OCR failed: {e}")
        return ""

def perform_ai_vision_ocr(
    media_bytes: bytes,
    mime_type: str,
    provider: str,
    api_key: str,
    model_name: str = "",
    language_hint: str = "auto"
) -> Dict[str, Any]:
    """
    Executes high-accuracy multimodal OCR using Google Gemini or OpenAI Vision.
    Extracts verbatim text, structural tables, headers, signatures, and stamps.
    """
    api_key = (api_key or "").strip()
    provider = (provider or "gemini").lower()

    ocr_system_prompt = (
        "You are an expert Chief Document Optical Character Recognition (OCR) and Layout Extraction AI. "
        "Your task is to transcribe EVERY detail from this document, photo, or scan with 100% precision.\n\n"
        "GUIDELINES:\n"
        "1. Extract ALL text verbatim in its original script (Bengali বাংলা and English).\n"
        "2. Accurately capture handwritten notes, marginalia, signatures, seals, and official stamps.\n"
        "3. Preserve all table structures, numbering (1, 2, 3... / ১, ২, ৩...), bullet hierarchies, and columns.\n"
        "4. Capture dates, Memo/Smashok numbers (স্মারক নং), subject lines, titles, and recipient/attendee lists.\n"
        "5. Correct obvious physical OCR scan distortions (e.g. tilted characters, faded ink, smudge spots).\n"
        "6. Return the clean, optimized, fully extracted text in a clear hierarchical markdown format with tables."
    )

    # 1. Google Gemini Multimodal Vision / Document OCR
    if provider == "gemini" or api_key.startswith("AIzaSy") or api_key.startswith("AQ."):
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        models_to_try = [model_name or "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash"]
        models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))

        # Optimize image if not PDF
        target_bytes = media_bytes
        target_mime = mime_type or "image/jpeg"
        if target_mime != "application/pdf":
            target_bytes, target_mime = preprocess_image_for_ocr(media_bytes)

        part = types.Part.from_bytes(data=target_bytes, mime_type=target_mime)

        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[ocr_system_prompt, part]
                )
                if response and response.text:
                    clean_text = optimize_ocr_text(response.text)
                    return {
                        "success": True,
                        "provider": "gemini",
                        "model": model,
                        "text": clean_text
                    }
            except Exception as e:
                logger.warning(f"Gemini OCR attempt with {model} failed: {e}")

    # 2. OpenAI Multimodal Vision (gpt-4o / gpt-4o-mini)
    elif provider == "openai" or api_key.startswith("sk-"):
        import httpx

        target_bytes, target_mime = preprocess_image_for_ocr(media_bytes) if mime_type != "application/pdf" else (media_bytes, mime_type)
        b64_img = base64.b64encode(target_bytes).decode("utf-8")
        data_url = f"data:{target_mime};base64,{b64_img}"

        model = model_name or "gpt-4o"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": ocr_system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please perform full OCR and layout extraction on this document:"},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "temperature": 0.1
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"]
                    clean_text = optimize_ocr_text(raw_text)
                    return {
                        "success": True,
                        "provider": "openai",
                        "model": model,
                        "text": clean_text
                    }
        except Exception as e:
            logger.warning(f"OpenAI Vision OCR failed: {e}")

    # Fallback to local Tesseract
    local_txt = perform_local_ocr(media_bytes)
    if local_txt:
        return {
            "success": True,
            "provider": "local_tesseract",
            "model": "tesseract",
            "text": local_txt
        }

    return {
        "success": False,
        "provider": provider,
        "model": model_name,
        "text": ""
    }
