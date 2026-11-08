"""
Hierarchical Transcription Orchestrator
Central Brain coordinating all worker sub-agents:
- HardwareProfilerSubAgent: Assesses PC resources (auto-selects INT8 vs Turbo)
- WhisperWorkerSubAgent: Local ASR engine
- LiveStreamWorkerSubAgent: Real-time record studio
- BatchProcessorSubAgent: Audio/video file uploads
- DiarizationWorkerSubAgent: Speaker tags & timestamps
- CustomApiGatewaySubAgent: Single customizable API integration
"""

import os
from typing import Dict, Any, Optional
try:
    from .config import load_settings, save_settings
    from .subagents.hardware_profiler import HardwareProfilerSubAgent
    from .subagents.diarization_worker import DiarizationWorkerSubAgent
    from .subagents.custom_api_gateway import CustomApiGatewaySubAgent
    from .subagents.whisper_worker import WhisperWorkerSubAgent
    from .subagents.live_stream_worker import LiveStreamWorkerSubAgent
    from .subagents.batch_processor import BatchProcessorSubAgent
except (ImportError, ValueError):
    from config import load_settings, save_settings
    from subagents.hardware_profiler import HardwareProfilerSubAgent
    from subagents.diarization_worker import DiarizationWorkerSubAgent
    from subagents.custom_api_gateway import CustomApiGatewaySubAgent
    from subagents.whisper_worker import WhisperWorkerSubAgent
    from subagents.live_stream_worker import LiveStreamWorkerSubAgent
    from subagents.batch_processor import BatchProcessorSubAgent

class TranscriptionOrchestrator:
    """Master controller managing the transcription pipeline and sub-agents."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        print("[Orchestrator] Initializing Hierarchical Transcription Sub-Agents...")
        self.settings = load_settings()

        # 1. Initialize Hardware Profiler Sub-Agent
        self.hardware_subagent = HardwareProfilerSubAgent()
        self.hw_profile = self.hardware_subagent.get_profile()

        # 2. Initialize Speaker Diarization Sub-Agent (always enabled)
        self.diarization_subagent = DiarizationWorkerSubAgent()

        # 3. Initialize Single Custom API Gateway Sub-Agent
        self.custom_api_subagent = CustomApiGatewaySubAgent()

        # 4. Initialize Local Whisper Worker Sub-Agent
        self.whisper_subagent = WhisperWorkerSubAgent(self.hw_profile)

        # 5. Initialize Live Stream Worker Sub-Agent (Record Button)
        self.live_stream_subagent = LiveStreamWorkerSubAgent(
            whisper_worker=self.whisper_subagent,
            custom_api_gateway=self.custom_api_subagent,
            diarizer=self.diarization_subagent
        )

        # 6. Initialize Batch Processor Sub-Agent (Upload Button)
        self.batch_processor_subagent = BatchProcessorSubAgent(
            whisper_worker=self.whisper_subagent,
            custom_api_gateway=self.custom_api_subagent,
            diarizer=self.diarization_subagent
        )

        print("[Orchestrator] All sub-agents successfully assembled and ready.")

    def get_system_status(self) -> Dict[str, Any]:
        """Provides full status of hardware, active mode, diarization, and custom API."""
        mode = self.settings.get("default_mode", "auto")
        
        # Determine actual active engine
        if self.custom_api_subagent.is_enabled():
            active_engine = f"Custom API ({self.custom_api_subagent.config.get('name')})"
        elif mode == "whisper-turbo":
            active_engine = "Whisper-Large-v3-Turbo (Forced)"
        elif mode == "faster-whisper-int8":
            active_engine = "Faster-Whisper INT8 (Forced)"
        else:
            # Auto based on specs
            rec = self.hw_profile.get("recommended_engine", "faster-whisper-int8")
            active_engine = f"{rec.upper()} (Auto-Detected)"

        return {
            "status": "ready",
            "hardware": self.hw_profile,
            "settings": self.settings,
            "active_engine": active_engine,
            "speaker_diarization": "Enabled ([MM:SS] Speaker X: ...)",
            "timestamps": "Enabled",
            "custom_api": self.custom_api_subagent.get_safe_config()
        }

    # --- Live Recording Controls (Record Button) ---
    def start_live_session(self, session_id: str, language: str = "auto") -> Dict[str, Any]:
        return self.live_stream_subagent.start_session(session_id, language=language)

    def process_live_chunk(self, session_id: str, audio_bytes: bytes, mime_type: str = "audio/webm", is_final: bool = False) -> Dict[str, Any]:
        return self.live_stream_subagent.process_live_chunk(session_id, audio_bytes, mime_type=mime_type, is_final=is_final)

    def stop_live_session(self, session_id: str) -> Dict[str, Any]:
        return self.live_stream_subagent.stop_session(session_id)

    # --- Batch Processing Controls (Upload Button) ---
    def process_batch_upload(self, job_id: str, file_path: str, original_filename: str, language: str = "auto") -> Dict[str, Any]:
        return self.batch_processor_subagent.process_file(job_id, file_path, original_filename, language=language)

    def get_batch_job_status(self, job_id: str) -> Dict[str, Any]:
        return self.batch_processor_subagent.get_job_status(job_id)

    # --- Single Custom API Controls ---
    def get_custom_api_config(self) -> Dict[str, Any]:
        return self.custom_api_subagent.get_safe_config()

    def update_custom_api_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        return self.custom_api_subagent.save_config(new_config)

    def test_custom_api(self) -> Dict[str, Any]:
        return self.custom_api_subagent.test_connection()
