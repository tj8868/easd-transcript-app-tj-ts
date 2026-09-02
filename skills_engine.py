import os
import json
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills_store")
SKILLS_JSON_PATH = os.path.join(SKILLS_DIR, "skills.json")

os.makedirs(SKILLS_DIR, exist_ok=True)

PRESET_SKILLS: List[Dict[str, Any]] = [
    {
        "id": "gemini_audio",
        "name": "Gemini Multimodal Speech Transcription",
        "category": "Gemini",
        "is_builtin": True,
        "description": "High-fidelity transcription of mixed Bangla + English speech directly from audio/video binaries.",
        "prompt": "Transcribe spoken Bangla phonetics and code-switched English terms with verbatim accuracy."
    },
    {
        "id": "claude_action_items",
        "name": "Claude Action Item & Deadline Extractor",
        "category": "Claude",
        "is_builtin": True,
        "description": "Deep reasoning to extract specific task assignments, responsible owners, and target deadlines.",
        "prompt": "Extract each action item in the format: • [Task Description] - Assigned to: [Name] (Deadline: [Date/Time])."
    },
    {
        "id": "bangla_standardizer",
        "name": "Eminence Bengali Terminology Standardizer",
        "category": "Language",
        "is_builtin": True,
        "description": "Converts spoken Banglish phrases into natural, formal Bengali grammar while retaining organizational acronyms.",
        "prompt": "Ensure Bangla transcript uses formal Bengali script while keeping technical acronyms (e.g. EASD, Eminence, DOHS, NCDs, WASH) intact."
    },
    {
        "id": "executive_summary",
        "name": "Executive Decisions Synthesizer",
        "category": "Analysis",
        "is_builtin": True,
        "description": "Distills multi-hour discussions into concise, bulleted strategic outcomes.",
        "prompt": "Synthesize meeting decisions into crisp, high-impact executive summary points."
    }
]

def load_saved_skills() -> List[Dict[str, Any]]:
    """Loads all skills (presets + user custom skills saved on disk)."""
    if os.path.exists(SKILLS_JSON_PATH):
        try:
            with open(SKILLS_JSON_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
                if isinstance(stored, list):
                    stored_ids = {s.get("id") for s in stored}
                    combined = list(stored)
                    for p in PRESET_SKILLS:
                        if p["id"] not in stored_ids:
                            combined.insert(0, p)
                    return combined
        except Exception as e:
            print(f"[Skills Load Warning] {e}")
            
    return list(PRESET_SKILLS)

def save_skills_to_disk(skills: List[Dict[str, Any]]):
    """Saves skills list to skills.json."""
    try:
        with open(SKILLS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(skills, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Skills Save Error] {e}")

def save_custom_skill(skill_data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves or updates a custom skill on disk."""
    all_s = load_saved_skills()
    s_id = skill_data.get("id")
    if not s_id:
        import uuid
        s_id = f"custom_{uuid.uuid4().hex[:8]}"
        skill_data["id"] = s_id
        
    updated = False
    for idx, s in enumerate(all_s):
        if s.get("id") == s_id:
            all_s[idx] = skill_data
            updated = True
            break
    if not updated:
        all_s.append(skill_data)
        
    save_skills_to_disk(all_s)
    return skill_data

def delete_custom_skill(skill_id: str) -> bool:
    """Deletes a custom skill from disk (presets are protected)."""
    all_s = load_saved_skills()
    target = None
    for s in all_s:
        if s.get("id") == skill_id:
            if s.get("is_builtin"):
                return False  # Protect built-ins
            target = s
            break
            
    if target:
        filtered = [s for s in all_s if s.get("id") != skill_id]
        save_skills_to_disk(filtered)
        return True
    return False
