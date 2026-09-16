export const MODEL_OPTIONS_BY_PROVIDER = {
  gemini: {
    stt: [
      { value: 'gemini-3.5-transcribe', label: 'gemini-3.5-transcribe (⭐ Recommended - Gemini Audio STT)' },
      { value: 'gemini-3.5-transcribe-live', label: 'gemini-3.5-transcribe-live (Live Streaming Audio STT)' },
      { value: 'gemini-3.5-live-translate-preview', label: 'gemini-3.5-live-translate-preview (Live Speech Translation)' },
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (Fast Multimodal Audio STT)' },
      { value: 'gemini-3.7-flash', label: 'gemini-3.7-flash (Deep Multimodal Audio STT)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'gemini-3.7-flash', label: 'gemini-3.7-flash (⭐ Recommended - GA Flash Synthesis)' },
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (Fast Low-Latency Synthesis)' },
      { value: 'gemini-3.6-flash', label: 'gemini-3.6-flash (Balanced Multimodal)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  whisperx: {
    stt: [
      { value: 'pyannote/speaker-diarization-community-1', label: 'pyannote/speaker-diarization-community-1 (⭐ Hugging Face Diarization)' },
      { value: 'pyannote/speaker-diarization-3.1', label: 'pyannote/speaker-diarization-3.1 (Pyannote 3.1 Neural Diarization)' },
      { value: 'whisperx-small', label: 'WhisperX Small + Alignment + Diarization' },
      { value: 'whisperx-large-v3', label: 'WhisperX Large v3 + Alignment + Diarization' },
      { value: 'custom', label: '✏️ Type Custom Diarization Pipeline...' }
    ],
    llm: [
      { value: 'gemini-3.7-flash', label: 'gemini-3.7-flash (⭐ Recommended LLM Synthesis)' },
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (Fast Synthesis)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  groq: {
    stt: [
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (⭐ Recommended - 216x Real-Time)' },
      { value: 'whisper-large-v3', label: 'whisper-large-v3 (High-Fidelity Multilingual Whisper)' },
      { value: 'distil-whisper-large-v3-en', label: 'distil-whisper-large-v3-en (Fast English Only)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'openai/gpt-oss-120b', label: 'openai/gpt-oss-120b (⭐ Recommended - 120B Executive Synthesizer)' },
      { value: 'llama-3.3-70b-versatile', label: 'llama-3.3-70b-versatile (Meta Llama 3.3 70B)' },
      { value: 'llama-3.1-8b-instant', label: 'llama-3.1-8b-instant (Instant Low-Latency 8B)' },
      { value: 'mixtral-8x7b-32768', label: 'mixtral-8x7b-32768 (32K MoE Long Context)' },
      { value: 'qwen-2.5-32b', label: 'qwen-2.5-32b (Bilingual Bangla/English Reasoning)' },
      { value: 'deepseek-r1-distill-llama-70b', label: 'deepseek-r1-distill-llama-70b (Deep Analytical Reasoning)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  openai: {
    stt: [
      { value: 'whisper-1', label: 'whisper-1 (OpenAI Cloud Speech-to-Text)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'gpt-4o', label: 'gpt-4o (Omni High-Reasoning Synthesis)' },
      { value: 'gpt-4o-mini', label: 'gpt-4o-mini (Fast Efficient Synthesis)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  anthropic: {
    stt: [
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (Via Groq Cloud STT Bridge)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'claude-3-7-sonnet-latest', label: 'claude-3-7-sonnet-latest (⭐ Hybrid Reasoning & Synthesis)' },
      { value: 'claude-3-5-sonnet-20241022', label: 'claude-3-5-sonnet (High Precision Executive Minutes)' },
      { value: 'claude-3-5-haiku-20241022', label: 'claude-3-5-haiku (Lightning-Fast Synthesis)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  custom: {
    stt: [
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (OpenAI / VLLM / Ollama Spec)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'custom-model', label: 'Self-Hosted / Proxy Model (Local / Enterprise Endpoint)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  }
};
