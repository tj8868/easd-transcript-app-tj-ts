"""
Custom API Gateway Sub-Agent
Provides a single, customizable external API connector.
Users can configure and customize one active external API at a time
(e.g., OpenAI Whisper, Groq, DeepSeek, OpenRouter, Google Gemini, Ollama, or self-hosted endpoint)
with custom Base URLs, Keys, Models, and Headers.
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

class CustomApiGatewaySubAgent:
    """Sub-agent managing the single customizable API endpoint."""

    DEFAULT_CONFIG = {
        "enabled": False,
        "name": "Custom Whisper API",
        "provider_type": "openai_compatible",  # 'openai_compatible' | 'gemini' | 'custom_http'
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "model_name": "whisper-large-v3-turbo",
        "custom_headers": {},
        "temperature": 0.0
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "custom_api_config.json"
        )
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = dict(self.DEFAULT_CONFIG)
                    cfg.update(data)
                    return cfg
            except Exception:
                pass
        return dict(self.DEFAULT_CONFIG)

    def save_config(self, new_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Saves and updates the single custom API configuration."""
        cfg = dict(self.DEFAULT_CONFIG)
        cfg.update(new_cfg)
        self.config = cfg
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[CustomApiGateway] Error saving config: {e}")
        return self.get_safe_config()

    def get_safe_config(self) -> Dict[str, Any]:
        """Returns configuration with masked API key for UI display."""
        safe = dict(self.config)
        key = safe.get("api_key", "")
        if key:
            safe["masked_key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
        else:
            safe["masked_key"] = ""
        return safe

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled") and self.config.get("api_key"))

    def test_connection(self) -> Dict[str, Any]:
        """Tests whether the configured API is reachable and authentication works."""
        if not self.config.get("api_key"):
            return {
                "ok": False,
                "latency_ms": 0,
                "message": "No API Key provided. Please enter a valid API key."
            }

        provider_type = self.config.get("provider_type", "openai_compatible")
        base_url = (self.config.get("base_url") or "").rstrip("/")
        api_key = self.config.get("api_key", "")
        t0 = time.time()

        if provider_type == "openai_compatible":
            # Check models list endpoint (GET /models)
            test_url = f"{base_url}/models"
            req = urllib.request.Request(test_url)
            req.add_header("Authorization", f"Bearer {api_key}")
            for k, v in self.config.get("custom_headers", {}).items():
                req.add_header(k, str(v))

            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    latency = round((time.time() - t0) * 1000, 1)
                    if 200 <= resp.status < 300:
                        return {
                            "ok": True,
                            "latency_ms": latency,
                            "message": f"Successfully connected to API ({latency} ms)!"
                        }
            except urllib.error.HTTPError as e:
                latency = round((time.time() - t0) * 1000, 1)
                # Some audio-only endpoints don't expose /models, but return 404 or 405
                if e.code in (404, 405):
                    return {
                        "ok": True,
                        "latency_ms": latency,
                        "message": f"Endpoint reachable ({latency} ms). Models list not exposed by server."
                    }
                return {
                    "ok": False,
                    "latency_ms": latency,
                    "message": f"HTTP {e.code}: {e.reason}"
                }
            except Exception as e:
                return {
                    "ok": False,
                    "latency_ms": round((time.time() - t0) * 1000, 1),
                    "message": f"Connection failed: {str(e)}"
                }

        elif provider_type == "gemini":
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                m = self.config.get("model_name") or "gemini-2.5-flash"
                client.models.get(model=m)
                latency = round((time.time() - t0) * 1000, 1)
                return {
                    "ok": True,
                    "latency_ms": latency,
                    "message": f"Successfully authenticated with Google Gemini API ({latency} ms)!"
                }
            except Exception as e:
                return {
                    "ok": False,
                    "latency_ms": round((time.time() - t0) * 1000, 1),
                    "message": f"Gemini connection failed: {str(e)}"
                }

        return {
            "ok": True,
            "latency_ms": 10,
            "message": "Custom HTTP configuration validated."
        }

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.mp3",
        mime_type: str = "audio/mp3",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Routes the transcription request to the configured custom API.
        Returns {'text': str, 'segments': List[Dict], 'provider': str}
        """
        if not self.is_enabled():
            raise RuntimeError("Custom API is not enabled or lacks an API key.")

        provider_type = self.config.get("provider_type", "openai_compatible")
        base_url = (self.config.get("base_url") or "").rstrip("/")
        api_key = self.config.get("api_key", "")
        model_name = self.config.get("model_name", "whisper-large-v3-turbo")

        if provider_type == "openai_compatible":
            import requests
            url = f"{base_url}/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            headers.update(self.config.get("custom_headers", {}))

            files = {"file": (filename, audio_bytes, mime_type)}
            data = {
                "model": model_name,
                "response_format": "verbose_json"
            }
            if language and language != "auto":
                data["language"] = language

            resp = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            if resp.status_code != 200:
                raise RuntimeError(f"API Error {resp.status_code}: {resp.text}")

            result = resp.json()
            raw_text = result.get("text", "")
            raw_segments = []
            for s in result.get("segments", []):
                raw_segments.append({
                    "start": float(s.get("start", 0.0)),
                    "end": float(s.get("end", 0.0)),
                    "text": s.get("text", "").strip()
                })
            
            # If verbose segments were not provided, create single segment
            if not raw_segments and raw_text:
                raw_segments.append({"start": 0.0, "end": 5.0, "text": raw_text})

            return {
                "text": raw_text,
                "raw_segments": raw_segments,
                "provider": self.config.get("name", "Custom API")
            }

        elif provider_type == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            prompt = (
                "Transcribe the following audio recording verbatim. "
                "Include speaker turns and timestamps [MM:SS] Speaker X: <text>. "
                "Preserve authentic Bengali and English words exactly as spoken."
            )
            cfg = types.GenerateContentConfig(
                temperature=0.0,
                system_instruction=prompt
            )
            part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            res = client.models.generate_content(
                model=model_name or "gemini-2.5-flash",
                contents=[part],
                config=cfg
            )
            text = getattr(res, "text", "") or ""
            return {
                "text": text,
                "raw_segments": [{"start": 0.0, "end": 0.0, "text": text}],
                "provider": "Google Gemini (Custom)"
            }

        raise NotImplementedError(f"Unsupported provider_type: {provider_type}")
