# Universal Standalone Transcription Module

A modular, cross-platform Speech-to-Text (ASR) system cloned and isolated from the EASD application. Built specifically for **Bangla (বাংলা) & English bilingual speech** with native speaker diarization and timestamps.

---

## 🏛️ Architecture: Hierarchical Sub-Agents

This module implements a **Hierarchical Orchestrator-Worker Sub-Agents Architecture**, selected to maximize efficiency and avoid memory thrashing on resource-constrained systems (such as dual-core Intel i3 with limited RAM) while retaining modularity.

```
┌───────────────────────────────────────────────────────────────┐
│               Transcription Orchestrator                      │
│            (Central Lifecycle & Routing Brain)                │
└───────┬──────────────┬──────────────┬──────────────┬──────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│  Hardware    ││ Local Whisper││ Speaker      ││ Custom API   │
│  Profiler    ││ Worker       ││ Diarization  ││ Gateway      │
│  Sub-Agent   ││ Sub-Agent    ││ Sub-Agent    ││ Sub-Agent    │
│(INT8 vs Turbo││(Lazy load/VAD││([MM:SS] Spk X││(Single custom│
│ auto-detect) ││ bilingual)   ││ SRT/VTT/TXT) ││ endpoint)    │
└──────────────┘└──────┬───────┘└──────────────┘└──────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│Live Stream Worker│       │ Batch Processor  │
│    Sub-Agent     │       │    Sub-Agent     │
│ (Record Button)  │       │ (Upload Button)  │
└──────────────────┘       └──────────────────┘
```

### Specialized Sub-Agents:
1. **`HardwareProfilerSubAgent` (`subagents/hardware_profiler.py`)**:
   - Assesses CPU logical cores, total/free RAM, and GPU accelerators (CUDA, Metal, Vulkan).
   - Dynamically selects **Faster-Whisper INT8** for low-end/resource-limited PCs or **Whisper-Large-v3-Turbo** for modern multi-core/GPU systems.
2. **`WhisperWorkerSubAgent` (`subagents/whisper_worker.py`)**:
   - Manages local faster-whisper CTranslate2 models with quantization, thread locking, and Silero VAD silence filtering.
   - Steers bilingual Bangla-English transcription using pre-conditioned token prompting.
3. **`DiarizationWorkerSubAgent` (`subagents/diarization_worker.py`)**:
   - Always enabled. Computes conversational turn shifts based on acoustic pauses (>1.6s).
   - Formats every utterance into `[MM:SS] Speaker X: <text>`.
   - Generates SRT, WebVTT, formatted Text, and structured JSON exports.
4. **`CustomApiGatewaySubAgent` (`subagents/custom_api_gateway.py`)**:
   - Manages the single customizable API connection (OpenAI-compatible, Groq, DeepSeek, OpenRouter, Google Gemini, Ollama, or vLLM).
   - Allows users to test connection latency, configure custom headers, and override local Whisper.
5. **`LiveStreamWorkerSubAgent` (`subagents/live_stream_worker.py`)**:
   - Dedicated engine for the **Record Button** (micro-chunking, real-time waveform visualizer, low-latency greedy inference).
6. **`BatchProcessorSubAgent` (`subagents/batch_processor.py`)**:
   - Dedicated engine for the **Upload Button** (FFmpeg media conversion, multi-file queue, progress tracking from 0% to 100%).

---

## ⚡ Key Features

| Feature | Details |
| :--- | :--- |
| **Default Mode** | **Auto-detect**: If system is low-end (<8GB RAM or <=4 CPU threads without discrete GPU), it runs `faster-whisper-int8`. Otherwise, runs `whisper-large-v3-turbo`. Can also be manually toggled. |
| **🎙️ Live Record** | Instant live microphone recording with interactive waveform visualizer and real-time timestamped transcript feed. |
| **📁 Batch Processing** | Drag & drop audio/video upload (MP3, WAV, M4A, FLAC, OGG, MP4, MKV, MOV, WEBM) with queue progress tracking. |
| **👥 Diarization & Timestamps** | Fully enabled on all outputs: `[MM:SS] Speaker 1: <text>` with exports to `.txt`, `.srt`, `.vtt`, and `.json`. |
| **🔌 Single Custom API** | One customizable API connector that can be configured, tested with live latency probe, and updated anytime. |

---

## 🚀 How to Run

### Linux / macOS:
```bash
cd "Transcription Module"
./launch.sh
```

### Windows:
Double-click `launch.bat` or run:
```cmd
cd "Transcription Module"
launch.bat
```

### Direct Python:
```bash
cd "Transcription Module"
python3 app.py
```
Open **`http://127.0.0.1:8085`** in any web browser.

---

## 📡 API Endpoints

- `GET /api/status` - Returns hardware diagnostic profile, recommended engine, and active state.
- `POST /api/settings` - Updates engine mode (`auto`, `faster-whisper-int8`, `whisper-turbo`) and language.
- `GET /api/custom_api` - Fetches single custom API configuration (masked key).
- `POST /api/custom_api` - Updates single custom API settings.
- `POST /api/custom_api/test` - Tests custom API connection and reports latency.
- `POST /api/live/chunk` - Ingests live microphone audio chunks.
- `POST /api/live/stop` - Finalizes live recording and exports formatted transcript.
- `WebSocket /ws/live` - Real-time bidirectional streaming audio endpoint.
- `POST /api/batch/upload` - Uploads media files for batch queue processing.
- `GET /api/batch/status/{job_id}` - Checks batch job progress and retrieves results.
