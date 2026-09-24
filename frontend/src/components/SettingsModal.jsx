import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  X, Sliders, Type, Palette, Monitor, Check, Sparkles, Smartphone, Apple,
  Terminal, ShieldCheck, RefreshCw, AlertTriangle, CheckCircle, FileText,
  Activity, Key, Plus, Trash2, Eye, EyeOff, CheckCircle2, Copy, Clipboard,
  Zap, ChevronDown, ChevronUp, Cpu, Server, Globe, ExternalLink,
  UploadCloud, RotateCcw, Image as ImageIcon
} from 'lucide-react';
import {
  activateProvider,
  saveKeyForProvider,
  getSavedKeyForProvider,
  getSavedBaseUrlForProvider,
  getActiveApiDisplayName,
  saveServerSettings,
  PROVIDERS,
  CUSTOM_API_PRESETS
} from '../utils/apiKeyStorage';

export const ACCENT_PALETTES = [
  { id: 'cerulean', name: 'Eminence Cerulean', hex: '#0284c7', glow: 'rgba(2, 132, 199, 0.25)' },
  { id: 'govt_emerald', name: 'Govt Secretariat Emerald', hex: '#047857', glow: 'rgba(4, 120, 87, 0.25)' },
  { id: 'royal_navy', name: 'EASD Royal Navy', hex: '#004b87', glow: 'rgba(0, 75, 135, 0.25)' },
  { id: 'sunset_orange', name: 'Eminence Orange', hex: '#ea580c', glow: 'rgba(234, 88, 12, 0.25)' },
  { id: 'royal_violet', name: 'Thought Leadership Violet', hex: '#7c3aed', glow: 'rgba(124, 58, 237, 0.25)' },
  { id: 'crimson_red', name: 'Crimson Red', hex: '#dc2626', glow: 'rgba(220, 38, 38, 0.25)' }
];

const BANGLA_FONTS = [
  { id: 'nikosh', name: 'Nikosh (Official Bangladesh Govt Secretariat Standard)', fontStack: "'Nikosh', 'NikoshBAN', 'SolaimanLipi', 'Hind Siliguri', sans-serif" },
  { id: 'nikosh_ban', name: 'NikoshBAN (Govt Bilingual Standard with English Glyphs)', fontStack: "'NikoshBAN', 'Nikosh', 'Hind Siliguri', sans-serif" },
  { id: 'kalpurush', name: 'Kalpurush (Classic Standard Unicode Bangla)', fontStack: "'Kalpurush', 'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'hind_siliguri', name: 'Hind Siliguri (Modern Clean Web Bangla)', fontStack: "'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'solaiman_lipi', name: 'SolaimanLipi (Traditional Clean Typography)', fontStack: "'SolaimanLipi', 'Hind Siliguri', sans-serif" }
];

const ENGLISH_FONTS = [
  { id: 'times_new_roman', name: 'Times New Roman (Microsoft Standard Serif - Official Minutes)', fontStack: "'Times New Roman', Times, serif" },
  { id: 'calibri', name: 'Calibri (Microsoft Standard Sans-Serif - Corporate Briefs)', fontStack: "'Calibri', 'Segoe UI', Arial, sans-serif" },
  { id: 'arial', name: 'Arial (Microsoft High-Legibility Sans-Serif)', fontStack: "Arial, Helvetica, sans-serif" },
  { id: 'inter', name: 'Inter (Modern UI & Presentation Font)', fontStack: "'Inter', system-ui, sans-serif" },
  { id: 'nikosh_ban_en', name: 'NikoshBAN (Bangladesh Govt English Standard)', fontStack: "'NikoshBAN', 'Times New Roman', serif" }
];

const PLATFORM_TARGETS = [
  {
    icon: Monitor,
    title: 'Windows Portable (.exe & .bat)',
    color: '#0284c7',
    desc: 'Run `python build_windows_exe.py` to generate a standalone portable `.exe` or use `Launch_App.bat` for instant zero-dependency launch.'
  },
  {
    icon: Terminal,
    title: 'Linux (Ubuntu / Debian / AppImage / Docker)',
    color: '#f59e0b',
    desc: 'Runs natively with Python 3.11+ & Uvicorn. Packaged as a standalone Linux ELF binary via PyInstaller or self-contained Docker container.'
  },
  {
    icon: Apple,
    title: 'macOS (.app & .dmg Bundle)',
    color: '#a855f7',
    desc: 'Compiles into a native `.app` bundle using PyInstaller on macOS with WebKit native windowing (pywebview).'
  },
  {
    icon: Smartphone,
    title: 'Android (APK) & iOS (PWA / Mobile Web)',
    color: '#10b981',
    desc: 'Built as a Progressive Web App (PWA) with offline support or compiled into an Android APK via Capacitor using `build_android_apk.py`.'
  }
];

function FontOptionCard({ font, isSelected, onSelect, sampleText }) {
  return (
    <div
      onClick={() => onSelect(font.id)}
      style={{
        padding: '10px 14px',
        borderRadius: '10px',
        border: isSelected ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
        background: isSelected ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
        cursor: 'pointer',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        transition: 'all 0.2s ease'
      }}
    >
      <div>
        <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
          {font.name}
        </div>
        <div style={{ fontFamily: font.fontStack, fontSize: '0.92rem', color: 'var(--accent-color)', marginTop: '2px' }}>
          {sampleText}
        </div>
      </div>
      {isSelected && <Check size={18} color="var(--accent-color)" />}
    </div>
  );
}

function AuditMetricCard({ title, value, badgeText, badgeColor, badgeBg, subText }) {
  return (
    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>{title}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 800, color: badgeColor || 'var(--text-primary)', marginTop: '2px' }}>
        {value}
      </div>
      {badgeText ? (
        <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: '4px', background: badgeBg, color: badgeColor, fontWeight: 700 }}>
          {badgeText}
        </span>
      ) : subText ? (
        <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
          {subText}
        </span>
      ) : null}
    </div>
  );
}

export default function SettingsModal({
  isOpen,
  onClose,
  theme,
  setTheme,
  settings,
  setSettings,
  aiConfig = { provider: 'gemini', model: 'gemini-3.8-flash', apiKey: '' },
  setAiConfig = () => {},
  onOpenDeviceViewer,
  onOpenGDrive
}) {
  const [activeTab, setActiveTab] = useState('keys');
  const [auditData, setAuditData] = useState(null);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Gemini (Default) State
  const [geminiKeyInput, setGeminiKeyInput] = useState(() => getSavedKeyForProvider('gemini') || (aiConfig?.provider === 'gemini' ? aiConfig?.apiKey : '') || '');
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [geminiFeedback, setGeminiFeedback] = useState('');

  // Custom OpenAI-compatible endpoint (OpenRouter / DeepSeek / Ollama / LM Studio) State
  const [customBaseUrl, setCustomBaseUrl] = useState(() => getSavedBaseUrlForProvider('openai_compatible') || '');
  const [customModel, setCustomModel] = useState(() => localStorage.getItem('custom_api_model') || '');
  const [customKeyInput, setCustomKeyInput] = useState(() => getSavedKeyForProvider('openai_compatible') || '');
  const [customModelPlaceholder, setCustomModelPlaceholder] = useState('deepseek/deepseek-v4.1-flash');
  const [showCustomKey, setShowCustomKey] = useState(false);
  const [customFeedback, setCustomFeedback] = useState('');

  // Local Whisper (Fallback) State
  const [localWhisperModel, setLocalWhisperModel] = useState(() => localStorage.getItem('local_whisper_model') || 'auto');
  const [localWhisperFeedback, setLocalWhisperFeedback] = useState('');

  const [envKeys, setEnvKeys] = useState(null);
  const [loadingEnvKeys, setLoadingEnvKeys] = useState(false);
  const [showEnvKeys, setShowEnvKeys] = useState(false);
  const [testStatus, setTestStatus] = useState({});

  // Custom Logo Management State
  const logoInputRef = useRef(null);
  const [logoFeedback, setLogoFeedback] = useState('');

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setLogoFeedback('❌ Image exceeds 5MB limit. Please upload a smaller file.');
      setTimeout(() => setLogoFeedback(''), 5000);
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result;
      if (!dataUrl || typeof dataUrl !== 'string') return;

      const img = new Image();
      img.onload = () => {
        const maxDim = 500;
        let { width, height } = img;
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        const constrainedUrl = canvas.toDataURL('image/png');

        try {
          localStorage.setItem('customAppLogo', constrainedUrl);
        } catch (err) {
          console.warn('LocalStorage notice:', err);
        }

        if (setSettings) {
          setSettings((prev) => ({ ...prev, customLogo: constrainedUrl }));
        }
        setLogoFeedback(`✅ Logo updated & constrained (${width}×${height}px)!`);
        setTimeout(() => setLogoFeedback(''), 4000);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  };

  const handleResetLogo = () => {
    try {
      localStorage.removeItem('customAppLogo');
    } catch (e) {}
    if (setSettings) {
      setSettings((prev) => ({ ...prev, customLogo: '' }));
    }
    setLogoFeedback('✅ Restored default EASD logo.');
    setTimeout(() => setLogoFeedback(''), 3000);
  };

  // Hydrate the custom endpoint fields from the server (api_settings.json survives app restarts)
  useEffect(() => {
    if (!isOpen) return;
    axios.get('/api/settings').then((res) => {
      const s = res.data?.settings || {};
      if (s.custom_api_base_url) setCustomBaseUrl((prev) => prev || s.custom_api_base_url);
      if (s.custom_api_model) setCustomModel((prev) => prev || s.custom_api_model);
      if (s.custom_api_key) setCustomKeyInput((prev) => prev || s.custom_api_key);
    }).catch(() => {});
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      fetchEnvKeys();
      setGeminiKeyInput(getSavedKeyForProvider('gemini') || (aiConfig?.provider === 'gemini' ? aiConfig?.apiKey : '') || '');
    }
  }, [isOpen, aiConfig]);

  const fetchEnvKeys = async () => {
    setLoadingEnvKeys(true);
    try {
      const res = await axios.get('/api/env_keys');
      if (res.data && res.data.env_keys) {
        setEnvKeys(res.data.env_keys);
      }
    } catch (e) {
      console.error('Failed to fetch env keys:', e);
    } finally {
      setLoadingEnvKeys(false);
    }
  };

  const handleSaveGemini = () => {
    const clean = geminiKeyInput.trim();
    saveKeyForProvider('gemini', clean);
    activateProvider('gemini', setAiConfig);
    saveServerSettings({
      gemini_api_key: clean,
      transcription_provider: 'gemini',
      transcription_model: 'gemini-3.5-transcribe',
      summarization_api_key: clean,
      summarization_provider: 'gemini',
      summarization_model: 'gemini-3.8-flash'
    });
    setGeminiFeedback('✅ Google Gemini saved & activated as default engine (Live 3.5 Transcribe + Flash 3.8 Low)!');
    setTimeout(() => setGeminiFeedback(''), 4000);
  };

  const applyCustomPreset = (preset) => {
    setCustomBaseUrl(preset.baseUrl);
    setCustomModel(preset.model);
    setCustomModelPlaceholder(preset.model || (preset.id === 'lmstudio' ? 'model id shown in LM Studio' : 'model id'));
    if (preset.key !== null) setCustomKeyInput(preset.key);
    setCustomFeedback('');
  };

  const handleSaveCustom = () => {
    const url = customBaseUrl.trim().replace(/\/+$/, '');
    const model = customModel.trim();
    const key = customKeyInput.trim();
    if (!url || !model) {
      setCustomFeedback('❌ Enter a Base URL and a Model ID first.');
      setTimeout(() => setCustomFeedback(''), 4000);
      return;
    }
    saveKeyForProvider('openai_compatible', key, url);
    localStorage.setItem('custom_api_model', model);
    saveServerSettings({
      summarization_provider: 'openai_compatible',
      summarization_model: model,
      custom_api_base_url: url,
      custom_api_key: key,
      custom_api_model: model
    });
    // Only the template-fill (summarization) step moves to the custom endpoint; transcription is unchanged.
    setAiConfig((prev) => ({
      ...prev,
      provider: 'openai_compatible',
      name: PROVIDERS.find((p) => p.id === 'openai_compatible')?.name,
      customName: '',
      summarizationProvider: 'openai_compatible',
      apiKey: key,
      baseUrl: url,
      summarizationModel: model,
      modelName: model
    }));
    setCustomFeedback(`✅ Custom API saved & activated for Generate (${model}).`);
    setTimeout(() => setCustomFeedback(''), 4000);
  };

  const handleTestCustom = () => {
    return runVerifyKey('custom', 'openai_compatible', customKeyInput.trim(), customBaseUrl.trim(), 'Custom API reachable!');
  };

  const handleSaveLocalWhisper = () => {
    localStorage.setItem('local_whisper_model', localWhisperModel);
    activateProvider('local_whisper', setAiConfig);
    saveServerSettings({
      transcription_provider: 'local_whisper',
      transcription_model: localWhisperModel,
      local_whisper_model: localWhisperModel,
      summarization_provider: 'local_whisper',
      summarization_model: 'local_synthesis'
    });
    setLocalWhisperFeedback(`✅ Local Whisper (${localWhisperModel}) activated as active engine!`);
    setTimeout(() => setLocalWhisperFeedback(''), 4000);
  };

  const runVerifyKey = async (statusKey, provider, apiKey, baseUrl = '', successLabel = '') => {
    setTestStatus(prev => ({ ...prev, [statusKey]: { loading: true, message: `Testing ${provider} connection...` } }));
    try {
      const res = await axios.post('/api/verify_key', {
        provider,
        api_key: apiKey,
        base_url: baseUrl
      });
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        [statusKey]: {
          loading: false,
          success: isValid,
          message: (res.data?.message || (isValid ? (successLabel || `${provider} connected successfully!`) : 'Verification failed.')) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        [statusKey]: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Connection test error'
        }
      }));
    }
  };

  const handleTestActiveEngine = () => {
    const p = aiConfig?.provider || 'gemini';
    if (p === 'local_whisper') {
      return handleTestLocalWhisper();
    }
    const k = aiConfig?.apiKey || getSavedKeyForProvider(p) || '';
    const u = aiConfig?.baseUrl || '';
    return runVerifyKey('active_engine', p, k, u, 'Active engine verified & connected!');
  };

  const handleTestGemini = () => {
    return runVerifyKey('gemini', 'gemini', geminiKeyInput.trim(), '', 'Gemini connected successfully!');
  };

  const handleTestLocalWhisper = async () => {
    setTestStatus(prev => ({ ...prev, local_whisper: { loading: true, message: 'Testing Local Whisper engine...' } }));
    try {
      const res = await axios.post('/api/test_engine', {
        test_type: 'stt',
        stt_provider: 'local_whisper',
        stt_model: localWhisperModel
      });
      const stt = res.data?.stt || {};
      const isValid = Boolean(stt.success);
      const lat = stt.latency_ms ? ` (${stt.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        local_whisper: {
          loading: false,
          success: isValid,
          message: (stt.message || 'Local Whisper engine verified & ready!') + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        local_whisper: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Local Whisper test failed'
        }
      }));
    }
  };

  const handleRunAudit = async () => {
    setLoadingAudit(true);
    try {
      const res = await axios.get('/api/system_audit');
      if (res.data && res.data.report) {
        setAuditData(res.data.report);
      }
    } catch (err) {
      console.error('Failed to run system audit:', err);
    } finally {
      setLoadingAudit(false);
    }
  };

  if (!isOpen) return null;

  const currentAccent = settings.accentColor || '#0284c7';
  const currentBangla = settings.banglaFont || 'nikosh';
  const currentEnglish = settings.englishFont || 'times_new_roman';
  const currentScale = settings.docScale || 'standard';

  const handleSelectAccent = (colorHex) => {
    setSettings({ ...settings, accentColor: colorHex });
  };

  const handleSelectBangla = (fontId) => {
    setSettings({ ...settings, banglaFont: fontId });
  };

  const handleSelectEnglish = (fontId) => {
    setSettings({ ...settings, englishFont: fontId });
  };

  return (
    <div className="modal" onClick={onClose} style={{ zIndex: 1100 }}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '680px', width: '92%', maxHeight: '90vh', overflowY: 'auto', padding: '24px 28px' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ background: 'rgba(2, 132, 199, 0.15)', padding: '8px', borderRadius: '10px', color: 'var(--accent-color)' }}>
              <Sliders size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>System Settings & Preferences</h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Configure Font Engine, Appearance, Accent Colors, and Cross-Platform Setup.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Quick Tools & Cloud Sync Row (Controls from Header cleanly housed in Settings) */}
        {(onOpenDeviceViewer || onOpenGDrive) && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '14px', flexWrap: 'wrap' }}>
            {onOpenDeviceViewer && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  onClose();
                  onOpenDeviceViewer();
                }}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600 }}
                title="Open responsive 3-device simulator"
              >
                📱 3-Device View
              </button>
            )}
            {onOpenGDrive && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  onClose();
                  onOpenGDrive();
                }}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', fontWeight: 600 }}
                title="Open Google Drive Sync"
              >
                ☁️ Google Drive Sync
              </button>
            )}
          </div>
        )}

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', flexWrap: 'wrap' }}>
          <button
            className={`btn ${activeTab === 'keys' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('keys')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Key size={14} /> API Keys & Environment
          </button>
          <button
            className={`btn ${activeTab === 'fonts' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('fonts')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Type size={14} /> Font Engine (Microsoft & Govt)
          </button>
          <button
            className={`btn ${activeTab === 'appearance' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('appearance')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Palette size={14} /> Appearance & Accent Colors
          </button>
          <button
            className={`btn ${activeTab === 'platforms' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('platforms')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Monitor size={14} /> Cross-Platform Package
          </button>
          <button
            className={`btn ${activeTab === 'audit' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => {
              setActiveTab('audit');
              if (!auditData && !loadingAudit) {
                handleRunAudit();
              }
            }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <ShieldCheck size={14} /> Daily Security & Setup Audit
          </button>
        </div>

        {/* TAB 0: STREAMLINED API CONFIGURATION & CUSTOM APIS */}
        {activeTab === 'keys' && (
          <div>
            {/* Active Engine Summary Banner */}
            <div
              style={{
                background: 'rgba(2, 132, 199, 0.12)',
                border: '2px solid var(--accent-color)',
                borderRadius: '12px',
                padding: '16px 20px',
                marginBottom: '20px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    background: 'var(--accent-color)',
                    color: '#ffffff',
                    borderRadius: '10px',
                    padding: '8px',
                    display: 'flex'
                  }}
                >
                  <Cpu size={22} />
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-color)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Active AI Engine
                  </div>
                  <h4 style={{ margin: '2px 0 0 0', fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {getActiveApiDisplayName(aiConfig)}
                  </h4>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Provider: <strong>{aiConfig.provider?.toUpperCase()}</strong> • Model: <code>{aiConfig.summarizationModel || aiConfig.modelName || 'gemini-3.8-flash'}</code>
                    {aiConfig.baseUrl && <> • Endpoint: <code>{aiConfig.baseUrl}</code></>}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  id="testActiveEngineBtn"
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleTestActiveEngine}
                  disabled={testStatus.active_engine?.loading}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, padding: '7px 14px', background: 'var(--bg-primary)' }}
                  title="Run connection test on active API engine"
                >
                  <Cpu size={14} color="var(--accent-color)" /> {testStatus.active_engine?.loading ? 'Testing API...' : 'Test Active API'}
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '6px 12px', borderRadius: '20px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }}></span>
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#10b981' }}>Active</span>
                </div>
              </div>

              {testStatus.active_engine?.message && (
                <div style={{
                  width: '100%',
                  marginTop: '8px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  background: testStatus.active_engine.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: testStatus.active_engine.success ? '#10b981' : '#ef4444',
                  border: testStatus.active_engine.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {testStatus.active_engine.success ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  <span>{testStatus.active_engine.message}</span>
                </div>
              )}
            </div>

            {/* SECTION 1: GOOGLE GEMINI (DEFAULT ENGINE) */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: aiConfig.provider === 'gemini' ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '18px 20px',
                marginBottom: '20px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Cpu size={20} color="var(--accent-color)" />
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Google Gemini API (Default Engine)
                    </h4>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      Cloud engine using your configured Gemini transcription and summarization models.
                    </span>
                  </div>
                </div>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: '0.78rem', color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none', fontWeight: 600 }}
                >
                  Get Gemini Key <ExternalLink size={12} />
                </a>
              </div>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
                <input
                  type={showGeminiKey ? 'text' : 'password'}
                  id="geminiApiKeyInput"
                  className="form-control"
                  placeholder="Paste Google Gemini API Key (e.g. AIzaSy...)"
                  value={geminiKeyInput}
                  onChange={(e) => setGeminiKeyInput(e.target.value)}
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.88rem', padding: '9px 12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowGeminiKey(!showGeminiKey)}
                  title={showGeminiKey ? 'Hide key' : 'Show key'}
                  style={{ padding: '9px 12px' }}
                >
                  {showGeminiKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={async () => {
                    try {
                      if (navigator.clipboard?.readText) {
                        const t = await navigator.clipboard.readText();
                        if (t) setGeminiKeyInput(t.trim());
                      }
                    } catch (e) {}
                  }}
                  title="Paste from clipboard"
                  style={{ padding: '9px 12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <Clipboard size={14} /> Paste
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: geminiFeedback ? '#10b981' : testStatus.gemini?.success ? '#10b981' : '#ef4444' }}>
                  {geminiFeedback || testStatus.gemini?.message || ''}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    id="testGeminiBtn"
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestGemini}
                    disabled={testStatus.gemini?.loading || !geminiKeyInput.trim()}
                    style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Cpu size={14} /> {testStatus.gemini?.loading ? 'Testing...' : 'Test Gemini API'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleSaveGemini}
                    style={{ padding: '6px 14px', fontWeight: 700 }}
                  >
                    <Check size={14} /> Set as Active Default
                  </button>
                </div>
              </div>
            </div>

            {/* SECTION 2: LOCAL WHISPER (OFFLINE & HARDWARE-ADAPTIVE FALLBACK) */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: aiConfig.provider === 'local_whisper' ? '2px solid #10b981' : '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '18px 20px',
                marginBottom: '20px',
                boxShadow: aiConfig.provider === 'local_whisper' ? '0 4px 16px rgba(16, 185, 129, 0.15)' : 'none'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ background: '#10b981', color: '#ffffff', borderRadius: '8px', padding: '6px', display: 'flex' }}>
                    <Server size={18} />
                  </div>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Local Whisper Engine (Offline & Hardware-Adaptive Fallback)
                    </h4>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      100% Free & Zero Cloud Dependency. Automatically adapts model size to available system RAM.
                    </span>
                  </div>
                </div>
                <span style={{ fontSize: '0.74rem', padding: '3px 8px', borderRadius: '6px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 700 }}>
                  Offline Engine
                </span>
              </div>

              {/* Hardware Sizing Architecture Banner */}
              <div style={{ background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '8px', padding: '10px 14px', marginBottom: '14px', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                <strong style={{ color: '#10b981' }}>Model sizing:</strong> <code>auto</code> picks the largest downloaded model your free RAM can run (<code>whisper-medium</code> needs ~8GB total and 2.5GB free). A model you choose here is always used as-is. Runs INT8 on the CPU, or on an NVIDIA GPU automatically when one is available.
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Whisper Model Selection:
                  </label>
                  <select
                    id="localWhisperModelSelect"
                    className="form-control"
                    value={localWhisperModel}
                    onChange={(e) => setLocalWhisperModel(e.target.value)}
                    style={{ fontSize: '0.85rem', padding: '8px 12px', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                  >
                    <option value="auto">auto (Hardware Adaptive: Auto-size to system RAM)</option>
                    <option value="whisper-tiny">whisper-tiny (Ultra-Fast / Low RAM: &lt;= 4GB)</option>
                    <option value="whisper-base">whisper-base (Fast Lightweight: 4-8GB)</option>
                    <option value="whisper-small">whisper-small (Standard Balance: 6GB+)</option>
                    <option value="whisper-medium">whisper-medium (High Precision: 8GB+ with 2.5GB free)</option>
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Offline Meeting Minutes Synthesis:
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    disabled
                    value="Deep Semantic Synthesis (Built-in Rule Engine)"
                    style={{ fontSize: '0.82rem', padding: '8px 12px', background: 'var(--bg-primary)', color: 'var(--text-secondary)', borderStyle: 'dashed' }}
                  />
                  <small style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Structures discussions, decisions, and action items locally without external API tokens.
                  </small>
                </div>
              </div>

              {/* Action row & Feedback */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: localWhisperFeedback ? '#10b981' : testStatus.local_whisper?.success ? '#10b981' : '#ef4444' }}>
                  {localWhisperFeedback || testStatus.local_whisper?.message || ''}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    id="testLocalWhisperBtn"
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestLocalWhisper}
                    disabled={testStatus.local_whisper?.loading}
                    style={{ padding: '7px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Server size={14} /> {testStatus.local_whisper?.loading ? 'Testing Engine...' : 'Test Local Whisper'}
                  </button>
                  <button
                    type="button"
                    id="saveLocalWhisperBtn"
                    className="btn btn-primary btn-sm"
                    onClick={handleSaveLocalWhisper}
                    style={{ padding: '7px 16px', fontWeight: 700, background: '#10b981', borderColor: '#10b981' }}
                  >
                    <Check size={15} /> Set as Active Engine
                  </button>
                </div>
              </div>
            </div>

            {/* SECTION 3: CUSTOM OPENAI-COMPATIBLE ENDPOINT (OpenRouter / DeepSeek / Ollama / LM Studio) */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: aiConfig.provider === 'openai_compatible' ? '2px solid #f59e0b' : '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '18px 20px',
                marginBottom: '20px',
                boxShadow: aiConfig.provider === 'openai_compatible' ? '0 4px 16px rgba(245, 158, 11, 0.15)' : 'none'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ background: '#f59e0b', color: '#ffffff', borderRadius: '8px', padding: '6px', display: 'flex' }}>
                    <Globe size={18} />
                  </div>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Custom / OpenRouter / Local (OpenAI-Compatible)
                    </h4>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      Fills the template on Generate using any OpenAI-compatible endpoint. Transcription is not affected.
                    </span>
                  </div>
                </div>
                <a
                  href="https://openrouter.ai/docs"
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: '0.78rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '4px', textDecoration: 'none', fontWeight: 600 }}
                >
                  OpenRouter docs <ExternalLink size={12} />
                </a>
              </div>

              <div role="group" aria-label="Custom API presets" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
                {CUSTOM_API_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => applyCustomPreset(preset)}
                    style={{ padding: '4px 10px', fontSize: '0.76rem', borderRadius: '14px' }}
                    title={preset.baseUrl ? `Prefill ${preset.baseUrl}` : 'Clear all fields'}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', marginBottom: '10px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="customApiBaseUrlInput" style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Base URL:
                  </label>
                  <input
                    id="customApiBaseUrlInput"
                    type="text"
                    className="form-control"
                    placeholder="https://openrouter.ai/api/v1"
                    value={customBaseUrl}
                    onChange={(e) => setCustomBaseUrl(e.target.value)}
                    style={{ fontFamily: 'monospace', fontSize: '0.85rem', padding: '8px 12px' }}
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label htmlFor="customApiModelInput" style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Model ID:
                  </label>
                  <input
                    id="customApiModelInput"
                    type="text"
                    className="form-control"
                    placeholder={customModelPlaceholder}
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    style={{ fontFamily: 'monospace', fontSize: '0.85rem', padding: '8px 12px' }}
                  />
                </div>
              </div>

              <label htmlFor="customApiKeyInput" style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                API key <span style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>(optional - no key required for local Ollama / LM Studio)</span>
              </label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
                <input
                  id="customApiKeyInput"
                  type={showCustomKey ? 'text' : 'password'}
                  className="form-control"
                  placeholder="Paste API key (leave blank for local Ollama/LM Studio)"
                  value={customKeyInput}
                  onChange={(e) => setCustomKeyInput(e.target.value)}
                  style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.88rem', padding: '9px 12px' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCustomKey(!showCustomKey)}
                  title={showCustomKey ? 'Hide key' : 'Show key'}
                  style={{ padding: '9px 12px' }}
                >
                  {showCustomKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: customFeedback ? (customFeedback.startsWith('❌') ? '#ef4444' : '#10b981') : testStatus.custom?.success ? '#10b981' : '#ef4444' }}>
                  {customFeedback || testStatus.custom?.message || ''}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    id="testCustomApiBtn"
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestCustom}
                    disabled={testStatus.custom?.loading || !customBaseUrl.trim()}
                    style={{ padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Globe size={14} /> {testStatus.custom?.loading ? 'Testing...' : 'Test Connection'}
                  </button>
                  <button
                    type="button"
                    id="saveCustomApiBtn"
                    className="btn btn-primary btn-sm"
                    onClick={handleSaveCustom}
                    style={{ padding: '6px 14px', fontWeight: 700, background: '#f59e0b', borderColor: '#f59e0b' }}
                  >
                    <Check size={14} /> Use for Generate
                  </button>
                </div>
              </div>
            </div>

            {/* SECTION 4: SYSTEM & .ENV ENVIRONMENT AUDIT (COLLAPSIBLE) */}
            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
              <div
                onClick={() => setShowEnvKeys(!showEnvKeys)}
                style={{
                  padding: '12px 16px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  userSelect: 'none'
                }}
              >
                <span style={{ fontSize: '0.84rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
                  <Terminal size={14} color="var(--accent-color)" /> System Environment & Key Detection
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      fetchEnvKeys();
                    }}
                    disabled={loadingEnvKeys}
                    style={{ fontSize: '0.72rem', padding: '2px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <RefreshCw size={11} className={loadingEnvKeys ? 'spin' : ''} /> {loadingEnvKeys ? 'Checking...' : 'Refresh'}
                  </button>
                  {showEnvKeys ? <ChevronUp size={16} color="var(--text-secondary)" /> : <ChevronDown size={16} color="var(--text-secondary)" />}
                </div>
              </div>

              {showEnvKeys && (
                <div style={{ padding: '0 16px 14px 16px', borderTop: '1px solid var(--border-color)' }}>
                  {envKeys ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', marginTop: '12px' }}>
                      {Object.entries(envKeys).map(([envName, info]) => (
                        <div
                          key={envName}
                          style={{
                            padding: '8px 12px',
                            borderRadius: '8px',
                            background: 'var(--bg-primary)',
                            border: '1px solid var(--border-color)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            fontSize: '0.8rem'
                          }}
                        >
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <code style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--accent-color)' }}>{envName}</code>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{info.preview}</span>
                          </div>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: info.configured ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: info.configured ? '#10b981' : '#ef4444'
                            }}
                          >
                            {info.configured ? 'SET' : 'NOT SET'}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', padding: '10px 0' }}>Loading environment keys...</div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 1: FONT ENGINE */}
        {activeTab === 'fonts' && (
          <div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-color)', padding: '12px 16px', borderRadius: '10px', marginBottom: '18px', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              💡 <strong>Standards-Compliant Font Engine</strong>: Uses official Microsoft Office typographic standards (`Times New Roman`, `Calibri`) and Bangladesh Secretariat Government standards (`Nikosh`, `NikoshBAN`, `Kalpurush`). Applied live to document preview and `.docx` export.
            </div>

            {/* Bangla / Govt Font Selector */}
            <div className="form-group">
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Type size={14} color="var(--accent-color)" /> Bangladesh Government / Bangla Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {BANGLA_FONTS.map((font) => (
                  <FontOptionCard
                    key={font.id}
                    font={font}
                    isSelected={currentBangla === font.id}
                    onSelect={handleSelectBangla}
                    sampleText="নমুনা: গণপ্রজাতন্ত্রী বাংলাদেশ সরকার — স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়"
                  />
                ))}
              </div>
            </div>

            {/* English Font Selector */}
            <div className="form-group" style={{ marginTop: '20px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Type size={14} color="var(--accent-color)" /> English Document & Minutes Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {ENGLISH_FONTS.map((font) => (
                  <FontOptionCard
                    key={font.id}
                    font={font}
                    isSelected={currentEnglish === font.id}
                    onSelect={handleSelectEnglish}
                    sampleText="Sample: Weekly Strategic, Programmatic and Review Meeting Minutes"
                  />
                ))}
              </div>
            </div>

            {/* Document Scale */}
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>Document Preview Typography Scale:</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                {[
                  { id: 'compact', label: 'Compact (9.5pt / Dense)' },
                  { id: 'standard', label: 'Standard (10.5pt / Word Default)' },
                  { id: 'large', label: 'Large (12pt / High Legibility)' }
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`btn ${currentScale === s.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    style={{ flex: 1 }}
                    onClick={() => setSettings({ ...settings, docScale: s.id })}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: APPEARANCE & ACCENT COLORS */}
        {activeTab === 'appearance' && (
          <div>
            {/* Organization Logo & Branding Card */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '16px 18px',
                marginBottom: '20px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ImageIcon size={18} color="var(--accent-color)" />
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Organization Logo & Seal Branding
                    </h4>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      Default is the official EASD seal. Upload any custom logo to replace it across the app and documents.
                    </span>
                  </div>
                </div>
                {settings?.customLogo && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handleResetLogo}
                    style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    title="Reset to default EASD logo"
                  >
                    <RotateCcw size={12} /> Reset to Default
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                {/* Logo Preview Container (Constrained Aspect Ratio & Size) */}
                <div
                  style={{
                    width: '76px',
                    height: '76px',
                    borderRadius: '12px',
                    background: '#ffffff',
                    border: '2px solid var(--border-color)',
                    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.15)',
                    padding: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}
                  title="Constrained logo preview"
                >
                  <img
                    src={settings?.customLogo || '/eminence_logo.png'}
                    alt="Logo Preview"
                    style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  />
                </div>

                <div style={{ flex: 1, minWidth: '220px' }}>
                  <input
                    ref={logoInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    onChange={handleLogoUpload}
                    style={{ display: 'none' }}
                  />
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => logoInputRef.current?.click()}
                      style={{ padding: '7px 14px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}
                    >
                      <UploadCloud size={14} /> Upload Custom Logo
                    </button>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                      PNG, JPG, WEBP (Max 5MB • Auto-constrained)
                    </span>
                  </div>
                  {logoFeedback && (
                    <div style={{ marginTop: '6px', fontSize: '0.78rem', fontWeight: 600, color: logoFeedback.startsWith('❌') ? '#ef4444' : '#10b981' }}>
                      {logoFeedback}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Theme Toggle inside Settings */}
            <div className="form-group">
              <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>Base Workspace Theme:</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  className={`btn ${theme === 'dark' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setTheme('dark')}
                >
                  🌙 Dark Studio Theme
                </button>
                <button
                  type="button"
                  className={`btn ${theme === 'light' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setTheme('light')}
                >
                  ☀️ Light Executive Theme
                </button>
              </div>
            </div>

            {/* Accent Color Palette Selector */}
            <div className="form-group" style={{ marginTop: '22px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Palette size={14} color="var(--accent-color)" /> Accent Color & Dynamic Glow:
              </label>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                Sets the active highlight color across buttons, form borders, active tabs, and input focus rings.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px' }}>
                {ACCENT_PALETTES.map((pal) => (
                  <div
                    key={pal.id}
                    onClick={() => handleSelectAccent(pal.hex)}
                    style={{
                      padding: '12px',
                      borderRadius: '12px',
                      border: currentAccent === pal.hex ? `2px solid ${pal.hex}` : '1px solid var(--border-color)',
                      background: currentAccent === pal.hex ? 'rgba(255, 255, 255, 0.06)' : 'var(--bg-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: pal.hex,
                        boxShadow: `0 0 10px ${pal.glow}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff'
                      }}
                    >
                      {currentAccent === pal.hex && <Check size={14} />}
                    </div>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {pal.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Consistent Textbox Preview */}
            <div className="form-group" style={{ marginTop: '24px', background: 'rgba(255, 255, 255, 0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Consistent Form Control & Textbox Preview:
              </label>
              <input
                type="text"
                className="form-control"
                style={{ fontSize: '0.9rem' }}
                placeholder="Click here to test the consistent focus ring and accent glow..."
                defaultValue="Consistent input field with smooth accent glow border"
              />
            </div>
          </div>
        )}

        {/* TAB 3: CROSS-PLATFORM ARCHITECTURE */}
        {activeTab === 'platforms' && (
          <div>
            <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', marginBottom: '14px', lineHeight: '1.6' }}>
              This single repository structure is built using a decoupled <strong>FastAPI Backend + React Frontend</strong> architecture designed for 100% cross-platform parity across all major operating systems:
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {PLATFORM_TARGETS.map((target) => {
                const IconComponent = target.icon;
                return (
                  <div key={target.title} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: target.color }}>
                      <IconComponent size={18} /> {target.title}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      {target.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 4: DAILY SYSTEM & SECURITY AUDIT */}
        {activeTab === 'audit' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ShieldCheck size={18} color="var(--accent-color)" /> Daily Operational, Security & App-Building Audit
                </h4>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  Automated scan of tasks, secret exposure, system toolchains, and build parity.
                </p>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleRunAudit}
                disabled={loadingAudit}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <RefreshCw size={13} style={{ animation: loadingAudit ? 'spin 1s linear infinite' : 'none' }} />
                {loadingAudit ? 'Auditing...' : 'Run Audit Now'}
              </button>
            </div>

            {loadingAudit && !auditData && (
              <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 8px auto', display: 'block', color: 'var(--accent-color)' }} />
                Running comprehensive system, security, and toolchain audit...
              </div>
            )}

            {auditData && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {/* 4 Metric Summary Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                  <AuditMetricCard
                    title="Security Score"
                    value={`${auditData.security?.score ?? 100}/100`}
                    badgeText={auditData.security?.status ?? 'SECURE'}
                    badgeColor={auditData.security?.score >= 90 ? '#10b981' : '#f59e0b'}
                    badgeBg={auditData.security?.status === 'SECURE' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'}
                  />
                  <AuditMetricCard
                    title="OCR & Media Engine"
                    value={auditData.toolchains?.tesseract_ocr?.found ? 'OCR Ready' : 'AI Vision'}
                    badgeColor={auditData.toolchains?.tesseract_ocr?.found ? '#10b981' : '#3b82f6'}
                    subText={`FFmpeg: ${auditData.toolchains?.ffmpeg?.found ? 'Active' : 'Missing'}`}
                  />
                  <AuditMetricCard
                    title="Frontend Build"
                    value={auditData.build?.frontend_dist_exists ? 'Compiled' : 'Not Built'}
                    badgeColor={auditData.build?.frontend_dist_exists ? '#10b981' : '#ef4444'}
                    subText={`Dist: ${auditData.build?.frontend_dist_age_hours != null ? `${auditData.build.frontend_dist_age_hours}h ago` : 'Ready'}`}
                  />
                  <AuditMetricCard
                    title="Code Backlog"
                    value={auditData.tasks?.total_code_debt_items ?? 0}
                    subText="Active TODOs"
                  />
                </div>

                {/* Toolchain Health Status */}
                <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                  <div style={{ fontSize: '0.84rem', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Activity size={15} color="var(--accent-color)" /> System Toolchain & Engine Diagnostics
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '8px', fontSize: '0.8rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle size={14} color="#10b981" />
                      <span><strong>Python:</strong> {auditData.toolchains?.python?.version || 'Detected'}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {auditData.toolchains?.ffmpeg?.found ? <CheckCircle size={14} color="#10b981" /> : <AlertTriangle size={14} color="#f59e0b" />}
                      <span><strong>FFmpeg:</strong> {auditData.toolchains?.ffmpeg?.found ? 'Available' : 'Not found in PATH'}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle size={14} color="#10b981" />
                      <span><strong>OCR Engine:</strong> {auditData.toolchains?.tesseract_ocr?.found ? 'Tesseract Local Active' : 'Google Gemini Vision Active'}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {auditData.toolchains?.nodejs?.found ? <CheckCircle size={14} color="#10b981" /> : <AlertTriangle size={14} color="#f59e0b" />}
                      <span><strong>Node.js:</strong> {auditData.toolchains?.nodejs?.version || 'N/A'}</span>
                    </div>
                  </div>
                </div>

                {/* Prioritized Improvements */}
                {auditData.recommendations && auditData.recommendations.length > 0 && (
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                    <div style={{ fontSize: '0.84rem', fontWeight: 700, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Check size={15} color="#10b981" /> Daily Improvement Recommendations
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {auditData.recommendations.map((rec, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '8px 12px',
                            borderRadius: '8px',
                            background: 'var(--bg-primary)',
                            border: '1px solid var(--border-color)',
                            fontSize: '0.8rem',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '3px'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                fontSize: '0.68rem',
                                padding: '1px 5px',
                                borderRadius: '4px',
                                fontWeight: 700,
                                background: rec.priority === 'HIGH' ? 'rgba(239, 68, 68, 0.15)' : rec.priority === 'MEDIUM' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                                color: rec.priority === 'HIGH' ? '#ef4444' : rec.priority === 'MEDIUM' ? '#f59e0b' : '#10b981'
                              }}
                            >
                              {rec.priority}
                            </span>
                            <strong style={{ color: 'var(--text-primary)' }}>{rec.area}:</strong>
                            <span style={{ color: 'var(--text-secondary)' }}>{rec.issue}</span>
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--accent-color)', paddingLeft: '4px' }}>
                            💡 {rec.recommendation}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button className="btn btn-primary" onClick={onClose} style={{ padding: '8px 20px' }}>
            Save & Apply Settings
          </button>
        </div>
      </div>
    </div>
  );
}
