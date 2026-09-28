import os
import re
import json
import base64
import time
import httpx
import io
import wave
import struct
import math
import random
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)
except Exception:
    pass

from google import genai
from google.genai import types
from document_engine import DEFAULT_MEMBERS
from ocr_engine import optimize_ocr_text, preprocess_image_for_ocr
from diag_logging import get_logger, describe_exception, fmt_ts, redact_key, current_job_id
_stt_log = get_logger("stt")
try:
    import google.genai as _genai_pkg
    _GENAI_VERSION = getattr(_genai_pkg, "__version__", "?")
except Exception:
    _GENAI_VERSION = "?"

DEFAULT_WHISPER_PROMPT = (
    "EASD Eminence Associates for Social Development. "
    "বাংলা এবং English আলোচনা ও কার্যবিবরণী। "
    "Agenda, follow-up, decisions, action items, participants, Dr. Shamim Talukder."
)

LLM_SYSTEM_PROMPT = """
You are an expert bilingual Chief Executive Rapporteur and AI Documentation Director for Eminence Associates for Social Development (EASD).
The input provided to you is a raw meeting transcript, draft notes, or audio transcription in mixed Bangla + English.

Your task is to DEEPLY ANALYZE, REWRITE, RESTRUCTURE, and SYNTHESIZE the raw content into formal, high-impact executive meeting minutes.

You must produce a valid JSON object with the following schema:
{
  "detected_language": "bn",
  "bangla_transcript": "বাংলা ভাষায় সম্পূর্ণ প্রাতিষ্ঠানিক, সাবলীল এবং বিস্তারিত মিটিং বিবরণ (অনুবাদ ও পরিমার্জনসহ)।",
  "english_transcript": "Comprehensive, formal, and polished English executive meeting record.",
  "summary": {
    "title": "Specific Formal Meeting Title",
    "location": "Meeting Venue (e.g. Eminence Conference Room, Mohakhali DOHS, Dhaka / Online Zoom)",
    "date": "Extracted Date (e.g. 29 August, 2026)",
    "time": "Extracted Time (e.g. 11:00 AM - 01:00 PM)",
    "agendas": [
      "Agenda title with clear programmatic focus without number prefixes",
      "Second agenda title",
      "Third agenda title",
      "Fourth agenda title",
      "Fifth agenda title"
    ],
    "discussions": [
      {
        "sn": "1",
        "topic": "Followup from previous meeting",
        "details": "• Summary of progress made on all items raised in the prior meeting.\n• Outstanding issues and resolution status with accountable team leads."
      },
      {
        "sn": "2",
        "topic": "Action items",
        "details": "All action directives issued during this session with responsible owners.\n• Deadlines, quality benchmarks, and compliance requirements per action."
      },
      {
        "sn": "3",
        "topic": "Task Assignments",
        "details": "Specific tasks allocated to named team leads with agreed delivery timelines.\n• Workstream ownership confirmed by the meeting chair."
      },
      {
        "sn": "4",
        "topic": "Meeting Decisions",
        "details": "All formally approved strategic and institutional decisions taken in this session.\n• Locked deadlines, approved frameworks, and next scheduled review date."
      }
    ],
    "decisions": "Formally approved strategic decisions.\n• Locked submission deadlines and milestone commitments.\n• Directives for institutional compliance and next review schedule.",
    "present_members": [
      "Names of all team members who participated, presented, or were assigned tasks"
    ]
  }
}

INSTRUCTIONS:
1. Do NOT simply copy-paste raw fragments. Synthesize and upgrade raw bullet points into formal executive prose.
2. Table 0 MUST always have EXACTLY 4 discussion rows — use these EXACT topic names (match the template document):
   Row 1: "Followup from previous meeting" — status of prior action items and pending issues.
   Row 2: "Action items" — all concrete action directives issued in this session with owners.
   Row 3: "Task Assignments" — named task allocations with delivery timelines per team lead.
   Row 4: "Meeting Decisions" — all formally approved strategic decisions, deadlines, and next review date.
3. Formulate 4 to 5 concise meeting agendas matching the 4 discussion themes. IMPORTANT: Do NOT include number prefixes like "1.", "2." inside the agenda text strings.
4. Each bullet in "details" and "decisions" MUST begin with a single bullet symbol ("• ") — do NOT output duplicate bullets ("• •") or tabs ("•\t•").
5. The 'decisions' field in the JSON should mirror/summarize Row 4 (Meeting Decisions).
6. Return ONLY the JSON object — no markdown fencing, no extra text.
"""

def clean_agenda_item(text: str) -> str:
    """Strips any leading numbering, double numbering, or bullet symbols from an agenda item."""
    if not text:
        return ""
    cleaned = re.sub(r'^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\u2022\u2023\u25E6\u2043\u2219\t]+\s*)+', '', str(text).strip())
    cleaned = re.sub(r'^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\u2022\u2023\u25E6\u2043\u2219\t]+\s*)+', '', cleaned).strip()
    return cleaned

def clean_bullet_points(text: str) -> str:
    """Ensures each line starts with exactly one single bullet point (• ) and strips duplicate bullets/numbers."""
    if not text:
        return ""
    cleaned_lines = []
    for line in str(text).splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        content = re.sub(r'^(?:[•\-\*\u2022\u2023\u25E6\u2043\u2219\t\s]|\d+[\.\)\:\-]\s*)+', '', line_str).strip()
        if content:
            cleaned_lines.append(f"• {content}")
    return "\n".join(cleaned_lines)

def detect_text_language(text: str) -> str:
    """Detects whether text is primarily Bangla ('bn') or English ('en')."""
    if not text:
        return "bn"
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    if bengali_chars > 0 and (bengali_chars >= latin_chars * 0.25):
        return "bn"
    elif latin_chars > bengali_chars:
        return "en"
    return "bn"

def extract_and_repair_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses JSON from raw LLM output, with robust markdown cleanup and bracket balancing."""
    cleaned = raw_text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find the outermost JSON block { ... }
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Clean trailing commas
        fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    return None

def match_attendance_list(present_names: List[str], text_corpus: str = "") -> List[Dict[str, str]]:
    """Matches detected attendee names against the default 21 EASD members."""
    results = []
    text_corpus_lower = text_corpus.lower() if text_corpus else ""

    for item in DEFAULT_MEMBERS:
        mem_name = item["name"]
        mem_norm = mem_name.lower().replace("dr.", "").replace("mr.", "").replace("ms.", "").strip()

        is_present = False
        for p in present_names:
            p_norm = p.lower().replace("dr.", "").replace("mr.", "").replace("ms.", "").strip()
            if len(p_norm) >= 3 and (p_norm in mem_norm or mem_norm in p_norm):
                is_present = True
                break

        if not is_present and text_corpus_lower:
            parts = [pt for pt in mem_norm.split() if len(pt) >= 4]
            if any(pt in text_corpus_lower for pt in parts):
                is_present = True

        results.append({
            "serial": item["serial"],
            "name": mem_name,
            "participation": "Yes" if is_present else "No"
        })
    return results

_DATE_PATTERNS = [
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*,?\s+\d{4}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b",
]
_TIME_PATTERN = r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b(?:\s*(?:-|to|–)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?"
_STANDING_FIELD_KEYS = {"location", "ministry", "department", "author", "authors", "media_contact",
                        "signatory", "project_lead", "survey_team", "dateline"}


def _strip_transcript_prefix(line: str) -> str:
    """'[12:30] Speaker 2: text' -> 'text'. Gap markers are dropped entirely."""
    if "TRANSCRIPT GAP" in line:
        return ""
    return re.sub(r"^\[[\d:]+\]\s*(?:⚠\s*)?(?:Speaker\s*\d+\s*:)?\s*", "", line).strip()


def deep_semantic_synthesis(
    raw_text: str,
    custom_skills: str = "",
    org_context: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Offline, zero-cost template filling used when no cloud LLM is reachable.

    v8.3 rule: this function NEVER invents content. Every value it writes is either
    (a) text found in the transcript, (b) a standing organisational default from the
    template (e.g. venue), or (c) left empty for the user to complete. Dates/times are
    only filled when they literally appear in the transcript.
    """
    from template_engine import DEFAULT_TEMPLATES
    tpl = template_schema or next((t for t in DEFAULT_TEMPLATES if t.get("id") == "easd_default_minutes"), DEFAULT_TEMPLATES[0])
    cleaned_input = str(raw_text or "").strip()
    lang = detect_text_language(cleaned_input)
    doc_type = tpl.get("doc_type") or "meeting_minutes"
    utterances = [u for u in (_strip_transcript_prefix(l) for l in cleaned_input.splitlines()) if u]
    corpus_lower = "\n".join(utterances).lower()

    def find_bullets(patterns: List[str], max_count: int = 5) -> str:
        hits, seen = [], set()
        for u in utterances:
            ul = u.lower()
            if any(re.search(p, ul) for p in patterns):
                clean_u = re.sub(r"^(?:[•\-\*\d\.\)\:]\s*)+", "", u).strip()
                if len(clean_u) > 8 and clean_u not in seen:
                    seen.add(clean_u)
                    hits.append(f"• {clean_u}")
            if len(hits) >= max_count:
                break
        return clean_bullet_points("\n".join(hits)) if hits else ""

    def find_date() -> str:
        for pat in _DATE_PATTERNS:
            m = re.search(pat, corpus_lower, re.I)
            if m:
                return m.group(0).strip().title()
        return ""

    def find_time() -> str:
        m = re.search(_TIME_PATTERN, corpus_lower, re.I)
        return m.group(0).upper() if m else ""

    def keyword_patterns(sec: Dict[str, Any]) -> List[str]:
        words = re.findall(r"[a-zA-Z]{4,}", f"{sec.get('id', '')} {sec.get('title', '')}".replace("_", " "))
        stop = {"meeting", "section", "details", "with", "from", "and", "the", "wise", "point", "points"}
        pats = [re.escape(w.lower()) for w in words if w.lower() not in stop]
        extra = {
            "decisions": [r"decision", r"সিদ্ধান্ত", r"agreed", r"approved", r"গৃহীত"],
            "recommendations": [r"recommend", r"সুপারিশ", r"suggest"],
            "observations": [r"observ", r"পর্যবেক্ষণ", r"found", r"finding"],
            "next_steps": [r"next step", r"will ", r"করণীয়"],
            "key_quotes": [r"said", r"stated", r"বলেন"],
        }
        return pats + extra.get(sec.get("id", ""), [])

    summary: Dict[str, Any] = {}
    sections_data: Dict[str, Any] = {}
    tables_data: Dict[str, Any] = {}

    # Fields
    for fld in tpl.get("fields", []):
        key = fld.get("key", "")
        if not key:
            continue
        if "date" in key:
            val = find_date()
        elif "time" in key or "period" in key:
            val = find_time() if "time" in key else ""
        elif key in _STANDING_FIELD_KEYS or (key == "title" and doc_type == "meeting_minutes"):
            val = fld.get("default", "")
        elif key in ("title", "subject") and utterances:
            first = re.split(r"(?<=[.!?।])\s", utterances[0])[0].strip()
            val = first if len(first) <= 90 else first[:87].rsplit(" ", 1)[0] + "..."
        else:
            val = ""
        summary[key] = val

    # Sections
    for sec in tpl.get("sections", []):
        sid, stype = sec.get("id", ""), sec.get("type", "text")
        if not sid:
            continue
        if sid == "agendas" or stype == "list":
            val: Any = []
        elif stype == "bullets":
            val = find_bullets(keyword_patterns(sec))
        else:
            val = find_bullets(keyword_patterns(sec), max_count=3).replace("• ", "")
        summary[sid] = val
        sections_data[sid] = val

    # Tables
    for tbl in tpl.get("tables", []):
        tid = tbl.get("id", "")
        if tid == "discussions":
            rows = [
                {"sn": "1", "topic": "Followup from previous meeting",
                 "details": find_bullets([r"follow[\s\-]?up", r"পূর্ববর্তী", r"আগের সভা", r"previous meeting", r"last meeting"])},
                {"sn": "2", "topic": "Action items",
                 "details": find_bullets([r"action item", r"করণীয়", r"পদক্ষেপ", r"will (?:do|prepare|send|submit|share)"])},
                {"sn": "3", "topic": "Task Assignments",
                 "details": find_bullets([r"assign", r"দায়িত্ব", r"responsible", r"in charge", r"deadline"])},
                {"sn": "4", "topic": "Meeting Decisions",
                 "details": find_bullets([r"decision", r"সিদ্ধান্ত", r"approved", r"agreed", r"গৃহীত"])},
            ]
        elif tid == "attendance":
            present = []
            for mem in DEFAULT_MEMBERS:
                parts = [p.lower() for p in mem["name"].split() if len(p) >= 4]
                if parts and any(p in corpus_lower for p in parts):
                    present.append(mem["name"])
            rows = match_attendance_list(present, cleaned_input)
            summary["present_members"] = present
        elif tbl.get("fixed_rows"):
            rows = [dict(r) for r in tbl["fixed_rows"]]
        else:
            rows = []
        summary[tid] = rows
        tables_data[tid] = rows

    if doc_type == "meeting_minutes":
        summary.setdefault("agendas", [])
        summary["decisions"] = summary.get("decisions") or (tables_data.get("discussions", [{}] * 4)[3].get("details", "") if tables_data.get("discussions") else "")
        sections_data["decisions"] = summary["decisions"]

    summary["sections_data"] = sections_data
    summary["tables_data"] = tables_data
    return {
        "detected_language": lang,
        "raw_transcript": cleaned_input,
        "transcript": cleaned_input,
        "bangla_transcript": cleaned_input if lang == "bn" else "",
        "english_transcript": cleaned_input if lang == "en" else "",
        "summary": summary,
        "doc_type": doc_type,
        "summary_source": "offline_extraction",
    }

def build_template_system_prompt(
    template_schema: Optional[Dict[str, Any]] = None,
    org_context: str = "",
    custom_skills: str = ""
) -> str:
    """Builds the AI system prompt tailored to the active template, injecting its exact JSON Schema and example."""
    from template_engine import get_template_json_schema, get_template_json_example, DEFAULT_TEMPLATES

    target_tpl = template_schema or DEFAULT_TEMPLATES[0]
    
    # 1. Base AI Role
    ai_role = target_tpl.get("ai_system_prompt")
    if not ai_role:
        ai_role = (
            "You are an expert bilingual Chief Executive Rapporteur and AI Documentation Director. "
            "Your task is to DEEPLY ANALYZE, REWRITE, RESTRUCTURE, and SYNTHESIZE raw spoken notes, "
            "transcripts, or audio into formal, authoritative institutional documentation."
        )

    # 2. Template Directives
    tpl_name = target_tpl.get("name", "Document")
    context_str = target_tpl.get("context", "")
    rules_str = target_tpl.get("rules", "")
    reqs_str = target_tpl.get("requirements", "")

    # 3. Retrieve JSON Schema and JSON Example
    json_schema = get_template_json_schema(target_tpl)
    json_example = get_template_json_example(target_tpl)
    schema_formatted = json.dumps(json_schema, indent=2, ensure_ascii=False)
    example_formatted = json.dumps(json_example, indent=2, ensure_ascii=False)

    prompt = (
        f"{ai_role}\n\n"
        f"DOCUMENT TARGET: {tpl_name}\n"
        f"====================================================\n"
        f"CONTEXT & PURPOSE:\n{context_str}\n\n"
        f"CORE EDITING RULES:\n{rules_str}\n\n"
        f"OUTPUT REQUIREMENTS:\n{reqs_str}\n"
        f"====================================================\n\n"
        f"CRITICAL JSON OUTPUT DIRECTIVE:\n"
        f"You MUST produce a valid JSON object strictly conforming to this JSON Schema:\n\n"
        f"```json\n{schema_formatted}\n```\n\n"
        f"EXACT OUTPUT JSON STRUCTURE & ILLUSTRATIVE EXAMPLE:\n"
        f"```json\n{example_formatted}\n```\n\n"
        f"STRICT FORMATTING DIRECTIVES:\n"
        f"1. Output ONLY the raw JSON object. Do NOT wrap in markdown formatting (no ```json or ``` fences), and do NOT add any introductory or concluding text.\n"
        f"2. Every field, section, and table in the schema MUST be populated with meaningful, high-impact synthesized content.\n"
        f"3. For bulleted points or details, EVERY point MUST begin with exactly one single bullet symbol ('• '). NEVER use double bullets ('• •') or numbers with bullets.\n"
        f"4. If meeting minutes, ensure discussions table has exactly 4 rows (Followup from previous meeting, Action items, Task Assignments, Meeting Decisions).\n"
        f"5. Maintain bilingual fidelity: provide rich, formal Bengali in 'bangla_transcript' and polished English in 'english_transcript'.\n"
        f"6. GROUNDING: use ONLY facts stated in the transcript. Do NOT invent names, numbers, dates, times, venues or decisions. "
        f"If a field's value is not in the transcript, return an empty string for it (\"\").\n"
        f"7. Lines containing 'TRANSCRIPT GAP' mark audio that could not be transcribed. Never guess what was said there; "
        f"if a gap affects a section, you may note '(part of the recording was not transcribed)'.\n"
        f"8. Do NOT copy values from the illustrative example above - it only shows the shape of the JSON."
    )

    if org_context and org_context.strip():
        prompt += f"\n\nORGANIZATIONAL CONTEXT:\n{org_context.strip()}"
    if custom_skills and custom_skills.strip():
        prompt += f"\n\nACTIVE CUSTOM DIRECTIVES:\n{custom_skills.strip()}"

    return prompt

def process_extracted_payload(
    raw_text: str,
    fallback_content: str = "",
    custom_skills: str = "",
    org_context: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Parses and standardizes extracted LLM output according to target template schema."""
    parsed = extract_and_repair_json(raw_text)
    doc_type = (template_schema.get("doc_type") if template_schema else None) or "meeting_minutes"

    if parsed and isinstance(parsed, dict):
        summary = parsed.get("summary")
        if not isinstance(summary, dict) or not summary:
            # Check if LLM returned summary fields at the root of parsed
            summary = {k: v for k, v in parsed.items() if k not in ["detected_language", "raw_transcript", "transcript", "bangla_transcript", "english_transcript"]}

        # Initialize sections_data and tables_data maps
        sections_data = summary.get("sections_data") if isinstance(summary.get("sections_data"), dict) else {}
        tables_data = summary.get("tables_data") if isinstance(summary.get("tables_data"), dict) else {}

        # Standardize fields defined in the template
        if template_schema:
            for fld in template_schema.get("fields", []):
                f_key = fld.get("key", "")
                if not f_key:
                    continue
                missing = f_key not in summary or summary.get(f_key) is None or not str(summary.get(f_key)).strip()
                if missing:
                    if "date" in f_key or "time" in f_key:
                        summary[f_key] = ""  # sample dates would be wrong for every other meeting
                    elif f_key in _STANDING_FIELD_KEYS or (f_key == "title" and doc_type == "meeting_minutes"):
                        summary[f_key] = fld.get("default", "")  # standing organisational value (e.g. venue)
                    else:
                        summary[f_key] = summary.get(f_key) or ""

            # Standardize sections defined in the template
            for sec in template_schema.get("sections", []):
                sec_id = sec.get("id", "")
                sec_type = sec.get("type", "text")
                raw_sec_val = summary.get(sec_id) if summary.get(sec_id) is not None else sections_data.get(sec_id, "")
                
                if sec_type == "bullets":
                    cleaned_val = clean_bullet_points(str(raw_sec_val))
                    summary[sec_id] = cleaned_val
                    sections_data[sec_id] = cleaned_val
                elif sec_type == "list":
                    if isinstance(raw_sec_val, list):
                        cleaned_list = [clean_agenda_item(a) for a in raw_sec_val if a]
                    else:
                        cleaned_list = [clean_agenda_item(l) for l in str(raw_sec_val).splitlines() if clean_agenda_item(l)]
                    summary[sec_id] = cleaned_list
                    sections_data[sec_id] = cleaned_list
                else: # text
                    summary[sec_id] = str(raw_sec_val).strip()
                    sections_data[sec_id] = str(raw_sec_val).strip()

            # Standardize tables defined in the template
            for tbl in template_schema.get("tables", []):
                tbl_id = tbl.get("id", "")
                tbl_rows = summary.get(tbl_id) if summary.get(tbl_id) is not None else tables_data.get(tbl_id, [])
                if isinstance(tbl_rows, list):
                    tables_data[tbl_id] = tbl_rows
                    summary[tbl_id] = tbl_rows

        # Specific standardizations for meeting_minutes
        if doc_type == "meeting_minutes" or template_schema is None:
            discussions = summary.get("discussions", [])
            if not isinstance(discussions, list) or len(discussions) == 0:
                discussions = [
                    {"sn": "1", "topic": "Followup from previous meeting", "details": clean_bullet_points(summary.get("followup", ""))},
                    {"sn": "2", "topic": "Action items", "details": clean_bullet_points(summary.get("action_items", ""))},
                    {"sn": "3", "topic": "Task Assignments", "details": clean_bullet_points(summary.get("tasks", ""))},
                    {"sn": "4", "topic": "Meeting Decisions", "details": clean_bullet_points(summary.get("decisions", ""))}
                ]
            else:
                for d in discussions:
                    if isinstance(d, dict):
                        d["details"] = clean_bullet_points(d.get("details", ""))
            summary["discussions"] = discussions
            tables_data["discussions"] = discussions

            summary["decisions"] = clean_bullet_points(summary.get("decisions", ""))
            sections_data["decisions"] = summary["decisions"]

            raw_agendas = summary.get("agendas", [])
            if isinstance(raw_agendas, list):
                summary["agendas"] = [clean_agenda_item(a) for a in raw_agendas if a]
            elif isinstance(raw_agendas, str):
                summary["agendas"] = [clean_agenda_item(a) for a in raw_agendas.splitlines() if clean_agenda_item(a)]
            sections_data["agendas"] = summary.get("agendas", [])

            present_names = summary.get("present_members", [])
            if not summary.get("attendance"):
                summary["attendance"] = match_attendance_list(present_names, fallback_content or raw_text)
            tables_data["attendance"] = summary["attendance"]

        # Ensure sections_data and tables_data are attached in summary
        summary["sections_data"] = sections_data
        summary["tables_data"] = tables_data

        # The source transcript is authoritative; never replace it with the LLM's rewrite.
        raw_tx = fallback_content if (fallback_content or "").strip() else (parsed.get("raw_transcript") or parsed.get("transcript") or "")
        return {
            "detected_language": parsed.get("detected_language", detect_text_language(raw_tx)),
            "raw_transcript": raw_tx,
            "transcript": raw_tx,
            "bangla_transcript": parsed.get("bangla_transcript") or "",
            "english_transcript": parsed.get("english_transcript") or "",
            "summary": summary,
            "doc_type": doc_type,
            "summary_source": "llm"
        }

    return deep_semantic_synthesis(fallback_content or raw_text, custom_skills, org_context, template_schema)

# --- CONFIGURATION & PERSISTENCE HELPERS ---

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_settings.json")
GEMINI_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GeminiAPI.txt")

def get_default_api_key_from_disk() -> Dict[str, str]:
    """Retrieves default Gemini API key and active providers from disk."""
    gemini_key = ""
    if os.path.exists(GEMINI_KEY_FILE):
        try:
            with open(GEMINI_KEY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    c = line.split("#")[0].strip()
                    if c and (c.startswith("AIzaSy") or c.startswith("AQ.")):
                        gemini_key = c
                        break
        except Exception:
            pass

    cfg = load_api_settings_from_disk()
    key = cfg.get("gemini_api_key") or gemini_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

    return {
        "provider": cfg.get("transcription_provider", "gemini"),
        "api_key": key,
        "transcription_model": cfg.get("transcription_model", "gemini-3.5-transcribe"),
        "summarization_model": cfg.get("summarization_model", "gemini-3.8-flash")
    }

def load_api_settings_from_disk() -> Dict[str, Any]:
    """Loads persistent settings from api_settings.json and environment variables."""
    default_settings = {
        "transcription_provider": "gemini",
        "transcription_model": "gemini-3.5-transcribe",
        "summarization_provider": "gemini",
        "summarization_model": "gemini-3.8-flash",
        "gemini_api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
        "local_whisper_model": "whisper-small",
        "custom_api_base_url": os.getenv("CUSTOM_API_BASE_URL") or "",
        "custom_api_key": os.getenv("CUSTOM_API_KEY") or "",
        "custom_api_model": os.getenv("CUSTOM_API_MODEL") or ""
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    default_settings.update(saved)
        except Exception:
            pass
    # If settings file had empty keys, fallback to environment
    if not default_settings.get("gemini_api_key"):
        default_settings["gemini_api_key"] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not default_settings.get("custom_api_key"):
        default_settings["custom_api_key"] = os.getenv("CUSTOM_API_KEY") or ""
    if not default_settings.get("custom_api_base_url"):
        default_settings["custom_api_base_url"] = os.getenv("CUSTOM_API_BASE_URL") or ""
    if not default_settings.get("custom_api_model"):
        default_settings["custom_api_model"] = os.getenv("CUSTOM_API_MODEL") or ""

    return default_settings

def save_api_settings_to_disk(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Saves settings to api_settings.json and synchronizes active keys to environment variables and .env."""
    current = load_api_settings_from_disk()
    current.update({k: v for k, v in settings.items() if v is not None})
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    # Sync environment variables in process
    if current.get("gemini_api_key"):
        os.environ["GEMINI_API_KEY"] = current["gemini_api_key"].strip()
    if current.get("custom_api_key"):
        os.environ["CUSTOM_API_KEY"] = current["custom_api_key"].strip()
    if current.get("custom_api_base_url"):
        os.environ["CUSTOM_API_BASE_URL"] = current["custom_api_base_url"].strip()
    if current.get("custom_api_model"):
        os.environ["CUSTOM_API_MODEL"] = current["custom_api_model"].strip()

    # Sync to .env file (safely ignored from git commits by .gitignore)
    env_file = os.path.join(BASE_DIR, ".env")
    try:
        lines = [
            "# EASD AI Engine Environment Configuration",
            "# DO NOT COMMIT OR SHARE THIS FILE (ignored in .gitignore)",
            f"GEMINI_API_KEY={current.get('gemini_api_key', '')}",
            f"CUSTOM_API_KEY={current.get('custom_api_key', '')}",
            f"CUSTOM_API_BASE_URL={current.get('custom_api_base_url', '')}",
            f"CUSTOM_API_MODEL={current.get('custom_api_model', '')}",
            f"EASD_TRANSCRIPTION_PROVIDER={current.get('transcription_provider', 'gemini')}",
            f"EASD_SUMMARIZATION_PROVIDER={current.get('summarization_provider', 'gemini')}",
        ]
        with open(env_file, "w", encoding="utf-8") as ef:
            ef.write("\n".join(lines) + "\n")
    except Exception:
        pass

    # Sync to GeminiAPI.txt if updated
    if current.get("gemini_api_key"):
        try:
            with open(GEMINI_KEY_FILE, "w", encoding="utf-8") as gf:
                gf.write(current["gemini_api_key"].strip())
        except Exception:
            pass

    return current

def _requested_whisper_model(provider: str, model_name: str = "") -> str:
    """
    The Whisper size the user actually chose. For the local provider the request's own
    model_name wins (e.g. 'medium'); otherwise the saved 'local_whisper_model' setting.
    '' / 'auto' means automatic selection (local_whisper_engine.resolve_whisper_model_choice).
    """
    if (provider or "").lower() in ("local_whisper", "local", "whisper_local") and model_name \
            and not model_name.lower().startswith("gemini"):
        return model_name
    return str(load_api_settings_from_disk().get("local_whisper_model") or "auto")


# Provider ids accepted for the OpenAI-compatible custom endpoint (normalised to "openai_compatible").
_OPENAI_COMPAT_ALIASES = ("openai_compatible", "openai-compatible", "openai", "custom", "openrouter")


def _local_llm_user_reason(err: Exception) -> str:
    """Plain-language reason for a local-LLM failure (the raw exception is only logged)."""
    text = f"{type(err).__name__}: {err}".lower()
    if "not installed" in text or "importerror" in text or "no module named" in text:
        return "the on-device model software is not installed"
    if "not found" in text or "download" in text or "filenotfound" in text or ".gguf" in text:
        return "the on-device model file is not downloaded yet"
    if "unparseable" in text:
        return "the on-device model's answer could not be read"
    return "it failed while generating - details are in the app log"


def is_fatal_auth_error(err: Exception) -> bool:
    """Returns True if the error indicates a fatal permission/key denial or unavailable model (no retrying needed)."""
    s = str(err).lower()
    return any(p in s for p in [
        "401", "403", "permission_denied", "api_key_invalid",
        "unauthorized", "denied access", "project has been denied",
        "not_found", "no longer available", "invalid_argument"
    ])

def ping_openai_compatible(base_url: Optional[str] = None, api_key: Optional[str] = None, model_name: Optional[str] = None,
                           timeout: float = 10.0) -> Dict[str, Any]:
    """
    Lightweight reachability/auth check for an OpenAI-compatible endpoint: GET {base_url}/models
    (supported by OpenRouter, DeepSeek, Ollama and LM Studio). Falls back to the saved
    custom_api_* settings when arguments are None. Returns {valid, success, message, latency_ms, status_code, model_listed}.
    """
    cfg = load_api_settings_from_disk()
    root = (base_url if base_url is not None else (cfg.get("custom_api_base_url") or "")).strip().rstrip("/")
    key = (api_key if api_key is not None else (cfg.get("custom_api_key") or "")).strip()
    model = (model_name if model_name is not None else (cfg.get("custom_api_model") or "")).strip()
    t0 = time.time()
    if not root:
        return {"valid": False, "success": False, "latency_ms": 0, "status_code": None,
                "message": "Custom API Base URL is empty. Enter it in Settings."}
    url = f"{root}/models"
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    _oac_log.info("ping GET %s key=%s", url, redact_key(key))
    try:
        resp = httpx.get(url, headers=headers, timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)))
    except httpx.ConnectError as e:
        _oac_log.error("ping connection FAILED %s: %s", url, describe_exception(e))
        return {"valid": False, "success": False, "latency_ms": round((time.time() - t0) * 1000), "status_code": None,
                "message": f"Could not connect to {root} - is the server running and the Base URL correct?"}
    except httpx.TimeoutException as e:
        _oac_log.error("ping TIMEOUT %s: %s", url, describe_exception(e))
        return {"valid": False, "success": False, "latency_ms": round((time.time() - t0) * 1000), "status_code": None,
                "message": f"{root} did not answer within {int(timeout)}s."}
    except httpx.HTTPError as e:
        _oac_log.error("ping FAILED %s: %s", url, describe_exception(e))
        return {"valid": False, "success": False, "latency_ms": round((time.time() - t0) * 1000), "status_code": None,
                "message": f"The request to {root} failed."}
    lat = round((time.time() - t0) * 1000)
    _oac_log.info("ping GET %s -> HTTP %s in %dms", url, resp.status_code, lat)
    if resp.status_code in (401, 403):
        _oac_log_body("ping AUTH rejected:", resp)
        return {"valid": False, "success": False, "latency_ms": lat, "status_code": resp.status_code,
                "message": "Custom API rejected the API key."}
    if resp.status_code >= 400:
        _oac_log_body("ping FAILED:", resp)
        return {"valid": False, "success": False, "latency_ms": lat, "status_code": resp.status_code,
                "message": f"Custom API answered with HTTP {resp.status_code} - check the Base URL."}
    model_listed = None
    try:
        ids = [m.get("id") or m.get("name") for m in (resp.json().get("data") or resp.json().get("models") or [])]
        if model:
            model_listed = model in ids
    except Exception:
        pass
    note = "" if model_listed in (None, True) else f" (model '{model}' is not in its model list - check the Model ID)"
    return {"valid": True, "success": True, "latency_ms": lat, "status_code": resp.status_code,
            "model_listed": model_listed, "message": f"Custom API reachable at {root}{note}"}


def verify_ai_api_key(provider: str, api_key: str = "", base_url: str = "") -> Dict[str, Any]:
    """Verifies Gemini API key, pings an OpenAI-compatible endpoint, or reports Local Whisper availability with latency (ms)."""
    t0 = time.time()
    prov = (provider or "gemini").lower()

    if prov in _OPENAI_COMPAT_ALIASES:
        return ping_openai_compatible(base_url=base_url, api_key=api_key)

    if prov in ["local_whisper", "local", "whisper_local"]:
        import local_whisper_engine
        diag = local_whisper_engine.get_engine_status()
        lat = round((time.time() - t0) * 1000)
        return {
            "valid": True,
            "success": True,
            "message": f"Local Whisper Engine ready ({diag.get('model_name')}, {diag.get('threads')} threads, {lat}ms)",
            "latency_ms": lat
        }

    key = (api_key or "").strip()
    if not key:
        disk_info = get_default_api_key_from_disk()
        key = disk_info.get("api_key", "").strip()

    if not key:
        return {
            "valid": False,
            "success": False,
            "message": "Gemini API key is empty. Enter key in Settings or save to GeminiAPI.txt.",
            "latency_ms": 0
        }

    try:
        client = genai.Client(api_key=key)
        # Fast lightweight ping using models.list or tiny generate_content
        models = client.models.list()
        lat = round((time.time() - t0) * 1000)
        return {
            "valid": True,
            "success": True,
            "message": f"Google Gemini API verified & active ({lat}ms)!",
            "latency_ms": lat
        }
    except Exception as e:
        lat = round((time.time() - t0) * 1000)
        return {
            "valid": False,
            "success": False,
            "message": f"Gemini Key error: {str(e)[:180]}",
            "latency_ms": lat
        }

def generate_synthetic_test_wav() -> bytes:
    """Generates a minimal valid PCM WAV byte payload for rapid ping testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        data = bytearray()
        for i in range(1600):
            val = int(3000 * math.sin(2 * math.pi * 440 * (i / 16000)))
            data.extend(struct.pack("<h", val))
        wf.writeframes(data)
    buf.seek(0)
    return buf.read()

def test_transcription_engine(
    provider: str = "gemini",
    api_key: str = "",
    model_name: str = "gemini-3.5-transcribe",
    base_url: str = ""
) -> Dict[str, Any]:
    """Tests the STT Transcription engine (Gemini 3.5 Transcribe or Local Whisper)."""
    t0 = time.time()
    prov = (provider or "gemini").lower()

    if prov in _OPENAI_COMPAT_ALIASES:
        return ping_openai_compatible(base_url=base_url, api_key=api_key, model_name=model_name)

    if prov in ["local_whisper", "local", "whisper_local"]:
        import stt_pipeline
        st = stt_pipeline.whisper_status(_requested_whisper_model(prov, model_name))
        lat = round((time.time() - t0) * 1000)
        if not st.get("available"):
            return {"success": False, "valid": False, "message": st.get("error", "faster-whisper not installed"),
                    "latency_ms": lat, "model": None}
        if not st.get("weights_present"):
            return {"success": False, "valid": False,
                    "message": (f"Local Whisper model '{st.get('model')}' is not downloaded yet (expected in "
                                f"{st.get('path')}). It downloads automatically on first use when online."),
                    "latency_ms": lat, "model": st.get("model")}
        return {"success": True, "valid": True,
                "message": f"Local Whisper ready (model '{st.get('model')}').", "latency_ms": lat, "model": st.get("model")}

    key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()
    if not key:
        return {
            "success": False,
            "valid": False,
            "message": "Gemini API key is missing.",
            "latency_ms": 0,
            "model": model_name
        }

    try:
        client = genai.Client(api_key=key)
        wav = generate_synthetic_test_wav()
        stt_m = model_name if (model_name and "transcribe" in model_name) else "gemini-3.5-transcribe"
        resp = client.models.generate_content(
            model=stt_m,
            contents=[types.Part.from_bytes(data=wav, mime_type="audio/wav")]
        )
        lat = round((time.time() - t0) * 1000)
        return {
            "success": True,
            "valid": True,
            "message": f"Gemini 3.5 Transcribe engine ready ({lat}ms)!",
            "latency_ms": lat,
            "model": "gemini-3.5-transcribe"
        }
    except Exception as e:
        lat = round((time.time() - t0) * 1000)
        return {
            "success": False,
            "valid": False,
            "message": f"Gemini STT notice ({lat}ms): {str(e)[:160]}",
            "latency_ms": lat,
            "model": model_name
        }

def test_summarization_engine(
    provider: str = "gemini",
    api_key: str = "",
    model_name: str = "gemini-3.8-flash",
    base_url: str = ""
) -> Dict[str, Any]:
    """Tests the LLM Summarization engine (Gemini Flash, OpenAI-compatible endpoint or Local Semantic Synthesis)."""
    t0 = time.time()
    prov = (provider or "gemini").lower()

    if prov in _OPENAI_COMPAT_ALIASES:
        res = ping_openai_compatible(base_url=base_url, api_key=api_key, model_name=model_name)
        res["model"] = model_name or load_api_settings_from_disk().get("custom_api_model")
        return res

    if prov in ["local", "local_whisper", "local_llm"]:
        lat = round((time.time() - t0) * 1000)
        try:
            import local_llm_engine
            st = local_llm_engine.get_local_llm_status()
            gpu_str = " (Vulkan GPU offload)" if st.get("vulkan_supported") else " (CPU)"
            return {
                "success": True,
                "valid": True,
                "message": f"Local LLM ready ({st.get('model')}{gpu_str}, {lat}ms).",
                "latency_ms": lat,
                "model": st.get("model")
            }
        except Exception:
            return {
                "success": True,
                "valid": True,
                "message": "Local Deep Semantic Synthesis ready.",
                "latency_ms": lat,
                "model": "deep_semantic_synthesis"
            }

    key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()
    if not key:
        return {
            "success": False,
            "valid": False,
            "message": "Gemini API key is missing.",
            "latency_ms": 0,
            "model": model_name
        }

    try:
        client = genai.Client(api_key=key)
        target_model = model_name or "gemini-3.8-flash"
        cfg = None
        if "3.8" in target_model or "3.7" in target_model or "3" in target_model:
            cfg = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            )
        resp = client.models.generate_content(
            model=target_model,
            contents="Respond with 'PONG' for health check.",
            config=cfg
        )
        lat = round((time.time() - t0) * 1000)
        txt = getattr(resp, "text", "") or ""
        return {
            "success": True,
            "valid": True,
            "message": f"Gemini Flash LLM connected ({lat}ms)!",
            "latency_ms": lat,
            "model": target_model
        }
    except Exception as e:
        lat = round((time.time() - t0) * 1000)
        return {
            "success": False,
            "valid": False,
            "message": f"Gemini LLM error ({lat}ms): {str(e)[:160]}",
            "latency_ms": lat,
            "model": model_name
        }

def format_seconds_to_timestamp(seconds: float) -> str:
    """Formats seconds into [MM:SS] timestamp."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"[{m:02d}:{s:02d}]"

# --- DEFAULT IMPLEMENTATION: GEMINI 3.5 TRANSCRIBE & FLASH ---

def transcribe_audio_gemini(
    media_bytes: bytes,
    api_key: str,
    model_name: str = "gemini-3.5-transcribe",
    mime_type: str = "audio/mp3",
    language_hint: str = "auto",
    _ctx: str = ""
) -> Dict[str, Any]:
    """
    Single-buffer STT: Gemini (retry/backoff + prompt-mode fallback) then Local Whisper.
    Returns {"text", "raw_transcript", "language", "provider", "error"}; never raises.
    An empty "text" is always accompanied by a concrete "error".
    """
    import stt_pipeline
    if not media_bytes or len(media_bytes) < 32:
        return {"text": "", "raw_transcript": "", "language": "auto", "provider": None, "error": "empty audio"}
    clean_key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()
    ctx = _ctx or "[stt]"
    g = stt_pipeline.gemini_transcribe_bytes(media_bytes, clean_key, model_name, mime_type or "audio/mp3", ctx)
    if g["ok"]:
        return {"text": g["text"], "raw_transcript": g["text"], "language": detect_text_language(g["text"]),
                "provider": "gemini", "error": ""}
    w = stt_pipeline.whisper_transcribe_bytes(media_bytes, language_hint, mime_type or "audio/mp3", ctx,
                                              model_name=_requested_whisper_model("gemini"))
    if w["ok"]:
        return {"text": w["text"], "raw_transcript": w["text"], "language": w.get("language") or detect_text_language(w["text"]),
                "provider": "local_whisper", "error": "", "gemini_error": g["error"]}
    return {"text": "", "raw_transcript": "", "language": "auto", "provider": None,
            "error": f"Gemini: {g['error']} | {w['error']}"}

def live_transcribe_audio_chunk(
    media_bytes: bytes,
    api_key: str = "",
    provider: str = "gemini",
    model_name: str = "gemini-3.5-transcribe",
    mime_type: str = "audio/webm",
    language: str = "auto"
) -> Dict[str, Any]:
    """High-speed live transcription for microphone audio chunks."""
    if not media_bytes or len(media_bytes) < 32:
        return {"text": "", "language": "auto"}

    prov = (provider or "gemini").lower()
    clean_key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()

    if prov == "gemini" and clean_key:
        try:
            client = genai.Client(api_key=clean_key)
            prompt_instruction = (
                "You are an expert real-time verbatim meeting transcriptionist. "
                "CRITICAL REQUIREMENTS:\n"
                "1. Auto-detect spoken language dynamically (Bengali or English).\n"
                "2. If spoken in Bengali, transcribe in authentic Bengali script (বাংলা).\n"
                "3. If spoken in English, transcribe verbatim in English.\n"
                "4. If code-switching occurs (Bangla + English in same utterance), preserve both languages verbatim.\n"
                "5. NEVER translate. NEVER hallucinate. Output ONLY the exact words spoken with temperature 0 accuracy."
            )
            cfg = types.GenerateContentConfig(
                temperature=0.0,
                system_instruction=prompt_instruction
            )
            # Use gemini-2.5-flash for real-time low latency and multimodal audio transcription
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=media_bytes, mime_type=mime_type or "audio/webm")],
                config=cfg
            )
            txt = getattr(resp, "text", "") or ""
            if txt:
                return {"text": txt.strip(), "language": detect_text_language(txt)}
        except Exception as e:
            if is_fatal_auth_error(e):
                pass

    # Instant Fallback: Local Whisper (beam_size=1 for lowest latency)
    try:
        import local_whisper_engine
        # Respect an explicit model choice; only auto-select when none was requested
        opt_m, _src = local_whisper_engine.resolve_whisper_model_choice(_requested_whisper_model(prov, model_name))
        res = local_whisper_engine.transcribe_local_audio(
            media_input=media_bytes,
            language=None if language in ["auto", ""] else language,
            model_name=opt_m,
            mime_type=mime_type,
            beam_size=1,
            temperature=0.0
        )
        clean = local_whisper_engine.sanitize_whisper_text(res.get("raw_transcript") or res.get("clean_text", ""))
        return {"text": clean, "language": res.get("detected_language", "auto")}
    except Exception as e:
        return {"text": "", "language": "auto", "error": str(e)}

def transcribe_single_chunk(
    media_bytes: bytes,
    provider: str = "gemini",
    api_key: str = "",
    base_url: str = "",
    model_name: str = "gemini-3.5-transcribe",
    mime_type: str = "audio/mp3",
) -> str:
    """Transcribes a single audio chunk and returns verbatim text."""
    if not media_bytes or len(media_bytes) < 32:
        return ""
    prov = (provider or "gemini").lower()
    if prov in ["local_whisper", "local", "whisper_local"]:
        try:
            import local_whisper_engine
            opt_m, _ = local_whisper_engine.resolve_whisper_model_choice(_requested_whisper_model(prov, model_name))
            res = local_whisper_engine.transcribe_local_audio(
                media_input=media_bytes,
                language=None,
                model_name=opt_m,
                mime_type=mime_type or "audio/mp3",
                beam_size=1,
                temperature=0.0
            )
            return local_whisper_engine.sanitize_whisper_text(res.get("raw_transcript") or res.get("clean_text", ""))
        except Exception as e:
            return ""
    res = transcribe_audio_gemini(
        media_bytes=media_bytes,
        api_key=api_key,
        model_name=model_name or "gemini-3.5-transcribe",
        mime_type=mime_type or "audio/mp3",
    )
    if isinstance(res, dict):
        return (res.get("text") or res.get("raw_transcript") or "").strip()
    return str(res).strip() if res else ""


MAX_CONCURRENT_CHUNKS = 5

async def transcribe_chunks_parallel(
    audio_chunks: list[bytes],
    provider: str,
    api_key: str,
    base_url: str,
    model_name: str,
    mime_type: str,
) -> list[str]:
    """Transcribe all audio chunks at the same time instead of one by one."""

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)

    async def transcribe_one(index: int, chunk: bytes) -> tuple[int, str]:
        async with semaphore:
            text = await asyncio.to_thread(
                transcribe_single_chunk,
                media_bytes=chunk,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                mime_type=mime_type,
            )
            return index, text

    tasks = [transcribe_one(i, chunk) for i, chunk in enumerate(audio_chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    ordered = [None] * len(audio_chunks)
    for r in results:
        if isinstance(r, Exception):
            print(f"[transcribe_chunks_parallel] chunk failed: {r}")
            continue
        index, text = r
        ordered[index] = text

    return [t or "" for t in ordered]


def transcribe_audio_chunks_detailed(
    chunks: List[bytes],
    provider: str = "gemini",
    api_key: str = "",
    model_name: str = "gemini-3.5-transcribe",
    language: str = "auto",
    mime_type: str = "audio/mp3",
    segment_time_sec: float = 600.0,
    chunk_durations: Optional[List[float]] = None,
    base_offset_sec: float = 0.0,
    label: str = "",
    on_progress: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Multi-chunk STT with per-chunk status, word timestamps and diarization.
    Delegates to stt_pipeline using Gemini AudioTranscriptionConfig(mode="VERBATIM", diarization=True)
    or local Whisper fallback. Supports on_progress callback for real-time progress mapping.
    Contract: {status: success|partial|error, transcript, language, chunks, missing_ranges, errors, message}
    """
    import stt_pipeline
    prov = (provider or "gemini").lower()
    if prov not in ["gemini", "local_whisper", "local", "whisper_local"]:
        prov = "gemini"
    cfg = load_api_settings_from_disk()
    target_key = (api_key or cfg.get("transcription_api_key") or cfg.get("gemini_api_key")
                  or get_default_api_key_from_disk().get("api_key") or "").strip()
    target_model = model_name or cfg.get("transcription_model") or "gemini-3.5-transcribe"
    return stt_pipeline.transcribe_chunks(
        chunks=chunks, chunk_durations=chunk_durations, provider=prov, api_key=target_key,
        model_name=target_model, language=language or "auto", mime_type=mime_type or "audio/mp3",
        segment_time_sec=segment_time_sec, base_offset_sec=base_offset_sec, label=label,
        on_progress=on_progress, whisper_model=_requested_whisper_model(prov, model_name)
    )


def transcribe_normalized_audio_chunks(
    chunks: List[bytes],
    provider: str = "gemini",
    api_key: str = "",
    model_name: str = "gemini-3.5-transcribe",
    language: str = "auto",
    mime_type: str = "audio/mp3",
    segment_time_sec: float = 600.0,
    chunk_durations: Optional[List[float]] = None
) -> Tuple[str, str]:
    """Backwards-compatible (transcript, language) wrapper. Prefer transcribe_audio_chunks_detailed."""
    res = transcribe_audio_chunks_detailed(chunks, provider, api_key, model_name, language, mime_type,
                                           segment_time_sec, chunk_durations)
    return res.get("transcript", ""), res.get("language", "auto")

_llm_log = get_logger("llm")


def summarize_text_gemini(
    text_content: str,
    api_key: str,
    model_name: str = "gemini-3.8-flash",
    org_context: str = "",
    custom_skills: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fills the selected template's JSON schema from the transcript with Gemini.
    - JSON response mode, low temperature, generous output budget.
    - Retries transient errors (429/5xx/timeouts) with backoff.
    - If the JSON is truncated/unparseable, retries once asking for compact transcripts.
    - On total failure falls back to offline extraction and says WHY in "warning".
    """
    import stt_pipeline
    clean_key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    target_model = model_name or "gemini-3.8-flash"
    if any(v in target_model for v in ("1.5", "2.0")):
        _llm_log.warning("summarization model %s is retired; using gemini-3.8-flash", target_model)
        target_model = "gemini-3.8-flash"

    failure_reason = "No Gemini API key configured (add it in Settings)"
    if clean_key and (text_content or "").strip():
        client = stt_pipeline._gemini_client(clean_key)
        compact_note = ("\n\nIMPORTANT: keep 'bangla_transcript' and 'english_transcript' to a concise formal record "
                        "of at most ~600 words each so the whole JSON fits in one response.")
        for pass_no, extra in enumerate(["", compact_note], start=1):
            prompt = (f"{system_prompt}{extra}\n\nAnalyze and organize this transcript into the exact JSON format:\n\n"
                      f"{text_content}")
            for attempt in range(1, 4):
                t0 = time.time()
                try:
                    kwargs = dict(temperature=0.1, max_output_tokens=65536, response_mime_type="application/json")
                    if target_model.startswith("gemini-3"):
                        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
                    try:
                        cfg = types.GenerateContentConfig(**kwargs)
                    except Exception:
                        kwargs.pop("thinking_config", None)
                        cfg = types.GenerateContentConfig(**kwargs)
                    resp = client.models.generate_content(model=target_model, contents=prompt, config=cfg)
                    raw_text = (getattr(resp, "text", None) or "").strip()
                    finish = None
                    try:
                        finish = str(resp.candidates[0].finish_reason)
                    except Exception:
                        pass
                    parsed = extract_and_repair_json(raw_text) if raw_text else None
                    _llm_log.info("summarize pass=%d attempt=%d model=%s in %.1fs chars_in=%d chars_out=%d finish=%s parsed=%s",
                                  pass_no, attempt, target_model, time.time() - t0, len(text_content), len(raw_text), finish, bool(parsed))
                    if parsed and isinstance(parsed, dict):
                        out = process_extracted_payload(raw_text, fallback_content=text_content, custom_skills=custom_skills,
                                                        org_context=org_context, template_schema=template_schema)
                        out["model"] = target_model
                        return out
                    failure_reason = f"model returned unparseable JSON (finish_reason={finish}, {len(raw_text)} chars)"
                    break  # go to compact pass
                except Exception as e:
                    failure_reason = stt_pipeline._friendly(stt_pipeline._short_reason(e))
                    _llm_log.error("summarize attempt=%d model=%s FAILED after %.1fs: %s", attempt, target_model,
                                   time.time() - t0, describe_exception(e))
                    if not stt_pipeline._is_retryable(e) or attempt == 3:
                        pass_no = 99
                        break
                    time.sleep((stt_pipeline._retry_delay_hint(e) or 4 * 2 ** (attempt - 1)) + random.uniform(0, 1))
            if pass_no == 99:
                break
    elif not (text_content or "").strip():
        failure_reason = "transcript is empty"

    _llm_log.error("summarize FALLBACK to offline extraction: %s", failure_reason)
    res = deep_semantic_synthesis(text_content, custom_skills, org_context, template_schema)
    res["warning"] = (f"Cloud AI could not fill the template ({failure_reason}). Fields were filled offline only with "
                      f"text found in the transcript - please review and complete them before exporting.")
    return res

_oac_log = get_logger("openai_compat")

# HTTP statuses where retrying without response_format makes sense: the endpoint
# understood the request but rejected a field (older Ollama / LM Studio builds).
_OAC_FIELD_REJECTION_STATUSES = (400, 415, 422)


class OpenAICompatibleError(RuntimeError):
    """
    Raised when an OpenAI-compatible endpoint can't fill the template.
    ``user_message`` is short and safe to show; the full detail is only logged.
    """

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(detail or user_message)
        self.user_message = user_message


def _oac_log_body(label: str, resp: "httpx.Response") -> None:
    """Logs a non-2xx or unusable response body (truncated) - file only, never shown to users."""
    try:
        body = resp.text
    except Exception:
        body = "<unreadable>"
    _oac_log.error("%s status=%s content_type=%s body=%s", label, resp.status_code,
                   resp.headers.get("content-type"), (body or "")[:4000])


def _oac_extract_content(data: Dict[str, Any]) -> str:
    """Pulls the assistant text out of a Chat Completions response (string or content-part list)."""
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):  # some gateways return [{"type": "text", "text": "..."}]
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return (content or "").strip()


def summarize_text_openai_compatible(
    text_content: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: Optional[str] = None,
    org_context: str = "",
    custom_skills: str = "",
    template_schema: Optional[Dict[str, Any]] = None,
    timeout: float = 120.0
) -> Dict[str, Any]:
    """
    Fills the selected template's JSON schema from the transcript using any OpenAI
    Chat-Completions-compatible endpoint (OpenRouter, DeepSeek, Ollama, LM Studio, ...).
    - POST {base_url}/chat/completions with the same system prompt as the Gemini/local paths.
    - Asks for response_format=json_object first; if the endpoint rejects that field,
      retries once without it and salvages the JSON with extract_and_repair_json().
    - Output goes through process_extracted_payload() like every other provider.
    Raises OpenAICompatibleError (with a short user_message) on auth failure, connection
    refused, timeout, HTTP errors or unparseable output - the caller falls back and warns.
    """
    cfg = load_api_settings_from_disk()
    root = (base_url if base_url is not None else (cfg.get("custom_api_base_url") or "")).strip().rstrip("/")
    model = (model_name if model_name is not None else (cfg.get("custom_api_model") or "")).strip()
    key = (api_key if api_key is not None else (cfg.get("custom_api_key") or "")).strip()
    endpoint = f"{root}/chat/completions"
    _oac_log.info("resolved provider=openai_compatible base_url=%s model=%s key=%s transcript_chars=%d timeout=%.0fs",
                  root or "<none>", model or "<none>", redact_key(key), len(text_content or ""), timeout)
    if not root or not model:
        raise OpenAICompatibleError("the Custom API needs a Base URL and a Model ID in Settings",
                                    f"missing config base_url={root!r} model={model!r}")
    if not (text_content or "").strip():
        raise OpenAICompatibleError("the transcript is empty")

    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Transcript:\n\n{text_content}\n\nReturn only the JSON object, nothing else."},
    ]
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    def _post(client: "httpx.Client", with_response_format: bool) -> "httpx.Response":
        payload: Dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.1}
        if with_response_format:
            payload["response_format"] = {"type": "json_object"}
        t_req = time.time()
        _oac_log.info("POST %s model=%s response_format=%s", endpoint, model,
                      "json_object" if with_response_format else "none")
        resp = client.post(endpoint, json=payload, headers=headers)
        _oac_log.info("POST %s -> HTTP %s in %.1fs (response_format=%s)", endpoint, resp.status_code,
                      time.time() - t_req, "json_object" if with_response_format else "none")
        return resp

    t0 = time.time()
    used_response_format = True
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            resp = _post(client, with_response_format=True)
            if resp.status_code in _OAC_FIELD_REJECTION_STATUSES:
                _oac_log_body("response_format=json_object rejected; retrying once without it:", resp)
                used_response_format = False
                resp = _post(client, with_response_format=False)
    except httpx.ConnectError as e:
        _oac_log.error("connection FAILED to %s after %.1fs: %s", endpoint, time.time() - t0, describe_exception(e))
        raise OpenAICompatibleError(f"could not connect to {root} - is the server running and the Base URL correct?",
                                    str(e)) from e
    except httpx.TimeoutException as e:
        _oac_log.error("TIMEOUT after %.1fs calling %s: %s", time.time() - t0, endpoint, describe_exception(e))
        raise OpenAICompatibleError(f"{root} did not answer within {int(timeout)}s", str(e)) from e
    except httpx.HTTPError as e:
        _oac_log.error("HTTP transport error calling %s after %.1fs: %s", endpoint, time.time() - t0,
                       describe_exception(e))
        raise OpenAICompatibleError(f"the request to {root} failed", str(e)) from e

    if resp.status_code in (401, 403):
        _oac_log_body("AUTH rejected:", resp)
        raise OpenAICompatibleError("the Custom API rejected the API key - check it in Settings",
                                    f"HTTP {resp.status_code}")
    if resp.status_code == 404:
        _oac_log_body("NOT FOUND (wrong Base URL or model id?):", resp)
        raise OpenAICompatibleError(f"the endpoint or model '{model}' was not found - check the Base URL and Model ID",
                                    "HTTP 404")
    if resp.status_code == 429:
        _oac_log_body("RATE LIMITED:", resp)
        raise OpenAICompatibleError("the Custom API rate limit or credit was exceeded - try again shortly", "HTTP 429")
    if resp.status_code >= 400:
        _oac_log_body("request FAILED:", resp)
        raise OpenAICompatibleError(f"the Custom API returned an error (HTTP {resp.status_code})",
                                    f"HTTP {resp.status_code}")

    try:
        data = resp.json()
    except ValueError:
        _oac_log_body("response is not JSON:", resp)
        raise OpenAICompatibleError("the Custom API returned a response that is not JSON")
    raw_text = _oac_extract_content(data)
    parsed = extract_and_repair_json(raw_text) if raw_text else None
    _oac_log.info("completion model=%s finish_reason=%s chars_out=%d parsed=%s response_format=%s usage=%s in %.1fs",
                  data.get("model") or model, ((data.get("choices") or [{}])[0]).get("finish_reason"),
                  len(raw_text), bool(parsed), "json_object" if used_response_format else "none(fallback)",
                  data.get("usage"), time.time() - t0)
    if not (parsed and isinstance(parsed, dict)):
        _oac_log_body("UNPARSEABLE completion (no JSON object found):", resp)
        raise OpenAICompatibleError("the model's answer could not be read as the template's JSON",
                                    f"unparseable output, {len(raw_text)} chars")

    out = process_extracted_payload(
        raw_text, fallback_content=text_content, custom_skills=custom_skills,
        org_context=org_context, template_schema=template_schema
    )
    out["model"] = f"openai_compatible:{model}"
    out["provider"] = "openai_compatible"
    out["response_format_fallback"] = not used_response_format
    return out


def transcribe_and_summarize_gemini(
    media_bytes: Optional[bytes],
    mime_type: str,
    api_key: str,
    transcription_model: str = "gemini-3.5-transcribe",
    summarization_model: str = "gemini-3.8-flash",
    org_context: str = "",
    custom_skills: str = "",
    text_content: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Multimodal document / image OCR and vision extraction via Gemini."""
    clean_key = (api_key or get_default_api_key_from_disk().get("api_key") or "").strip()
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)

    if audio_chunks and len(audio_chunks) > 0:
        texts = asyncio.run(transcribe_chunks_parallel(
            audio_chunks=audio_chunks,
            provider="gemini",
            api_key=clean_key,
            base_url="",
            model_name=transcription_model,
            mime_type=mime_type or "audio/mp3"
        ))
        joined = "\n\n".join([t for t in texts if t])
        if joined:
            text_content = f"{text_content}\n\n{joined}".strip() if text_content else joined

    if (mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf")) and media_bytes and clean_key:
        target_bytes = media_bytes
        target_mime = mime_type
        if target_mime != "application/pdf":
            target_bytes, target_mime = preprocess_image_for_ocr(media_bytes)

        ocr_prompt = (
            f"{system_prompt}\n\n"
            "TASK: Perform high-fidelity optical character recognition (OCR) and layout extraction from this document/image. "
            "Transcribe all Bengali (বাংলা) and English text verbatim. Preserve tables, dates, memo numbers, attendees, "
            "agendas, discussions, and decisions. Clean any OCR distortions and format into the exact JSON schema requested."
        )

        try:
            client = genai.Client(api_key=clean_key)
            target_model = summarization_model or "gemini-3.8-flash"
            cfg = None
            if "3.8" in target_model or "3.7" in target_model or "3" in target_model:
                cfg = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            resp = client.models.generate_content(
                model=target_model,
                contents=[
                    types.Part.from_bytes(data=target_bytes, mime_type=target_mime),
                    ocr_prompt
                ],
                config=cfg
            )
            raw_text = (getattr(resp, "text", None) or "").strip()
            if raw_text:
                return process_extracted_payload(
                    raw_text,
                    fallback_content=text_content,
                    custom_skills=custom_skills,
                    org_context=org_context,
                    template_schema=template_schema
                )
        except Exception as e:
            print(f"[Gemini Vision OCR Error] {e}")

    return deep_semantic_synthesis(text_content or "Scanned Document", custom_skills, org_context, template_schema)

# --- UNIFIED AI PIPELINE ENTRYPOINT ---

def process_ai_request(
    provider: str = "gemini",
    api_key: str = "",
    base_url: str = "",
    model_name: str = "",
    transcription_model: str = "",
    summarization_model: str = "",
    transcription_provider: str = "",
    transcription_api_key: str = "",
    summarization_provider: str = "",
    summarization_api_key: str = "",
    media_bytes: Optional[bytes] = None,
    mime_type: str = "text/plain",
    text_content: str = "",
    org_context: str = "",
    custom_skills: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None,
    audio_segments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Unified entrypoint routing strictly between:
    1. Default: Gemini 3.5 Transcribe Live STT + Gemini Flash LLM
    2. Fallback: Local Whisper (dynamic RAM specs) + Deep Semantic Synthesis
    """
    disk_cfg = load_api_settings_from_disk()

    # 1. Resolve STT Provider & Model
    stt_prov = (transcription_provider or provider or disk_cfg.get("transcription_provider") or "gemini").lower()
    if stt_prov not in ["gemini", "local_whisper", "local", "whisper_local"]:
        stt_prov = "gemini"

    # A generic api_key that belongs to the Custom API must never be sent to Gemini STT.
    generic_key_for_gemini = api_key if (provider or "").lower() not in _OPENAI_COMPAT_ALIASES else ""
    stt_key = (transcription_api_key or generic_key_for_gemini or disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()
    stt_model = transcription_model or disk_cfg.get("transcription_model") or "gemini-3.5-transcribe"
    _stt_log.info("process_ai_request resolved STT provider=%s model=%s whisper_model=%s key=%s",
                  stt_prov, stt_model, _requested_whisper_model(stt_prov, stt_model), redact_key(stt_key))

    # 2. Resolve LLM Provider & Model
    llm_prov = (summarization_provider or provider or disk_cfg.get("summarization_provider") or "gemini").lower()
    if llm_prov in _OPENAI_COMPAT_ALIASES:
        llm_prov = "openai_compatible"
    if llm_prov not in ["gemini", "local", "local_whisper", "openai_compatible"]:
        _llm_log.warning("process_ai_request: unknown summarization provider %r - using gemini", llm_prov)
        llm_prov = "gemini"

    llm_base_url = ""
    if llm_prov == "openai_compatible":
        # Custom endpoint: its own key/model/base URL only - never the Gemini key.
        llm_key = (summarization_api_key if summarization_api_key is not None
                   else (api_key or disk_cfg.get("custom_api_key") or "")).strip()
        requested_model = (summarization_model or model_name or "").strip()
        if not requested_model or requested_model.startswith("gemini") or requested_model.startswith("local"):
            requested_model = disk_cfg.get("custom_api_model") or ""
        llm_model = requested_model
        llm_base_url = (base_url or disk_cfg.get("custom_api_base_url") or "").strip()
    else:
        llm_key = (summarization_api_key or api_key or disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()
        llm_model = summarization_model or model_name or disk_cfg.get("summarization_model") or "gemini-3.8-flash"
    _llm_log.info("process_ai_request resolved LLM provider=%s model=%s base_url=%s key=%s",
                  llm_prov, llm_model or "<none>", llm_base_url or "-", redact_key(llm_key))

    # 3. Vision OCR Check
    if media_bytes and mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf"):
        return transcribe_and_summarize_gemini(
            media_bytes=media_bytes,
            mime_type=mime_type,
            api_key=llm_key or stt_key,
            transcription_model=stt_model,
            summarization_model=llm_model,
            org_context=org_context,
            custom_skills=custom_skills,
            text_content=text_content,
            template_schema=template_schema
        )

    # 4. Audio Transcription Stage (STT)
    raw_transcript = (text_content or "").strip()
    segments = list(audio_segments or [])
    if not segments:
        chunks = audio_chunks if (audio_chunks and len(audio_chunks) > 0) else ([media_bytes] if media_bytes else [])
        if chunks:
            segments = [{"name": "", "chunks": chunks, "durations": None}]

    stt_report: Dict[str, Any] = {}
    if audio_chunks and len(audio_chunks) > 0:
        chunk_texts = asyncio.run(transcribe_chunks_parallel(
            audio_chunks=audio_chunks,
            provider=stt_prov,
            api_key=stt_key,
            base_url=base_url,
            model_name=stt_model,
            mime_type=mime_type or "audio/mp3",
        ))
        joined = "\n\n".join([t for t in chunk_texts if t])
        if joined:
            raw_transcript = f"{raw_transcript}\n\n{joined}".strip() if raw_transcript else joined
            stt_report = {"status": "success", "errors": [], "missing_ranges": []}
    elif segments:
        parts, all_errors, all_missing, statuses = [], [], [], []
        for seg in segments:
            seg_chunks = seg.get("chunks") or []
            if len(seg_chunks) > 1 and not seg.get("durations"):
                c_texts = asyncio.run(transcribe_chunks_parallel(
                    audio_chunks=seg_chunks,
                    provider=stt_prov,
                    api_key=stt_key,
                    base_url=base_url,
                    model_name=stt_model,
                    mime_type=seg.get("mime_type") or mime_type or "audio/mp3"
                ))
                seg_text = "\n\n".join([t for t in c_texts if t])
                if seg_text:
                    parts.append(seg_text)
                statuses.append("success" if seg_text else "error")
            else:
                res = transcribe_audio_chunks_detailed(
                    chunks=seg_chunks, provider=stt_prov, api_key=stt_key, model_name=stt_model,
                    language="auto", mime_type=seg.get("mime_type") or mime_type or "audio/mp3",
                    segment_time_sec=600.0, chunk_durations=seg.get("durations"), label=seg.get("name", "")
                )
                statuses.append(res["status"])
                multi = len(segments) > 1 and seg.get("name")
                prefix = f"{seg['name']}: " if multi else ""
                all_errors.extend(prefix + e for e in res.get("errors", []))
                all_missing.extend(dict(m, file=seg.get("name", "")) for m in res.get("missing_ranges", []))
                if res.get("transcript"):
                    header = f"=== {seg['name']} ===\n" if multi else ""
                    parts.append(header + res["transcript"])
        audio_text = "\n\n".join(parts)
        overall = ("success" if all(st == "success" for st in statuses)
                   else "error" if all(st == "error" for st in statuses) else "partial")
        stt_report = {"status": overall, "errors": all_errors, "missing_ranges": all_missing}
        if audio_text:
            raw_transcript = f"{raw_transcript}\n\n{audio_text}".strip() if raw_transcript else audio_text

    if not raw_transcript:
        reason = "; ".join(stt_report.get("errors", [])[:3]) or "no text or audio was provided"
        _stt_log.error("process_ai_request: nothing to summarise - %s", reason)
        return {"status": "error", "error": f"Transcription failed - nothing to fill the template with. {reason}",
                "stt": stt_report, "raw_transcript": "", "transcript": ""}

    # 5. Summarization & Meeting Minutes Stage (LLM)
    if llm_prov in ["local", "local_whisper", "offline"]:
        try:
            import local_llm_engine
            result = local_llm_engine.generate_template_fill(
                transcript=raw_transcript, template_schema=template_schema,
                org_context=org_context, custom_skills=custom_skills
            )
            _llm_log.info("Local LLM (%s) filled the template successfully.", result.get("model"))
        except Exception as e_local:
            _llm_log.error("Local LLM unavailable/failed (%s) - falling back to offline regex extraction",
                            describe_exception(e_local), exc_info=True)
            result = deep_semantic_synthesis(raw_transcript, custom_skills, org_context, template_schema)
            result["warning"] = (f"Local model could not run ({_local_llm_user_reason(e_local)}). Fields were filled "
                                 f"offline only with text found in the transcript - please review and complete them "
                                 f"before exporting. (reference {current_job_id()})")
    elif llm_prov == "openai_compatible":
        try:
            result = summarize_text_openai_compatible(
                text_content=raw_transcript,
                api_key=llm_key,
                base_url=llm_base_url,
                model_name=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema
            )
            _llm_log.info("Custom API (%s) filled the template successfully.", result.get("model"))
        except Exception as e_custom:
            _llm_log.error("Custom API failed (%s) - falling back to offline extraction",
                           describe_exception(e_custom), exc_info=True)
            reason = getattr(e_custom, "user_message", "") or "an unexpected error occurred"
            result = deep_semantic_synthesis(raw_transcript, custom_skills, org_context, template_schema)
            result["warning"] = (f"Custom API could not fill the template ({reason}). Fields were filled offline only "
                                 f"with text found in the transcript - please review and complete them before "
                                 f"exporting. (reference {current_job_id()})")
    else:
        result = summarize_text_gemini(
            text_content=raw_transcript,
            api_key=llm_key,
            model_name=llm_model,
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )
    result["raw_transcript"] = raw_transcript
    result["transcript"] = raw_transcript
    if stt_report:
        result["stt"] = stt_report
        if stt_report["status"] == "partial":
            gap_msg = f"Part of the audio could not be transcribed: {'; '.join(stt_report['errors'][:3])}"
            result["warning"] = f"{gap_msg}. {result['warning']}" if result.get("warning") else gap_msg
    result.setdefault("status", "success")
    return result
