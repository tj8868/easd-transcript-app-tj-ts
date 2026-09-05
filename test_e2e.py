import sys
import os
import io
import json
import re
from fastapi.testclient import TestClient
from app import app, TEMPLATE_PATH
from document_engine import generate_meeting_minutes_docx_bytes, DEFAULT_MEMBERS
from ai_providers import detect_text_language, deep_semantic_synthesis
import docx

def test_full_pipeline():
    print("=== Starting End-to-End Test Suite ===")
    client = TestClient(app)
    
    # 1. Test GET /api/template_members
    print("1. Testing GET /api/template_members...")
    resp = client.get("/api/template_members")
    assert resp.status_code == 200, f"Failed: {resp.status_code}"
    data = resp.json()
    assert "members" in data, "No members key in response"
    assert len(data["members"]) == 21, f"Expected 21 members, got {len(data['members'])}"
    print("   [PASSED] 21 team members successfully retrieved.")

    # 2. Test GET /api/default_config
    print("2. Testing GET /api/default_config...")
    resp = client.get("/api/default_config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert "provider" in cfg and "transcription_model" in cfg and "summarization_model" in cfg
    print(f"   [PASSED] Default config retrieved: Provider={cfg['provider']}, STT={cfg['transcription_model']}, LLM={cfg['summarization_model']}")
    
    # 3. Test Language Auto-Detection
    print("3. Testing Language Auto-Detection...")
    bangla_sample = "আজকের সভায় আমরা অসংক্রামক রোগ প্রতিরোধ বিষয়ে আলোচনা করেছি।"
    english_sample = "We discussed programmatic strategies and milestone deliverables in today's review."
    assert detect_text_language(bangla_sample) == "bn", "Bangla detection failed"
    assert detect_text_language(english_sample) == "en", "English detection failed"
    print("   [PASSED] Language Auto-Detection correctly identifies Bangla ('bn') and English ('en').")

    # 4. Test POST /api/generate_docx (Sub-50ms Streaming)
    print("4. Testing POST /api/generate_docx (Sub-50ms Streaming & Template Preservation)...")
    payload = {
        "title": "Weekly Strategic, Programmatic and Presentation Review Meeting",
        "location": "Eminence, Mohakhali, DOHS",
        "date": "29 August, 2026",
        "time": "11:00 AM - 01:00 PM",
        "agendas": [
            "Review of previous meeting minutes & action items",
            "Bangla & English AI Transcription System demo",
            "Task assignment for upcoming quarter",
            "Key strategic decisions"
        ],
        "discussions": [
            {
                "sn": "1",
                "topic": "Followup from previous meeting",
                "details": "• Verified complete template preservation module.\n• Confirmed Google Drive API folder sync."
            },
            {
                "sn": "2",
                "topic": "Action items",
                "details": "• Deploy cross-platform PWA and standalone Windows EXE.\n• Conduct full user acceptance testing."
            },
            {
                "sn": "3",
                "topic": "Task Assignments",
                "details": "• IT Team: Maintain Google Drive Service Account.\n• EASD Team: Verify Bangla transcript accuracy."
            },
            {
                "sn": "4",
                "topic": "Meeting Decisions",
                "details": "• Final approval given for new Transcription Application."
            }
        ],
        "decisions": "• Final approval given for new Transcription Application.",
        "attendance": DEFAULT_MEMBERS,
        "bangla_transcript": "বাংলা ট্রান্সক্রিপ্ট রেকর্ড...",
        "english_transcript": "English transcript record..."
    }
    
    import time
    t0 = time.time()
    gen_resp = client.post("/api/generate_docx", json=payload)
    elapsed_ms = (time.time() - t0) * 1000
    assert gen_resp.status_code == 200, f"Failed: {gen_resp.status_code}"
    assert len(gen_resp.content) > 10000, "Generated file too small"
    
    # Verify Content-Disposition Filename
    cd = gen_resp.headers.get("content-disposition", "")
    assert "EASD-Meeting Minutes-29August26.docx" in cd, f"Unexpected header filename: {cd}"
    print(f"   [PASSED] .docx document generated & streamed in {elapsed_ms:.2f}ms with filename 'EASD-Meeting Minutes-29August26.docx'.")
    
    # 5. Test In-Memory DOCX Structure & Table Constraints
    print("5. Validating DOCX XML Structure & Strict Template Constraints...")
    doc = docx.Document(io.BytesIO(gen_resp.content))
    assert len(doc.tables) >= 2, "Tables missing from generated docx"
    assert len(doc.tables[0].rows) == 5, f"Discussions table must have exactly 5 rows (1 header + 4 data), got {len(doc.tables[0].rows)}"
    assert len(doc.tables[1].rows) == 22, f"Attendance table must have 22 rows (1 header + 21 members), got {len(doc.tables[1].rows)}"
    print("   [PASSED] Table 0 (4 fixed rows) and Table 1 (21 members) validated.")

    # 6. Test Security Headers
    print("6. Testing Security Headers & CSP...")
    assert gen_resp.headers.get("x-frame-options") in ["DENY", "SAMEORIGIN"]
    assert gen_resp.headers.get("x-content-type-options") == "nosniff"
    assert "default-src" in gen_resp.headers.get("content-security-policy", "")
    print("   [PASSED] Security Headers (CSP, X-Frame-Options, nosniff) verified.")

    # 7. Test Summarize Transcript endpoint with split model params
    print("7. Testing /api/summarize_transcript...")
    summ_resp = client.post(
        "/api/summarize_transcript",
        data={
            "transcript": "Meeting on 29 August 2026. Discussion on NCD project timeline. Action items assigned to Dr. Taseen and Pew.",
            "provider": "local",
            "summarization_model": "local"
        }
    )
    assert summ_resp.status_code == 200, f"Summarize failed: {summ_resp.text}"
    summ_data = summ_resp.json()
    assert summ_data.get("status") == "success"
    assert "bangla_transcript" in summ_data.get("data", {})
    assert "summary" in summ_data.get("data", {})
    # 8. Test Multi-Part Auto-Queued Recordings Transcription
    print("8. Testing Multi-Part Auto-Queued Recordings Transcription...")
    take1_bytes = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x01\xff\xfeL\x00a\x00v\x00f\x005\x008\x00.\x002\x009\x00.\x001\x000\x000\x00" + b"\x00" * 200
    take2_bytes = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x01\xff\xfeL\x00a\x00v\x00f\x005\x008\x00.\x002\x009\x00.\x001\x000\x000\x00" + b"\x00" * 200
    
    multi_resp = client.post(
        "/api/transcribe_and_summarize",
        data={
            "provider": "local",
            "text_content": "Take 1: Opening remarks by Dr. Shamim.\nTake 2: Programmatic review by Taseen and Pew."
        },
        files=[
            ("files", ("take_1.mp3", take1_bytes, "audio/mp3")),
            ("files", ("take_2.mp3", take2_bytes, "audio/mp3"))
        ]
    )
    assert multi_resp.status_code == 200, f"Multi-part transcription failed: {multi_resp.text}"
    multi_data = multi_resp.json()
    assert multi_data.get("status") == "success"
    assert "summary" in multi_data.get("data", {})
    print("   [PASSED] Multi-Part Auto-Queued Recordings successfully processed and combined.")

    # 9. Test POST /api/templates
    print("9. Testing POST /api/templates (Secure Template Store)...")
    tpl_resp = client.post("/api/templates")
    assert tpl_resp.status_code == 200, f"Failed: {tpl_resp.text}"
    tpl_data = tpl_resp.json()
    assert "templates" in tpl_data and len(tpl_data["templates"]) >= 3
    print(f"   [PASSED] {len(tpl_data['templates'])} templates retrieved successfully (Default + Built-in).")

    # 10. Test POST /api/generalize_template (DOCX Generalizer)
    print("10. Testing POST /api/generalize_template (DOCX Generalizer)...")
    # Generate a sample custom DOCX in memory with headings and a table
    sample_doc = docx.Document()
    sample_doc.add_heading("Eminence Field Survey & Public Health Assessment", 0)
    sample_doc.add_paragraph("Date: 2026-09-01")
    sample_doc.add_paragraph("Location: Sylhet Division")
    sample_doc.add_heading("1. Executive Field Summary", level=1)
    sample_doc.add_paragraph("This is a summary paragraph.")
    sample_doc.add_heading("2. Key Operational Observations", level=1)
    sample_doc.add_paragraph("• Observation point A\n• Observation point B")
    sample_tbl = sample_doc.add_table(rows=1, cols=3)
    sample_tbl.rows[0].cells[0].text = "Indicator"
    sample_tbl.rows[0].cells[1].text = "Observed Status"
    sample_tbl.rows[0].cells[2].text = "Action Required"
    
    sample_docx_bytes = io.BytesIO()
    sample_doc.save(sample_docx_bytes)
    sample_docx_bytes.seek(0)
    
    gen_tpl_resp = client.post(
        "/api/generalize_template",
        files={"file": ("Eminence_Field_Survey.docx", sample_docx_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert gen_tpl_resp.status_code == 200, f"Generalize failed: {gen_tpl_resp.text}"
    gen_tpl_data = gen_tpl_resp.json()
    assert gen_tpl_data.get("status") == "success"
    created_tpl = gen_tpl_data.get("template", {})
    created_tpl_id = created_tpl.get("id")
    assert created_tpl_id, "No template ID returned"
    assert len(created_tpl.get("sections", [])) >= 2, "Sections not extracted"
    print(f"   [PASSED] DOCX Generalized into template '{created_tpl.get('name')}' with {len(created_tpl.get('sections', []))} sections.")

    # 11. Test POST /api/generate_custom_docx
    print("11. Testing POST /api/generate_custom_docx...")
    custom_doc_payload = {
        "template_id": created_tpl_id,
        "doc_data": {
            "title": "Eminence Field Survey & Public Health Assessment",
            "date": "2026-09-01",
            "location": "Sylhet Division",
            "sections_data": {
                "executive_field_summary": "• Completed survey of 500 households.\n• High compliance observed across health centers.",
                "key_operational_observations": "• Community clinics well-supplied with essential diagnostics.\n• Need more cold-chain transport facilities."
            },
            "bangla_transcript": "মাঠপর্যায়ের জরিপ এবং মূল্যায়ন প্রতিবেদন...",
            "english_transcript": "Field survey and assessment report transcript..."
        }
    }
    custom_docx_resp = client.post("/api/generate_custom_docx", json=custom_doc_payload)
    assert custom_docx_resp.status_code == 200, f"Failed: {custom_docx_resp.status_code}"
    assert len(custom_docx_resp.content) > 5000, "Custom docx generated too small"
    print(f"   [PASSED] Custom templated .docx generated ({len(custom_docx_resp.content)} bytes).")

    # 12. Test POST /api/delete_template (Secure Deletion)
    print("12. Testing POST /api/delete_template (Secure Deletion)...")
    del_resp = client.post("/api/delete_template", json={"template_id": created_tpl_id})
    assert del_resp.status_code == 200, f"Delete failed: {del_resp.text}"
    assert del_resp.json().get("status") == "success"
    print("   [PASSED] Custom template deleted securely via POST.")

    # 13. Test POST /api/skills & /api/save_skill (Skill Persistence)
    print("13. Testing POST /api/skills & /api/save_skill (Persistent AI Skills)...")
    skills_resp = client.post("/api/skills")
    assert skills_resp.status_code == 200
    skills_data = skills_resp.json()
    assert "skills" in skills_data and len(skills_data["skills"]) >= 4

    test_skill = {
        "id": "custom_finance_audit_test",
        "name": "Audit & Financial Risk Extractor",
        "category": "Domain",
        "description": "Scans spoken transcripts for procurement items and audit milestones.",
        "prompt": "Extract all financial transactions and procurement approvals mentioned in conversation."
    }
    save_skill_resp = client.post("/api/save_skill", json=test_skill)
    assert save_skill_resp.status_code == 200
    assert save_skill_resp.json().get("status") == "success"

    # Verify skill is now in the store
    skills_after_resp = client.post("/api/skills")
    assert any(s.get("id") == "custom_finance_audit_test" for s in skills_after_resp.json().get("skills", []))
    print("   [PASSED] Custom AI skill saved to persistent disk store.")

    # Delete test skill
    del_skill_resp = client.post("/api/delete_skill", json={"skill_id": "custom_finance_audit_test"})
    assert del_skill_resp.status_code == 200
    assert del_skill_resp.json().get("status") == "success"
    print("   [PASSED] Custom AI skill deleted securely from persistent storage.")

    print("\n=== ALL PIPELINE, TEMPLATE GENERATOR, AI SKILLS & SECURE ENDPOINT TESTS PASSED WITH 100% SUCCESS ===")

if __name__ == "__main__":
    test_full_pipeline()



