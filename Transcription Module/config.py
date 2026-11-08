"""
Configuration Manager for the Transcription Module.
Handles settings persistence and runtime defaults.
"""

import os
import json
from typing import Dict, Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_BASE_DIR, "transcription_settings.json")

DEFAULT_SETTINGS = {
    "default_mode": "auto",  # 'auto' | 'faster-whisper-int8' | 'whisper-turbo' | 'custom_api'
    "default_model": "auto",
    "language": "auto",
    "enable_diarization": True,
    "enable_timestamps": True,
    "server_host": "127.0.0.1",
    "server_port": 8085
}

def load_settings() -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"[Config] Error reading {CONFIG_FILE}: {e}")
    return settings

def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    settings = load_settings()
    settings.update(new_settings)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[Config] Error writing {CONFIG_FILE}: {e}")
    return settings
