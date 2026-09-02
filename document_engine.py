import io
import re
import copy
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

DEFAULT_MEMBERS = [
    {"serial": "1", "name": "Md. Shamim Hayder Talukder", "participation": "Yes"},
    {"serial": "2", "name": "Shahin Akter", "participation": "Yes"},
    {"serial": "3", "name": "Ummay Farihin Sultana", "participation": "Yes"},
    {"serial": "4", "name": "Abu Tareq Muhammad Salahuddin", "participation": "Yes"},
    {"serial": "5", "name": "Md. Robiul Islam", "participation": "Yes"},
    {"serial": "6", "name": "Salman Mahmud Siddique", "participation": "Yes"},
    {"serial": "7", "name": "Md. Saddam Hossain", "participation": "Yes"},
    {"serial": "8", "name": "Abhijeet Kumar Singh", "participation": "Yes"},
    {"serial": "9", "name": "Suman Sikder", "participation": "Yes"},
    {"serial": "10", "name": "H M Taseen Jubair Bhuiyan", "participation": "Yes"},
    {"serial": "11", "name": "Safkat Faruk Sezan", "participation": "Yes"},
    {"serial": "12", "name": "Md Shahazin Rhaman Mayen", "participation": "Yes"},
    {"serial": "13", "name": "Pew Roy Chowdhury", "participation": "Yes"},
    {"serial": "14", "name": "Esha Sanjida", "participation": "Yes"},
    {"serial": "15", "name": "Jaima Nooren Zia", "participation": "Yes"},
    {"serial": "16", "name": "Maruf Hasan", "participation": "Yes"},
    {"serial": "17", "name": "Kartik Bala", "participation": "Yes"},
    {"serial": "18", "name": "MD Ismail Hossain Sabbir", "participation": "Yes"},
    {"serial": "19", "name": "Md Apon Munshi", "participation": "Yes"},
    {"serial": "20", "name": "MD Jahidul Mia", "participation": "Yes"},
    {"serial": "21", "name": "Nurrunnahar Begum", "participation": "Yes"}
]

def replace_paragraph_text_preserving_runs(paragraph, new_text: str):
    """Fast text replacement preserving run formatting."""
    if not paragraph.runs:
        paragraph.text = new_text
        return
    
    first_run = paragraph.runs[0]
    font_name = first_run.font.name
    font_size = first_run.font.size
    bold = first_run.bold
    italic = first_run.italic
    color = first_run.font.color.rgb if first_run.font.color else None

    p_element = paragraph._p
    for child in list(p_element):
        if child.tag.endswith('r'):
            p_element.remove(child)

    r = paragraph.add_run(new_text)
    if font_name:
        r.font.name = font_name
    if font_size:
        r.font.size = font_size
    if bold is not None:
        r.bold = bold
    if italic is not None:
        r.italic = italic
    if color:
        r.font.color.rgb = color

def set_cell_text_formatted(cell, text: str, bold_title: bool = False, font_name: str = "Times New Roman", font_size=Pt(10.5)):
    """Fast cell text setting maintaining paragraph structure."""
    p = cell.paragraphs[0]
    p.text = ""
    
    lines = text.split("\n") if isinstance(text, str) else [str(text)]
    for i, line in enumerate(lines):
        if i > 0:
            p = cell.add_paragraph()
        run = p.add_run(line)
        run.font.name = font_name
        run.font.size = font_size
        if bold_title:
            run.bold = True

def duplicate_tr_with_formatting(table, template_row_idx: int = 1):
    """Deep clones XML row structure for 100% border & margin preservation."""
    template_tr = table.rows[template_row_idx]._tr
    new_tr = copy.deepcopy(template_tr)
    table._tbl.append(new_tr)
    return table.rows[-1]

def clean_agenda_item(text: str) -> str:
    """Strips any leading numbering or bullet symbols from an agenda item."""
    if not text:
        return ""
    cleaned = re.sub(r'^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\u2022\u2023\u25E6\u2043\u2219\t]+\s*)+', '', str(text).strip())
    cleaned = re.sub(r'^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\u2022\u2023\u25E6\u2043\u2219\t]+\s*)+', '', cleaned).strip()
    return cleaned

def clean_bullet_points(text: str) -> str:
    """Ensures each line starts with exactly one bullet point (• ) and no double bullets."""
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

def generate_meeting_minutes_docx_bytes(data: dict, template_path: str) -> bytes:
    with open(template_path, "rb") as f:
        template_buffer = io.BytesIO(f.read())
        
    doc = docx.Document(template_buffer)
    
    # 1. Title, Location, Date & Time
    if "title" in data and len(doc.paragraphs) > 3 and data["title"]:
        replace_paragraph_text_preserving_runs(doc.paragraphs[3], data["title"])
        
    if "location" in data and len(doc.paragraphs) > 4 and data["location"]:
        replace_paragraph_text_preserving_runs(doc.paragraphs[4], data["location"])
        
    if len(doc.paragraphs) > 7:
        d_val = data.get("date") or "29 August, 2026"
        t_val = data.get("time") or "11:00 AM - 01:00 PM"
        date_time_str = f"Date: {d_val} \t\t\t\t\t\t           Time: {t_val}"
        replace_paragraph_text_preserving_runs(doc.paragraphs[7], date_time_str)

    # 2. Agendas (Clean single numbering: "1. Agenda...")
    agendas = data.get("agendas", [])
    if agendas and len(agendas) > 0:
        target_p_idx = 11
        if target_p_idx < len(doc.paragraphs):
            first_agenda = agendas[0] if isinstance(agendas, list) else agendas
            replace_paragraph_text_preserving_runs(doc.paragraphs[target_p_idx], f"1. {clean_agenda_item(first_agenda)}")
            
            if isinstance(agendas, list) and len(agendas) > 1:
                ref_p = doc.paragraphs[target_p_idx]._p
                for idx, agenda_item in enumerate(agendas[1:], start=2):
                    new_p = doc.add_paragraph()
                    replace_paragraph_text_preserving_runs(new_p, f"{idx}. {clean_agenda_item(agenda_item)}")
                    ref_p.addnext(new_p._p)
                    ref_p = new_p._p

    # 3. Clean Instruction Text
    for p in doc.paragraphs:
        if "Meeting Agenda" in p.text and "(4-5" in p.text:
            replace_paragraph_text_preserving_runs(p, "Meeting Agenda:")
        if "Attendance Sheet" in p.text and ("checklist" in p.text.lower() or "attendence section" in p.text.lower()):
            replace_paragraph_text_preserving_runs(p, "Attendance Sheet")

    # 4. Table 0 (Discussion Points Table) — always exactly 4 rows matching template
    TEMPLATE_TOPICS = [
        "Followup from previous meeting",
        "Action items",
        "Task Assignments",
        "Meeting Decisions",
    ]
    if len(doc.tables) > 0:
        t0 = doc.tables[0]
        raw_discussions = data.get("discussions", [])
        
        # Build a topic -> details lookup from incoming data
        topic_map = {}
        for item in raw_discussions:
            key = str(item.get("topic", "")).strip().lower()
            topic_map[key] = clean_bullet_points(str(item.get("details", "")))
        
        # Also map by sn for positional fallback
        sn_map = {}
        for item in raw_discussions:
            sn_map[str(item.get("sn", "")).strip()] = clean_bullet_points(str(item.get("details", "")))

        # Helper: resolve details for a template slot
        def resolve_details(sn: str, template_topic: str) -> str:
            # Try exact topic match
            if template_topic.lower() in topic_map:
                return topic_map[template_topic.lower()]
            # Try fuzzy keyword match
            for k, v in topic_map.items():
                if any(kw in k for kw in template_topic.lower().split()[:2]):
                    return v
            # Fallback by position
            return sn_map.get(sn, "")

        # Ensure table has exactly 5 rows (header + 4 data)
        while len(t0.rows) < 5:
            duplicate_tr_with_formatting(t0, template_row_idx=1)
        while len(t0.rows) > 5:
            t0._tbl.remove(t0.rows[-1]._tr)

        # Fill rows 1-4 with fixed template topics
        for idx, template_topic in enumerate(TEMPLATE_TOPICS):
            sn = str(idx + 1)
            row = t0.rows[idx + 1]
            details = resolve_details(sn, template_topic)
            set_cell_text_formatted(row.cells[0], sn, bold_title=False)
            set_cell_text_formatted(row.cells[1], template_topic, bold_title=True)
            set_cell_text_formatted(row.cells[2], clean_bullet_points(details), bold_title=False)
        

    # 6. Table 1 (Attendance Sheet) - ALWAYS KEEP ALL 21 MEMBERS
    if len(doc.tables) > 1:
        t1 = doc.tables[1]
        attendance_list = data.get("attendance")
        if not attendance_list or len(attendance_list) == 0:
            attendance_list = DEFAULT_MEMBERS
            
        existing_rows_count = len(t1.rows)
        for idx, member in enumerate(attendance_list):
            serial = str(member.get("serial", idx + 1))
            name = str(member.get("name", ""))
            participation = str(member.get("participation", "Yes"))
            
            row_idx = idx + 1
            if row_idx < existing_rows_count:
                row = t1.rows[row_idx]
            else:
                row = duplicate_tr_with_formatting(t1, template_row_idx=1)
                
            set_cell_text_formatted(row.cells[0], serial)
            set_cell_text_formatted(row.cells[1], name)
            set_cell_text_formatted(row.cells[2], participation, bold_title=(participation == "Yes"))
            
        while len(t1.rows) > len(attendance_list) + 1 and len(t1.rows) > 21:
            t1._tbl.remove(t1.rows[-1]._tr)

    # 7. Dual Transcripts Section
    bangla_t = data.get("bangla_transcript", "").strip()
    english_t = data.get("english_transcript", "").strip()
    
    if bangla_t or english_t:
        doc.add_page_break()
        h = doc.add_paragraph()
        r_h = h.add_run("Meeting Transcripts")
        r_h.bold = True
        r_h.font.name = "Times New Roman"
        r_h.font.size = Pt(14)
        
        if bangla_t:
            p_b_head = doc.add_paragraph()
            r_bh = p_b_head.add_run("Bangla Transcript (বাংলা ট্রান্সক্রিপ্ট):")
            r_bh.bold = True
            r_bh.font.name = "Times New Roman"
            r_bh.font.size = Pt(11)
            
            p_b_body = doc.add_paragraph()
            r_bb = p_b_body.add_run(bangla_t)
            r_bb.font.name = "Hind Siliguri"
            r_bb.font.size = Pt(10)
            
        if english_t:
            p_e_head = doc.add_paragraph()
            r_eh = p_e_head.add_run("English Transcript:")
            r_eh.bold = True
            r_eh.font.name = "Times New Roman"
            r_eh.font.size = Pt(11)
            
            p_e_body = doc.add_paragraph()
            r_eb = p_e_body.add_run(english_t)
            r_eb.font.name = "Times New Roman"
            r_eb.font.size = Pt(10)

    out_stream = io.BytesIO()
    doc.save(out_stream)
    return out_stream.getvalue()

def generate_meeting_minutes_docx(data: dict, template_path: str, output_path: str) -> str:
    docx_bytes = generate_meeting_minutes_docx_bytes(data, template_path)
    with open(output_path, "wb") as f:
        f.write(docx_bytes)
    return output_path
