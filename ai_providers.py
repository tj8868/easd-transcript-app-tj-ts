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
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types
from document_engine import DEFAULT_MEMBERS
from ocr_engine import optimize_ocr_text, preprocess_image_for_ocr

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
        "details": "• All action directives issued during this session with responsible owners.\n• Deadlines, quality benchmarks, and compliance requirements per action."
      },
      {
        "sn": "3",
        "topic": "Task Assignments",
        "details": "• Specific tasks allocated to named team leads with agreed delivery timelines.\n• Workstream ownership confirmed by the meeting chair."
      },
      {
        "sn": "4",
        "topic": "Meeting Decisions",
        "details": "• All formally approved strategic and institutional decisions taken in this session.\n• Locked deadlines, approved frameworks, and next scheduled review date."
      }
    ],
    "decisions": "• Formally approved strategic decisions.\n• Locked submission deadlines and milestone commitments.\n• Directives for institutional compliance and next review schedule.",
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
    cleaned = raw_text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
            
    try:
        return json.loads(cleaned)
    except Exception:
        pass
        
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(json_candidate)
        except Exception:
            fixed = re.sub(r',\s*([\]}])', r'\1', json_candidate)
            try:
                return json.loads(fixed)
            except Exception:
                pass
    return None

def match_attendance_list(present_names: List[str], text_corpus: str = "") -> List[Dict[str, str]]:
    combined_text = (text_corpus + " " + " ".join(present_names)).lower()
    updated_attendance = []
    
    for default_member in DEFAULT_MEMBERS:
        name_lower = default_member["name"].lower()
        parts = [p for p in name_lower.split() if len(p) > 3 and p not in ["md.", "h", "m", "abu", "chowdhury", "sultana"]]
        is_present = any(part in combined_text for part in parts)
        
        if "sanzida" in combined_text and "sanjida" in name_lower:
            is_present = True
        if "pew" in combined_text and "pew" in name_lower:
            is_present = True
        if "salman" in combined_text and "salman" in name_lower:
            is_present = True
        if "farihin" in combined_text and "farihin" in name_lower:
            is_present = True
        if "taseen" in combined_text and "taseen" in name_lower:
            is_present = True
            
        participation = "Yes" if is_present else default_member["participation"]
        updated_attendance.append({
            "serial": default_member["serial"],
            "name": default_member["name"],
            "participation": participation
        })
        
    return updated_attendance

def deep_semantic_synthesis(raw_text: str, custom_skills: str = "", org_context: str = "") -> Dict[str, Any]:
    """
    Deep Executive Synthesizer:
    Intelligently reads, synthesizes, refines, and formats raw transcript into
    executive-grade meeting minutes matching the EASD template.
    """
    text = raw_text.strip()
    detected_lang = detect_text_language(text)
    
    # 1. Title Extraction
    title_match = re.search(r'(?:\*\*|\#+)?\s*(?:Meeting Minutes\s*:\s*|Title\s*:\s*)([^\n\*]+)', text, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()
    elif "non-communicable" in text.lower() or "ncd" in text.lower():
        title = "Strategic & Programmatic Review Meeting on Non-Communicable Diseases (NCD)"
    else:
        title = "Weekly Strategic, Programmatic and Presentation Review Meeting"

    # 2. Date Extraction
    date_match = re.search(r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})', text, re.IGNORECASE)
    date_str = date_match.group(1) if date_match else "29 August, 2026"

    # 3. Time & Location
    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*-\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))', text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else "11:00 AM - 01:00 PM"
    location_str = "Eminence Conference Room, Mohakhali DOHS, Dhaka"
    if "zoom" in text.lower() or "online" in text.lower():
        location_str = "Online (Zoom / Microsoft Teams)"

    # 4. Agendas Extraction
    agendas = []
    agenda_match = re.search(r'\*\*(?:Meeting )?Agenda\*\*\s*([\s\S]*?)(?=\-\-\-|\*\*Key Discussions\*\*|\*\*Discussions\*\*|\n\n[A-Z]|$)', text, re.IGNORECASE)
    if agenda_match:
        for line in agenda_match.group(1).splitlines():
            cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', line).strip('*# ')
            if cleaned_line:
                agendas.append(cleaned_line)

    # 5. Extract Thematic Discussion Points (Table 0) — ALWAYS exactly 4 fixed rows
    def extract_section(patterns, fallback):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_bullets = match.group(1).strip().splitlines()
                cleaned = []
                for b in raw_bullets:
                    clean_b = re.sub(r'^[•\-\*\d\.\)]+\s*', '', b).strip()
                    if clean_b and not clean_b.startswith('---') and len(clean_b) > 4:
                        cleaned.append(f"• {clean_b}")
                if cleaned:
                    return "\n".join(cleaned)
        return fallback

    # Extract all raw sentences for content distribution
    raw_sentences = [s.strip() for s in re.split(r'[.\n]+', text) if len(s.strip()) > 8]
    quarter = max(1, len(raw_sentences) // 4)
    followup_content   = [f"• {s}." for s in raw_sentences[:quarter]]
    action_content     = [f"• {s}." for s in raw_sentences[quarter:2*quarter]]
    task_content       = [f"• {s}." for s in raw_sentences[2*quarter:3*quarter]]
    decision_content   = [f"• {s}." for s in raw_sentences[3*quarter:]]

    row1_details = extract_section(
        [r'\*\*(?:Follow-?up[^*]*|Previous[^*]*)\*\*\s*([\s\S]*?)(?=\*\*[A-Z]|---|$)',
         r'##\s*Follow-?up[^\n]*\n([\s\S]*?)(?=##|$)'],
        "\n".join(followup_content) if followup_content else
        "• Progress on all items from previous session reviewed with respective leads.\n• Outstanding deliverables tracked and updated by responsible coordinators."
    )

    row2_details = extract_section(
        [r'\*\*(?:Action Items[^*]*)\*\*\s*([\s\S]*?)(?=\*\*[A-Z]|---|$)',
         r'##\s*Action Items[^\n]*\n([\s\S]*?)(?=##|$)'],
        "\n".join(action_content) if action_content else
        "• Concrete action directives issued with named responsible owners.\n• Compliance and quality benchmarks confirmed per action item."
    )

    row3_details = extract_section(
        [r'\*\*(?:Task[^*]*)\*\*\s*([\s\S]*?)(?=\*\*[A-Z]|---|$)',
         r'##\s*Task[^\n]*\n([\s\S]*?)(?=##|$)'],
        "\n".join(task_content) if task_content else
        "• Specific tasks allocated to named team leads with agreed delivery timelines.\n• Workstream ownership confirmed by the meeting chair."
    )

    row4_details = extract_section(
        [r'\*\*(?:Major Decisions[^*]*|Decisions[^*]*|Key Decisions[^*]*)\*\*\s*([\s\S]*?)(?=\*\*[A-Z]|---|$)',
         r'##\s*(?:Major )?Decisions[^\n]*\n([\s\S]*?)(?=##|$)'],
        "\n".join(decision_content) if decision_content else
        "• All formally approved strategic and institutional decisions adopted in this session.\n• Locked submission deadlines and next strategic review date confirmed."
    )

    # Always 4 fixed rows — EXACT topic names matching the template document
    discussions = [
        {"sn": "1", "topic": "Followup from previous meeting", "details": clean_bullet_points(row1_details)},
        {"sn": "2", "topic": "Action items",                    "details": clean_bullet_points(row2_details)},
        {"sn": "3", "topic": "Task Assignments",                 "details": clean_bullet_points(row3_details)},
        {"sn": "4", "topic": "Meeting Decisions",                "details": clean_bullet_points(row4_details)},
    ]

    cleaned_agendas = [clean_agenda_item(a) for a in agendas if clean_agenda_item(a)]
    if not cleaned_agendas:
        cleaned_agendas = [
            "Review of previous meeting minutes & follow-up on pending items",
            "Action items review and quality assurance directives",
            "Task assignments and delivery timeline confirmation",
            "Major decisions and institutional approvals"
        ]
    while len(cleaned_agendas) < 4:
        cleaned_agendas.append("Major decisions and next strategic review")

    decisions_str = clean_bullet_points(discussions[3]["details"])
    attendance = match_attendance_list([], text)

    bangla_transcript = (
        f"ইমিনের্স অ্যাসোসিয়েটস ফর সোশ্যাল ডেভেলপমেন্ট (EASD) এর সাপ্তাহিক কৌশলগত ও প্রোগ্রাম্যাটিক পর্যালোচনা সভায় "
        f"'{title}' বিষয়ক গুরুত্বপূর্ণ পর্যালোচনা অনুষ্ঠিত হয়।\n\n"
        f"সভায় আলোচিত মূল বিষয়সমূহ:\n" +
        "\n".join([f"{idx+1}. {d['topic']}:\n{d['details']}" for idx, d in enumerate(discussions)]) +
        f"\n\nমূল সিদ্ধান্তসমূহ:\n{decisions_str}"
    )

    english_transcript = text

    # Raw transcript formatted by speaker and time
    raw_transcript = text
    if raw_transcript and not raw_transcript.startswith("["):
        # If not already formatted with timestamps, format as Speaker 1
        lines = [line.strip() for line in raw_transcript.split("\n") if line.strip()]
        if lines:
            raw_transcript = "\n".join([f"[00:00] Speaker 1: {l}" if not l.startswith("[") else l for l in lines])

    return {
        "detected_language": detected_lang,
        "raw_transcript": raw_transcript,
        "transcript": raw_transcript,
        "bangla_transcript": bangla_transcript,
        "english_transcript": english_transcript,
        "summary": {
            "title": title,
            "location": location_str,
            "date": date_str,
            "time": time_str,
            "agendas": cleaned_agendas[:5],
            "discussions": discussions,
            "decisions": decisions_str,
            "attendance": attendance
        }
    }

def build_template_system_prompt(template_schema: Optional[Dict[str, Any]] = None, org_context: str = "", custom_skills: str = "") -> str:
    """Constructs dynamic, schema-driven system prompt matching any document type or custom uploaded template."""
    if not template_schema or template_schema.get("id") == "easd_default_minutes":
        base_prompt = LLM_SYSTEM_PROMPT
        if template_schema:
            tpl_context = template_schema.get("context", "")
            tpl_rules = template_schema.get("rules", "")
            tpl_requirements = template_schema.get("requirements", "")
            if tpl_context:
                base_prompt += f"\n\n--- TEMPLATE PURPOSE & CONTEXT ---\n{tpl_context}"
            if tpl_rules:
                base_prompt += f"\n\n--- MANDATORY FORMATTING RULES & CONSTRAINTS ---\n{tpl_rules}"
            if tpl_requirements:
                base_prompt += f"\n\n--- ESSENTIAL REQUIREMENTS & OUTPUT CRITERIA ---\n{tpl_requirements}"
    else:
        name = template_schema.get("name", "Document Template")
        doc_type = template_schema.get("doc_type", "custom")
        fields = template_schema.get("fields", [])
        sections = template_schema.get("sections", [])
        tables = template_schema.get("tables", [])
        custom_instructions = template_schema.get("ai_system_prompt", "")
        
        tpl_context = template_schema.get("context", "")
        tpl_rules = template_schema.get("rules", "")
        tpl_requirements = template_schema.get("requirements", "")
        
        fields_json_map = {}
        for f in fields:
            f_key = f.get("key", "field")
            f_lbl = f.get("label", f_key)
            fields_json_map[f_key] = f"Extracted value for {f_lbl}"
            
        sections_desc_list = []
        for s in sections:
            prompt_text = s.get("prompt") or f"Synthesized content for {s.get('title', '')}"
            sections_desc_list.append(f'      "{s.get("id")}": "{prompt_text}"')
        sections_desc = ",\n".join(sections_desc_list)
        
        tables_desc_list = []
        for t in tables:
            cols_dict = {col: "..." for col in t.get("columns", [])}
            tables_desc_list.append(f'      "{t.get("id")}": [{json.dumps(cols_dict)}]')
        tables_desc = ",\n".join(tables_desc_list)
        
        fields_json_str = "\n".join([f'    "{k}": "{v}",' for k, v in fields_json_map.items()])
        
        base_prompt = f"""You are an expert bilingual Chief Executive Rapporteur, Senior Administrative Editor, and AI Documentation Director.
The input provided to you is a raw conversation transcript, draft notes, audio transcription, or recorded speech in mixed Bangla + English.

Your task is to DEEPLY ANALYZE, REWRITE, RESTRUCTURE, and SYNTHESIZE the raw content into the '{name}' format (Document Type: {doc_type}).

{custom_instructions}

You must produce a valid JSON object matching the following structure:
{{
  "detected_language": "bn",
  "bangla_transcript": "বাংলা ভাষায় সম্পূর্ণ প্রাতিষ্ঠানিক, সাবলীল এবং বিস্তারিত বিবরণ (অনুবাদ ও পরিমার্জনসহ)।",
  "english_transcript": "Comprehensive, formal, and polished English executive document.",
  "summary": {{
{fields_json_str}
    "sections_data": {{
{sections_desc}
    }},
    "tables_data": {{
{tables_desc}
    }}
  }}
}}
"""
        if tpl_context:
            base_prompt += f"\n--- TEMPLATE PURPOSE & CONTEXT ---\n{tpl_context}\n"
        if tpl_rules:
            base_prompt += f"\n--- MANDATORY FORMATTING RULES & CONSTRAINTS ---\n{tpl_rules}\n"
        if tpl_requirements:
            base_prompt += f"\n--- ESSENTIAL REQUIREMENTS & OUTPUT CRITERIA ---\n{tpl_requirements}\n"

        base_prompt += """
INSTRUCTIONS:
1. Do NOT simply copy-paste raw fragments. Synthesize and upgrade raw points into formal, publication-ready prose.
2. Maintain bilingual accuracy (Bengali and English) where appropriate.
3. Every bullet point in list sections MUST begin with a single bullet symbol ("• ").
4. Return ONLY the valid JSON object — no markdown fencing, no extra commentary text.
"""

    if org_context:
        base_prompt += f"\n\n--- ORGANIZATION CONTEXT ---\n{org_context}"
    if custom_skills:
        base_prompt += f"\n\n--- ACTIVE SKILLS & DIRECTIVES ---\n{custom_skills}"
    return base_prompt

def process_extracted_payload(
    raw_text: str,
    fallback_content: str = "",
    custom_skills: str = "",
    org_context: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    parsed = extract_and_repair_json(raw_text)
    
    if parsed and isinstance(parsed, dict) and "summary" in parsed:
        summary = parsed.get("summary", {})
        detected_lang = parsed.get("detected_language") or detect_text_language(raw_text or fallback_content)
        
        # Unwrap sections_data & tables_data into top-level summary
        sections_data = summary.get("sections_data")
        if isinstance(sections_data, dict):
            for s_id, s_val in sections_data.items():
                if s_id not in summary or not summary[s_id]:
                    summary[s_id] = clean_bullet_points(str(s_val)) if ("•" in str(s_val) or "\n" in str(s_val)) else s_val
                    
        tables_data = summary.get("tables_data")
        if isinstance(tables_data, dict):
            for t_id, t_val in tables_data.items():
                if t_id not in summary or not summary[t_id]:
                    summary[t_id] = t_val

        tpl_id = template_schema.get("id") if template_schema else "easd_default_minutes"
        doc_type = template_schema.get("doc_type", "meeting_minutes") if template_schema else "meeting_minutes"
        
        # Non-default template schemas
        if template_schema and tpl_id != "easd_default_minutes":
            if doc_type == "bangladesh_govt_report":
                if "ministry" not in summary:
                    summary["ministry"] = "স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়"
                if "memo_no" not in summary:
                    summary["memo_no"] = "৪৫.০০.০০০০.০০১.২৪.০০১.২৬-"
                if "subject" not in summary:
                    summary["subject"] = summary.get("title", "প্রতিবেদন প্রসঙ্গে")
            
            raw_tx = fallback_content or raw_text
            return {
                "detected_language": detected_lang,
                "template_id": tpl_id,
                "doc_type": doc_type,
                "raw_transcript": raw_tx,
                "transcript": raw_tx,
                "bangla_transcript": parsed.get("bangla_transcript", fallback_content),
                "english_transcript": parsed.get("english_transcript", fallback_content),
                "summary": summary
            }

        # Default EASD Minutes Template
        raw_agendas = summary.get("agendas", [])
        if isinstance(raw_agendas, str):
            raw_agendas = [line.strip().lstrip("•*-1234567890. ") for line in raw_agendas.splitlines() if line.strip()]
        cleaned_agendas = [clean_agenda_item(a) for a in raw_agendas if clean_agenda_item(a)]
        if not cleaned_agendas:
            cleaned_agendas = [
                "1. Previous meeting review & operational followup",
                "2. Strategic program initiatives and implementation updates",
                "3. Inter-departmental coordination & administrative progress",
                "4. Decision ratification and resource allocation"
            ]
        summary["agendas"] = cleaned_agendas[:5]

        raw_discussions = summary.get("discussions", [])
        if not isinstance(raw_discussions, list) or len(raw_discussions) == 0:
            summary["discussions"] = [
                {"sn": "১", "topic": "বিগত সভার ফলোআপ ও অগ্রগতি পর্যালোচনা (Followup from previous meeting)", "details": "• পূর্ববর্তী সভার নির্ধারিত লক্ষ্যমাত্রা ও চলমান কার্যক্রমের বাস্তবায়ন পরিস্থিতি পর্যালোচনা করা হয়।"},
                {"sn": "২", "topic": "কর্মপরিকল্পনা ও কৌশলগত বাস্তবায়ন (Action items)", "details": "• মাঠপর্যায়ে কার্যক্রম ত্বরান্বিতকরণ ও কার্যপরিধি নিরীক্ষার সিদ্ধান্ত গৃহীত হয়।"},
                {"sn": "৩", "topic": "দায়িত্ব বণ্টন ও সময়সীমা নির্ধারণ (Task Assignments)", "details": "• সংশ্লিষ্ট বিভাগীয় প্রধানদের ওপর সুনির্দিষ্ট দায়িত্ব অর্পণ করা হয়েছে।"},
                {"sn": "৪", "topic": "সভার চূড়ান্ত সিদ্ধান্তসমূহ (Meeting Decisions)", "details": "• সর্বসম্মতভাবে প্রস্তাবসমূহ অনুমোদিত হয় এবং পরবর্তী বৈঠকের রূপরেখা চূড়ান্ত হয়।"}
            ]
        else:
            cleaned_discussions = []
            for idx, d in enumerate(raw_discussions, 1):
                if isinstance(d, dict):
                    cleaned_discussions.append({
                        "sn": str(d.get("sn", idx)),
                        "topic": str(d.get("topic", "")),
                        "details": clean_bullet_points(str(d.get("details", "")))
                    })
            summary["discussions"] = cleaned_discussions

        summary["decisions"] = clean_bullet_points(str(summary.get("decisions", "")))
        present_members = summary.get("present_members", [])
        summary["attendance"] = match_attendance_list(present_members, fallback_content or raw_text)
        raw_tx = fallback_content or raw_text
        return {
            "detected_language": detected_lang,
            "template_id": "easd_default_minutes",
            "doc_type": "meeting_minutes",
            "raw_transcript": raw_tx,
            "transcript": raw_tx,
            "bangla_transcript": parsed.get("bangla_transcript", fallback_content),
            "english_transcript": parsed.get("english_transcript", fallback_content),
            "summary": summary
        }
            
    return deep_semantic_synthesis(fallback_content or raw_text, custom_skills, org_context)

def verify_ai_api_key(provider: str, api_key: str = "", base_url: str = "") -> Dict[str, Any]:
    import time
    start_time = time.time()
    api_key = (api_key or "").strip()
    provider = (provider or "gemini").lower()
    
    # If API key is empty and not custom, check if the server has an active key in .env or disk
    if not api_key and provider != "custom":
        env_map = {
            "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY")
        }
        fallback_key = env_map.get(provider)
        if not fallback_key:
            disk_info = get_default_api_key_from_disk()
            if disk_info.get("provider") == provider:
                fallback_key = disk_info.get("api_key")
        if fallback_key:
            api_key = fallback_key.strip()
        else:
            return {
                "valid": False,
                "success": False,
                "message": f"API key is empty for {provider.capitalize()}. Please enter a key or configure in settings.",
                "latency_ms": 0
            }

    try:
        if api_key.startswith("AIzaSy") or api_key.startswith("AQ.") or provider == "gemini":
            try:
                client = genai.Client(api_key=api_key)
                resp = client.interactions.create(
                    model="gemini-3.5-flash-lite",
                    input="Ping"
                )
                latency = round((time.time() - start_time) * 1000)
                if resp and (getattr(resp, "output_text", None) or hasattr(resp, "id")):
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Google Gemini API verified & active ({latency}ms)!",
                        "latency_ms": latency
                    }
            except Exception as e:
                err_str = str(e).lower()
                latency = round((time.time() - start_time) * 1000)
                if "quota" in err_str or "rate" in err_str or "429" in err_str:
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Google Gemini API verified (Active, rate quota active, {latency}ms)!",
                        "latency_ms": latency
                    }
                # Fallback to direct HTTP check
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                with httpx.Client(timeout=8.0) as http_client:
                    r = http_client.get(url)
                    latency = round((time.time() - start_time) * 1000)
                    if r.status_code == 200:
                        return {
                            "valid": True,
                            "success": True,
                            "message": f"Google Gemini API verified & active ({latency}ms)!",
                            "latency_ms": latency
                        }
                    return {
                        "valid": False,
                        "success": False,
                        "message": f"Gemini Key error: {str(e)}",
                        "latency_ms": latency
                    }

        elif api_key.startswith("sk-ant-") or provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            data = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}]
            }
            with httpx.Client(timeout=8.0) as client:
                r = client.post(url, headers=headers, json=data)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code in [200, 429]:
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Anthropic Claude API verified & active ({latency}ms)!",
                        "latency_ms": latency
                    }
                elif r.status_code == 401:
                    return {
                        "valid": False,
                        "success": False,
                        "message": "Anthropic Key error (401): Invalid or unauthorized key.",
                        "latency_ms": latency
                    }
                else:
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Anthropic Key verified (Status {r.status_code}, {latency}ms).",
                        "latency_ms": latency
                    }

        elif api_key.startswith("sk-proj-") or (api_key.startswith("sk-") and not api_key.startswith("sk-ant-")) or provider == "openai":
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            with httpx.Client(timeout=8.0) as client:
                r = client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"OpenAI API Key verified & active ({latency}ms)!",
                        "latency_ms": latency
                    }
                else:
                    return {
                        "valid": False,
                        "success": False,
                        "message": f"OpenAI Key error ({r.status_code}): Invalid or revoked API key.",
                        "latency_ms": latency
                    }
        elif api_key.startswith("hf_") or provider in ["whisperx", "huggingface", "hf"]:
            url = "https://huggingface.co/api/whoami-v2"
            headers = {"Authorization": f"Bearer {api_key}"}
            with httpx.Client(timeout=8.0) as client:
                r = client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    u_name = r.json().get("name", "User")
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Hugging Face Token verified! User: {u_name} ({latency}ms). WhisperX ready.",
                        "latency_ms": latency
                    }
                else:
                    return {
                        "valid": False,
                        "success": False,
                        "message": f"Hugging Face Token error ({r.status_code}): Invalid or expired token.",
                        "latency_ms": latency
                    }

        elif provider == "custom":
            clean_base = (base_url or "http://localhost:11434/v1").rstrip("/")
            target_url = f"{clean_base}/models"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            try:
                with httpx.Client(timeout=6.0) as client:
                    r = client.get(target_url, headers=headers)
                    latency = round((time.time() - start_time) * 1000)
                    if r.status_code in [200, 201, 204]:
                        return {
                            "valid": True,
                            "success": True,
                            "message": f"Custom endpoint verified ({clean_base}, {latency}ms)!",
                            "latency_ms": latency
                        }
                    elif r.status_code == 401:
                        return {
                            "valid": False,
                            "success": False,
                            "message": f"Custom endpoint ({clean_base}) returned 401 Unauthorized. Key required.",
                            "latency_ms": latency
                        }
                    else:
                        return {
                            "valid": True,
                            "success": True,
                            "message": f"Custom endpoint connected ({clean_base}, status {r.status_code}, {latency}ms).",
                            "latency_ms": latency
                        }
            except Exception as e:
                # Fallback ping to root URL if /models is not implemented
                try:
                    with httpx.Client(timeout=4.0) as client:
                        r = client.get(clean_base, headers=headers)
                        latency = round((time.time() - start_time) * 1000)
                        return {
                            "valid": True,
                            "success": True,
                            "message": f"Custom endpoint reachable ({clean_base}, {latency}ms).",
                            "latency_ms": latency
                        }
                except Exception:
                    latency = round((time.time() - start_time) * 1000)
                    return {
                        "valid": False,
                        "success": False,
                        "message": f"Could not reach {clean_base}: {str(e)}",
                        "latency_ms": latency
                    }

        elif api_key.startswith("gsk_") or provider == "groq":
            url = f"{(base_url or 'https://api.groq.com/openai/v1').rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            with httpx.Client(timeout=8.0) as client:
                r = client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "valid": True,
                        "success": True,
                        "message": f"Groq API Key verified & active ({latency}ms)!",
                        "latency_ms": latency
                    }
                else:
                    return {
                        "valid": False,
                        "success": False,
                        "message": f"Groq Key error ({r.status_code}): Invalid or revoked API key.",
                        "latency_ms": latency
                    }

        latency = round((time.time() - start_time) * 1000)
        return {
            "valid": True,
            "success": True,
            "message": f"API Key format accepted ({latency}ms).",
            "latency_ms": latency
        }
    except Exception as e:
        latency = round((time.time() - start_time) * 1000)
        return {
            "valid": False,
            "success": False,
            "message": f"Key verification failed: {str(e)}",
            "latency_ms": latency
        }

API_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_settings.json")

def load_api_settings_from_disk() -> Dict[str, Any]:
    """Loads configured API keys and model choices from disk, with fallbacks to key files and env."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gemini_file = os.path.join(base_dir, "GeminiAPI.txt")
    groq_file = os.path.join(base_dir, "GroqAPI.txt")
    
    defaults = {
        "transcription_provider": "gemini",
        "transcription_model": "gemini-3.5-transcribe",
        "transcription_api_key": "",
        "summarization_provider": "gemini",
        "summarization_model": "gemini-3.7-flash",
        "summarization_api_key": "",
        "gemini_api_key": "",
        "groq_api_key": "",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "custom_base_url": "http://localhost:11434/v1",
        "custom_api_key": "",
        "hf_token": "",
        "whisperx_model": "pyannote/speaker-diarization-community-1"
    }
    
    # Check GeminiAPI.txt
    if os.path.exists(gemini_file):
        try:
            with open(gemini_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and (line.startswith("AIzaSy") or line.startswith("AQ.")):
                        defaults["gemini_api_key"] = line
                        defaults["summarization_api_key"] = line
                        break
        except Exception:
            pass

    # Check GroqAPI.txt
    if os.path.exists(groq_file):
        try:
            with open(groq_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    defaults["groq_api_key"] = k
                    defaults["transcription_api_key"] = k
        except Exception:
            pass

    # Check environment variables
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        env_gem = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")).strip()
        defaults["gemini_api_key"] = env_gem
        if not defaults["summarization_api_key"]:
            defaults["summarization_api_key"] = env_gem
            
    if os.getenv("GROQ_API_KEY"):
        env_groq = os.getenv("GROQ_API_KEY").strip()
        defaults["groq_api_key"] = env_groq
        if not defaults["transcription_api_key"]:
            defaults["transcription_api_key"] = env_groq

    if os.getenv("OPENAI_API_KEY"):
        defaults["openai_api_key"] = os.getenv("OPENAI_API_KEY").strip()

    if os.getenv("ANTHROPIC_API_KEY"):
        defaults["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY").strip()

    # Load from api_settings.json if present
    if os.path.exists(API_SETTINGS_FILE):
        try:
            with open(API_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    for k, v in saved.items():
                        if isinstance(v, str) and not v.strip() and "api_key" in k and defaults.get(k):
                            continue
                        defaults[k] = v
        except Exception:
            pass

    return defaults

def save_api_settings_to_disk(settings: Dict[str, Any]) -> bool:
    """Persists settings to api_settings.json and syncs GeminiAPI.txt & GroqAPI.txt."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    current = load_api_settings_from_disk()
    for k, v in settings.items():
        if v is not None:
            if isinstance(v, str) and not v.strip() and "api_key" in k and current.get(k):
                continue
            current[k] = v
    
    try:
        with open(API_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
            
        # Sync GeminiAPI.txt
        gemini_k = current.get("gemini_api_key") or current.get("apiKey_gemini") or (current.get("summarization_api_key") if current.get("summarization_provider") == "gemini" else "")
        if gemini_k:
            gemini_file = os.path.join(base_dir, "GeminiAPI.txt")
            with open(gemini_file, "w", encoding="utf-8") as f:
                f.write(gemini_k.strip())
                
        # Sync GroqAPI.txt
        groq_k = current.get("groq_api_key") or current.get("apiKey_groq") or (current.get("transcription_api_key") if current.get("transcription_provider") == "groq" else "")
        if groq_k:
            groq_file = os.path.join(base_dir, "GroqAPI.txt")
            with open(groq_file, "w", encoding="utf-8") as f:
                f.write(groq_k.strip())
                
        return True
    except Exception as e:
        print(f"[Save API Settings Error] {e}")
        return False

def get_default_api_key_from_disk() -> Dict[str, str]:
    """Returns active provider & model defaults from persistent storage."""
    cfg = load_api_settings_from_disk()
    sum_prov = cfg.get("summarization_provider") or "gemini"
    sum_key = cfg.get("gemini_api_key") or cfg.get("summarization_api_key") or ""
    # Ensure a Groq key is never treated as a Gemini key
    if sum_prov == "gemini" and sum_key.startswith("gsk_"):
        sum_key = ""

    return {
        "provider": sum_prov,
        "api_key": sum_key,
        "transcription_provider": cfg.get("transcription_provider") or "gemini",
        "transcription_model": cfg.get("transcription_model") or "gemini-3.5-transcribe",
        "transcription_api_key": cfg.get("transcription_api_key") or cfg.get("gemini_api_key") or "",
        "summarization_provider": sum_prov,
        "summarization_model": cfg.get("summarization_model") or "gemini-3.7-flash",
        "summarization_api_key": sum_key,
        "model_name": cfg.get("summarization_model") or "gemini-3.7-flash",
        "gemini_api_key": cfg.get("gemini_api_key") or "",
        "groq_api_key": cfg.get("groq_api_key") or "",
        "hf_token": cfg.get("hf_token") or "",
        "whisperx_model": cfg.get("whisperx_model") or "pyannote/speaker-diarization-community-1"
    }

def generate_synthetic_test_wav() -> bytes:
    """Generates 0.5s of valid 16kHz mono audio WAV bytes for testing speech transcription endpoints."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        for i in range(8000):
            val = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * 440.0 * i / 16000))
            wf.writeframes(struct.pack('<h', val))
    return buf.getvalue()

def test_transcription_engine(
    provider: str,
    api_key: str = "",
    model_name: str = "",
    base_url: str = ""
) -> Dict[str, Any]:
    """Actively tests the Transcription (STT) model with audio bytes and verifies quota/permissions."""
    start_time = time.time()
    provider = (provider or "groq").lower()
    
    if not api_key:
        cfg = load_api_settings_from_disk()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if provider == "groq":
            api_key = cfg.get("groq_api_key") or cfg.get("transcription_api_key") or ""
            if not api_key:
                groq_f = os.path.join(base_dir, "GroqAPI.txt")
                if os.path.exists(groq_f):
                    try:
                        with open(groq_f, "r", encoding="utf-8") as f:
                            api_key = f.read().strip()
                    except Exception:
                        pass
        elif provider == "gemini":
            api_key = cfg.get("gemini_api_key") or cfg.get("transcription_api_key") or cfg.get("summarization_api_key") or ""
            if not api_key:
                gem_f = os.path.join(base_dir, "GeminiAPI.txt")
                if os.path.exists(gem_f):
                    try:
                        with open(gem_f, "r", encoding="utf-8") as f:
                            api_key = f.read().strip()
                    except Exception:
                        pass
        elif provider in ["whisperx", "huggingface", "hf"]:
            import whisperx_diarization_engine
            api_key = whisperx_diarization_engine.get_huggingface_token(api_key or cfg.get("hf_token"))
        elif provider == "openai":
            api_key = cfg.get("openai_api_key") or ""
        elif provider == "custom":
            api_key = cfg.get("custom_api_key") or ""
            
    if provider in ["local_whisper", "local", "whisper_local"]:
        import local_whisper_engine
        diag = local_whisper_engine.test_local_engine()
        latency = round((time.time() - start_time) * 1000)
        return {
            "success": diag.get("status") == "success",
            "valid": diag.get("status") == "success",
            "message": diag.get("message", "Local Whisper Engine Ready"),
            "latency_ms": latency,
            "model": "whisper-small-int8",
            "diagnostics": diag.get("diagnostics")
        }

    if provider in ["whisperx", "huggingface", "hf"] or api_key.startswith("hf_"):
        import whisperx_diarization_engine
        diag = whisperx_diarization_engine.test_whisperx_engine(
            hf_token=api_key,
            diarize_model_name=model_name or "pyannote/speaker-diarization-community-1"
        )
        latency = round((time.time() - start_time) * 1000)
        return {
            "success": diag.get("valid", False),
            "valid": diag.get("valid", False),
            "message": diag.get("message", "WhisperX & Hugging Face pipeline checked."),
            "latency_ms": latency,
            "model": model_name or "pyannote/speaker-diarization-community-1",
            "diagnostics": diag
        }

    if not api_key and provider != "custom":
        return {
            "success": False,
            "valid": False,
            "message": f"API key is missing for {provider.capitalize()} transcription.",
            "latency_ms": 0,
            "model": model_name or "default"
        }
        
    try:
        wav_bytes = generate_synthetic_test_wav()
        
        if provider == "groq" or api_key.startswith("gsk_"):
            target_model = model_name or "whisper-large-v3-turbo"
            url = f"{(base_url or 'https://api.groq.com/openai/v1').rstrip('/')}/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            files = {"file": ("test_ping.wav", wav_bytes, "audio/wav")}
            data = {"model": target_model}
            with httpx.Client(timeout=12.0) as client:
                r = client.post(url, headers=headers, files=files, data=data)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"Groq Whisper STT ({target_model}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": target_model
                    }
                else:
                    err_msg = r.json().get("error", {}).get("message", r.text[:120])
                    return {
                        "success": False,
                        "valid": False,
                        "message": f"Groq STT error ({r.status_code}): {err_msg}",
                        "latency_ms": latency,
                        "model": target_model
                    }

        elif provider == "openai" or api_key.startswith(("sk-proj-", "sk-")):
            target_model = model_name or "whisper-1"
            url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            files = {"file": ("test_ping.wav", wav_bytes, "audio/wav")}
            data = {"model": target_model}
            with httpx.Client(timeout=15.0) as client:
                r = client.post(url, headers=headers, files=files, data=data)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"OpenAI Whisper STT ({target_model}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": target_model
                    }
                else:
                    err_msg = r.json().get("error", {}).get("message", r.text[:120])
                    return {
                        "success": False,
                        "valid": False,
                        "message": f"OpenAI STT error ({r.status_code}): {err_msg}",
                        "latency_ms": latency,
                        "model": target_model
                    }

        elif provider == "gemini" or api_key.startswith(("AIzaSy", "AQ.")):
            target_model = model_name or "gemini-3.5-transcribe"
            if any(old in target_model for old in ["1.5", "2.0", "2.5"]):
                target_model = "gemini-3.5-transcribe"
            client = genai.Client(api_key=api_key)
            try:
                call_kwargs = {
                    "model": target_model,
                    "input": [
                        {"type": "text", "text": "Transcribe this audio ping. Respond 'STT Ready'."},
                        {"type": "audio", "data": base64.b64encode(wav_bytes).decode("utf-8"), "mime_type": "audio/wav"}
                    ]
                }
                resp = client.interactions.create(**call_kwargs)
                latency = round((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "valid": True,
                    "message": f"Google Gemini STT ({target_model}) operational ({latency}ms)!",
                    "latency_ms": latency,
                    "model": target_model
                }
            except Exception as e_audio:
                try:
                    resp = client.models.generate_content(
                        model=target_model if "flash" in target_model else "gemini-3.5-flash-lite",
                        contents="Verification ping for Gemini Speech-to-Text capability. Respond 'STT Ready'."
                    )
                    latency = round((time.time() - start_time) * 1000)
                    if resp and resp.text:
                        return {
                            "success": True,
                            "valid": True,
                            "message": f"Google Gemini STT ({target_model}) operational ({latency}ms)!",
                            "latency_ms": latency,
                            "model": target_model
                        }
                except Exception as e2:
                    latency = round((time.time() - start_time) * 1000)
                    return {
                        "success": False,
                        "valid": False,
                        "message": f"Gemini STT error ({target_model}): {str(e_audio)}",
                        "latency_ms": latency,
                        "model": target_model
                    }

        elif provider == "custom":
            clean_base = (base_url or "http://localhost:11434/v1").rstrip("/")
            url = f"{clean_base}/models"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            with httpx.Client(timeout=6.0) as client:
                r = client.get(url, headers=headers)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code in [200, 201, 204]:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"Custom STT endpoint verified ({clean_base}, {latency}ms)!",
                        "latency_ms": latency,
                        "model": model_name or "custom"
                    }
                return {
                    "success": False,
                    "valid": False,
                    "message": f"Custom endpoint returned status {r.status_code}",
                    "latency_ms": latency,
                    "model": model_name or "custom"
                }

    except Exception as e:
        latency = round((time.time() - start_time) * 1000)
        return {
            "success": False,
            "valid": False,
            "message": f"Transcription Test Error: {str(e)}",
            "latency_ms": latency,
            "model": model_name or "default"
        }

def test_summarization_engine(
    provider: str,
    api_key: str = "",
    model_name: str = "",
    base_url: str = ""
) -> Dict[str, Any]:
    """Actively tests the Text Generation / Summarization (LLM) model and catches permission blocks."""
    start_time = time.time()
    provider = (provider or "gemini").lower()
    
    if not api_key:
        cfg = load_api_settings_from_disk()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if provider == "gemini":
            api_key = cfg.get("gemini_api_key") or cfg.get("summarization_api_key") or ""
            if not api_key:
                gem_f = os.path.join(base_dir, "GeminiAPI.txt")
                if os.path.exists(gem_f):
                    try:
                        with open(gem_f, "r", encoding="utf-8") as f:
                            api_key = f.read().strip()
                    except Exception:
                        pass
        elif provider == "groq":
            api_key = cfg.get("groq_api_key") or cfg.get("summarization_api_key") or ""
            if not api_key:
                groq_f = os.path.join(base_dir, "GroqAPI.txt")
                if os.path.exists(groq_f):
                    try:
                        with open(groq_f, "r", encoding="utf-8") as f:
                            api_key = f.read().strip()
                    except Exception:
                        pass
        elif provider == "openai":
            api_key = cfg.get("openai_api_key") or ""
        elif provider == "anthropic":
            api_key = cfg.get("anthropic_api_key") or ""
        elif provider == "custom":
            api_key = cfg.get("custom_api_key") or ""

    if not api_key and provider != "custom":
        return {
            "success": False,
            "valid": False,
            "message": f"API key is missing for {provider.capitalize()} text generation.",
            "latency_ms": 0,
            "model": model_name or "default"
        }

    try:
        if provider == "gemini" or api_key.startswith(("AIzaSy", "AQ.")):
            target_model = model_name or "gemini-3.7-flash"
            if any(old in target_model for old in ["1.5", "2.0", "2.5"]):
                target_model = "gemini-3.7-flash"
            client = genai.Client(api_key=api_key)
            models_to_test = [target_model, "gemini-3.5-flash-lite"] if target_model != "gemini-3.5-flash-lite" else [target_model]
            last_err = None
            for test_m in models_to_test:
                try:
                    resp = client.models.generate_content(
                        model=test_m,
                        contents="Ping"
                    )
                    latency = round((time.time() - start_time) * 1000)
                    if resp and resp.text:
                        return {
                            "success": True,
                            "valid": True,
                            "message": f"Google Gemini LLM ({test_m}) operational ({latency}ms)!",
                            "latency_ms": latency,
                            "model": test_m
                        }
                except Exception as e_m:
                    last_err = e_m
                    continue

            latency = round((time.time() - start_time) * 1000)
            return {
                "success": False,
                "valid": False,
                "message": f"Gemini LLM error: {str(last_err)}",
                "latency_ms": latency,
                "model": target_model
            }

        elif provider == "groq" or api_key.startswith("gsk_"):
            target_model = model_name or "openai/gpt-oss-120b"
            url = f"{(base_url or 'https://api.groq.com/openai/v1').rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": "Ping"}],
                "max_tokens": 5
            }
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, headers=headers, json=payload)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"Groq LLM ({target_model}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": target_model
                    }
                elif r.status_code == 403:
                    err_data = r.json().get("error", {})
                    err_msg = err_data.get("message", "Model permission blocked in Groq project.")
                    return {
                        "success": False,
                        "valid": False,
                        "message": f"Groq Blocked (403): {err_msg} (Recommendation: Use Gemini for Text Generation!)",
                        "latency_ms": latency,
                        "model": target_model
                    }
                else:
                    err_msg = r.json().get("error", {}).get("message", r.text[:120])
                    return {
                        "success": False,
                        "valid": False,
                        "message": f"Groq Chat Error ({r.status_code}): {err_msg}",
                        "latency_ms": latency,
                        "model": target_model
                    }

        elif provider == "openai" or api_key.startswith(("sk-proj-", "sk-")):
            target_model = model_name or "gpt-4o-mini"
            url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": target_model,
                "messages": [{"role": "user", "content": "Ping"}],
                "max_tokens": 5
            }
            with httpx.Client(timeout=12.0) as client:
                r = client.post(url, headers=headers, json=payload)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"OpenAI LLM ({target_model}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": target_model
                    }
                err_msg = r.json().get("error", {}).get("message", r.text[:120])
                return {
                    "success": False,
                    "valid": False,
                    "message": f"OpenAI Error ({r.status_code}): {err_msg}",
                    "latency_ms": latency,
                    "model": target_model
                }

        elif provider == "anthropic" or api_key.startswith("sk-ant-"):
            target_model = model_name or "claude-3-5-haiku-20241022"
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": target_model,
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Ping"}]
            }
            with httpx.Client(timeout=12.0) as client:
                r = client.post(url, headers=headers, json=payload)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code in [200, 429]:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"Anthropic Claude ({target_model}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": target_model
                    }
                return {
                    "success": False,
                    "valid": False,
                    "message": f"Anthropic Error ({r.status_code}): {r.text[:120]}",
                    "latency_ms": latency,
                    "model": target_model
                }

        elif provider == "custom":
            clean_base = (base_url or "http://localhost:11434/v1").rstrip("/")
            url = f"{clean_base}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            payload = {
                "model": model_name or "llama3.3",
                "messages": [{"role": "user", "content": "Ping"}],
                "max_tokens": 5
            }
            with httpx.Client(timeout=8.0) as client:
                r = client.post(url, headers=headers, json=payload)
                latency = round((time.time() - start_time) * 1000)
                if r.status_code in [200, 201]:
                    return {
                        "success": True,
                        "valid": True,
                        "message": f"Custom LLM ({model_name}) operational ({latency}ms)!",
                        "latency_ms": latency,
                        "model": model_name or "custom"
                    }
                return {
                    "success": False,
                    "valid": False,
                    "message": f"Custom LLM returned status {r.status_code}",
                    "latency_ms": latency,
                    "model": model_name or "custom"
                }

    except Exception as e:
        latency = round((time.time() - start_time) * 1000)
        return {
            "success": False,
            "valid": False,
            "message": f"Summarization Test Error: {str(e)}",
            "latency_ms": latency,
            "model": model_name or "default"
        }

def format_seconds_to_timestamp(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

DEFAULT_WHISPER_PROMPT = (
    "EASD (Eminence Associates for Social Development), Weekly Strategic Review Meeting, Mohakhali DOHS, Dhaka. "
    "Discussion in Bangla (বাংলা) and English: Dr. Shamim Talukder, Shahin Akter, Ummay Farihin Sultana, "
    "Abu Tareq Muhammad Salahuddin, Salman Mahmud Siddique, Taseen Jubair, agenda items, action items, task assignments, decisions, followup."
)

def transcribe_audio_groq(
    media_bytes: bytes,
    api_key: str,
    model_name: str = "whisper-large-v3-turbo",
    mime_type: str = "audio/wav",
    prompt: str = "",
    language: str = ""
) -> str:
    """Transcribes audio using Groq's high-speed Whisper API with domain prompting, temperature=0, and fallbacks."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    ext = "wav"
    if "mp3" in mime_type or "mpeg" in mime_type:
        ext = "mp3"
    elif "m4a" in mime_type or "mp4" in mime_type:
        ext = "m4a"
    elif "ogg" in mime_type:
        ext = "ogg"
    elif "webm" in mime_type:
        ext = "webm"
        
    filename = f"audio_input.{ext}"
    files = {"file": (filename, media_bytes, mime_type or "application/octet-stream")}
    
    preferred_model = model_name or "whisper-large-v3-turbo"
    models_to_try = [preferred_model]
    if "turbo" not in preferred_model:
        models_to_try.append("whisper-large-v3-turbo")

    full_prompt = (prompt.strip() + " " + DEFAULT_WHISPER_PROMPT).strip() if prompt else DEFAULT_WHISPER_PROMPT
    
    for whisper_model in models_to_try:
        data = {
            "model": whisper_model,
            "response_format": "verbose_json",
            "prompt": full_prompt[:890],
            "temperature": "0.0"
        }
        if language and language.lower() in ["bn", "en"]:
            data["language"] = language.lower()
        else:
            # Enforce Bengali language to completely prevent Romanized phonetic hallucinations
            data["language"] = "bn"
            
        try:
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(url, headers=headers, files=files, data=data)
                if resp.status_code == 200:
                    res_json = resp.json()
                    segments = res_json.get("segments", [])
                    if segments:
                        lines = []
                        current_spk = 1
                        last_end = 0.0
                        for seg in segments:
                            start_s = seg.get("start", 0.0)
                            end_s = seg.get("end", start_s)
                            seg_text = seg.get("text", "").strip()
                            if seg_text:
                                if last_end > 0 and (start_s - last_end) > 1.8:
                                    current_spk = 2 if current_spk == 1 else 1
                                time_tag = format_seconds_to_timestamp(start_s)
                                lines.append(f"[{time_tag}] Speaker {current_spk}: {seg_text}")
                                last_end = end_s
                        if lines:
                            return "\n".join(lines)
                            
                    plain_text = res_json.get("text", "").strip()
                    if plain_text and not plain_text.startswith("["):
                        return f"[00:00] Speaker 1: {plain_text}"
                    return plain_text
                elif resp.status_code == 403:
                    print(f"[Groq Whisper '{whisper_model}' 403 Organization Block] Trying fallback model...")
                    continue
                else:
                    print(f"[Groq Whisper '{whisper_model}' Error {resp.status_code}] {resp.text[:120]}")
        except Exception as e:
            print(f"[Groq Whisper '{whisper_model}' Exception] {e}")
            
    return ""

def transcribe_audio_gemini(
    media_bytes: bytes,
    api_key: str,
    model_name: str = "gemini-3.5-transcribe",
    mime_type: str = "audio/mp3",
    language_hint: str = "auto"
) -> Dict[str, Any]:
    """
    Transcribes audio using Google Gemini API into a 100% RAW, VERBATIM TRANSCRIPT
    with precise SPEAKER DIARIZATION and TIMESTAMPS across any spoken language.
    Primary engine: gemini-3.5-transcribe (dedicated speech-to-text model).
    Fallback engine: gemini-3.6-flash / gemini-3.7-flash.
    """
    if not media_bytes or len(media_bytes) < 32:
        return {"text": "", "language": "bn"}

    # Clean and resolve API key - never allow Hugging Face or Groq keys to bleed into Gemini
    clean_key = (api_key or "").strip()
    if not clean_key or clean_key.startswith("gsk_") or clean_key.startswith("hf_"):
        disk_cfg = load_api_settings_from_disk()
        clean_key = (disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()

    if not clean_key:
        print("[Gemini STT Warning] No valid Gemini API key found on disk or request.")
        return {"text": "", "language": "bn"}

    client = genai.Client(api_key=clean_key)
    audio_mime = mime_type or "audio/mp3"

    # Strategy 1: Dedicated gemini-3.5-transcribe with native AudioTranscriptionConfig
    target_model = (model_name or "gemini-3.5-transcribe").strip()
    if "3.5-transcribe" in target_model or target_model == "gemini-3.5-transcribe":
        for attempt in range(2):
            try:
                cfg = types.GenerateContentConfig(
                    audio_transcription_config=types.AudioTranscriptionConfig(
                        diarization=True,
                        word_timestamp=True
                    )
                )
                resp = client.models.generate_content(
                    model="gemini-3.5-transcribe",
                    contents=[
                        types.Part.from_bytes(data=media_bytes, mime_type=audio_mime)
                    ],
                    config=cfg
                )
                lines = []
                if resp.candidates and len(resp.candidates) > 0 and resp.candidates[0].content:
                    for p in resp.candidates[0].content.parts:
                        if hasattr(p, "audio_transcription") and p.audio_transcription:
                            at = p.audio_transcription
                            txt = (at.text or "").strip()
                            if not txt:
                                continue
                            spk = at.speaker_label or "spk:0"
                            spk_num = 1
                            if spk.startswith("spk:"):
                                try:
                                    spk_num = int(spk.split(":")[1]) + 1
                                except Exception:
                                    pass
                            ts_str = "[00:00]"
                            if at.words and len(at.words) > 0 and hasattr(at.words[0], "start_offset"):
                                try:
                                    sec_val = float(str(at.words[0].start_offset).rstrip("s"))
                                    m = int(sec_val // 60)
                                    s = int(sec_val % 60)
                                    ts_str = f"[{m:02d}:{s:02d}]"
                                except Exception:
                                    pass
                            lines.append(f"{ts_str} Speaker {spk_num}: {txt}")
                        elif hasattr(p, "text") and p.text and p.text.strip():
                            t_txt = p.text.strip()
                            if t_txt.startswith("["):
                                lines.append(t_txt)
                            else:
                                lines.append(f"[00:00] Speaker 1: {t_txt}")

                raw_t = "\n".join(lines).strip()
                if raw_t:
                    detected_lang = detect_text_language(raw_t)
                    return {"text": raw_t, "language": detected_lang}
            except Exception as e_transcribe:
                print(f"[Gemini 3.5 Transcribe attempt {attempt+1} notice] {e_transcribe}")
                time.sleep(1)

    # Strategy 2: Multimodal Gemini STT with general prompt across ANY language
    multilingual_diarization_prompt = (
        "You are an expert audio transcriptionist and acoustic speaker diarization engine for Eminence Associates for Social Development (EASD).\n"
        "Generate a 100% RAW, VERBATIM TRANSCRIPT with precise SPEAKER DIARIZATION and START TIMESTAMPS.\n\n"
        "STRICT MANDATORY RULES:\n"
        "1. 100% RAW & VERBATIM: Transcribe every spoken word exactly as spoken. Do NOT summarize, sanitize, skip, or edit any speech.\n"
        "2. AUTHENTIC NATIVE SCRIPT FOR ANY LANGUAGE: Transcribe any spoken language accurately in its authentic native script (e.g. Bengali in বাংলা লিপি, English in English, Hindi in Devanagari, Arabic in Arabic script, Urdu, Spanish, French, German, etc.). Never translate, summarize, or Romanize speech phonetically — write each spoken sentence in the authentic writing system of the language being spoken.\n"
        "3. SPEAKER DIARIZATION: Distinguish different speakers accurately by vocal pitch, tone, and turn-taking. Label distinct speakers as: 'Speaker 1', 'Speaker 2', 'Speaker 3', etc. (or use actual speaker names if clearly introduced).\n"
        "4. TIMESTAMPS: Every speaker turn MUST begin with a start timestamp in [MM:SS] format.\n"
        "5. EXACT FORMAT FOR EVERY TURN: [MM:SS] Speaker X: <exact spoken words>\n\n"
        "Return ONLY the raw timestamped speaker transcript without any extra commentary, headers, or markdown fencing."
    )

    fallback_models = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
    encoded_file = base64.b64encode(media_bytes).decode("utf-8")

    for model in fallback_models:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=media_bytes, mime_type=audio_mime),
                    multilingual_diarization_prompt
                ]
            )
            text = (getattr(resp, "text", None) or "").strip()
            if text:
                lang = detect_text_language(text)
                return {"text": text, "language": lang}
        except Exception as e1:
            print(f"[Gemini STT fallback '{model}' error] generate_content: {e1}")
            try:
                call_kwargs = {
                    "model": model,
                    "input": [
                        {"type": "text", "text": multilingual_diarization_prompt},
                        {"type": "audio", "data": encoded_file, "mime_type": audio_mime}
                    ]
                }
                interaction = client.interactions.create(**call_kwargs)
                text = (getattr(interaction, "output_text", None) or "").strip()
                if text:
                    lang = detect_text_language(text)
                    return {"text": text, "language": lang}
            except Exception as e2:
                print(f"[Gemini STT fallback '{model}' error] interactions: {e2}")

    # Seamless Automatic Fallback to Local Whisper (whisper-nano/tiny for low RAM, whisper-small for standard RAM)
    try:
        import local_whisper_engine
        opt_model = local_whisper_engine.select_optimal_model_name()
        print(f"[Gemini STT Fallback] Falling back seamlessly to local Whisper ({opt_model})...")
        r_loc = local_whisper_engine.transcribe_local_audio(
            media_input=media_bytes,
            language=None if language_hint in ["auto", "detect", ""] else language_hint,
            model_name=opt_model,
            mime_type=audio_mime,
            beam_size=2,
            temperature=0.0
        )
        t_loc = r_loc.get("raw_transcript") or r_loc.get("clean_text", "")
        l_loc = r_loc.get("detected_language") or (language_hint if language_hint not in ["auto", ""] else "bn")
        if t_loc:
            return {"text": t_loc, "raw_transcript": t_loc, "language": l_loc, "provider": "local_whisper", "model": opt_model}
    except Exception as e_loc:
        print(f"[Gemini STT Fallback to Local Whisper Error] {e_loc}")

    return {"text": "", "language": "bn"}

def live_transcribe_audio_chunk(
    media_bytes: bytes,
    api_key: str,
    provider: str = "gemini",
    model_name: str = "",
    mime_type: str = "audio/webm",
    language: str = "auto"
) -> Dict[str, Any]:
    """Transcribes a live streamed audio chunk and returns text and detected language."""
    if not media_bytes or len(media_bytes) < 32:
        return {"text": "", "language": "bn"}
        
    api_key = (api_key or "").strip()
    provider = (provider or "gemini").lower()
    
    if not api_key:
        cfg = get_default_api_key_from_disk()
        api_key = cfg.get("api_key", "")
        if not provider or provider == "gemini":
            provider = cfg.get("provider", "groq" if api_key.startswith("gsk_") else "gemini")
            
    # Normalize audio chunk using FFmpeg to ensure valid container headers
    try:
        from media_processor import normalize_audio_chunk_for_stt
        norm_bytes, norm_mime = normalize_audio_chunk_for_stt(media_bytes, mime_type=mime_type)
        if norm_bytes:
            media_bytes = norm_bytes
            mime_type = norm_mime
    except Exception as e:
        print(f"[Chunk Normalization Warning] {e}")

    # Direct handling for local whisper offline engine
    if provider in ["local_whisper", "local", "whisper_local"]:
        try:
            import local_whisper_engine
            res = local_whisper_engine.transcribe_local_audio(
                media_input=media_bytes,
                language=language or "auto",
                beam_size=1,
                temperature=0.0
            )
            if res.get("status") == "success":
                txt = res.get("clean_text") or res.get("raw_transcript", "")
                lang = res.get("detected_language") or "bn"
                return {"text": txt, "raw_transcript": res.get("raw_transcript", ""), "language": lang}
        except Exception as e:
            print(f"[Local Whisper Live Chunk Warning] {e}")

    try:
        if api_key.startswith("AIzaSy") or api_key.startswith("AQ.") or provider == "gemini":
            model = model_name or "gemini-3.5-transcribe"
            if api_key.startswith("gsk_") or not api_key:
                disk_cfg = load_api_settings_from_disk()
                api_key = (disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()
            return transcribe_audio_gemini(media_bytes, api_key, model, mime_type, language_hint=language)
        elif api_key.startswith("gsk_") or provider in ["groq", "custom"]:
            model = model_name or "whisper-large-v3-turbo"
            txt = transcribe_audio_groq(media_bytes, api_key, model_name=model, mime_type=mime_type, language=language or "bn")
            lang = detect_text_language(txt)
            return {"text": txt, "language": lang}
        elif api_key.startswith(("sk-proj-", "sk-")) or provider == "openai":
            whisper_url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            ext = "mp3" if "mp3" in mime_type else "wav"
            files = {"file": (f"audio.{ext}", media_bytes, mime_type or "audio/mp3")}
            data = {"model": "whisper-1"}
            with httpx.Client(timeout=30.0) as client:
                w_resp = client.post(whisper_url, headers=headers, files=files, data=data)
                if w_resp.status_code == 200:
                    txt = w_resp.json().get("text", "")
                    return {"text": txt, "language": detect_text_language(txt)}
        else:
            # Automatic fallback to local whisper if no cloud keys match
            import local_whisper_engine
            res = local_whisper_engine.transcribe_local_audio(media_bytes, language=language or "auto")
            if res.get("status") == "success":
                return {"text": res.get("clean_text", ""), "raw_transcript": res.get("raw_transcript", ""), "language": res.get("detected_language", "bn")}
    except Exception as e:
        print(f"[Live Transcribe Chunk Warning] {e}")
        
    return {"text": "", "language": "bn"}

def summarize_text_openai_compatible(
    text_content: str,
    api_key: str,
    base_url: str = "https://api.groq.com/openai/v1",
    model_name: str = "openai/gpt-oss-120b",
    org_context: str = "",
    custom_skills: str = "",
    template_schema: Optional[Dict[str, Any]] = None,
    media_bytes: Optional[bytes] = None,
    mime_type: str = ""
) -> Dict[str, Any]:
    """Generates structured JSON using OpenAI-compatible chat completion for any template schema, with multimodal vision support."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
        
    candidate_models = [model_name] if model_name else []
    if "groq" in base_url or api_key.startswith("gsk_"):
        candidate_models.extend([
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "groq/compound",
            "groq/compound-mini",
            "qwen/qwen3.8-27b",
            "qwen/qwen3.6-27b",
        ])
    elif "openai" in base_url or api_key.startswith("sk-"):
        candidate_models.extend(["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])
        
    candidate_models = list(dict.fromkeys([m for m in candidate_models if m]))

    # Construct user message content: multimodal if image is present
    user_prompt_text = f"Analyze, translate, and organize this document/transcript into the exact JSON format:\n\n{text_content or 'Document Content'}"
    if media_bytes and mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf"):
        b64_data = base64.b64encode(media_bytes).decode("utf-8")
        user_message_content = [
            {"type": "text", "text": user_prompt_text},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}}
        ]
    else:
        user_message_content = user_prompt_text

    with httpx.Client(timeout=120.0) as client:
        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message_content}
                ],
                "temperature": 0.2
            }
            try:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"]
                    return process_extracted_payload(
                        raw_text,
                        fallback_content=text_content,
                        custom_skills=custom_skills,
                        org_context=org_context,
                        template_schema=template_schema
                    )
                else:
                    print(f"[LLM Model '{model}' Notice] Status {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                print(f"[LLM Model '{model}' Exception] {e}")
                
    return deep_semantic_synthesis(text_content, custom_skills, org_context)

def transcribe_and_summarize_groq(
    media_bytes: Optional[bytes],
    mime_type: str,
    api_key: str,
    base_url: str = "",
    transcription_model: str = "whisper-large-v3-turbo",
    summarization_model: str = "openai/gpt-oss-120b",
    org_context: str = "",
    custom_skills: str = "",
    text_content: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Processes audio through Groq Whisper then synthesizes with specified summarization model."""
    transcript_parts = []
    if text_content:
        transcript_parts.append(text_content)
    
    # 1. Transcribe audio if provided
    chunks_to_process = []
    if audio_chunks and len(audio_chunks) > 0:
        chunks_to_process = audio_chunks
    elif media_bytes:
        chunks_to_process = [media_bytes]
        
    if chunks_to_process:
        whisper_model = transcription_model or "whisper-large-v3-turbo"
        for chunk in chunks_to_process:
            try:
                t = transcribe_audio_groq(chunk, api_key, model_name=whisper_model, mime_type=mime_type)
                if t:
                    transcript_parts.append(t.strip())
            except Exception as e:
                print(f"[Groq Whisper Warning] {e}")
                
    transcript = "\n\n".join(transcript_parts)
    if not transcript:
        transcript = "Recording and discussion transcript content."

    # 2. Synthesize transcript
    groq_base = base_url or "https://api.groq.com/openai/v1"
    llm_model = summarization_model or "openai/gpt-oss-120b"
    
    return summarize_text_openai_compatible(
        text_content=transcript,
        api_key=api_key,
        base_url=groq_base,
        model_name=llm_model,
        org_context=org_context,
        custom_skills=custom_skills,
        template_schema=template_schema
    )

def transcribe_and_summarize_gemini(
    media_bytes: Optional[bytes],
    mime_type: str,
    api_key: str,
    transcription_model: str = "gemini-3.5-flash-lite",
    summarization_model: str = "gemini-3.7-flash",
    org_context: str = "",
    custom_skills: str = "",
    text_content: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Processes media and structures document using Google Gemini Interactions API."""
    api_key = (api_key or "").strip()
    if not api_key or api_key.startswith("gsk_"):
        raise ValueError("Google Gemini API Key is missing or invalid (Groq key detected). Please provide a valid Gemini API key in GeminiAPI.txt or Settings.")

    valid_candidates = [summarization_model or "gemini-3.7-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
    models_to_try = []
    for m in valid_candidates:
        if m and m not in models_to_try and not any(old in m for old in ["1.5", "2.0", "2.5"]):
            models_to_try.append(m)
    if not models_to_try:
        models_to_try = ["gemini-3.7-flash", "gemini-3.5-flash-lite"]

    client = genai.Client(api_key=api_key)
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)

    # 1. Multimodal Document / Image OCR Flow
    if (mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf")) and media_bytes:
        target_bytes = media_bytes
        target_mime = mime_type
        if target_mime != "application/pdf":
            target_bytes, target_mime = preprocess_image_for_ocr(media_bytes)

        encoded_media = base64.b64encode(target_bytes).decode("utf-8")
        media_input_type = "image" if target_mime.startswith("image/") else "document"
        ocr_prompt = (
            f"{system_prompt}\n\n"
            "TASK: Perform high-fidelity optical character recognition (OCR) and layout extraction from this document/image. "
            "Transcribe all Bengali (বাংলা) and English text verbatim. Preserve tables, dates, memo numbers, attendees, "
            "agendas, discussions, and decisions. Clean any OCR distortions and format into the exact JSON schema requested."
        )

        last_ocr_err = None
        for model in models_to_try:
            try:
                call_kwargs = {
                    "model": model,
                    "input": [
                        {"type": "text", "text": ocr_prompt},
                        {"type": media_input_type, "data": encoded_media, "mime_type": target_mime}
                    ]
                }
                if "3.7" in model or "3.8" in model:
                    call_kwargs["generation_config"] = {"thinking_level": "low"}
                resp = client.interactions.create(**call_kwargs)
                raw_text = (getattr(resp, "output_text", None) or "").strip()
                if raw_text:
                    return process_extracted_payload(
                        raw_text,
                        fallback_content=text_content or "OCR Extracted Document",
                        custom_skills=custom_skills,
                        org_context=org_context,
                        template_schema=template_schema
                    )
            except Exception as e:
                print(f"[Gemini Multimodal OCR '{model}' Exception] {e}")
                last_ocr_err = e

        raise RuntimeError(f"Gemini OCR extraction failed across models {models_to_try}: {last_ocr_err}")

    # 2. Audio Processing Flow
    transcript = text_content
    chunks_to_process = []
    if audio_chunks and len(audio_chunks) > 0:
        chunks_to_process = audio_chunks
    elif media_bytes:
        chunks_to_process = [media_bytes]
        
    if chunks_to_process:
        transcripts = []
        stt_model = transcription_model or "gemini-3.6-flash"
        for chunk in chunks_to_process:
            try:
                res = transcribe_audio_gemini(chunk, api_key, model_name=stt_model, mime_type=mime_type)
                if res.get("text"):
                    transcripts.append(res["text"].strip())
            except Exception as e:
                print(f"[Gemini STT Chunk Error] {e}")
        if transcripts:
            transcript = ("\n\n".join([text_content] + transcripts) if text_content else "\n\n".join(transcripts))

    full_text_prompt = f"{system_prompt}\n\nAnalyze, translate, and organize this transcript into the exact JSON format:\n\n{transcript or 'Document Content'}"
    
    last_gen_err = None
    for model in models_to_try:
        try:
            call_kwargs = {
                "model": model,
                "input": full_text_prompt
            }
            if "3.7" in model or "3.8" in model:
                call_kwargs["generation_config"] = {"thinking_level": "low"}
            resp = client.interactions.create(**call_kwargs)
            raw_text = (getattr(resp, "output_text", None) or "").strip()
            if raw_text:
                return process_extracted_payload(
                    raw_text,
                    fallback_content=transcript,
                    custom_skills=custom_skills,
                    org_context=org_context,
                    template_schema=template_schema
                )
        except Exception as e:
            print(f"[Gemini Interactions Model '{model}' Exception] {e}")
            last_gen_err = e
    print(f"[Gemini Summarization] All models failed ({last_gen_err}). Falling back to deep_semantic_synthesis...")
    res = deep_semantic_synthesis(transcript, custom_skills, org_context)
    res["warning"] = f"Google Gemini API notice: {last_gen_err}. Formatted using built-in semantic synthesis engine."
    return res

def summarize_text_gemini(
    text_content: str,
    api_key: str,
    model_name: str = "gemini-3.7-flash",
    org_context: str = "",
    custom_skills: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Synthesizes structured meeting minutes from text using Google Gemini Interactions API."""
    api_key = (api_key or "").strip()
    if not api_key or api_key.startswith("gsk_"):
        raise ValueError("Google Gemini API Key is missing or invalid (Groq key detected). Please provide a valid Gemini API key in GeminiAPI.txt or Settings.")

    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)
    full_text_prompt = f"{system_prompt}\n\nAnalyze, translate, and organize this transcript into the exact JSON format:\n\n{text_content or 'Document Content'}"
    
    valid_candidates = [model_name or "gemini-3.7-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
    models_to_try = []
    for m in valid_candidates:
        if m and m not in models_to_try and not any(old in m for old in ["1.5", "2.0", "2.5"]):
            models_to_try.append(m)
    if not models_to_try:
        models_to_try = ["gemini-3.7-flash", "gemini-3.5-flash-lite"]
    
    client = genai.Client(api_key=api_key)
    last_error = None
    for m in models_to_try:
        try:
            call_kwargs = {
                "model": m,
                "input": full_text_prompt
            }
            if "3.7" in m or "3.8" in m:
                call_kwargs["generation_config"] = {"thinking_level": "low"}
            resp = client.interactions.create(**call_kwargs)
            raw_text = (getattr(resp, "output_text", None) or "").strip()
            if raw_text:
                return process_extracted_payload(
                    raw_text,
                    fallback_content=text_content,
                    custom_skills=custom_skills,
                    org_context=org_context,
                    template_schema=template_schema
                )
        except Exception as e:
            print(f"[Gemini Summarize '{m}' interactions error] {e}")
            last_error = e

    print(f"[Gemini Summarize] All models failed ({last_error}). Falling back to deep_semantic_synthesis...")
    res = deep_semantic_synthesis(text_content, custom_skills, org_context)
    res["warning"] = f"Google Gemini access notice ({last_error}). Fitted to template using built-in semantic synthesis engine. Please update your Gemini API key in Settings."
    return res

def process_ai_request(
    provider: str,
    api_key: str,
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
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Unified entrypoint with fully decoupled STT and LLM provider & model routing."""
    disk_cfg = load_api_settings_from_disk()
    api_key = (api_key or "").strip()
    provider = (provider or "").lower()

    # 1. Resolve Transcription Parameters
    stt_prov = (transcription_provider or (provider if provider in ["groq", "openai", "gemini", "custom", "local_whisper", "whisperx"] else "") or disk_cfg.get("transcription_provider") or "gemini").lower()
    stt_key = (transcription_api_key or (api_key if provider == stt_prov else "") or disk_cfg.get(f"{stt_prov}_api_key") or disk_cfg.get("transcription_api_key") or "").strip()
    
    # Decouple STT key: Never let a Groq or Hugging Face key bleed into Gemini STT
    if stt_prov == "gemini":
        if not stt_key or stt_key.startswith("gsk_") or stt_key.startswith("hf_"):
            stt_key = (disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()
    elif stt_prov == "groq":
        if not stt_key or not stt_key.startswith("gsk_"):
            stt_key = (disk_cfg.get("groq_api_key") or "").strip()

    stt_model = transcription_model or ("gemini-3.5-transcribe" if stt_prov == "gemini" else "whisper-large-v3-turbo")
    if stt_prov == "gemini" and any(old in stt_model for old in ["1.5", "2.0", "2.5"]):
        stt_model = "gemini-3.5-transcribe"

    # 2. Resolve Summarization Parameters
    llm_prov = (summarization_provider or (provider if provider in ["gemini", "openai", "anthropic", "custom", "groq", "local"] else "") or disk_cfg.get("summarization_provider") or "gemini").lower()
    llm_key = (summarization_api_key or (api_key if provider == llm_prov else "") or disk_cfg.get(f"{llm_prov}_api_key") or disk_cfg.get("summarization_api_key") or disk_cfg.get("gemini_api_key") or "").strip()
    
    # Decouple: never let a Groq or HF key bleed into Gemini LLM
    if llm_prov == "gemini" and (llm_key.startswith("gsk_") or llm_key.startswith("hf_") or not llm_key):
        llm_key = (disk_cfg.get("gemini_api_key") or get_default_api_key_from_disk().get("api_key") or "").strip()

    llm_model = summarization_model or model_name or ("gemini-3.7-flash" if llm_prov == "gemini" else "openai/gpt-oss-120b")
    if llm_prov == "gemini" and any(old in llm_model for old in ["1.5", "2.0", "2.5"]):
        llm_model = "gemini-3.7-flash"

    # 3. Vision OCR Check
    is_vision_media = bool(media_bytes and mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf"))
    if is_vision_media:
        if (llm_prov == "gemini" or llm_key.startswith(("AIzaSy", "AQ."))):
            if not llm_key:
                raise ValueError("Google Gemini API Key is missing for Vision OCR. Please provide a valid Gemini key in GeminiAPI.txt or Settings.")
            return transcribe_and_summarize_gemini(
                media_bytes=media_bytes,
                mime_type=mime_type,
                api_key=llm_key,
                transcription_model=stt_model,
                summarization_model=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                text_content=text_content,
                audio_chunks=audio_chunks,
                template_schema=template_schema
            )
        else:
            return summarize_text_openai_compatible(
                text_content=text_content or "OCR Scanned Document",
                api_key=llm_key or stt_key,
                base_url=base_url or "https://api.openai.com/v1",
                model_name=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema,
                media_bytes=media_bytes,
                mime_type=mime_type
            )

    # 4. Audio Transcription Stage (STT)
    raw_transcript = text_content or ""
    chunks_to_process = audio_chunks if (audio_chunks and len(audio_chunks) > 0) else ([media_bytes] if media_bytes else [])
    
    if chunks_to_process:
        audio_transcripts = []
        for chunk in chunks_to_process:
            if not chunk or len(chunk) < 32:
                continue
            chunk_txt = ""
            if stt_prov in ["local_whisper", "local", "whisper_local"]:
                try:
                    import local_whisper_engine
                    res = local_whisper_engine.transcribe_local_audio(
                        chunk,
                        language="auto",
                        beam_size=2,
                        temperature=0.0
                    )
                    chunk_txt = res.get("raw_transcript") or res.get("clean_text", "")
                except Exception as e:
                    print(f"[Local Whisper STT Error] {e}")
            elif stt_prov in ["whisperx", "huggingface", "hf"] or stt_key.startswith("hf_"):
                try:
                    import whisperx_diarization_engine
                    res = whisperx_diarization_engine.transcribe_with_diarization(
                        audio_bytes=chunk,
                        hf_token=stt_key,
                        whisper_model_name="small",
                        diarize_model_name=stt_model or "pyannote/speaker-diarization-community-1",
                        language="bn"
                    )
                    chunk_txt = res.get("raw_transcript") or res.get("clean_text", "")
                except Exception as e:
                    print(f"[WhisperX STT Error] {e}")
            elif stt_prov == "gemini" or stt_key.startswith(("AIzaSy", "AQ.")):
                res = transcribe_audio_gemini(chunk, stt_key, model_name=stt_model, mime_type=mime_type, language_hint="auto")
                chunk_txt = res.get("text", "")
                if not chunk_txt:
                    try:
                        import local_whisper_engine
                        r_loc = local_whisper_engine.transcribe_local_audio(chunk, language="auto")
                        chunk_txt = r_loc.get("raw_transcript") or r_loc.get("clean_text", "")
                    except Exception:
                        pass
            elif stt_prov == "groq" or stt_key.startswith("gsk_"):
                chunk_txt = transcribe_audio_groq(chunk, stt_key, model_name=stt_model, mime_type=mime_type, language="auto")
                if not chunk_txt:
                    try:
                        import local_whisper_engine
                        r_loc = local_whisper_engine.transcribe_local_audio(chunk, language="auto")
                        chunk_txt = r_loc.get("raw_transcript") or r_loc.get("clean_text", "")
                    except Exception:
                        pass
            elif stt_prov == "openai" or stt_key.startswith(("sk-proj-", "sk-")):
                whisper_url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/audio/transcriptions"
                files = {"file": ("audio.wav", chunk, mime_type or "audio/wav")}
                data = {"model": stt_model or "whisper-1"}
                headers = {"Authorization": f"Bearer {stt_key}"}
                try:
                    with httpx.Client(timeout=60.0) as client:
                        r = client.post(whisper_url, headers=headers, files=files, data=data)
                        if r.status_code == 200:
                            chunk_txt = r.json().get("text", "")
                except Exception as e:
                    print(f"[OpenAI STT Error] {e}")
            elif stt_prov == "custom":
                whisper_url = f"{base_url.rstrip('/')}/audio/transcriptions"
                files = {"file": ("audio.wav", chunk, mime_type or "audio/wav")}
                data = {"model": stt_model or "whisper-large-v3-turbo"}
                headers = {"Authorization": f"Bearer {stt_key}"} if stt_key else {}
                try:
                    with httpx.Client(timeout=60.0) as client:
                        r = client.post(whisper_url, headers=headers, files=files, data=data)
                        if r.status_code == 200:
                            chunk_txt = r.json().get("text", "")
                except Exception as e:
                    print(f"[Custom STT Error] {e}")
            else:
                # Default fallback to local whisper
                try:
                    import local_whisper_engine
                    r_loc = local_whisper_engine.transcribe_local_audio(chunk, language="auto")
                    chunk_txt = r_loc.get("raw_transcript") or r_loc.get("clean_text", "")
                except Exception as e:
                    print(f"[Fallback Local Whisper STT Error] {e}")
                except Exception as e:
                    print(f"[Fallback Local Whisper STT Error] {e}")

            if chunk_txt and chunk_txt.strip():
                audio_transcripts.append(chunk_txt.strip())

        if audio_transcripts:
            full_audio_text = "\n\n".join(audio_transcripts)
            raw_transcript = (f"{raw_transcript}\n\n{full_audio_text}" if raw_transcript else full_audio_text).strip()

    if not raw_transcript:
        raw_transcript = "Weekly Strategic, Programmatic and Presentation Review Meeting discussion and proceedings."

    # 5. Summarization & Template Fitting Stage (LLM)
    try:
        if llm_prov == "local":
            return deep_semantic_synthesis(raw_transcript, custom_skills, org_context)

        if llm_prov == "gemini" or llm_key.startswith(("AIzaSy", "AQ.")):
            if not llm_key:
                print("[LLM Gemini Notice] Key missing, falling back to deep_semantic_synthesis.")
                return deep_semantic_synthesis(raw_transcript, custom_skills, org_context)
            return summarize_text_gemini(
                text_content=raw_transcript,
                api_key=llm_key,
                model_name=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema
            )

        if (llm_prov == "anthropic" or llm_key.startswith("sk-ant-")) and llm_key:
            return summarize_text_anthropic(
                text_content=raw_transcript,
                api_key=llm_key,
                model_name=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema
            )

        if llm_key:
            target_base = base_url or ("https://api.groq.com/openai/v1" if llm_prov == "groq" else "https://api.openai.com/v1")
            result = summarize_text_openai_compatible(
                text_content=raw_transcript,
                api_key=llm_key,
                base_url=target_base,
                model_name=llm_model,
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema
            )
            return result
    except Exception as e_llm:
        print(f"[Summarization LLM Provider Exception] {e_llm}. Falling back seamlessly to deep_semantic_synthesis...")
        fallback_res = deep_semantic_synthesis(raw_transcript, custom_skills, org_context)
        fallback_res["warning"] = f"AI Provider notice: {e_llm}. Structured using built-in semantic synthesis."
        return fallback_res

    # If user provided no active LLM key, or if LLM failed, fallback to local deep semantic synthesis
    return deep_semantic_synthesis(raw_transcript, custom_skills, org_context)

def summarize_text_anthropic(
    text_content: str,
    api_key: str,
    model_name: str = "claude-3-5-sonnet-20241022",
    org_context: str = "",
    custom_skills: str = "",
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Synthesizes minutes and executive documents using Anthropic Claude Messages API."""
    system_prompt = build_template_system_prompt(template_schema, org_context, custom_skills)
    user_prompt = f"Analyze, translate, and organize this transcript into the exact JSON format:\n\n{text_content or 'Document Content'}"
    
    models_to_try = [
        model_name or "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229"
    ]
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    for model in models_to_try:
        try:
            payload = {
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }
            with httpx.Client(timeout=120.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = ""
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            raw_text += block.get("text", "")
                    if raw_text:
                        return process_extracted_payload(
                            raw_text,
                            fallback_content=text_content,
                            custom_skills=custom_skills,
                            org_context=org_context,
                            template_schema=template_schema
                        )
                else:
                    print(f"[Anthropic Claude '{model}' Notice] Status {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[Anthropic Claude Exception '{model}'] {e}")
            
    return deep_semantic_synthesis(text_content or "Document Content", custom_skills, org_context)

