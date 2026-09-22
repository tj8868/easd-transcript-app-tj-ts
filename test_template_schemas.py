import json
import jsonschema
import template_engine
import ai_providers

def run_all_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE TEMPLATE JSON SCHEMA TEST SUITE")
    print("=" * 60)

    templates = template_engine.DEFAULT_TEMPLATES
    print(f"Total Default Templates: {len(templates)}")

    for t in templates:
        t_id = t["id"]
        doc_type = t.get("doc_type")
        name = t.get("name")
        print(f"\n[Testing Template: '{name}' ({t_id} / {doc_type})]")

        # 1. Schema Generation
        schema = template_engine.get_template_json_schema(t)
        assert schema is not None, f"Schema is None for {t_id}"
        assert schema.get("$schema") == "http://json-schema.org/draft-07/schema#", f"Invalid $schema for {t_id}"
        assert "properties" in schema, f"Missing properties in schema for {t_id}"
        assert "summary" in schema["properties"], f"Missing summary in schema for {t_id}"
        print(f"  [PASS] Valid Draft-07 Schema generated (title: '{schema.get('title')}')")

        # 2. Example Generation & Validation against Schema
        example = template_engine.get_template_json_example(t)
        assert example is not None, f"Example is None for {t_id}"
        assert "detected_language" in example, f"Missing detected_language in example for {t_id}"
        assert "summary" in example, f"Missing summary in example for {t_id}"

        # Strict JSON Schema validation
        try:
            jsonschema.validate(instance=example, schema=schema)
            print(f"  [PASS] Example payload strictly validated against JSON Schema via jsonschema.validate()")
        except jsonschema.ValidationError as ve:
            print(f"  [FAIL] Schema Validation Error for {t_id}: {ve.message}")
            raise ve

        # 3. System Prompt Construction
        prompt = ai_providers.build_template_system_prompt(t)
        assert t.get("context", "") in prompt, f"Context missing in prompt for {t_id}"
        assert t.get("rules", "") in prompt, f"Rules missing in prompt for {t_id}"
        assert "CRITICAL JSON OUTPUT DIRECTIVE" in prompt, f"JSON output directive missing for {t_id}"
        assert "EXACT OUTPUT JSON STRUCTURE & ILLUSTRATIVE EXAMPLE" in prompt, f"JSON example missing for {t_id}"
        assert "• " in prompt, f"Bullet directive missing in prompt for {t_id}"
        print(f"  [PASS] System prompt built ({len(prompt)} chars) with embedded JSON schema & example")

        # 4. Payload Parsing
        raw_json_str = json.dumps(example, ensure_ascii=False)
        extracted = ai_providers.process_extracted_payload(
            raw_text=raw_json_str,
            fallback_content="Raw meeting discussion",
            template_schema=t
        )
        assert extracted is not None, f"Failed to extract payload for {t_id}"
        summary = extracted.get("summary", {})
        assert summary, f"Empty summary for {t_id}"
        assert "sections_data" in summary, f"sections_data missing in summary for {t_id}"
        assert "tables_data" in summary, f"tables_data missing in summary for {t_id}"
        print(f"  [PASS] Payload parser extracted {len(summary)} fields/sections/tables into summary")

        # 5. Offline Deep Semantic Synthesis
        fallback = ai_providers.deep_semantic_synthesis(
            raw_text="The meeting was convened to review public health initiatives and project milestones.",
            template_schema=t
        )
        fb_summary = fallback.get("summary", {})
        assert fb_summary, f"Empty fallback summary for {t_id}"
        assert "sections_data" in fb_summary, f"sections_data missing in fallback summary for {t_id}"
        print(f"  [PASS] Offline Deep Semantic Synthesis successfully populated template structure")

        # 6. DOCX Generation Test
        docx_bytes = template_engine.generate_custom_template_docx_bytes(t, summary)
        assert len(docx_bytes) > 1000, f"DOCX generation output too small ({len(docx_bytes)} bytes) for {t_id}"
        print(f"  [PASS] DOCX generated successfully ({len(docx_bytes)} bytes)")

    print("\n" + "=" * 60)
    print("ALL 5 DEFAULT TEMPLATES VALIDATED 100% SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
