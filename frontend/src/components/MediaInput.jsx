import React, { useState } from 'react';
import axios from 'axios';
import { UploadCloud, Eye, EyeOff, Sparkles, FolderOpen, ExternalLink, Key, CheckCircle, AlertTriangle, RefreshCw, Cpu, Mic } from 'lucide-react';

export const MODEL_OPTIONS_BY_PROVIDER = {
  gemini: {
    stt: [
      { value: 'gemini-2.5-flash', label: 'gemini-2.5-flash (⭐ Recommended - Fast Multilingual STT)' },
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (Ultra Fast & Lightweight STT)' },
      { value: 'gemini-3.7-flash', label: 'gemini-3.7-flash (Advanced Reasoning & Audio STT)' },
      { value: 'gemini-2.5-pro', label: 'gemini-2.5-pro (Deep Multimodal Audio Understanding)' },
      { value: 'gemini-3.1-pro-preview', label: 'gemini-3.1-pro-preview (Next-Gen Gemini Pro)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (⭐ Recommended - High Speed Synthesis)' },
      { value: 'gemini-2.5-flash', label: 'gemini-2.5-flash (Balanced Speed & Quality)' },
      { value: 'gemini-3.7-flash', label: 'gemini-3.7-flash (Advanced Multilingual Executive Reports)' },
      { value: 'gemini-2.5-pro', label: 'gemini-2.5-pro (Comprehensive Institutional Briefs)' },
      { value: 'gemini-3.1-pro-preview', label: 'gemini-3.1-pro-preview (Deep Executive Reasoning)' },
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
      { value: 'whisper-1', label: 'whisper-1 (⭐ Official OpenAI Whisper STT)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'gpt-4o', label: 'gpt-4o (⭐ Recommended - Flagship Omnimodal)' },
      { value: 'gpt-4o-mini', label: 'gpt-4o-mini (Fast & Cost-Efficient)' },
      { value: 'o1-mini', label: 'o1-mini (Deep Scientific Reasoning)' },
      { value: 'o3-mini', label: 'o3-mini (High-Speed Reasoning Engine)' },
      { value: 'gpt-4-turbo', label: 'gpt-4-turbo (High-Capacity GPT-4)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  anthropic: {
    stt: [
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (Gemini Multilingual Audio STT)' },
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (Groq High-Speed Whisper STT)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'claude-3-5-sonnet-20241022', label: 'claude-3-5-sonnet-20241022 (⭐ Recommended - Top Executive Prose)' },
      { value: 'claude-3-5-haiku-20241022', label: 'claude-3-5-haiku-20241022 (Ultra-Fast Responsive Haiku)' },
      { value: 'claude-3-opus-20240229', label: 'claude-3-opus-20240229 (Deep Analytical Reports)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  },
  custom: {
    stt: [
      { value: 'whisper-large-v3-turbo', label: 'whisper-large-v3-turbo (Groq / vLLM Whisper)' },
      { value: 'whisper-1', label: 'whisper-1 (OpenAI Compatible Whisper)' },
      { value: 'custom', label: '✏️ Type Custom STT Model...' }
    ],
    llm: [
      { value: 'llama3.3:70b', label: 'llama3.3:70b (Ollama Local 70B)' },
      { value: 'qwen2.5:32b', label: 'qwen2.5:32b (Ollama / vLLM Bilingual)' },
      { value: 'deepseek-r1:32b', label: 'deepseek-r1:32b (Ollama Reasoning)' },
      { value: 'openai/gpt-oss-120b', label: 'openai/gpt-oss-120b (Groq / OpenRouter 120B)' },
      { value: 'custom', label: '✏️ Type Custom LLM Model...' }
    ]
  }
};

export default function MediaInput({
  selectedFile,
  setSelectedFile,
  directText,
  setDirectText,
  aiConfig,
  setAiConfig,
  templates,
  activeTemplateId,
  onSelectTemplate,
  onProcessAi,
  isProcessing
}) {
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleKeyChange = (keyVal) => {
    const val = keyVal.trim();
    let newProvider = aiConfig.provider;
    let newSTT = aiConfig.transcriptionModel;
    let newLLM = aiConfig.summarizationModel;
    let newBaseUrl = aiConfig.baseUrl;

    if (val.startsWith('gsk_')) {
      newProvider = 'groq';
      newBaseUrl = 'https://api.groq.com/openai/v1';
      newSTT = 'whisper-large-v3-turbo';
      newLLM = 'openai/gpt-oss-120b';
    } else if (val.startsWith('AIzaSy') || val.startsWith('AQ.')) {
      newProvider = 'gemini';
      newSTT = 'gemini-3.5-flash-lite';
      newLLM = 'gemini-3.5-flash-lite';
    } else if (val.startsWith('sk-ant-')) {
      newProvider = 'anthropic';
      newLLM = 'claude-3-5-sonnet-20241022';
      newSTT = 'gemini-3.5-flash-lite';
    } else if (val.startsWith('sk-proj-') || (val.startsWith('sk-') && !val.startsWith('sk-ant-'))) {
      newProvider = 'openai';
      newSTT = 'whisper-1';
      newLLM = 'gpt-4o';
    }

    setVerifyStatus(null);
    setAiConfig({
      ...aiConfig,
      apiKey: keyVal,
      provider: newProvider,
      transcriptionModel: newSTT,
      summarizationModel: newLLM,
      modelName: newLLM,
      baseUrl: newBaseUrl
    });
  };

  const handleVerifyKey = async () => {
    if (!aiConfig.apiKey.trim()) {
      setVerifyStatus({ valid: false, message: 'Please enter an API Key first.' });
      return;
    }
    setVerifying(true);
    setVerifyStatus(null);

    try {
      const res = await axios.post('/api/verify_key', {
        provider: aiConfig.provider,
        api_key: aiConfig.apiKey.trim(),
        base_url: aiConfig.baseUrl.trim()
      });
      setVerifying(false);
      setVerifyStatus(res.data);
    } catch (err) {
      setVerifying(false);
      setVerifyStatus({ valid: false, message: 'Key verification failed.' });
    }
  };

  const getKeyLink = () => {
    if (aiConfig.provider === 'groq') return 'https://console.groq.com/keys';
    if (aiConfig.provider === 'gemini') return 'https://aistudio.google.com/app/apikey';
    if (aiConfig.provider === 'openai') return 'https://platform.openai.com/api-keys';
    if (aiConfig.provider === 'anthropic') return 'https://console.anthropic.com/';
    if (aiConfig.provider === 'custom') return 'https://console.groq.com/keys';
    return 'https://console.groq.com/keys';
  };

  const isGroqKey = aiConfig.apiKey.trim().startsWith('gsk_') || aiConfig.provider === 'groq';
  const isGeminiKey = aiConfig.apiKey.trim().startsWith('AIzaSy') || aiConfig.apiKey.trim().startsWith('AQ.') || aiConfig.provider === 'gemini';

  const getFileFormatBadge = (file) => {
    if (!file) return null;
    const name = file.name.toLowerCase();
    if (name.endsWith('.hevc') || name.endsWith('.h265') || name.endsWith('.265')) {
      return { label: 'HEVC / H.265 High-Efficiency Video', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)', border: 'rgba(139, 92, 246, 0.3)' };
    }
    if (name.endsWith('.mov') || name.endsWith('.qt') || name.endsWith('.prores')) {
      return { label: 'Apple / iPhone Video (MOV / ProRes)', color: '#ec4899', bg: 'rgba(236, 72, 153, 0.15)', border: 'rgba(236, 72, 153, 0.3)' };
    }
    if (name.endsWith('.m4a') || name.endsWith('.aac') || name.endsWith('.alac') || name.endsWith('.caf') || name.endsWith('.aif') || name.endsWith('.aiff')) {
      return { label: 'Apple / iPhone Voice Memo & Audio (M4A / AAC / ALAC)', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)', border: 'rgba(6, 182, 212, 0.3)' };
    }
    if (name.endsWith('.mp4') || name.endsWith('.m4v')) {
      return { label: 'MP4 / H.264 / HEVC Video', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)', border: 'rgba(59, 130, 246, 0.3)' };
    }
    if (name.endsWith('.mkv')) {
      return { label: 'MKV Video Container', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)', border: 'rgba(6, 182, 212, 0.3)' };
    }
    if (name.endsWith('.webm') || name.endsWith('.avi') || name.endsWith('.flv') || name.endsWith('.wmv') || name.endsWith('.ts') || name.endsWith('.mts') || name.endsWith('.m2ts') || name.endsWith('.3gp') || name.endsWith('.3g2')) {
      return { label: 'Video Recording Stream', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.3)' };
    }
    if (name.endsWith('.mp3') || name.endsWith('.wav') || name.endsWith('.ogg') || name.endsWith('.opus') || name.endsWith('.flac') || name.endsWith('.amr') || name.endsWith('.awb') || name.endsWith('.wma') || name.endsWith('.ac3') || name.endsWith('.pcm')) {
      return { label: 'Speech Audio Recording', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.3)' };
    }
    if (name.endsWith('.docx') || name.endsWith('.doc')) {
      return { label: 'Word Document (DOCX)', color: '#2563eb', bg: 'rgba(37, 99, 235, 0.15)', border: 'rgba(37, 99, 235, 0.3)' };
    }
    if (name.endsWith('.srt') || name.endsWith('.vtt')) {
      return { label: 'Subtitle / Transcript File', color: '#14b8a6', bg: 'rgba(20, 184, 166, 0.15)', border: 'rgba(20, 184, 166, 0.3)' };
    }
    return { label: 'Media / Text', color: 'var(--accent-color)', bg: 'rgba(14, 165, 233, 0.15)', border: 'rgba(14, 165, 233, 0.3)' };
  };

  const fileBadge = getFileFormatBadge(selectedFile);

  return (
    <div className="grid-2col" id="section-input" style={{ marginBottom: '24px' }}>
      {/* File Input Card */}
      <div className="card" style={{ marginBottom: 0 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <UploadCloud size={20} color="var(--accent-color)" /> 1. Universal Media & Document Input
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
          Upload any Video (including <strong>HEVC / H.265</strong>, iPhone <strong>MOV / ProRes</strong>, MP4, MKV, TS), iPhone <strong>Voice Memos (M4A/AAC/ALAC)</strong>, Audio, or Document in Bangla + English.
        </p>

        <div className="drop-zone" onClick={() => document.getElementById('fileInputReact').click()}>
          <UploadCloud size={40} color="var(--accent-color)" />
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '6px 0 2px 0' }}>
            Drag & Drop Any Video, iPhone Recording, Audio, or Document
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'center', margin: '6px 0 10px 0' }}>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', fontWeight: 600, border: '1px solid rgba(139, 92, 246, 0.3)' }}>HEVC / H.265</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', fontWeight: 600, border: '1px solid rgba(236, 72, 153, 0.3)' }}>iPhone MOV / M4A / AAC</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', fontWeight: 600, border: '1px solid rgba(59, 130, 246, 0.3)' }}>MP4 / MKV / TS / WebM</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', fontWeight: 600, border: '1px solid rgba(16, 185, 129, 0.3)' }}>MP3 / WAV / FLAC / AMR</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', fontWeight: 600, border: '1px solid rgba(245, 158, 11, 0.3)' }}>DOCX / SRT / VTT</span>
          </div>

          <label className="btn btn-primary" style={{ pointerEvents: 'none', cursor: 'pointer', marginTop: '4px' }}>
            <FolderOpen size={16} /> Choose File
          </label>

          <input
            id="fileInputReact"
            type="file"
            accept="audio/*,video/*,.hevc,.h265,.265,.mp4,.mkv,.mov,.qt,.prores,.avi,.webm,.flv,.wmv,.m4v,.ts,.mts,.m2ts,.3gp,.3g2,.ogv,.vob,.mxf,.rm,.rmvb,.asf,.divx,.xvid,.mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,.wma,.amr,.awb,.ac3,.eac3,.aiff,.aif,.alac,.ape,.caf,.dts,.pcm,.doc,.docx,.txt,.md,.srt,.vtt,.rtf,.csv,.tsv,.json"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          {selectedFile ? (
            <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)
              </span>
              {fileBadge && (
                <span style={{
                  fontSize: '0.75rem',
                  padding: '3px 8px',
                  borderRadius: '12px',
                  background: fileBadge.bg,
                  color: fileBadge.color,
                  border: `1px solid ${fileBadge.border}`,
                  fontWeight: 600
                }}>
                  {fileBadge.label}
                </span>
              )}
            </div>
          ) : (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
              No file selected (Supports up to 1GB)
            </span>
          )}
        </div>

        <div className="form-group" style={{ marginTop: '16px' }}>
          <label>Or Paste Raw Text / Transcript Directly:</label>
          <textarea
            className="form-control"
            rows="5"
            placeholder="Paste raw conversation notes, draft bullet points, or transcript here..."
            value={directText}
            onChange={(e) => setDirectText(e.target.value)}
          />
        </div>

        <button
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '10px', padding: '14px', fontSize: '1rem' }}
          onClick={onProcessAi}
          disabled={isProcessing}
        >
          <Sparkles size={18} /> {isProcessing ? 'Extracting Speech & Fitting to Template...' : '⚡ Generate Meeting minutes'}
        </button>
      </div>

      {/* AI Config Card */}
      <div className="card" style={{ marginBottom: 0 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Key size={20} color="var(--accent-color)" /> AI Provider & Dedicated Models
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
          Connect Groq, Google Gemini (Interactions API), OpenAI, Claude, Manual MCP Server, or Custom endpoints.
        </p>

        <div className="form-group">
          <label>AI Provider:</label>
          <select
            className="form-control"
            value={aiConfig.provider}
            onChange={(e) => {
              const val = e.target.value;
              let defaultSTT = 'whisper-large-v3-turbo';
              let defaultLLM = 'openai/gpt-oss-120b';
              let defaultBase = '';

              if (val === 'groq') {
                defaultSTT = 'whisper-large-v3-turbo';
                defaultLLM = 'openai/gpt-oss-120b';
                defaultBase = 'https://api.groq.com/openai/v1';
              } else if (val === 'gemini') {
                defaultSTT = 'gemini-3.5-flash-lite';
                defaultLLM = 'gemini-3.5-flash-lite';
              } else if (val === 'openai') {
                defaultSTT = 'whisper-1';
                defaultLLM = 'gpt-4o';
              } else if (val === 'anthropic') {
                defaultSTT = 'gemini-3.5-flash-lite';
                defaultLLM = 'claude-3-5-sonnet-20241022';
              } else if (val === 'mcp') {
                defaultSTT = 'mcp-stt-agent';
                defaultLLM = 'mcp-executive-agent';
                defaultBase = 'http://localhost:8000/sse';
              } else if (val === 'custom') {
                defaultSTT = 'whisper-large-v3-turbo';
                defaultLLM = 'openai/gpt-oss-120b';
              }

              setAiConfig({
                ...aiConfig,
                provider: val,
                transcriptionModel: defaultSTT,
                summarizationModel: defaultLLM,
                modelName: defaultLLM,
                baseUrl: defaultBase
              });
              setVerifyStatus(null);
            }}
          >
            <option value="groq">Groq Cloud (GPT-OSS-120B / Whisper)</option>
            <option value="gemini">Google Gemini (Gemini 3.5 Flash Lite Interactions API)</option>
            <option value="openai">OpenAI (GPT-4o / Whisper)</option>
            <option value="anthropic">Anthropic Claude</option>
            <option value="mcp">Manual MCP Server (SSE / HTTP Endpoint)</option>
            <option value="custom">Custom OpenAI-Compatible (Ollama, vLLM, OpenRouter)</option>
          </select>
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ margin: 0 }}>API Key:</label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                onClick={handleVerifyKey}
                disabled={verifying}
              >
                {verifying ? <RefreshCw size={12} className="spin" /> : <CheckCircle size={12} />} Test Key
              </button>
              <a
                href={getKeyLink()}
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--accent-color)', fontSize: '0.78rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
              >
                Get Free Key <ExternalLink size={12} />
              </a>
            </div>
          </div>

          <div style={{ position: 'relative' }}>
            <input
              type={aiConfig.showKey ? 'text' : 'password'}
              className="form-control"
              placeholder="Paste API Key here (e.g. AIzaSy... or gsk_...)"
              value={aiConfig.apiKey}
              onChange={(e) => handleKeyChange(e.target.value)}
            />
            <button
              type="button"
              style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
              onClick={() => setAiConfig({ ...aiConfig, showKey: !aiConfig.showKey })}
            >
              {aiConfig.showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Test Status Feedback */}
          {verifyStatus && (
            <div
              style={{
                marginTop: '8px',
                padding: '8px 12px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: verifyStatus.valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                border: `1px solid ${verifyStatus.valid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                color: verifyStatus.valid ? '#10b981' : '#ef4444'
              }}
            >
              {verifyStatus.valid ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
              {verifyStatus.message}
            </div>
          )}

          {/* Auto Detection Badges */}
          {!verifyStatus && isGroqKey && (
            <div style={{ marginTop: '8px', padding: '6px 12px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', color: '#10b981', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={14} /> Detected Groq Key format. Click 'Test Key' to check if active.
            </div>
          )}

          {!verifyStatus && isGeminiKey && (
            <div style={{ marginTop: '8px', padding: '6px 12px', borderRadius: '8px', background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.3)', color: '#60a5fa', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={14} /> Detected Google Gemini Key format. Click 'Test Key' to check if active.
            </div>
          )}
        </div>

        {(aiConfig.provider === 'custom' || aiConfig.provider === 'openai' || aiConfig.provider === 'mcp') && (
          <div className="form-group">
            <label>{aiConfig.provider === 'mcp' ? 'Manual MCP Server URL (SSE or HTTP):' : 'Custom Base URL:'}</label>
            <input
              type="text"
              className="form-control"
              placeholder={aiConfig.provider === 'mcp' ? 'http://localhost:8000/sse or http://127.0.0.1:3000/mcp' : 'https://api.groq.com/openai/v1 or http://localhost:11434/v1'}
              value={aiConfig.baseUrl}
              onChange={(e) => setAiConfig({ ...aiConfig, baseUrl: e.target.value })}
            />
            {aiConfig.provider === 'mcp' && (
              <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
                Connects to any running MCP Server over Server-Sent Events (SSE) or HTTP gateway.
              </small>
            )}
          </div>
        )}

        {/* Dedicated Split Model Selectors with Comprehensive Options */}
        <div className="grid-2col" style={{ gap: '12px', marginTop: '14px' }}>
          {/* STT Model Selector */}
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.82rem', fontWeight: 600 }}>
              <Mic size={14} color="var(--accent-color)" /> STT Transcription Model:
            </label>
            {(() => {
              const providerKey = aiConfig.provider || 'groq';
              const providerOptions = (MODEL_OPTIONS_BY_PROVIDER[providerKey] || MODEL_OPTIONS_BY_PROVIDER.groq).stt;
              const currentVal = aiConfig.transcriptionModel || '';
              const isKnownModel = providerOptions.some((opt) => opt.value === currentVal);
              const selectVal = isKnownModel ? currentVal : 'custom';

              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <select
                    className="form-control"
                    style={{ fontSize: '0.84rem', fontWeight: 600 }}
                    value={selectVal}
                    onChange={(e) => {
                      const chosen = e.target.value;
                      if (chosen !== 'custom') {
                        setAiConfig({ ...aiConfig, transcriptionModel: chosen });
                      } else {
                        setAiConfig({ ...aiConfig, transcriptionModel: '' });
                      }
                    }}
                  >
                    {providerOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>

                  {(!isKnownModel || selectVal === 'custom') && (
                    <input
                      type="text"
                      className="form-control"
                      style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                      value={currentVal}
                      onChange={(e) => setAiConfig({ ...aiConfig, transcriptionModel: e.target.value })}
                      placeholder="Type custom STT model ID (e.g. whisper-large-v3)..."
                    />
                  )}
                </div>
              );
            })()}
          </div>

          {/* LLM Model Selector */}
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.82rem', fontWeight: 600 }}>
              <Cpu size={14} color="var(--accent-color)" /> LLM Summarization Model:
            </label>
            {(() => {
              const providerKey = aiConfig.provider || 'groq';
              const providerOptions = (MODEL_OPTIONS_BY_PROVIDER[providerKey] || MODEL_OPTIONS_BY_PROVIDER.groq).llm;
              const currentVal = aiConfig.summarizationModel || aiConfig.modelName || '';
              const isKnownModel = providerOptions.some((opt) => opt.value === currentVal);
              const selectVal = isKnownModel ? currentVal : 'custom';

              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <select
                    className="form-control"
                    style={{ fontSize: '0.84rem', fontWeight: 600 }}
                    value={selectVal}
                    onChange={(e) => {
                      const chosen = e.target.value;
                      if (chosen !== 'custom') {
                        setAiConfig({
                          ...aiConfig,
                          summarizationModel: chosen,
                          modelName: chosen
                        });
                      } else {
                        setAiConfig({
                          ...aiConfig,
                          summarizationModel: '',
                          modelName: ''
                        });
                      }
                    }}
                  >
                    {providerOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>

                  {(!isKnownModel || selectVal === 'custom') && (
                    <input
                      type="text"
                      className="form-control"
                      style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                      value={currentVal}
                      onChange={(e) =>
                        setAiConfig({
                          ...aiConfig,
                          summarizationModel: e.target.value,
                          modelName: e.target.value
                        })
                      }
                      placeholder="Type custom LLM model ID (e.g. gemini-3.7-flash)..."
                    />
                  )}
                </div>
              );
            })()}
          </div>
        </div>

        {/* Target Document Template Selector */}
        {templates && templates.length > 0 && (
          <div className="form-group" style={{ marginTop: '14px', marginBottom: 0 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 600 }}>
              <FolderOpen size={14} color="var(--accent-color)" /> Target Document Template Format:
            </label>
            <select
              className="form-control"
              style={{ fontSize: '0.85rem', fontWeight: 600 }}
              value={activeTemplateId || 'easd_default_minutes'}
              onChange={(e) => onSelectTemplate && onSelectTemplate(e.target.value)}
            >
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name} {tpl.is_builtin ? '(Built-in)' : '(Custom DOCX)'}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
