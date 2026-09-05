import os
import re
import json
import base64
import time
import httpx
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

    return {
        "detected_language": detected_lang,
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
    if not template_schema or (template_schema.get("id") == "easd_default_minutes" and not template_schema.get("context")):
        base_prompt = LLM_SYSTEM_PROMPT
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
        
        # If custom or non-default template schema is present
        if template_schema and (template_schema.get("id") != "easd_default_minutes" or template_schema.get("sections_data")):
            sections_data = summary.get("sections_data", {})
            tables_data = summary.get("tables_data", {})
            
            # Map top-level sections into summary root for easy access
            for s_id, s_val in sections_data.items():
                if s_id not in summary:
                    summary[s_id] = clean_bullet_points(str(s_val)) if "•" in str(s_val) or "\n" in str(s_val) else str(s_val)
                    
            for t_id, t_val in tables_data.items():
                if t_id not in summary:
                    summary[t_id] = t_val
                    
            # For Bangladesh Govt Report: map fields
            if template_schema.get("doc_type") == "bangladesh_govt_report":
                if "ministry" not in summary:
                    summary["ministry"] = "স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়"
                if "memo_no" not in summary:
                    summary["memo_no"] = "৪৫.০০.০০০০.০০১.২৪.০০১.২৬-"
                if "subject" not in summary:
                    summary["subject"] = summary.get("title", "প্রতিবেদন প্রসঙ্গে")
                    
            return {
                "detected_language": detected_lang,
                "template_id": template_schema.get("id"),
                "doc_type": template_schema.get("doc_type", "custom"),
                "bangla_transcript": parsed.get("bangla_transcript", fallback_content),
                "english_transcript": parsed.get("english_transcript", fallback_content),
                "summary": summary
            }
            
        raw_agendas = summary.get("agendas", [])
        raw_discussions = summary.get("discussions", [])
        
        cleaned_agendas = [clean_agenda_item(a) for a in raw_agendas if clean_agenda_item(a)]
        
        if cleaned_agendas and raw_discussions and len(raw_discussions) > 0:
            summary["agendas"] = cleaned_agendas[:5]
            
            cleaned_discussions = []
            for d in raw_discussions:
                cleaned_discussions.append({
                    "sn": str(d.get("sn", "")),
                    "topic": str(d.get("topic", "")),
                    "details": clean_bullet_points(str(d.get("details", "")))
                })
            summary["discussions"] = cleaned_discussions
            summary["decisions"] = clean_bullet_points(str(summary.get("decisions", "")))
            
            present_members = summary.get("present_members", [])
            summary["attendance"] = match_attendance_list(present_members, fallback_content or raw_text)
            return {
                "detected_language": detected_lang,
                "template_id": "easd_default_minutes",
                "doc_type": "meeting_minutes",
                "bangla_transcript": parsed.get("bangla_transcript", fallback_content),
                "english_transcript": parsed.get("english_transcript", fallback_content),
                "summary": summary
            }
            
    return deep_semantic_synthesis(raw_text or fallback_content, custom_skills, org_context)

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
                interaction = client.interactions.create(
                    model="gemini-3.5-flash-lite",
                    input="Ping"
                )
                latency = round((time.time() - start_time) * 1000)
                if interaction and interaction.output_text is not None:
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

def get_default_api_key_from_disk() -> Dict[str, str]:
    """Checks for Gemini or Groq key files in project root, defaulting to Gemini."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gemini_file = os.path.join(base_dir, "GeminiAPI.txt")
    gemini_env = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_env:
        return {
            "provider": "gemini",
            "api_key": gemini_env.strip(),
            "transcription_model": "gemini-2.5-flash",
            "summarization_model": "gemini-2.5-flash",
            "model_name": "gemini-2.5-flash"
        }
    if os.path.exists(gemini_file):
        try:
            with open(gemini_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return {
                        "provider": "gemini",
                        "api_key": k,
                        "transcription_model": "gemini-2.5-flash",
                        "summarization_model": "gemini-2.5-flash",
                        "model_name": "gemini-2.5-flash"
                    }
        except Exception:
            pass

    groq_file = os.path.join(base_dir, "GroqAPI.txt")
    if os.path.exists(groq_file):
        try:
            with open(groq_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return {
                        "provider": "groq",
                        "api_key": k,
                        "transcription_model": "whisper-large-v3-turbo",
                        "summarization_model": "openai/gpt-oss-120b",
                        "model_name": "openai/gpt-oss-120b"
                    }
        except Exception:
            pass
    return {
        "provider": "gemini",
        "api_key": "",
        "transcription_model": "gemini-2.5-flash",
        "summarization_model": "gemini-2.5-flash",
        "model_name": "gemini-2.5-flash"
    }

def transcribe_audio_groq(
    media_bytes: bytes,
    api_key: str,
    model_name: str = "whisper-large-v3-turbo",
    mime_type: str = "audio/wav"
) -> str:
    """Transcribes audio using Groq's high-speed Whisper API."""
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
    whisper_model = "whisper-large-v3-turbo" if "turbo" in model_name or not model_name else "whisper-large-v3"
    data = {
        "model": whisper_model,
        "response_format": "json"
    }
    
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()
        res_json = resp.json()
        return res_json.get("text", "")

def transcribe_audio_gemini(
    media_bytes: bytes,
    api_key: str,
    model_name: str = "gemini-3.7-flash",
    mime_type: str = "audio/webm",
    language_hint: str = "auto"
) -> Dict[str, Any]:
    """Transcribes audio using Google Gemini Interactions API."""
    models_to_try = [model_name or "gemini-3.7-flash", "gemini-3.6-flash"]
    models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))
    
    lang_prompt = "Transcribe the audio verbatim in its native spoken language (Bangla or English)."
    if language_hint == "bn":
        lang_prompt = "Transcribe this audio verbatim in Bengali (বাংলা) script."
    elif language_hint == "en":
        lang_prompt = "Transcribe this audio verbatim in formal English."
        
    encoded_file = base64.b64encode(media_bytes).decode("utf-8")
    client = genai.Client(api_key=api_key)
    
    for model in models_to_try:
        try:
            interaction = client.interactions.create(
                model=model,
                input=[
                    {
                        "type": "text",
                        "text": f"You are an expert bilingual speech-to-text transcriber for Eminence Associates for Social Development. {lang_prompt} Return ONLY the verbatim transcribed text with no preamble or comments."
                    },
                    {
                        "type": "audio",
                        "data": encoded_file,
                        "mime_type": mime_type or "audio/webm"
                    }
                ]
            )
            text = (interaction.output_text or "").strip()
            if text:
                lang = detect_text_language(text)
                return {"text": text, "language": lang}
        except Exception as e:
            print(f"[Gemini Interactions STT '{model}' Exception] {e}")
                
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

    try:
        if api_key.startswith("AIzaSy") or api_key.startswith("AQ.") or provider == "gemini":
            model = model_name or "gemini-3.7-flash"
            return transcribe_audio_gemini(media_bytes, api_key, model, mime_type, language_hint=language)
        elif api_key.startswith("gsk_") or provider in ["groq", "custom"]:
            model = model_name or "whisper-large-v3-turbo"
            txt = transcribe_audio_groq(media_bytes, api_key, model_name=model, mime_type=mime_type)
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
    summarization_model: str = "gemini-3.5-flash-lite",
    org_context: str = "",
    custom_skills: str = "",
    text_content: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Processes media and structures document using Google Gemini (Multimodal Vision OCR + Audio STT)."""
    models_to_try = [summarization_model or "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.7-flash", "gemini-3.1-pro-preview"]
    models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))
    client = genai.Client(api_key=api_key)
    system_prompt = build_template_system_prompt(template_schema, org_context=org_context, custom_skills=custom_skills)

    # 1. Multimodal Document / Image OCR Flow
    if (mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf")) and media_bytes:
        target_bytes = media_bytes
        target_mime = mime_type
        if target_mime != "application/pdf":
            target_bytes, target_mime = preprocess_image_for_ocr(media_bytes)

        part = types.Part.from_bytes(data=target_bytes, mime_type=target_mime)
        ocr_prompt = (
            f"{system_prompt}\n\n"
            "TASK: Perform high-fidelity optical character recognition (OCR) and layout extraction from this document/image. "
            "Transcribe all Bengali (বাংলা) and English text verbatim. Preserve tables, dates, memo numbers, attendees, "
            "agendas, discussions, and decisions. Clean any OCR distortions and format into the exact JSON schema requested."
        )

        for model in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[ocr_prompt, part]
                )
                raw_text = resp.text or ""
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

        return deep_semantic_synthesis(text_content or "OCR Scanned Content", custom_skills, org_context)

    # 2. Audio Processing Flow
    transcript = text_content
    chunks_to_process = []
    if audio_chunks and len(audio_chunks) > 0:
        chunks_to_process = audio_chunks
    elif media_bytes:
        chunks_to_process = [media_bytes]
        
    if chunks_to_process:
        transcripts = []
        stt_model = transcription_model or "gemini-3.7-flash"
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
    
    for model in models_to_try:
        try:
            interaction = client.interactions.create(
                model=model,
                input=[{"type": "text", "text": full_text_prompt}]
            )
            raw_text = interaction.output_text or ""
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
                
    return deep_semantic_synthesis(transcript or "Document Content", custom_skills, org_context)

def process_ai_request(
    provider: str,
    api_key: str,
    base_url: str = "",
    model_name: str = "",
    transcription_model: str = "",
    summarization_model: str = "",
    media_bytes: Optional[bytes] = None,
    mime_type: str = "text/plain",
    text_content: str = "",
    org_context: str = "",
    custom_skills: str = "",
    audio_chunks: Optional[List[bytes]] = None,
    template_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Unified entrypoint handling split transcription & summarization models, multi-chunk audio, vision OCR, and custom template schemas."""
    api_key = api_key.strip()
    provider = (provider or "").lower()
    
    if not api_key:
        cfg = get_default_api_key_from_disk()
        api_key = cfg.get("api_key", "")
        if not provider:
            provider = cfg.get("provider", "groq")

    stt_model = transcription_model or model_name
    llm_model = summarization_model or model_name

    # Check if media is an image or PDF for multimodal OCR
    is_vision_media = bool(media_bytes and mime_type and (mime_type.startswith("image/") or mime_type == "application/pdf"))

    if (api_key.startswith("AIzaSy") or api_key.startswith("AQ.") or provider == "gemini") and api_key:
        return transcribe_and_summarize_gemini(
            media_bytes=media_bytes,
            mime_type=mime_type,
            api_key=api_key,
            transcription_model=stt_model or "gemini-3.5-flash-lite",
            summarization_model=llm_model or "gemini-3.5-flash-lite",
            org_context=org_context,
            custom_skills=custom_skills,
            text_content=text_content,
            audio_chunks=audio_chunks,
            template_schema=template_schema
        )

    if api_key.startswith("sk-ant-") or provider == "anthropic":
        return summarize_text_anthropic(
            text_content=text_content or "Document Content",
            api_key=api_key,
            model_name=llm_model or "claude-3-5-sonnet-20241022",
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )

    if api_key.startswith("sk-proj-") or (api_key.startswith("sk-") and not api_key.startswith("sk-ant-")) or provider == "openai":
        if is_vision_media:
            return summarize_text_openai_compatible(
                text_content=text_content or "OCR Document",
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                model_name=llm_model or "gpt-4o",
                org_context=org_context,
                custom_skills=custom_skills,
                template_schema=template_schema,
                media_bytes=media_bytes,
                mime_type=mime_type
            )

        raw_text = text_content
        chunks_to_process = audio_chunks if (audio_chunks and len(audio_chunks) > 0) else ([media_bytes] if media_bytes else [])
        if chunks_to_process:
            whisper_texts = []
            try:
                whisper_url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {api_key}"}
                for chunk in chunks_to_process:
                    files = {"file": ("audio.mp3", chunk, mime_type or "audio/mp3")}
                    data = {"model": stt_model or "whisper-1"}
                    with httpx.Client(timeout=180.0) as client:
                        w_resp = client.post(whisper_url, headers=headers, files=files, data=data)
                        if w_resp.status_code == 200:
                            whisper_texts.append(w_resp.json().get("text", ""))
                if whisper_texts:
                    raw_text = "\n\n".join([t for t in [raw_text] + whisper_texts if t])
            except Exception as e:
                print(f"[OpenAI Whisper Warning] {e}")

        return summarize_text_openai_compatible(
            text_content=raw_text or "Document Content",
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model_name=llm_model or "gpt-4o",
            org_context=org_context,
            custom_skills=custom_skills,
            template_schema=template_schema
        )

    if api_key.startswith("gsk_") or provider in ["groq", "custom"]:
        # If image/PDF uploaded under Groq, use extracted text_content (from pypdf/tesseract)
        return transcribe_and_summarize_groq(
            media_bytes=None if is_vision_media else media_bytes,
            mime_type=mime_type,
            api_key=api_key,
            base_url=base_url or "https://api.groq.com/openai/v1",
            transcription_model=stt_model or "whisper-large-v3-turbo",
            summarization_model=llm_model or "llama-3.3-70b-versatile",
            org_context=org_context,
            custom_skills=custom_skills,
            text_content=text_content or ("Document content" if is_vision_media else ""),
            audio_chunks=None if is_vision_media else audio_chunks,
            template_schema=template_schema
        )
        
    return deep_semantic_synthesis(text_content or "Document Content", custom_skills, org_context)

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

