export const MODEL_OPTIONS_BY_PROVIDER = {
  gemini: {
    stt: [
      { value: 'gemini-3.5-transcribe', label: 'gemini-3.5-transcribe (Default - Verbatim Audio STT)' },
      { value: 'gemini-3.5-transcribe-live', label: 'gemini-3.5-transcribe-live (Live Streaming Audio STT)' }
    ],
    llm: [
      { value: 'gemini-3.8-flash', label: 'gemini-3.8-flash (Executive Meeting Minutes Synthesis)' }
    ]
  },
  local_whisper: {
    stt: [
      { value: 'auto', label: 'auto (Hardware Adaptive: Auto-sizes based on system RAM)' },
      { value: 'whisper-small', label: 'whisper-small (Standard Balance - 8-16 GB RAM)' },
      { value: 'whisper-medium', label: 'whisper-medium (Highest Precision - 16+ GB RAM)' },
      { value: 'whisper-base', label: 'whisper-base (Fast Lightweight - 4-8 GB RAM)' },
      { value: 'whisper-tiny', label: 'whisper-tiny (Ultra-Fast Minimal - <= 4 GB RAM)' }
    ],
    llm: [
      { value: 'local_synthesis', label: 'Deep Semantic Synthesis (100% Offline Built-in Engine)' }
    ]
  }
};
