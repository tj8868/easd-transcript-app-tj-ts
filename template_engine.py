import os
import io
import re
import json
import copy
import uuid
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

import docx
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates_store")
CUSTOM_DOCX_DIR = os.path.join(TEMPLATES_DIR, "custom_docx")
TEMPLATES_JSON_PATH = os.path.join(TEMPLATES_DIR, "templates.json")

os.makedirs(CUSTOM_DOCX_DIR, exist_ok=True)

# Standard Document Types Registry
DOCUMENT_TYPES = [
    {"id": "meeting_minutes", "name": "Meeting minutes", "has_attendance": True, "description": "Formal institutional meeting minutes with discussions table and attendance checklist."},
    {"id": "journal", "name": "Journal", "has_attendance": False, "description": "Academic & scientific journal article with abstract, methodology, findings, and references."},
    {"id": "news", "name": "News", "has_attendance": False, "description": "Press release and news story with headline, dateline, lead, quotes, and boilerplate."},
    {"id": "blog", "name": "Blog", "has_attendance": False, "description": "Engaging digital blog post with title, hook, key insights, actionable tips, and CTA."},
    {"id": "bangladesh_govt_report", "name": "Report-Bangladesh government structure", "has_attendance": False, "description": "Official Government of Bangladesh Nothi/Memo format with Ministry, Memo No, Subject, Background, Observations, Decisions, Recommendations, and Signatures."}
]

# Default pre-configured templates for all document types
DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "easd_default_minutes",
        "name": "EASD Meeting Minutes (Official Template)",
        "doc_type": "meeting_minutes",
        "category": "Meeting Minutes",
        "description": "Standard 4-topic discussion table (Followup, Action items, Task Assignments, Decisions) with 21-member attendance sheet.",
        "is_default": True,
        "is_builtin": True,
        "docx_filename": "EASD Meeting minutes - Template-DDMonthYY.docx",
        "context": "Official strategic, programmatic, and presentation review meetings conducted by Eminence Associates for Social Development (EASD). Designed for executive leadership, program managers, and stakeholders.",
        "rules": "1. Write in formal institutional tone.\n2. Must extract exactly 4 thematic discussion areas (Followup, Action items, Task assignments, Decisions).\n3. Keep bullet points concise and prefixed with a single bullet (• ).\n4. Maintain bilingual accuracy (Bangla + English).",
        "requirements": "- Document Title, Date, Venue, Time.\n- 4-5 high-level Agenda items.\n- 4-row Discussion & Action matrix.\n- Member participation verification in Attendance sheet.\n- Clearly stated major decisions.",
        "fields": [
            {"key": "title", "label": "Meeting Title", "type": "text", "default": "Weekly Strategic, Programmatic and Presentation Review Meeting"},
            {"key": "location", "label": "Venue / Location", "type": "text", "default": "Eminence, Mohakhali, DOHS"},
            {"key": "date", "label": "Meeting Date", "type": "text", "default": "29 August, 2026"},
            {"key": "time", "label": "Meeting Time", "type": "text", "default": "11:00 AM - 01:00 PM"}
        ],
        "sections": [
            {"id": "agendas", "title": "Meeting Agenda (4-5 points)", "type": "list", "prompt": "4 to 5 strategic agenda points reflecting the meeting focus."},
            {"id": "decisions", "title": "Major Strategic Decisions", "type": "bullets", "prompt": "Formally approved decisions, locked deadlines, and institutional directives."}
        ],
        "tables": [
            {
                "id": "discussions",
                "title": "Discussions & Action Framework",
                "fixed_rows": [
                    {"sn": "1", "topic": "Followup from previous meeting"},
                    {"sn": "2", "topic": "Action items"},
                    {"sn": "3", "topic": "Task Assignments"},
                    {"sn": "4", "topic": "Meeting Decisions"}
                ],
                "columns": ["S.N", "Topic", "Discussion Details"]
            },
            {
                "id": "attendance",
                "title": "Attendance Checklist",
                "columns": ["Serial", "Name", "Participation"]
            }
        ],
        "ai_system_prompt": "You are an expert bilingual Chief Executive Rapporteur for EASD. Analyze the input transcript/audio and map into the standard 4-topic meeting minutes format."
    },
    {
        "id": "bangladesh_govt_nothi",
        "name": "Bangladesh Government Official Nothi / Memo Report",
        "doc_type": "bangladesh_govt_report",
        "category": "Government Reports",
        "description": "Standard Government of the People's Republic of Bangladesh Nothi & Memo structure (গণপ্রজাতন্ত্রী বাংলাদেশ সরকার নোথি / স্মারক কাঠামো).",
        "is_default": False,
        "is_builtin": True,
        "docx_filename": "",
        "context": "Official administrative memo, inspection report, or policy brief for ministries, departments, directorates, and government commissions in Bangladesh. Adheres to Bangladesh Secretariat Instructions.",
        "rules": "1. Format according to official Bangladesh Secretariat Nothi conventions.\n2. Header must prominently state: 'গণপ্রজাতন্ত্রী বাংলাদেশ সরকার' / 'Government of the People\'s Republic of Bangladesh'.\n3. Use formal administrative Bengali/English terminology (e.g. বিষয়, স্মারক নং, পটভূমি, পর্যবেক্ষণ, সিদ্ধান্ত ও সুপারিশমালা).\n4. All recommendations must be numbered, unambiguous, and assigned to designated administrative wings.",
        "requirements": "- Ministry / Division / Department Name.\n- Official Memo / Nothi Reference Number (স্মারক নং).\n- Date in official format (Bangla & Gregorian).\n- Subject / বিষয় (clear, one-line thematic summary).\n- Background & Context (পটভূমি ও ভূমিকা).\n- Detailed Observations & Findings (পর্যবেক্ষণ ও তথ্য-উপাত্ত).\n- Decisions Taken (গৃহীত সিদ্ধান্তসমূহ).\n- Strategic Recommendations (সুপারিশমালা).\n- Designated Signatory / Authority Block (স্বাক্ষরকারী কর্মকর্তা).",
        "fields": [
            {"key": "ministry", "label": "Ministry / Division (মন্ত্রণালয় / বিভাগ)", "type": "text", "default": "Ministry of Health and Family Welfare / স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়"},
            {"key": "department", "label": "Department / Directorate (অধিদপ্তর / সংস্থা)", "type": "text", "default": "Directorate General of Health Services (DGHS)"},
            {"key": "memo_no", "label": "Memo / Nothi No (স্মারক নম্বর)", "type": "text", "default": "৪৫.০০.০০০০.০০১.২৪.০০১.২৬-"},
            {"key": "date", "label": "Date (তারিখ)", "type": "text", "default": "০২ সেপ্টেম্বর, ২০২৬ / 02 September 2026"},
            {"key": "subject", "label": "Subject (বিষয়)", "type": "text", "default": "জাতীয় স্বাস্থ্য নীতি ও প্রোগ্রাম বাস্তবায়ন পর্যালোচনা প্রতিবেদন প্রসঙ্গে।"}
        ],
        "sections": [
            {"id": "background", "title": "১. পটভূমি ও ভূমিকা (Background & Introduction)", "type": "text", "prompt": "Comprehensive background, legal mandate, and context of the administrative inquiry or meeting."},
            {"id": "observations", "title": "২. বিশদ পর্যবেক্ষণ ও তথ্য-উপাত্ত (Detailed Observations & Findings)", "type": "bullets", "prompt": "Key factual findings, field data, inspections, and administrative evaluations."},
            {"id": "decisions", "title": "৩. সভায় গৃহীত সিদ্ধান্তসমূহ (Decisions Taken)", "type": "bullets", "prompt": "Formally resolved directives and executive approvals."},
            {"id": "recommendations", "title": "৪. কৌশলগত সুপারিশমালা (Policy & Operational Recommendations)", "type": "bullets", "prompt": "Actionable, numbered recommendations with timelines for ministerial execution."},
            {"id": "signatory", "title": "৫. স্বাক্ষরকারী ও অনুলিপি (Signatory & Distribution Block)", "type": "text", "prompt": "Signatory officer's designation and distribution list (অনুলিপি সদয় জ্ঞাতার্থে ও কার্যার্থে প্রেরিত হলো)."}
        ],
        "tables": [
            {
                "id": "action_matrix",
                "title": "বাস্তবায়ন কর্মপরিকল্পনা (Implementation Action Matrix)",
                "columns": ["ক্রমিক", "কার্যক্রম / সিদ্ধান্ত", "বাস্তবায়নকারী কর্তৃপক্ষ", "সময়সীমা"]
            }
        ],
        "ai_system_prompt": "You are a Senior Secretary / Administrative Rapporteur in the Bangladesh Government Civil Service. Synthesize the input information into an authoritative, structured Bangladesh Government Nothi / Official Report."
    },
    {
        "id": "journal_academic",
        "name": "Academic & Scientific Journal Article",
        "doc_type": "journal",
        "category": "Academic & Publications",
        "description": "Peer-reviewed journal paper format with Abstract, Introduction, Methodology, Results, Discussion, Conclusion, and Citations.",
        "is_default": False,
        "is_builtin": True,
        "docx_filename": "",
        "context": "Scholarly publications, scientific research papers, clinical evaluations, and academic conference proceedings. Target audience includes researchers, academic peers, and scientific reviewers.",
        "rules": "1. Write in objective, rigorous academic prose.\n2. Ensure the Abstract contains a concise Background, Methods, Results, and Conclusion summary.\n3. Findings must be backed by qualitative/quantitative evidence presented in the text.\n4. Include structured references in standard APA/IEEE citation style.",
        "requirements": "- Paper Title, Authors, and Institutional Affiliation.\n- 150-250 word structured Abstract & Keywords.\n- Introduction and Research Objectives.\n- Methodology / Analytical Framework.\n- Results, Statistical / Thematic Insights.\n- Scholarly Discussion, Limitations & Future Scope.\n- References list.",
        "fields": [
            {"key": "title", "label": "Article Title", "type": "text", "default": "Epidemiological Trends and Public Health Interventions in Urban Communities"},
            {"key": "authors", "label": "Authors & Affiliations", "type": "text", "default": "EASD Research & Evaluation Wing"},
            {"key": "keywords", "label": "Keywords (comma separated)", "type": "text", "default": "Public Health, NCD Prevention, Health Systems, Community Interventions"},
            {"key": "date", "label": "Publication Date", "type": "text", "default": "September 2026"}
        ],
        "sections": [
            {"id": "abstract", "title": "Abstract", "type": "text", "prompt": "Structured synthesis: Context, Objectives, Methodology, Principal Results, and Scientific Conclusion."},
            {"id": "introduction", "title": "1. Introduction & Theoretical Framework", "type": "text", "prompt": "Problem statement, literature overview, and core research questions."},
            {"id": "methodology", "title": "2. Methodology & Study Design", "type": "text", "prompt": "Sampling, data collection protocols, ethical approvals, and analytical methods."},
            {"id": "results", "title": "3. Results & Empirical Findings", "type": "bullets", "prompt": "Key empirical findings, statistical observations, and quantitative/qualitative data points."},
            {"id": "discussion", "title": "4. Discussion & Implications", "type": "text", "prompt": "Interpretation of results in relation to existing literature and policy implications."},
            {"id": "conclusion", "title": "5. Conclusion & Recommendations", "type": "text", "prompt": "Final takeaways, research limitations, and future research directives."},
            {"id": "references", "title": "6. References / Citations", "type": "bullets", "prompt": "Scholarly references and bibliography."}
        ],
        "tables": [
            {
                "id": "data_table",
                "title": "Summary of Key Variables and Findings",
                "columns": ["Variable / Indicator", "Baseline Value", "Observed Outcome", "Significance"]
            }
        ],
        "ai_system_prompt": "You are a distinguished Principal Academic Investigator and Scientific Editor. Synthesize the provided research transcript/data into an authoritative, peer-reviewed academic journal article."
    },
    {
        "id": "news_press_release",
        "name": "Press Release & News Story",
        "doc_type": "news",
        "category": "Media & News",
        "description": "High-impact journalism and corporate press release format with Catchy Headline, Dateline, Inverted Pyramid Lead, Quotes, and Media Boilerplate.",
        "is_default": False,
        "is_builtin": True,
        "docx_filename": "",
        "context": "Public press releases, newsroom wire stories, media alerts, and journalistic coverage of events, product launches, or emergency briefings.",
        "rules": "1. Follow the inverted pyramid structure (crucial 5 Ws in the first paragraph: Who, What, When, Where, Why).\n2. Use punchy, objective journalistic tone in third person.\n3. Include authentic quotes with speaker attribution.\n4. Conclude with institutional boilerplate and media contact info.",
        "requirements": "- Headline & Sub-headline.\n- Dateline (City, Country).\n- Strong Lead Paragraph (the hook and core news event).\n- Body paragraphs with supporting context and statistics.\n- Key Direct Quotes from leadership/spokespersons.\n- About / Boilerplate and Media Contact section.",
        "fields": [
            {"key": "title", "label": "Headline", "type": "text", "default": "EASD Unveils Landmark Community Health Initiative to Combat Non-Communicable Diseases"},
            {"key": "dateline", "label": "Dateline (City, Country)", "type": "text", "default": "DHAKA, Bangladesh"},
            {"key": "date", "label": "Release Date", "type": "text", "default": "September 2, 2026"},
            {"key": "media_contact", "label": "Media Contact Person", "type": "text", "default": "Communications Directorate, Eminence"}
        ],
        "sections": [
            {"id": "lead_paragraph", "title": "Lead Paragraph (The Core News)", "type": "text", "prompt": "Immediate summary capturing Who, What, Where, When, and Why in 2-3 engaging sentences."},
            {"id": "body_story", "title": "Story Details & Background", "type": "text", "prompt": "In-depth narrative explaining the background, impact, and significance of the announcement."},
            {"id": "key_quotes", "title": "Executive Quotes & Statements", "type": "bullets", "prompt": "Direct quotes from leadership, subject matter experts, or key stakeholders with proper attribution."},
            {"id": "highlights", "title": "Key News Highlights & Milestones", "type": "bullets", "prompt": "Bullet points outlining pivotal facts, figures, and immediate milestones."},
            {"id": "boilerplate", "title": "About Organization & Media Inquiries", "type": "text", "prompt": "Standard institutional boilerplate description and media inquiry instructions."}
        ],
        "tables": [],
        "ai_system_prompt": "You are a Senior Bureau Chief and Veteran News Editor. Transform the input notes/audio into a crisp, engaging, and professional news story / press release adhering to AP Style guidelines."
    },
    {
        "id": "blog_article",
        "name": "High-Impact Digital Blog Article",
        "doc_type": "blog",
        "category": "Digital Content",
        "description": "Engaging, SEO-optimized digital blog post with Magnetic Title, Story Hook, Subheaders, Core Takeaways, and Call-to-Action (CTA).",
        "is_default": False,
        "is_builtin": True,
        "docx_filename": "",
        "context": "Digital content marketing, thought leadership blogs, industry insights, and educational articles for web audiences, LinkedIn, and corporate blogs.",
        "rules": "1. Write in an engaging, conversational, yet authoritative tone.\n2. Use short, readable paragraphs and punchy subheadings (H2, H3).\n3. Provide actionable, practical takeaways for readers.\n4. End with a compelling Call-to-Action (CTA) encouraging community engagement.",
        "requirements": "- Catchy, Click-Worthy Title.\n- Engaging Hook / Introduction.\n- 3-4 clearly defined Sub-topics.\n- Actionable Tips / Core Takeaways.\n- Engaging Conclusion & Call-to-Action (CTA).",
        "fields": [
            {"key": "title", "label": "Blog Post Title", "type": "text", "default": "Transforming Public Health from the Grassroots: 5 Key Lessons from the Field"},
            {"key": "author", "label": "Author / Contributor", "type": "text", "default": "EASD Thought Leadership Team"},
            {"key": "target_audience", "label": "Target Audience", "type": "text", "default": "Development Practitioners, Policymakers, and Global Health Advocates"},
            {"key": "date", "label": "Published Date", "type": "text", "default": "September 2026"}
        ],
        "sections": [
            {"id": "hook_intro", "title": "The Hook & Introduction", "type": "text", "prompt": "Relatable opening story, surprising statistic, or burning question that grabs reader attention."},
            {"id": "core_insights", "title": "Core Insights & In-Depth Analysis", "type": "text", "prompt": "Detailed exploration of the main topic broken down into logical thematic points."},
            {"id": "practical_tips", "title": "Practical Takeaways & Actionable Tips", "type": "bullets", "prompt": "List of concrete, actionable recommendations readers can immediately implement."},
            {"id": "conclusion_cta", "title": "Conclusion & Call to Action (CTA)", "type": "text", "prompt": "Inspiring wrap-up and a clear CTA (e.g., share thoughts, subscribe, join the initiative)."}
        ],
        "tables": [],
        "ai_system_prompt": "You are a World-Class Digital Content Strategist and Thought Leader. Transform the input transcript/notes into a viral, insightful, and beautifully formatted blog post."
    }
]

def get_document_types() -> List[Dict[str, Any]]:
    """Returns the list of supported document type categories."""
    return list(DOCUMENT_TYPES)

def load_saved_templates() -> List[Dict[str, Any]]:
    """Loads all templates from disk, combining built-ins with user-created custom templates."""
    if os.path.exists(TEMPLATES_JSON_PATH):
        try:
            with open(TEMPLATES_JSON_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
                if isinstance(stored, list):
                    existing_ids = {t.get("id") for t in stored}
                    combined = list(stored)
                    for d in DEFAULT_TEMPLATES:
                        if d["id"] not in existing_ids:
                            combined.insert(0, d)
                        else:
                            for idx, item in enumerate(combined):
                                if item.get("id") == d["id"]:
                                    for k in ["context", "rules", "requirements", "doc_type", "name", "description", "category", "sections", "fields", "tables", "ai_system_prompt"]:
                                        if k not in item and k in d:
                                            item[k] = d[k]
                    # Ensure all templates have 3 core directives
                    for item in combined:
                        if not item.get("context"):
                            item["context"] = f"General template for {item.get('name', 'Custom Document')}."
                        if not item.get("rules"):
                            item["rules"] = "1. Write in formal institutional tone.\n2. Keep bullet points clear with single bullets ('• ')."
                        if not item.get("requirements"):
                            item["requirements"] = "- Complete all mandatory sections.\n- Ensure accurate metadata fields."
                        if not item.get("doc_type"):
                            item["doc_type"] = "custom"
                    return combined
        except Exception as e:
            print(f"[Template Load Warning] {e}")
            
    return list(DEFAULT_TEMPLATES)

def save_templates_to_disk(templates: List[Dict[str, Any]]):
    """Saves template metadata list to templates.json."""
    try:
        with open(TEMPLATES_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Template Save Error] {e}")

def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    """Finds template by its unique ID."""
    all_t = load_saved_templates()
    for t in all_t:
        if t.get("id") == template_id:
            return t
    return all_t[0] if all_t else DEFAULT_TEMPLATES[0]

def analyze_and_generalize_docx(docx_bytes: bytes, filename: str, doc_type: str = "custom") -> Dict[str, Any]:
    """
    Intelligently inspects any uploaded DOCX document file and extracts:
    - Headings / Section titles
    - Metadata placeholders (e.g. Title, Date, Venue, Lead, Memo No)
    - Tables (headers, columns, row structure)
    - Automatically generates 3 core directives: Context, Rules, and Requirements!
    """
    clean_name = os.path.splitext(os.path.basename(filename))[0].replace("_", " ").replace("-", " ").title()
    template_id = f"custom_tpl_{uuid.uuid4().hex[:8]}"
    saved_docx_name = f"{template_id}.docx"
    saved_docx_path = os.path.join(CUSTOM_DOCX_DIR, saved_docx_name)
    
    with open(saved_docx_path, "wb") as f:
        f.write(docx_bytes)

    doc = docx.Document(io.BytesIO(docx_bytes))
    
    detected_title = clean_name
    detected_fields = []
    detected_sections = []
    detected_tables = []
    
    all_paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if all_paragraphs:
        for p in doc.paragraphs[:5]:
            txt = p.text.strip()
            if txt and len(txt) > 5 and len(txt) < 120:
                detected_title = txt
                break
                
    detected_fields.append({
        "key": "title",
        "label": "Document Title",
        "type": "text",
        "default": detected_title
    })
    
    meta_patterns = [
        ("date", "Date / Period", r'(?i)\bdate\b'),
        ("location", "Location / Venue", r'(?i)\b(?:location|venue|place|district)\b'),
        ("author", "Prepared By / Author", r'(?i)\b(?:prepared by|author|lead|officer|chair)\b'),
        ("reference", "Reference / Doc No", r'(?i)\b(?:ref|reference|memo|doc no|স্মারক)\b'),
        ("ministry", "Ministry / Division", r'(?i)\b(?:ministry|division|department|মন্ত্রণালয়)\b')
    ]
    
    for key, label, pattern in meta_patterns:
        found = False
        for p in doc.paragraphs[:12]:
            if re.search(pattern, p.text):
                found = True
                break
        if found or key in ["date"]:
            detected_fields.append({
                "key": key,
                "label": label,
                "type": "text",
                "default": ""
            })

    section_counter = 1
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        is_heading = False
        if p.style and p.style.name.startswith("Heading"):
            is_heading = True
        elif len(txt) < 80 and (txt.isupper() or re.match(r'^\d+[\.\)]\s+[A-Z\u0980-\u09FF]', txt) or (len(p.runs) > 0 and p.runs[0].bold)):
            is_heading = True
            
        if is_heading and len(txt) > 3:
            clean_head = re.sub(r'^\d+[\.\)]\s*', '', txt).strip()
            sec_id = re.sub(r'[^a-zA-Z0-9_]', '_', clean_head.lower())[:24] or f"section_{section_counter}"
            
            if not any(s["id"] == sec_id for s in detected_sections):
                detected_sections.append({
                    "id": sec_id,
                    "title": txt,
                    "type": "bullets" if any(w in txt.lower() for w in ["action", "finding", "decision", "recommendation", "সিদ্ধান্ত", "সুপারিশ"]) else "text",
                    "prompt": f"Synthesize information regarding '{clean_head}' in formal prose."
                })
                section_counter += 1

    if not detected_sections:
        detected_sections = [
            {"id": "overview", "title": "1. Overview & Context", "type": "text", "prompt": "General overview and key points discussed."},
            {"id": "key_discussions", "title": "2. Key Discussions & Findings", "type": "bullets", "prompt": "Main points, observations, and discussion themes."},
            {"id": "action_points", "title": "3. Action Items & Next Steps", "type": "bullets", "prompt": "Action directives, task allocations, and decisions."}
        ]

    for t_idx, table in enumerate(doc.tables):
        if len(table.rows) > 0:
            header_cells = [c.text.strip().replace("\n", " ") for c in table.rows[0].cells if c.text.strip()]
            if header_cells:
                t_title = f"Table {t_idx + 1}"
                detected_tables.append({
                    "id": f"table_{t_idx}",
                    "title": t_title,
                    "columns": header_cells
                })

    sections_summary = ", ".join([s["title"] for s in detected_sections])
    tables_summary = ", ".join([t["title"] for t in detected_tables]) if detected_tables else "None"
    
    auto_context = (
        f"Custom institutional document generated from the template '{clean_name}'. "
        f"Designed to organize spoken notes, meeting transcripts, and project data into a structured report for executive and operational stakeholders."
    )
    
    auto_rules = (
        f"1. Produce clear, professional prose matching the template sections.\n"
        f"2. Maintain bilingual accuracy (Bangla and English where applicable).\n"
        f"3. Format bullet lists with single bullets ('• ').\n"
        f"4. Do not invent facts; synthesize strictly from the provided input audio/text."
    )
    
    auto_requirements = (
        f"- Populate all extracted sections: {sections_summary}.\n"
        f"- Ensure metadata fields ({', '.join([f['label'] for f in detected_fields])}) are accurately filled.\n"
        f"- Maintain table structures ({tables_summary}) if relevant data is present."
    )

    ai_prompt = (
        f"You are an expert Executive Rapporteur and AI Documentation Lead. "
        f"Analyze the input transcript/audio and populate the '{detected_title}' template according to its context, rules, and requirements."
    )

    generalized_template = {
        "id": template_id,
        "name": detected_title,
        "doc_type": doc_type,
        "description": f"Custom uploaded template extracted from '{filename}' with {len(detected_sections)} sections and {len(detected_tables)} tables.",
        "category": "Custom Templates",
        "is_default": False,
        "is_builtin": False,
        "docx_filename": saved_docx_name,
        "context": auto_context,
        "rules": auto_rules,
        "requirements": auto_requirements,
        "fields": detected_fields,
        "sections": detected_sections,
        "tables": detected_tables,
        "ai_system_prompt": ai_prompt
    }

    all_t = load_saved_templates()
    all_t.append(generalized_template)
    save_templates_to_disk(all_t)

    return generalized_template

def save_custom_template(template_data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves or updates a template schema in the templates store."""
    all_t = load_saved_templates()
    t_id = template_data.get("id") or f"custom_tpl_{uuid.uuid4().hex[:8]}"
    template_data["id"] = t_id
    
    updated = False
    for idx, t in enumerate(all_t):
        if t.get("id") == t_id:
            all_t[idx] = template_data
            updated = True
            break
    if not updated:
        all_t.append(template_data)
        
    save_templates_to_disk(all_t)
    return template_data

def delete_custom_template(template_id: str) -> bool:
    """Deletes a custom template (built-in defaults cannot be deleted)."""
    all_t = load_saved_templates()
    target = None
    for t in all_t:
        if t.get("id") == template_id:
            if t.get("is_builtin"):
                return False
            target = t
            break
            
    if target:
        all_t = [t for t in all_t if t.get("id") != template_id]
        save_templates_to_disk(all_t)
        docx_fn = target.get("docx_filename")
        if docx_fn:
            docx_path = os.path.join(CUSTOM_DOCX_DIR, docx_fn)
            if os.path.exists(docx_path):
                try:
                    os.remove(docx_path)
                except Exception:
                    pass
        return True
    return False

def generate_custom_template_docx_bytes(template_info: Dict[str, Any], data: Dict[str, Any]) -> bytes:
    """
    Generates a high-fidelity .docx document for ANY document type or custom uploaded template.
    If the template has an original source DOCX file, it preserves original Word styling,
    logos, tables, and replaces placeholders / inserts sections directly into it.
    """
    doc_type = template_info.get("doc_type") or "custom"
    docx_fn = template_info.get("docx_filename")
    custom_docx_path = os.path.join(CUSTOM_DOCX_DIR, docx_fn) if docx_fn else None
    
    # 1. Fill uploaded source DOCX template if available
    if custom_docx_path and os.path.exists(custom_docx_path):
        try:
            with open(custom_docx_path, "rb") as f:
                doc = docx.Document(io.BytesIO(f.read()))
                
            for p in doc.paragraphs:
                for key, val in data.items():
                    if isinstance(val, str):
                        tokens = [f"{{{{{key}}}}}", f"{{{{{key.upper()}}}}}", f"[{key}]", f"[{key.title()}]", f"[{key.upper()}]"]
                        for token in tokens:
                            if token in p.text:
                                p.text = p.text.replace(token, val)
                                
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for key, val in data.items():
                            if isinstance(val, str):
                                tokens = [f"{{{{{key}}}}}", f"{{{{{key.upper()}}}}}", f"[{key}]"]
                                for token in tokens:
                                    if token in cell.text:
                                        cell.text = cell.text.replace(token, val)

            sections = template_info.get("sections", [])
            for sec in sections:
                sec_id = sec.get("id", "")
                sec_title = sec.get("title", "")
                sec_content = data.get(sec_id) or data.get("sections_data", {}).get(sec_id, "")
                
                if sec_content:
                    heading_found = False
                    for p in doc.paragraphs:
                        if sec_title.lower() in p.text.lower():
                            heading_found = True
                            p_body = doc.add_paragraph()
                            r_b = p_body.add_run(str(sec_content))
                            r_b.font.name = "Times New Roman"
                            r_b.font.size = Pt(10.5)
                            break
                    if not heading_found:
                        h = doc.add_paragraph()
                        r = h.add_run(sec_title)
                        r.bold = True
                        r.font.name = "Times New Roman"
                        r.font.size = Pt(12)
                        r.font.color.rgb = RGBColor(0, 51, 102)
                        
                        p_body = doc.add_paragraph()
                        r_b = p_body.add_run(str(sec_content))
                        r_b.font.name = "Times New Roman"
                        r_b.font.size = Pt(10.5)

            out_stream = io.BytesIO()
            doc.save(out_stream)
            return out_stream.getvalue()
        except Exception as e:
            print(f"[Custom DOCX Fill Warning] {e}, falling back to dynamic document builder...")

    # 2. Dynamic High-End Document Builder
    doc = docx.Document()
    
    # Custom Header for Bangladesh Government structure
    if doc_type == "bangladesh_govt_report":
        p_govt = doc.add_paragraph()
        p_govt.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_g1 = p_govt.add_run("গণপ্রজাতন্ত্রী বাংলাদেশ সরকার\n")
        r_g1.bold = True
        r_g1.font.name = "Hind Siliguri"
        r_g1.font.size = Pt(14)
        
        min_text = data.get("ministry") or "স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়"
        dept_text = data.get("department") or "স্বাস্থ্য সেবা বিভাগ"
        r_g2 = p_govt.add_run(f"{min_text}\n{dept_text}\n")
        r_g2.font.name = "Hind Siliguri"
        r_g2.font.size = Pt(11)
        
        p_memo = doc.add_paragraph()
        memo_val = data.get("memo_no") or "৪৫.০০.০০০০.০০১.২৪.০০১.২৬-"
        date_val = data.get("date") or "০২ সেপ্টেম্বর, ২০২৬"
        r_m1 = p_memo.add_run(f"স্মারক নম্বর: {memo_val}")
        r_m1.bold = True
        r_m1.font.name = "Hind Siliguri"
        r_m1.font.size = Pt(10.5)
        
        r_space = p_memo.add_run("\t\t\t\t")
        r_m2 = p_memo.add_run(f"তারিখ: {date_val}")
        r_m2.bold = True
        r_m2.font.name = "Hind Siliguri"
        r_m2.font.size = Pt(10.5)
        
        subj_val = data.get("subject") or data.get("title") or "নথি প্রতিবেদন"
        p_subj = doc.add_paragraph()
        r_s1 = p_subj.add_run("বিষয়: ")
        r_s1.bold = True
        r_s1.font.name = "Hind Siliguri"
        r_s1.font.size = Pt(11)
        r_s2 = p_subj.add_run(subj_val)
        r_s2.bold = True
        r_s2.underline = True
        r_s2.font.name = "Hind Siliguri"
        r_s2.font.size = Pt(11)
        
        doc.add_paragraph()
    else:
        doc_title = data.get("title") or template_info.get("name") or "Document Report"
        h1 = doc.add_paragraph()
        h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = h1.add_run(doc_title)
        r1.bold = True
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(16)
        r1.font.color.rgb = RGBColor(0, 51, 102)
        
        fields = template_info.get("fields", [])
        if fields:
            meta_table = doc.add_table(rows=0, cols=2)
            meta_table.autofit = True
            for fld in fields:
                f_key = fld.get("key", "")
                if f_key == "title":
                    continue
                f_lbl = fld.get("label", f_key.title())
                f_val = str(data.get(f_key) or fld.get("default") or "")
                if f_val:
                    row = meta_table.add_row()
                    c0, c1 = row.cells[0], row.cells[1]
                    r_lbl = c0.paragraphs[0].add_run(f"{f_lbl}:")
                    r_lbl.bold = True
                    r_lbl.font.name = "Times New Roman"
                    r_lbl.font.size = Pt(10)
                    r_val = c1.paragraphs[0].add_run(f_val)
                    r_val.font.name = "Times New Roman"
                    r_val.font.size = Pt(10)
            doc.add_paragraph()

    sections = template_info.get("sections", [])
    for sec in sections:
        sec_id = sec.get("id", "")
        sec_title = sec.get("title", "")
        sec_content = data.get(sec_id) or data.get("sections_data", {}).get(sec_id, "")
        
        h_sec = doc.add_paragraph()
        r_sec = h_sec.add_run(sec_title)
        r_sec.bold = True
        r_sec.font.name = "Hind Siliguri" if doc_type == "bangladesh_govt_report" else "Times New Roman"
        r_sec.font.size = Pt(12)
        r_sec.font.color.rgb = RGBColor(0, 51, 102)
        
        if sec_content:
            lines = str(sec_content).splitlines()
            for line in lines:
                l_str = line.strip()
                if l_str:
                    p = doc.add_paragraph()
                    r = p.add_run(l_str)
                    r.font.name = "Hind Siliguri" if doc_type == "bangladesh_govt_report" else "Times New Roman"
                    r.font.size = Pt(10.5)
        else:
            p = doc.add_paragraph()
            r = p.add_run("• No specific details recorded for this section.")
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)

    tables_schema = template_info.get("tables", [])
    for t_info in tables_schema:
        t_id = t_info.get("id", "")
        t_title = t_info.get("title", "Table")
        cols = t_info.get("columns", [])
        
        doc.add_paragraph()
        h_t = doc.add_paragraph()
        r_t = h_t.add_run(t_title)
        r_t.bold = True
        r_t.font.name = "Hind Siliguri" if doc_type == "bangladesh_govt_report" else "Times New Roman"
        r_t.font.size = Pt(11.5)
        
        if cols:
            table_el = doc.add_table(rows=1, cols=len(cols))
            table_el.autofit = True
            hdr_cells = table_el.rows[0].cells
            for c_idx, col_name in enumerate(cols):
                hdr_p = hdr_cells[c_idx].paragraphs[0]
                hdr_run = hdr_p.add_run(col_name)
                hdr_run.bold = True
                hdr_run.font.name = "Times New Roman"
                hdr_run.font.size = Pt(10)
                
            rows_data = data.get(t_id) or data.get("tables_data", {}).get(t_id, [])
            if rows_data and isinstance(rows_data, list):
                for row_item in rows_data:
                    row_el = table_el.add_row()
                    for c_idx, col_name in enumerate(cols):
                        val = ""
                        if isinstance(row_item, dict):
                            val = str(row_item.get(col_name) or row_item.get(col_name.lower()) or list(row_item.values())[min(c_idx, len(row_item)-1)])
                        elif isinstance(row_item, (list, tuple)) and c_idx < len(row_item):
                            val = str(row_item[c_idx])
                        row_el.cells[c_idx].paragraphs[0].add_run(val)

    bangla_t = (data.get("bangla_transcript") or "").strip()
    english_t = (data.get("english_transcript") or "").strip()
    if bangla_t or english_t:
        doc.add_page_break()
        h_tr = doc.add_paragraph()
        r_tr = h_tr.add_run("Attached Transcription & Source Record")
        r_tr.bold = True
        r_tr.font.name = "Times New Roman"
        r_tr.font.size = Pt(13)
        r_tr.font.color.rgb = RGBColor(0, 51, 102)
        
        if bangla_t:
            doc.add_paragraph().add_run("Bangla Transcript (বাংলা বিবরণ):").bold = True
            p_b = doc.add_paragraph()
            r_b = p_b.add_run(bangla_t)
            r_b.font.name = "Hind Siliguri"
            r_b.font.size = Pt(10)
            
        if english_t:
            doc.add_paragraph().add_run("English Transcript:").bold = True
            p_e = doc.add_paragraph()
            r_e = p_e.add_run(english_t)
            r_e.font.name = "Times New Roman"
            r_e.font.size = Pt(10)

    out_stream = io.BytesIO()
    doc.save(out_stream)
    return out_stream.getvalue()
