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
      { value: 'auto', label: 'Automatic (BengaliAI Bangla model; large-v3-turbo on NVIDIA GPU)' },
      { value: 'whisper-bengaliai', label: 'BengaliAI Whisper (Bangla, Bengali script)' },
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (NVIDIA GPU)' }
    ],
    llm: [
      { value: 'local_synthesis', label: 'Deep Semantic Synthesis (100% Offline Built-in Engine)' }
    ]
  }
};
