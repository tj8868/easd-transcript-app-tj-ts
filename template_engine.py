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
    {"id": "bangladesh_govt_report", "name": "Report-Bangladesh government structure", "has_attendance": False, "description": "Official Government of Bangladesh Nothi/Memo format with Ministry, Memo No, Subject, Background, Observations, Decisions, Recommendations, and Signatures."},
    {"id": "summary", "name": "Summary", "has_attendance": False, "description": "Pure transcript summary: Executive overview, key discussion points, core takeaways, and action items."}
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
        "docx_filename": "EASD Meeting minutes - Template.docx",
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
    },
    {
        "id": "transcript_summary",
        "name": "Transcript Summary (Direct & Concise)",
        "doc_type": "summary",
        "category": "Summarization",
        "description": "Pure concise synthesis of the transcript: Executive Overview, Key Topics Discussed, Key Decisions, and Action Items without complex tables or bureaucracy.",
        "is_default": False,
        "is_builtin": True,
        "docx_filename": "",
        "context": "Direct concise executive summary synthesized purely from verbatim transcripts, recordings, and audio notes. Designed for fast executive reviews and quick sharing.",
        "rules": "1. Just summarize the transcript faithfully, accurately, and concisely.\n2. Do NOT add extraneous commentary, hallucinated attendees, or unnecessary bureaucratic overhead.\n3. Present key takeaways and actionable points cleanly as bullet points.\n4. Maintain bilingual fidelity (Bangla and/or English as spoken in the transcript).",
        "requirements": "- Document Title & Date.\n- Executive Overview / Synopsis.\n- Key Discussion Highlights.\n- Decisions & Resolutions.\n- Action Items & Next Steps.",
        "fields": [
            {"key": "title", "label": "Summary Title", "type": "text", "default": "Executive Summary of Proceedings"},
            {"key": "date", "label": "Date", "type": "text", "default": "September 2026"}
        ],
        "sections": [
            {"id": "overview", "title": "1. Executive Overview", "type": "text", "prompt": "Concise high-level synthesis of what was discussed, the overarching objectives, and general context."},
            {"id": "key_topics", "title": "2. Key Discussion Points", "type": "bullets", "prompt": "Major thematic topics, questions, arguments, and viewpoints raised by participants."},
            {"id": "decisions", "title": "3. Decisions & Conclusions", "type": "bullets", "prompt": "All consensus points, agreed positions, directives, and conclusions reached."},
            {"id": "action_items", "title": "4. Action Items & Next Steps", "type": "bullets", "prompt": "Concrete action items, responsibilities, follow-ups, and subsequent deadlines."}
        ],
        "tables": [],
        "ai_system_prompt": "You are an elite Executive Summarizer. Your sole job is to summarize the transcript accurately, concisely, and cleanly into the designated sections without adding unnecessary filler."
    }
]

def generate_template_json_schema(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a standard JSON Schema (Draft-07 compliant) tailored specifically
    to the fields, sections, and tables of any document template.
    Guarantees strict type constraints, required fields, and clear directives for LLMs.
    """
    t_id = template.get("id", "")
    doc_type = template.get("doc_type", "custom")
    name = template.get("name", "Document Template")
    
    summary_properties: Dict[str, Any] = {}
    summary_required: List[str] = []
    
    # 1. Metadata Fields
    fields = template.get("fields", [])
    for fld in fields:
        f_key = fld.get("key", "")
        if not f_key:
            continue
        f_lbl = fld.get("label", f_key.title())
        summary_properties[f_key] = {
            "type": "string",
            "title": f_lbl,
            "description": f"Metadata field: {f_lbl}"
        }
        if f_key in ["title", "ministry", "memo_no", "date", "subject", "author", "authors"]:
            summary_required.append(f_key)

    # 2. Sections
    sections = template.get("sections", [])
    for sec in sections:
        sec_id = sec.get("id", "")
        if not sec_id:
            continue
        sec_title = sec.get("title", sec_id.title())
        sec_type = sec.get("type", "text")
        sec_prompt = sec.get("prompt", "")
        
        if sec_type == "list":
            summary_properties[sec_id] = {
                "type": "array",
                "title": sec_title,
                "description": f"{sec_prompt or sec_title}. Important: List items must not contain numbering prefixes like '1.' or '2.'",
                "items": {"type": "string"}
            }
        elif sec_type == "bullets":
            summary_properties[sec_id] = {
                "type": "string",
                "title": sec_title,
                "description": f"{sec_prompt or sec_title}. Important: Each bullet point MUST begin with a single bullet symbol ('• '). Never use double bullets ('• •') or numbers with bullets."
            }
        else: # text
            summary_properties[sec_id] = {
                "type": "string",
                "title": sec_title,
                "description": f"{sec_prompt or sec_title}. Formal, comprehensive institutional prose."
            }
        if sec_id in ["agendas", "decisions", "background", "observations", "abstract", "lead_paragraph", "hook_intro", "introduction"]:
            summary_required.append(sec_id)

    # 3. Tables
    tables = template.get("tables", [])
    for tbl in tables:
        tbl_id = tbl.get("id", "")
        if not tbl_id:
            continue
        tbl_title = tbl.get("title", tbl_id.title())
        cols = tbl.get("columns", [])
        
        # Specific structures for known default tables
        if tbl_id == "discussions" or (doc_type == "meeting_minutes" and tbl_id == "discussions"):
            row_schema = {
                "type": "object",
                "required": ["sn", "topic", "details"],
                "properties": {
                    "sn": {"type": "string", "enum": ["1", "2", "3", "4"], "description": "Serial number"},
                    "topic": {
                        "type": "string",
                        "enum": [
                            "Followup from previous meeting",
                            "Action items",
                            "Task Assignments",
                            "Meeting Decisions"
                        ],
                        "description": "Specific standard discussion theme"
                    },
                    "details": {
                        "type": "string",
                        "description": "Exhaustive discussion details. Each bullet point MUST start with a single bullet symbol ('• ')."
                    }
                }
            }
            summary_properties[tbl_id] = {
                "type": "array",
                "title": tbl_title,
                "description": "Standard 4-topic meeting discussion matrix.",
                "items": row_schema,
                "minItems": 4,
                "maxItems": 4
            }
            summary_required.append(tbl_id)
        elif tbl_id == "attendance":
            summary_properties[tbl_id] = {
                "type": "array",
                "title": tbl_title,
                "description": "Attendance status checklist for institutional members.",
                "items": {
                    "type": "object",
                    "required": ["serial", "name", "participation"],
                    "properties": {
                        "serial": {"type": "string"},
                        "name": {"type": "string"},
                        "participation": {"type": "string", "enum": ["Yes", "No", "Present", "Absent"]}
                    }
                }
            }
        elif tbl_id == "action_matrix":
            summary_properties[tbl_id] = {
                "type": "array",
                "title": tbl_title,
                "description": "বাস্তবায়ন কর্মপরিকল্পনা (Implementation Action Matrix)",
                "items": {
                    "type": "object",
                    "required": ["sn", "action", "authority", "deadline"],
                    "properties": {
                        "sn": {"type": "string", "description": "ক্রমিক (Serial number)"},
                        "action": {"type": "string", "description": "গৃহীত সিদ্ধান্ত / কার্যক্রম"},
                        "authority": {"type": "string", "description": "বাস্তবায়নকারী কর্তৃপক্ষ / উইং"},
                        "deadline": {"type": "string", "description": "বাস্তবায়নের সময়সীমা"}
                    }
                }
            }
            summary_required.append(tbl_id)
        elif tbl_id == "data_table":
            summary_properties[tbl_id] = {
                "type": "array",
                "title": tbl_title,
                "description": "Summary table of key research indicators, observations, and findings.",
                "items": {
                    "type": "object",
                    "required": ["variable", "baseline", "outcome", "significance"],
                    "properties": {
                        "variable": {"type": "string", "description": "Indicator or variable name"},
                        "baseline": {"type": "string", "description": "Baseline / reference measurement"},
                        "outcome": {"type": "string", "description": "Observed empirical outcome"},
                        "significance": {"type": "string", "description": "Statistical significance or impact level"}
                    }
                }
            }
            summary_required.append(tbl_id)
        else:
            # Custom table: generate properties from column names
            row_props = {}
            for col in cols:
                clean_col_key = re.sub(r'[^a-zA-Z0-9_]', '_', col.lower().strip())
                row_props[clean_col_key or col] = {"type": "string", "title": col}
            summary_properties[tbl_id] = {
                "type": "array",
                "title": tbl_title,
                "description": f"Extracted table rows for '{tbl_title}'.",
                "items": {
                    "type": "object",
                    "properties": row_props
                }
            }

    # If meeting minutes or attendance template, include present_members
    if doc_type == "meeting_minutes" or template.get("has_attendance"):
        summary_properties["present_members"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Names of all members/participants who attended, spoke, or were assigned tasks."
        }

    # Universal sections_data and tables_data for UI and document compatibility
    summary_properties["sections_data"] = {
        "type": "object",
        "description": "Optional key-value map linking each section ID directly to its string content."
    }
    summary_properties["tables_data"] = {
        "type": "object",
        "description": "Optional key-value map linking each table ID directly to its list of row objects."
    }

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": f"{name} Output Schema",
        "description": f"Standardized JSON schema for '{name}' ({doc_type}). The LLM output MUST strictly conform to this schema.",
        "type": "object",
        "required": ["detected_language", "summary"],
        "properties": {
            "detected_language": {
                "type": "string",
                "enum": ["bn", "en"],
                "description": "Detected primary language ('bn' for Bengali, 'en' for English)"
            },
            "bangla_transcript": {
                "type": "string",
                "description": "Refined, formal Bengali transcription and proceedings narrative."
            },
            "english_transcript": {
                "type": "string",
                "description": "Refined, formal English transcription and proceedings narrative."
            },
            "summary": {
                "type": "object",
                "description": f"Structured payload populated specifically for the '{name}' template.",
                "required": list(dict.fromkeys(summary_required)),
                "properties": summary_properties
            }
        }
    }
    return schema

def generate_template_json_example(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a realistic, fully populated JSON example payload matching the template's schema.
    Used for one-shot / few-shot in-context learning in the LLM system prompt.
    """
    t_id = template.get("id", "")
    doc_type = template.get("doc_type", "custom")
    
    if t_id == "easd_default_minutes" or doc_type == "meeting_minutes":
        return {
            "detected_language": "bn",
            "bangla_transcript": "ইমিনের্স অ্যাসোসিয়েটস ফর সোশ্যাল ডেভেলপমেন্ট (ইএএসডি) এর সাপ্তাহিক কৌশলগত এবং কর্মসূচি পর্যালোচনা সভা অনুষ্ঠিত হয়। সভায় পূর্ববর্তী সভার অগ্রগতি, চলমান প্রকল্পসমূহের কার্যপ্রণালী এবং আসন্ন কর্মপরিকল্পনা নিয়ে বিস্তারিত আলোচনা সম্পন্ন হয়।",
            "english_transcript": "Eminence Associates for Social Development (EASD) weekly strategic and programmatic review meeting held. Progress of previous action items, operational workstreams, and upcoming institutional targets were reviewed in detail.",
            "summary": {
                "title": "Weekly Strategic, Programmatic and Presentation Review Meeting",
                "location": "Eminence Conference Hall, Mohakhali DOHS, Dhaka",
                "date": "29 August, 2026",
                "time": "11:00 AM - 01:00 PM",
                "agendas": [
                    "Follow-up on previous review meeting action items",
                    "Strategic review of programmatic operations and active field projects",
                    "Task assignments and milestone delivery timelines",
                    "Executive decisions and upcoming institutional schedule"
                ],
                "discussions": [
                    {
                        "sn": "1",
                        "topic": "Followup from previous meeting",
                        "details": "• Verified completion of the interim project monitoring report.\n• Confirmed resolution of administrative queries from field coordinators.\n• Core milestones identified in the previous session achieved on schedule."
                    },
                    {
                        "sn": "2",
                        "topic": "Action items",
                        "details": "• Finalize the draft advocacy strategy document by Thursday.\n• Conduct comprehensive quality assurance for all community survey deliverables.\n• Submit weekly expenditure and logistics statements to finance."
                    },
                    {
                        "sn": "3",
                        "topic": "Task Assignments",
                        "details": "• Program Lead assigned oversight of the upcoming stakeholder consultation workshop.\n• Research Associate tasked with synthesizing baseline data by next Tuesday.\n• Communications Officer assigned public dissemination and press release preparation."
                    },
                    {
                        "sn": "4",
                        "topic": "Meeting Decisions",
                        "details": "• Formally approved the revised programmatic roadmap for Q4 2026.\n• Scheduled next weekly strategic review session for September 5, 2026 at 11:00 AM.\n• Mandated weekly milestone check-ins across all active department wings."
                    }
                ],
                "decisions": "• Formally approved the revised programmatic roadmap for Q4 2026.\n• Scheduled next weekly strategic review session for September 5, 2026 at 11:00 AM.\n• Mandated weekly milestone check-ins across all active department wings.",
                "present_members": [
                    "Dr. Shamim Talukder",
                    "Md. Rafiqul Islam",
                    "Nusrat Jahan"
                ],
                "attendance": [
                    {"serial": "1", "name": "Dr. Shamim Talukder", "participation": "Yes"},
                    {"serial": "2", "name": "Md. Rafiqul Islam", "participation": "Yes"},
                    {"serial": "3", "name": "Nusrat Jahan", "participation": "Yes"}
                ]
            }
        }
        
    elif t_id == "bangladesh_govt_nothi" or doc_type == "bangladesh_govt_report":
        return {
            "detected_language": "bn",
            "bangla_transcript": "গণপ্রজাতন্ত্রী বাংলাদেশ সরকারের স্বাস্থ্য সেবা বিভাগের আওতাধীন জাতীয় স্বাস্থ্য নীতি বাস্তবায়ন পর্যালোচনা সম্পর্কিত আনুষ্ঠানিক সভা কার্যবিবরণী। মাঠ পর্যায়ের তথ্য ও পর্যবেক্ষণ বিশদভাবে পর্যালোচনা করা হয়েছে।",
            "english_transcript": "Official review meeting proceedings on national health policy implementation under the Health Services Division, Ministry of Health and Family Welfare, Government of the People's Republic of Bangladesh.",
            "summary": {
                "ministry": "স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয় / Ministry of Health and Family Welfare",
                "department": "স্বাস্থ্য সেবা বিভাগ, পরিকল্পনা অনুবিভাগ",
                "memo_no": "৪৫.০০.০০০০.০০১.২৪.০০১.২৬-৫২২",
                "date": "০২ সেপ্টেম্বর, ২০২৬ / 02 September 2026",
                "subject": "জাতীয় স্বাস্থ্য নীতি ও স্বাস্থ্যসেবা প্রোগ্রাম বাস্তবায়ন অগ্রগতি পর্যালোচনা প্রতিবেদন প্রসঙ্গে।",
                "background": "গণপ্রজাতন্ত্রী বাংলাদেশ সরকারের রূপকল্প বাস্তবায়ন ও প্রান্তিক জনগোষ্ঠীর দোরগোড়ায় গুণগত স্বাস্থ্যসেবা নিশ্চিতকরণের লক্ষ্যে আয়োজিত আন্তঃবিভাগীয় সমন্বয় সভার পটভূমি ও উদ্দেশ্য।",
                "observations": "• ৬৪টি জেলায় ডিজিটাল স্বাস্থ্য রেকর্ড সিস্টেমের প্রথম পর্যায়ের পাইলট কার্যক্রম সফলভাবে সম্পন্ন হয়েছে।\n• তৃণমূল স্বাস্থ্য কেন্দ্রসমূহে জরুরি জীবনরক্ষাকারী ওষুধের পর্যাপ্ত সরবরাহ নিশ্চিত করা হয়েছে।\n• জনবল ঘাটতি চিহ্নিতকরণে প্রশাসনিক পরিদর্শন প্রতিবেদন গৃহীত হয়েছে।",
                "decisions": "• আগামী ৩১ অক্টোবরের মধ্যে জেলা পর্যায়ের পূর্ণাঙ্গ মূল্যায়ন প্রতিবেদন দাখিলের নির্দেশ প্রদান করা হলো।\n• উপজেলা স্বাস্থ্য কমপ্লেক্সসমূহে ২৪/৭ টেলিমেডিসিন সেবা কার্যকর করার সিদ্ধান্ত গৃহীত হয়।",
                "recommendations": "• ১. বিভাগীয় মনিটরিং সেলের সার্বক্ষণিক তত্ত্বাবধান জোরদার করা সমীচীন।\n• ২. মাঠ পর্যায়ের কর্মকর্তাদের আধুনিক স্বাস্থ্য তথ্য প্রযুক্তির উপর প্রশিক্ষণ প্রদান করা বাঞ্ছনীয়।\n• ৩. বরাদ্দকৃত উন্নয়ন বাজেটের ত্রৈমাসিক বাস্তবায়ন হার বৃদ্ধি করা আবশ্যক।",
                "signatory": "মোহাম্মদ আবদুল কাদের, যুগ্মসচিব (পরিকল্পনা), স্বাস্থ্য সেবা বিভাগ",
                "action_matrix": [
                    {
                        "sn": "১",
                        "action": "জেলা মূল্যায়ন প্রতিবেদন চূড়ান্তকরণ",
                        "authority": "পরিচালক (এমআইএস), স্বাস্থ্য অধিদপ্তর",
                        "deadline": "১৫ অক্টোবর, ২০২৬"
                    },
                    {
                        "sn": "২",
                        "action": "টেলিমেডিসিন সেবা অবকাঠামো আধুনিকায়ন",
                        "authority": "যুগ্মসচিব (হাসপাতাল অনুবিভাগ)",
                        "deadline": "৩০ নভেম্বর, ২০২৬"
                    }
                ]
            }
        }

    elif t_id == "journal_academic" or doc_type == "journal":
        return {
            "detected_language": "en",
            "bangla_transcript": "নগর ও গ্রামীণ জনগোষ্ঠীর মধ্যে অসংক্রামক রোগ প্রতিরোধে জনস্বাস্থ্য কর্মসূচি সমূহের কার্যকারিতা বিষয়ক গবেষণার বৈজ্ঞানিক ফলাফল।",
            "english_transcript": "Scientific evaluation of community-based public health interventions in reducing non-communicable disease prevalence across diverse cohorts.",
            "summary": {
                "title": "Epidemiological Trends and Public Health Interventions in Urban Communities: A Multi-Center Evaluation",
                "authors": "EASD Research & Evaluation Wing, Eminence Institute of Public Health",
                "keywords": "Public Health, NCD Prevention, Health Systems, Community Interventions, Epidemiology",
                "date": "September 2026",
                "abstract": "Background: Non-communicable diseases (NCDs) represent a growing public health crisis in rapidly urbanizing regions. Methods: A prospective mixed-methods cohort study was conducted across 1,200 households over an 18-month intervention period. Results: Interventions led to a 28% increase in screening adherence and a statistically significant reduction in untreated hypertension. Conclusion: Integrated grassroots health models substantially improve primary care management and clinical compliance.",
                "introduction": "The rapid pace of urbanization has altered demographic risk profiles, elevating NCD incidence across vulnerable socioeconomic strata. This study investigates the institutional efficacy of community health worker networks in bridging primary screening deficits.",
                "methodology": "A structured randomized cluster methodology was deployed across 8 urban wards. Quantitative clinical metrics (blood pressure, fasting glucose) were paired with qualitative focus group discussions. Data analysis utilized multivariate logistic regression.",
                "results": "• Screening uptake increased from 34.2% at baseline to 62.5% post-intervention (p < 0.001).\n• Community health education sessions achieved an 84% follow-through rate among enrolled participants.\n• Treatment compliance among diagnosed hypertensive patients showed a 31% relative enhancement.",
                "discussion": "The empirical outcomes corroborate existing literature emphasizing community-embedded frontline responders. Observed gains in screening adherence underline the criticality of decentralizing preventive diagnostics.",
                "conclusion": "Community-driven public health frameworks offer a scalable and cost-effective mechanism for mitigating urban chronic disease burdens. Institutional adoption by municipal authorities is strongly advocated.",
                "references": "• Talukder, S., et al. (2025). Community Health Interventions in South Asia. Journal of Global Health, 15(2), 112-125.\n• World Health Organization. (2024). Global Status Report on Noncommunicable Diseases. Geneva: WHO Press.",
                "data_table": [
                    {
                        "variable": "NCD Screening Coverage",
                        "baseline": "34.2%",
                        "outcome": "62.5%",
                        "significance": "p < 0.001 (Highly Significant)"
                    },
                    {
                        "variable": "Hypertension Adherence",
                        "baseline": "41.0%",
                        "outcome": "72.0%",
                        "significance": "p = 0.004 (Statistically Significant)"
                    }
                ]
            }
        }

    elif t_id == "news_press_release" or doc_type == "news":
        return {
            "detected_language": "en",
            "bangla_transcript": "ইমিনের্স অ্যাসোসিয়েটস ফর সোশ্যাল ডেভেলপমেন্ট (ইএএসডি) এর উদ্যোগে অসংক্রামক রোগ প্রতিরোধে নতুন জাতীয় কর্মসূচির আনুষ্ঠানিক উদ্বোধন ও প্রেস বিজ্ঞপ্তি।",
            "english_transcript": "Official press release announcing EASD's landmark nationwide community health initiative to combat non-communicable diseases.",
            "summary": {
                "title": "EASD Unveils Landmark Nationwide Community Health Initiative to Combat Non-Communicable Diseases",
                "dateline": "DHAKA, Bangladesh",
                "date": "September 2, 2026",
                "media_contact": "Communications Directorate, Eminence (media@eminence-bd.org, +880-2-9876543)",
                "lead_paragraph": "DHAKA, Bangladesh — Eminence Associates for Social Development (EASD) today officially inaugurated an expansive nationwide community health program aimed at delivering vital screening and preventive healthcare directly to 500,000 households.",
                "body_story": "The landmark initiative bridges persistent healthcare gaps by deploying specialized mobile diagnostic units and training 2,500 frontline community health champions across eight administrative divisions. The launch comes in response to alarming rises in hypertension and diabetes, particularly among underserved urban and peri-urban demographics.",
                "key_quotes": "• 'True healthcare equity begins when quality preventive diagnostics reach families directly at their doorsteps,' stated Dr. Shamim Talukder, Chief Executive Officer of EASD.\n• 'This partnership represents an unprecedented milestone in scaling grassroots preventative medicine,' noted the Director General of Health Services during the inaugural briefing.",
                "highlights": "• Direct coverage for over 500,000 households across 64 districts.\n• Deployment of 50 solar-powered mobile screening vans equipped with digital telemetry.\n• 100% free early diagnostic testing for diabetes, hypertension, and cardiovascular risk factors.",
                "boilerplate": "About Eminence: Founded in 2003, Eminence Associates for Social Development (EASD) is a premier non-profit development organization dedicated to public health innovation, social justice, and sustainable community empowerment in Bangladesh and globally."
            }
        }

    elif t_id == "blog_article" or doc_type == "blog":
        return {
            "detected_language": "en",
            "bangla_transcript": "তৃণমূল পর্যায়ে জনস্বাস্থ্য উন্নয়নে ৫টি বাস্তব অভিজ্ঞতা ও ভবিষ্যৎ দিকনির্দেশনা নিয়ে বিশেষ ডিজিটাল ব্লগ প্রবন্ধ।",
            "english_transcript": "Thought leadership blog article discussing grassroots public health transformation and key actionable lessons from the field.",
            "summary": {
                "title": "Transforming Public Health from the Grassroots: 5 Game-Changing Lessons from the Field",
                "author": "EASD Thought Leadership & Strategy Team",
                "target_audience": "Development Practitioners, Policymakers, Global Health Advocates, and Social Innovators",
                "date": "September 2026",
                "hook_intro": "What if the biggest barrier to saving millions of lives isn't costly high-tech medicine, but simply listening to what frontline community workers see every single morning? Over two decades in field operations have revealed five transformative insights.",
                "core_insights": "Public health succeeds when ownership shifts from distant boardroom planners to local communities. By equipping community health advocates with simple digital tools and cultural fluency, preventive healthcare transforms from a perceived burden into a celebrated neighborhood movement. Trust is the foundational infrastructure upon which every clinical outcome rests.",
                "practical_tips": "• 1. Involve local community elders and youth leaders before initiating any baseline intervention.\n• 2. Replace complex paper registries with intuitive, offline-first mobile reporting apps.\n• 3. Measure success through patient retention and trust indicators, not just raw attendance headcounts.\n• 4. Build resilient feedback loops that allow field coordinators to immediately refine intervention tactics.",
                "conclusion_cta": "Lasting transformation in global health never occurs from the top down—it blossoms from the roots up. What grassroots initiatives have inspired your work? Share your thoughts in the comments below or reach out to partner with us!"
            }
        }

    elif t_id == "transcript_summary" or doc_type == "summary":
        return {
            "detected_language": "en",
            "bangla_transcript": "আলোচনার মূল বিষয়বস্তু ও সিদ্ধান্তসমূহের সরাসরি সারসংক্ষেপ।",
            "english_transcript": "Concise executive synthesis and action points derived directly from the proceedings transcript.",
            "summary": {
                "title": "Executive Summary of Proceedings",
                "date": "September 2026",
                "overview": "The session addressed strategic program delivery, field milestone timelines, and immediate operational priorities. Participants reviewed key progress markers, aligned on immediate workstreams, and confirmed decisive operational directives.",
                "key_topics": "• Program delivery status across field operations.\n• Budgetary compliance, resource allocation, and quality standards.\n• Stakeholder coordination and community mobilization strategy.\n• Risk management protocols and schedule synchronization.",
                "decisions": "• Confirmed unified milestone roadmap and delivery schedule.\n• Formally approved operational resource adjustments for active workstreams.\n• Established recurring weekly review cadence for project leads.",
                "action_items": "• Finalize operational documentation and share with team leads by Friday.\n• Establish field monitoring checkpoints for upcoming program rollouts.\n• Consolidate weekly progress reports for executive review."
            }
        }

    else:
        # Custom uploaded template: generate synthetic example matching fields, sections, and tables
        summary_obj = {}
        for fld in template.get("fields", []):
            k = fld.get("key", "")
            if k:
                summary_obj[k] = fld.get("default") or f"Sample {fld.get('label', k)}"
                
        for sec in template.get("sections", []):
            s_id = sec.get("id", "")
            s_type = sec.get("type", "text")
            s_title = sec.get("title", s_id)
            if s_type == "bullets":
                summary_obj[s_id] = f"• Comprehensive finding regarding {s_title}.\n• Operational directive and verified stakeholder feedback."
            elif s_type == "list":
                summary_obj[s_id] = [f"First priority point for {s_title}", f"Second priority milestone for {s_title}"]
            else:
                summary_obj[s_id] = f"Detailed narrative synthesis addressing {s_title} with formal institutional context and outcomes."
                
        for tbl in template.get("tables", []):
            tbl_id = tbl.get("id", "")
            cols = tbl.get("columns", [])
            sample_rows = tbl.get("sample_rows", [])
            if sample_rows:
                tbl_rows = []
                for s_row in sample_rows[:3]:
                    row_dict = {}
                    for c_idx, c_name in enumerate(cols):
                        val = s_row[c_idx] if c_idx < len(s_row) else ""
                        row_dict[re.sub(r'[^a-zA-Z0-9_]', '_', c_name.lower().strip())] = val
                    tbl_rows.append(row_dict)
                summary_obj[tbl_id] = tbl_rows
            else:
                row_dict = {re.sub(r'[^a-zA-Z0-9_]', '_', col.lower().strip()): f"Sample {col}" for col in cols}
                summary_obj[tbl_id] = [row_dict]

        return {
            "detected_language": "bn",
            "bangla_transcript": f"'{template.get('name', 'কাস্টম নথি')}' টেমপ্লেট অনুযায়ী প্রস্তুতকৃত বাংলা আলোচনা ও সভার সারসংক্ষেপ।",
            "english_transcript": f"Structured transcript and synthesis generated according to '{template.get('name', 'Custom Document')}' specifications.",
            "summary": summary_obj
        }

def get_template_json_schema(template_or_id: Any) -> Dict[str, Any]:
    """Retrieves or generates the JSON Schema for a given template object or template ID."""
    if isinstance(template_or_id, dict):
        tpl = template_or_id
    elif isinstance(template_or_id, str):
        tpl = get_template_by_id(template_or_id)
    else:
        tpl = DEFAULT_TEMPLATES[0]
        
    if not tpl:
        tpl = DEFAULT_TEMPLATES[0]
        
    if "json_schema" in tpl and isinstance(tpl["json_schema"], dict):
        return tpl["json_schema"]
    return generate_template_json_schema(tpl)

def get_template_json_example(template_or_id: Any) -> Dict[str, Any]:
    """Retrieves or generates the illustrative JSON example for a given template object or template ID."""
    if isinstance(template_or_id, dict):
        tpl = template_or_id
    elif isinstance(template_or_id, str):
        tpl = get_template_by_id(template_or_id)
    else:
        tpl = DEFAULT_TEMPLATES[0]
        
    if not tpl:
        tpl = DEFAULT_TEMPLATES[0]
        
    if "json_example" in tpl and isinstance(tpl["json_example"], dict):
        return tpl["json_example"]
    return generate_template_json_example(tpl)

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
                    # Ensure all templates have 3 core directives, valid schemas, and examples
                    for item in combined:
                        if not item.get("context"):
                            item["context"] = f"General template for {item.get('name', 'Custom Document')}."
                        if not item.get("rules"):
                            item["rules"] = "1. Write in formal institutional tone.\n2. Keep bullet points clear with single bullets ('• ')."
                        if not item.get("requirements"):
                            item["requirements"] = "- Complete all mandatory sections.\n- Ensure accurate metadata fields."
                        if not item.get("doc_type"):
                            item["doc_type"] = "custom"
                        item["json_schema"] = generate_template_json_schema(item)
                        item["json_example"] = generate_template_json_example(item)
                    return combined
        except Exception as e:
            print(f"[Template Load Warning] {e}")
            
    # For default fallback, ensure json_schema and json_example are populated
    defaults_with_schema = []
    for d in DEFAULT_TEMPLATES:
        d_copy = copy.deepcopy(d)
        d_copy["json_schema"] = generate_template_json_schema(d_copy)
        d_copy["json_example"] = generate_template_json_example(d_copy)
        defaults_with_schema.append(d_copy)
    return defaults_with_schema

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
    meta_keywords = ["date", "time", "venue", "location", "memo", "ref", "স্মারক", "তারিখ", "স্থান", "উপস্থিত"]
    
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt or len(txt) < 3:
            continue
        
        # Skip if matches detected title or pure metadata line
        if txt.lower() == detected_title.lower():
            continue
        if re.match(r'^(?:date|time|venue|location|meeting date|place)\b', txt, re.IGNORECASE):
            continue
        if any(txt.lower().startswith(kw) for kw in ["date:", "time:", "venue:", "location:", "তারিখ:", "স্থান:"]):
            continue
            
        is_heading = False
        if p.style and p.style.name.startswith("Heading"):
            is_heading = True
        elif len(txt) < 80 and (
            txt.isupper() 
            or re.match(r'^\d+[\.\)]\s+[A-Z\u0980-\u09FF]', txt)
            or (len(p.runs) > 0 and p.runs[0].bold and not any(kw in txt.lower() for kw in meta_keywords))
        ):
            is_heading = True
            
        if is_heading:
            clean_head = re.sub(r'^\d+[\.\)]\s*', '', txt).strip()
            # Clean slug to avoid collisions on non-ASCII/Bengali text
            ascii_slug = re.sub(r'[^a-zA-Z0-9_]', '', clean_head.lower().replace(" ", "_"))[:18]
            sec_id = f"sec_{section_counter}_{ascii_slug}" if ascii_slug else f"sec_{section_counter}"
            
            if not any(s["id"] == sec_id for s in detected_sections):
                detected_sections.append({
                    "id": sec_id,
                    "title": txt,
                    "type": "bullets" if any(w in txt.lower() for w in ["action", "finding", "decision", "recommendation", "সিদ্ধান্ত", "সুপারিশ", "আলোচনা"]) else "text",
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
                # Deduplicate consecutive identical cells if merged
                dedup_cols = []
                for c in header_cells:
                    if not dedup_cols or dedup_cols[-1] != c:
                        dedup_cols.append(c)
                
                col_str = " ".join(dedup_cols).lower()
                t_title = f"Table {t_idx + 1}"
                if any(w in col_str for w in ["topic", "discussion", "decision"]):
                    t_title = "Agenda & Discussion Matrix"
                elif any(w in col_str for w in ["name", "designation", "present", "absent", "participation"]):
                    t_title = "Meeting Attendance List"

                # Extract sample / fixed rows (predefined discussion topics or attendance)
                sample_rows = []
                for row in table.rows[1:]:
                    vals = [c.text.strip().replace("\n", " ") for c in row.cells]
                    if any(v for v in vals):
                        sample_rows.append(vals)

                tbl_data = {
                    "id": f"table_{t_idx}",
                    "title": t_title,
                    "columns": dedup_cols
                }
                if sample_rows:
                    tbl_data["sample_rows"] = sample_rows[:25]
                detected_tables.append(tbl_data)

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
    generalized_template["json_schema"] = generate_template_json_schema(generalized_template)
    generalized_template["json_example"] = generate_template_json_example(generalized_template)

    all_t = load_saved_templates()
    all_t.append(generalized_template)
    save_templates_to_disk(all_t)

    return generalized_template

def save_custom_template(template_data: Dict[str, Any], save_as_new: bool = False) -> Dict[str, Any]:
    """Saves or updates a template schema in the templates store.
    Built-in templates are strictly protected and will always be saved as a new custom template."""
    all_t = load_saved_templates()
    builtin_ids = {d["id"] for d in DEFAULT_TEMPLATES}
    
    t_id = template_data.get("id")
    is_target_builtin = t_id in builtin_ids or template_data.get("is_builtin", False)
    
    # Ensure json_schema and json_example are fresh and accurate
    template_data["json_schema"] = generate_template_json_schema(template_data)
    template_data["json_example"] = generate_template_json_example(template_data)

    # If explicitly requesting Save as New OR attempting to overwrite a built-in template:
    if save_as_new or is_target_builtin or not t_id:
        new_id = f"custom_tpl_{uuid.uuid4().hex[:8]}"
        template_data = copy.deepcopy(template_data)
        template_data["id"] = new_id
        template_data["is_builtin"] = False
        template_data["is_default"] = False
        if is_target_builtin and template_data.get("name") in [d["name"] for d in DEFAULT_TEMPLATES]:
            template_data["name"] = f"{template_data['name']} (Custom)"
        template_data["category"] = template_data.get("category") or "Custom Templates"
        all_t.append(template_data)
        save_templates_to_disk(all_t)
        return template_data

    template_data["id"] = t_id
    updated = False
    for idx, t in enumerate(all_t):
        if t.get("id") == t_id:
            # Preserve original docx if not provided
            if not template_data.get("docx_filename") and t.get("docx_filename"):
                template_data["docx_filename"] = t["docx_filename"]
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

            # Smart date/time replacement in paragraphs
            date_val = str(data.get("date") or "")
            time_val = str(data.get("time") or "")
            title_val = str(data.get("title") or "")
            location_val = str(data.get("location") or "")

            if date_val or time_val:
                for p in doc.paragraphs[:10]:
                    if "Date:" in p.text and date_val:
                        p.text = re.sub(r'Date:\s*[^\t\n\r]+', f"Date: {date_val}", p.text, count=1)
                    if "Time:" in p.text and time_val:
                        p.text = re.sub(r'Time:\s*[^\t\n\r]+', f"Time: {time_val}", p.text, count=1)

            # Populate tables in the uploaded document (Discussions & Attendance)
            discussions = data.get("discussions") or data.get("summary", {}).get("discussions", [])
            attendance = data.get("attendance") or data.get("summary", {}).get("attendance", [])

            for table in doc.tables:
                if len(table.rows) > 1 and len(table.columns) >= 3:
                    hdr_text = " ".join([c.text.lower() for c in table.rows[0].cells])
                    # Discussion matrix table
                    if any(w in hdr_text for w in ["topic", "discussion", "sn"]):
                        for r_idx, row in enumerate(table.rows[1:]):
                            if r_idx < len(discussions):
                                d_item = discussions[r_idx]
                                dt = d_item.get("details", "")
                                if len(row.cells) >= 3 and dt:
                                    row.cells[2].text = dt
                                elif len(row.cells) == 2 and dt:
                                    row.cells[1].text = dt
                    # Attendance table
                    elif any(w in hdr_text for w in ["name", "participation", "status", "present"]):
                        for row in table.rows[1:]:
                            if len(row.cells) >= 3:
                                name_in_cell = row.cells[1].text.strip().lower()
                                for att in attendance:
                                    att_name = att.get("name", "").lower()
                                    if att_name and (att_name in name_in_cell or name_in_cell in att_name):
                                        st = att.get("status", "Present")
                                        row.cells[2].text = "Yes" if "present" in st.lower() or "yes" in st.lower() else "No"
                                        break

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
            if not rows_data:
                col_str = " ".join(cols).lower()
                if any(w in col_str for w in ["topic", "discussion", "sn"]):
                    rows_data = data.get("discussions") or data.get("summary", {}).get("discussions", [])
                elif any(w in col_str for w in ["name", "present", "attendance", "participation"]):
                    rows_data = data.get("attendance") or data.get("summary", {}).get("attendance", [])

            if rows_data and isinstance(rows_data, list):
                for row_item in rows_data:
                    row_el = table_el.add_row()
                    for c_idx, col_name in enumerate(cols):
                        val = ""
                        col_l = col_name.lower().strip()
                        if isinstance(row_item, dict):
                            if any(s in col_l for s in ["sl", "sn", "no", "serial", "ক্রম"]):
                                val = str(row_item.get("sn") or row_item.get("sl") or row_item.get("no") or "")
                            elif any(s in col_l for s in ["topic", "agenda", "বিষয়", "বিষয়"]):
                                val = str(row_item.get("topic") or row_item.get("agenda") or "")
                            elif any(s in col_l for s in ["discuss", "detail", "আলোচনা", "বিবরণ"]):
                                val = str(row_item.get("details") or row_item.get("discussion") or "")
                            elif any(s in col_l for s in ["decision", "action", "সিদ্ধান্ত"]):
                                val = str(row_item.get("decision") or row_item.get("decisions") or row_item.get("details") or "")
                            elif any(s in col_l for s in ["name", "নাম"]):
                                val = str(row_item.get("name") or "")
                            elif any(s in col_l for s in ["designation", "পদবী", "পদবি"]):
                                val = str(row_item.get("designation") or "")
                            elif any(s in col_l for s in ["status", "present", "participation", "উপস্থিতি"]):
                                val = str(row_item.get("status") or row_item.get("participation") or "Present")
                            else:
                                val = str(row_item.get(col_name) or row_item.get(col_l) or (list(row_item.values())[min(c_idx, len(row_item)-1)] if row_item else ""))
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
