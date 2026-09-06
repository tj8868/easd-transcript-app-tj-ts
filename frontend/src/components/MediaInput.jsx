import React, { useState } from 'react';
import axios from 'axios';
import { UploadCloud, Eye, EyeOff, Sparkles, FolderOpen, ExternalLink, Key, CheckCircle, AlertTriangle, RefreshCw, Cpu, Mic, Clipboard, Copy, Zap } from 'lucide-react';
import {
  PROVIDERS,
  detectProviderFromKey,
  getSavedKeyForProvider,
  saveKeyForProvider,
  activateProvider,
  getActiveApiDisplayName
} from '../utils/apiKeyStorage';

export const MODEL_OPTIONS_BY_PROVIDER = {
  gemini: {
    stt: [
      { value: 'gemini-3.5-flash-lite', label: 'gemini-3.5-flash-lite (⭐ Recommended - Fast Multilingual STT)' },
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
  isProcessing,
  onOpenSettings
}) {
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handlePasteClipboard = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          handleKeyChange(text.trim());
        }
      } else {
        alert('Please press Ctrl+V to paste your API key.');
      }
    } catch (err) {
      console.warn('Clipboard read error:', err);
      alert('Could not read from clipboard automatically. Please press Ctrl+V inside the API key input.');
    }
  };

  // Clipboard paste listener for instant screenshots & whiteboard snapshots
  React.useEffect(() => {
    const handlePaste = (e) => {
      if (e.clipboardData && e.clipboardData.items) {
        for (let i = 0; i < e.clipboardData.items.length; i++) {
          const item = e.clipboardData.items[i];
          if (item.type.indexOf('image') !== -1) {
            const blob = item.getAsFile();
            if (blob) {
              const pastedFile = new File([blob], `clipboard-scan-${Date.now()}.png`, { type: blob.type });
              setSelectedFile(pastedFile);
            }
            break;
          }
        }
      }
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [setSelectedFile]);

  const handleKeyChange = (keyVal) => {
    const val = keyVal.trim();
    const detected = detectProviderFromKey(val);
    const targetProvider = detected || aiConfig.provider;

    saveKeyForProvider(targetProvider, val);

    if (detected && detected !== aiConfig.provider) {
      activateProvider(detected, setAiConfig);
    } else {
      setAiConfig((prev) => ({
        ...prev,
        apiKey: keyVal
      }));
    }
    setVerifyStatus(null);
  };

  const handleVerifyKey = async () => {
    setVerifying(true);
    setVerifyStatus(null);

    try {
      const p = aiConfig.provider || 'gemini';
      const k = aiConfig.apiKey?.trim() || getSavedKeyForProvider(p) || '';
      const u = aiConfig.baseUrl || '';
      const res = await axios.post('/api/verify_key', {
        provider: p,
        api_key: k,
        base_url: u
      });
      setVerifying(false);
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setVerifyStatus({
        valid: isValid,
        success: isValid,
        message: (res.data?.message || (isValid ? 'API connected successfully!' : 'Verification failed.')) + lat
      });
      setTimeout(() => setVerifyStatus(null), 8000);
    } catch (err) {
      setVerifying(false);
      setVerifyStatus({
        valid: false,
        success: false,
        message: err.response?.data?.detail || err.message || 'Key verification failed.'
      });
      setTimeout(() => setVerifyStatus(null), 8000);
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
    if (name.endsWith('.pdf')) {
      return { label: '📄 PDF Document (Digital / Scanned OCR)', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)' };
    }
    if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.webp') || name.endsWith('.bmp') || name.endsWith('.tiff') || name.endsWith('.tif') || name.endsWith('.heic')) {
      return { label: '📸 Scanned Photo / Whiteboard / OCR Image', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)', border: 'rgba(139, 92, 246, 0.3)' };
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
          <UploadCloud size={20} color="var(--accent-color)" /> 1. Universal Media, OCR & Document Input
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
          Upload any Video (including <strong>HEVC/H.265</strong>, iPhone <strong>MOV/ProRes</strong>), Audio, <strong>Scanned Photos & Whiteboards (OCR)</strong>, or <strong>PDFs & Documents</strong> in Bangla + English.
        </p>

        <div
          className={`drop-zone ${isDragging ? 'dragging' : ''}`}
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(true);
          }}
          onDragEnter={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
              setSelectedFile(e.dataTransfer.files[0]);
            }
          }}
          onClick={() => document.getElementById('fileInputReact').click()}
          style={{
            border: isDragging ? '2px dashed #10b981' : undefined,
            background: isDragging ? 'rgba(16, 185, 129, 0.15)' : undefined,
            boxShadow: isDragging ? '0 0 16px rgba(16, 185, 129, 0.35)' : undefined,
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <UploadCloud size={40} color={isDragging ? 'var(--accent-color)' : 'var(--accent-color)'} />
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '6px 0 2px 0' }}>
            {isDragging ? 'Drop file to upload & transcribe!' : 'Drag & Drop Any Video, Audio, Scanned Photo (OCR), or Document'}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'center', margin: '6px 0 10px 0' }}>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', fontWeight: 600, border: '1px solid rgba(139, 92, 246, 0.3)' }}>📸 Scanned Photos & OCR</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', fontWeight: 600, border: '1px solid rgba(239, 68, 68, 0.3)' }}>📄 PDF Reports</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', fontWeight: 600, border: '1px solid rgba(236, 72, 153, 0.3)' }}>iPhone MOV / M4A</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', fontWeight: 600, border: '1px solid rgba(59, 130, 246, 0.3)' }}>MP4 / MKV / WebM</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', fontWeight: 600, border: '1px solid rgba(16, 185, 129, 0.3)' }}>MP3 / WAV / FLAC</span>
            <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', fontWeight: 600, border: '1px solid rgba(245, 158, 11, 0.3)' }}>DOCX / SRT / VTT</span>
          </div>

          <label className="btn btn-primary" style={{ pointerEvents: 'none', cursor: 'pointer', marginTop: '4px' }}>
            <FolderOpen size={16} /> Choose File
          </label>

          <small style={{ display: 'block', marginTop: '8px', fontSize: '0.74rem', color: 'var(--accent-color)' }}>
            💡 Tip: Press <strong>Ctrl+V</strong> anywhere to paste a screenshot or whiteboard photo for instant OCR.
          </small>

          <input
            id="fileInputReact"
            type="file"
            accept="audio/*,video/*,image/*,.pdf,.hevc,.h265,.265,.mp4,.mkv,.mov,.qt,.prores,.avi,.webm,.flv,.wmv,.m4v,.ts,.mts,.m2ts,.3gp,.3g2,.ogv,.vob,.mxf,.rm,.rmvb,.asf,.divx,.xvid,.mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,.wma,.amr,.awb,.ac3,.eac3,.aiff,.aif,.alac,.ape,.caf,.dts,.pcm,.doc,.docx,.txt,.md,.srt,.vtt,.rtf,.csv,.tsv,.json"
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

      {/* Active AI Engine Status & Models Card */}
      <div className="card" style={{ marginBottom: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px', paddingBottom: '12px', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Cpu size={18} color="var(--accent-color)" /> Active AI Engine: {getActiveApiDisplayName(aiConfig)}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '2px 0 0 0' }}>
              Provider: <strong>{aiConfig.provider?.toUpperCase()}</strong> • By default using Gemini API (or configured custom API).
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              id="frontPageTestApiBtn"
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleVerifyKey}
              disabled={verifying}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.8rem', padding: '6px 14px', background: 'rgba(2, 132, 199, 0.08)' }}
              title="Test connection to active API engine"
            >
              <Zap size={14} color="var(--accent-color)" /> {verifying ? 'Testing API...' : '⚡ Test API'}
            </button>
            {onOpenSettings && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onOpenSettings}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.8rem', padding: '6px 12px' }}
              >
                <Key size={14} /> Configure / Switch APIs
              </button>
            )}
          </div>
        </div>

        {/* Live Test Status Alert on Front Page */}
        {verifyStatus && (
          <div style={{
            marginBottom: '14px',
            padding: '8px 14px',
            borderRadius: '8px',
            fontSize: '0.82rem',
            fontWeight: 600,
            background: verifyStatus.valid || verifyStatus.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            color: verifyStatus.valid || verifyStatus.success ? '#10b981' : '#ef4444',
            border: verifyStatus.valid || verifyStatus.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            {verifyStatus.valid || verifyStatus.success ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
            <span>{verifyStatus.message}</span>
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
