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

  // Custom STT / LLM State
  const [customBaseUrl, setCustomBaseUrl] = useState(() => getSavedBaseUrlForProvider('openai_compatible') || '');
  const [customModel, setCustomModel] = useState(() => localStorage.getItem('custom_api_model') || '');
  const [customKeyInput, setCustomKeyInput] = useState(() => getSavedKeyForProvider('openai_compatible') || '');
  const [customModelPlaceholder, setCustomModelPlaceholder] = useState('deepseek/deepseek-v4.1-flash');
  const [showCustomKey, setShowCustomKey] = useState(false);
  const [customFeedback, setCustomFeedback] = useState('');

  // Transcription Model Selection State
  const [sttProvider, setSttProvider] = useState(() => localStorage.getItem('transcriptionProvider') || (aiConfig?.transcriptionProvider || aiConfig?.provider === 'local_whisper' ? 'local_whisper' : 'gemini'));
  const [sttModel, setSttModel] = useState(() => localStorage.getItem('transcriptionModel') || (aiConfig?.transcriptionModel || 'gemini-3.5-transcribe'));
  const [localWhisperModel, setLocalWhisperModel] = useState(() => localStorage.getItem('local_whisper_model') || 'whisper-small');
  const [sttFeedback, setSttFeedback] = useState('');

  // Summarization Model Selection State
  const [llmProvider, setLlmProvider] = useState(() => localStorage.getItem('summarizationProvider') || (aiConfig?.summarizationProvider || aiConfig?.provider || 'gemini'));
  const [geminiLlmModel, setGeminiLlmModel] = useState(() => localStorage.getItem('gemini_llm_model') || 'gemini-3.8-flash');
  const [localLlmModel, setLocalLlmModel] = useState(() => localStorage.getItem('local_llm_model') || 'qwen2.5-1.5b');
  const [llmFeedback, setLlmFeedback] = useState('');

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

  // Save & Apply Transcription Model (STT)
  const handleSaveTranscriptionModel = (overrideProvider = null, overrideModel = null) => {
    const prov = overrideProvider || sttProvider;
    const mod = overrideModel || (prov === 'local_whisper' ? localWhisperModel : prov === 'openai_compatible' ? (customModel || 'whisper-1') : 'gemini-3.5-transcribe');
    const key = prov === 'gemini' ? geminiKeyInput.trim() : prov === 'openai_compatible' ? customKeyInput.trim() : '';
    
    setSttProvider(prov);
    setSttModel(mod);
    localStorage.setItem('transcriptionProvider', prov);
    localStorage.setItem('transcriptionModel', mod);
    if (prov === 'local_whisper') {
      localStorage.setItem('local_whisper_model', mod);
    }
    
    saveServerSettings({
      transcription_provider: prov,
      transcription_model: mod,
      local_whisper_model: prov === 'local_whisper' ? mod : undefined,
      ...(prov === 'gemini' && key ? { gemini_api_key: key } : {}),
      ...(prov === 'openai_compatible' && customBaseUrl ? { custom_api_base_url: customBaseUrl.trim() } : {}),
      ...(prov === 'openai_compatible' && key ? { custom_api_key: key } : {})
    });

    setAiConfig(prev => ({
      ...prev,
      transcriptionProvider: prov,
      transcriptionModel: mod
    }));

    const label = prov === 'gemini' ? 'Gemini 3.5 Transcribe' : prov === 'local_whisper' ? `Local Whisper (${mod})` : `Custom STT (${mod})`;
    setSttFeedback(`✅ Active STT updated: ${label}`);
    setTimeout(() => setSttFeedback(''), 4000);
  };

  // Test Transcription Model (STT)
  const handleTestTranscriptionEngine = async (provToTest = null, modToTest = null) => {
    const targetProv = provToTest || sttProvider;
    const targetMod = modToTest || (targetProv === 'local_whisper' ? localWhisperModel : targetProv === 'openai_compatible' ? customModel : 'gemini-3.5-transcribe');
    const targetKey = targetProv === 'gemini' ? geminiKeyInput.trim() : targetProv === 'openai_compatible' ? customKeyInput.trim() : '';
    
    setTestStatus(prev => ({ ...prev, stt: { loading: true, message: `Testing ${targetProv} STT (${targetMod})...` } }));
    try {
      const res = await axios.post('/api/test_engine', {
        test_type: 'stt',
        stt_provider: targetProv,
        stt_model: targetMod,
        stt_api_key: targetKey,
        base_url: customBaseUrl.trim()
      });
      const stt = res.data?.stt || {};
      const isValid = Boolean(stt.success);
      const lat = stt.latency_ms ? ` (${stt.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        stt: {
          loading: false,
          success: isValid,
          message: (stt.message || `${targetProv} STT verified & ready!`) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        stt: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'STT connection test failed'
        }
      }));
    }
  };

  // Save & Apply Summarization Model (LLM)
  const handleSaveSummarizationModel = (overrideProvider = null, overrideModel = null) => {
    const prov = overrideProvider || llmProvider;
    const mod = overrideModel || (prov === 'gemini' ? geminiLlmModel : prov === 'local' || prov === 'local_whisper' ? localLlmModel : (customModel || 'deepseek/deepseek-v4.1-flash'));
    const key = prov === 'gemini' ? geminiKeyInput.trim() : prov === 'openai_compatible' ? customKeyInput.trim() : '';
    
    setLlmProvider(prov);
    localStorage.setItem('summarizationProvider', prov);
    localStorage.setItem('summarizationModel', mod);
    if (prov === 'gemini') {
      localStorage.setItem('gemini_llm_model', mod);
    } else if (prov === 'local' || prov === 'local_whisper') {
      localStorage.setItem('local_llm_model', mod);
    }
    
    saveServerSettings({
      summarization_provider: prov === 'local_whisper' ? 'local' : prov,
      summarization_model: mod,
      ...(prov === 'gemini' && key ? { gemini_api_key: key, summarization_api_key: key } : {}),
      ...(prov === 'openai_compatible' && customBaseUrl ? { custom_api_base_url: customBaseUrl.trim(), custom_api_model: mod } : {}),
      ...(prov === 'openai_compatible' && key ? { custom_api_key: key, summarization_api_key: key } : {})
    });

    setAiConfig(prev => ({
      ...prev,
      provider: prov === 'local_whisper' ? 'local' : prov,
      summarizationProvider: prov === 'local_whisper' ? 'local' : prov,
      summarizationModel: mod,
      modelName: mod,
      ...(key ? { apiKey: key } : {}),
      ...(prov === 'openai_compatible' && customBaseUrl ? { baseUrl: customBaseUrl.trim() } : {})
    }));

    const label = prov === 'gemini' ? `Gemini (${mod})` : (prov === 'local' || prov === 'local_whisper') ? `Local LLM (${mod})` : `Custom (${mod})`;
    setLlmFeedback(`✅ Active LLM updated: ${label}`);
    setTimeout(() => setLlmFeedback(''), 4000);
  };

  // Test Summarization Model (LLM)
  const handleTestSummarizationEngine = async (provToTest = null, modToTest = null) => {
    const targetProv = provToTest || (llmProvider === 'local_whisper' ? 'local' : llmProvider);
    const targetMod = modToTest || (targetProv === 'gemini' ? geminiLlmModel : targetProv === 'local' ? localLlmModel : customModel);
    const targetKey = targetProv === 'gemini' ? geminiKeyInput.trim() : targetProv === 'openai_compatible' ? customKeyInput.trim() : '';

    setTestStatus(prev => ({ ...prev, llm: { loading: true, message: `Testing ${targetProv} LLM (${targetMod})...` } }));
    try {
      const res = await axios.post('/api/test_engine', {
        test_type: 'llm',
        llm_provider: targetProv,
        llm_model: targetMod,
        llm_api_key: targetKey,
        base_url: customBaseUrl.trim()
      });
      const llm = res.data?.llm || {};
      const isValid = Boolean(llm.success);
      const lat = llm.latency_ms ? ` (${llm.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        llm: {
          loading: false,
          success: isValid,
          message: (llm.message || `${targetProv} LLM verified!`) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        llm: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'LLM connection test failed'
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

            {/* ========================================================
                HEADING 1: TRANSCRIPTION MODEL (STT)
                Under this heading: Gemini, Whisper (Small for low-end / Turbo for fast PC), and Custom STT
                ======================================================== */}
            <div style={{ marginBottom: '32px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '2px solid var(--border-color)', paddingBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ background: 'rgba(2, 132, 199, 0.15)', color: 'var(--accent-color)', padding: '6px', borderRadius: '8px', display: 'flex' }}>
                    <Server size={18} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.08rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.01em' }}>
                      Transcription Model (Speech-to-Text)
                    </h3>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      Select speech engine for transcribing audio files & microphone takes.
                    </span>
                  </div>
                </div>
                <span style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: '12px', background: 'rgba(2, 132, 199, 0.15)', color: 'var(--accent-color)', fontWeight: 700 }}>
                  Active STT: {sttProvider === 'gemini' ? 'Gemini 3.5 Transcribe' : sttProvider === 'local_whisper' ? `Whisper (${localWhisperModel})` : `Custom (${customModel || 'OpenAI-compatible'})`}
                </span>
              </div>

              {/* 1.A: Gemini Transcribe */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: sttProvider === 'gemini' ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px',
                  marginBottom: '14px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Cpu size={16} color="var(--accent-color)" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Gemini 3.5 Transcribe (Cloud Live STT)
                    </span>
                    <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(2, 132, 199, 0.12)', color: 'var(--accent-color)', fontWeight: 600 }}>
                      Official Google API
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestTranscriptionEngine('gemini', 'gemini-3.5-transcribe')}
                      disabled={testStatus.stt?.loading || !geminiKeyInput.trim()}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.stt?.loading && sttProvider === 'gemini' ? 'Testing...' : 'Test STT'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveTranscriptionModel('gemini', 'gemini-3.5-transcribe')}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700 }}
                    >
                      {sttProvider === 'gemini' ? '✓ Selected' : 'Use Gemini STT'}
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                  <input
                    type={showGeminiKey ? 'text' : 'password'}
                    className="form-control"
                    placeholder="Gemini API Key (stored in .env / os.environ)"
                    value={geminiKeyInput}
                    onChange={(e) => setGeminiKeyInput(e.target.value)}
                    style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.84rem', padding: '7px 10px' }}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowGeminiKey(!showGeminiKey)}
                    title={showGeminiKey ? 'Hide key' : 'Show key'}
                    style={{ padding: '7px 10px' }}
                  >
                    {showGeminiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                  🔒 Credential stored safely in server environment & <code>.env</code>. Never exposed to git repository.
                </div>
              </div>

              {/* 1.B: Whisper (Offline STT with Small / Turbo differentiation) */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: sttProvider === 'local_whisper' ? '2px solid #10b981' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px',
                  marginBottom: '14px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Server size={16} color="#10b981" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Whisper (Offline STT)
                    </span>
                    <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 600 }}>
                      100% Local • Zero API Cost
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestTranscriptionEngine('local_whisper', localWhisperModel)}
                      disabled={testStatus.stt?.loading}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.stt?.loading && sttProvider === 'local_whisper' ? 'Testing...' : 'Test Whisper'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveTranscriptionModel('local_whisper', localWhisperModel)}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700, background: '#10b981', borderColor: '#10b981' }}
                    >
                      {sttProvider === 'local_whisper' ? '✓ Selected' : 'Use Whisper STT'}
                    </button>
                  </div>
                </div>

                <div style={{ marginBottom: '10px' }}>
                  <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Model Precision & Performance Profile:
                  </label>
                  <select
                    className="form-control"
                    value={localWhisperModel}
                    onChange={(e) => {
                      const newMod = e.target.value;
                      setLocalWhisperModel(newMod);
                      if (sttProvider === 'local_whisper') {
                        handleSaveTranscriptionModel('local_whisper', newMod);
                      }
                    }}
                    style={{ fontSize: '0.84rem', padding: '7px 10px', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                  >
                    <option value="whisper-small">whisper-small ⚡ (Recommended for Low-End PC: ~460MB weights, low RAM)</option>
                    <option value="whisper-large-v3-turbo">whisper-large-v3-turbo 🚀 (Recommended for Faster PC / GPU: Top accuracy + 8x speed)</option>
                    <option value="auto">auto (Hardware Adaptive: Picks largest model RAM can comfortably host)</option>
                    <option value="whisper-base">whisper-base (Ultra-Lightweight: 4-8 GB RAM)</option>
                    <option value="whisper-medium">whisper-medium (Standard Precision: 8+ GB RAM)</option>
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  <div style={{ background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                    <strong style={{ color: 'var(--text-primary)' }}>💻 Low-End PC:</strong> Choose <code>whisper-small</code>. Minimal RAM load with stable Bengali/English bilingual recognition.
                  </div>
                  <div style={{ background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                    <strong style={{ color: 'var(--text-primary)' }}>⚡ Faster PC / GPU:</strong> Choose <code>whisper-large-v3-turbo</code>. State-of-the-art accuracy with fast 4-layer decoder speed.
                  </div>
                </div>
              </div>

              {/* 1.C: Custom STT (OpenAI-compatible / Whisper API) */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: sttProvider === 'openai_compatible' ? '2px solid #f59e0b' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Globe size={16} color="#f59e0b" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Custom STT (OpenAI-Compatible / Remote Endpoint)
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestTranscriptionEngine('openai_compatible', customModel || 'whisper-1')}
                      disabled={testStatus.stt?.loading || !customBaseUrl.trim()}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.stt?.loading && sttProvider === 'openai_compatible' ? 'Testing...' : 'Test STT'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveTranscriptionModel('openai_compatible', customModel || 'whisper-1')}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700, background: '#f59e0b', borderColor: '#f59e0b' }}
                    >
                      {sttProvider === 'openai_compatible' ? '✓ Selected' : 'Use Custom STT'}
                    </button>
                  </div>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Connects to external audio endpoints (Groq Whisper, self-hosted faster-whisper server, or cloud transcription proxies).
                </div>
              </div>

              {/* STT Status & Feedback banner */}
              {(sttFeedback || testStatus.stt?.message) && (
                <div style={{
                  marginTop: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  background: (sttFeedback || testStatus.stt?.success) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: (sttFeedback || testStatus.stt?.success) ? '#10b981' : '#ef4444',
                  border: (sttFeedback || testStatus.stt?.success) ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {(sttFeedback || testStatus.stt?.success) ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                  <span>{sttFeedback || testStatus.stt?.message}</span>
                </div>
              )}
            </div>

            {/* ========================================================
                HEADING 2: SUMMARIZATION MODEL (LLM)
                Under this heading: Gemini, Local LLM (llama.cpp / Vulkan), and Custom LLM
                ======================================================== */}
            <div style={{ marginBottom: '32px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '2px solid var(--border-color)', paddingBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ background: 'rgba(124, 58, 237, 0.15)', color: '#7c3aed', padding: '6px', borderRadius: '8px', display: 'flex' }}>
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.08rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.01em' }}>
                      Summarization Model (Meeting Minutes & Reports)
                    </h3>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      Select AI engine for structuring transcripts into executive minutes and custom templates.
                    </span>
                  </div>
                </div>
                <span style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: '12px', background: 'rgba(124, 58, 237, 0.15)', color: '#7c3aed', fontWeight: 700 }}>
                  Active LLM: {llmProvider === 'gemini' ? `Gemini (${geminiLlmModel})` : (llmProvider === 'local' || llmProvider === 'local_whisper') ? `Local (${localLlmModel})` : `Custom (${customModel || 'OpenAI-compatible'})`}
                </span>
              </div>

              {/* 2.A: Gemini LLM */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: llmProvider === 'gemini' ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px',
                  marginBottom: '14px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Cpu size={16} color="var(--accent-color)" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Gemini (Cloud Executive Synthesis)
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestSummarizationEngine('gemini', geminiLlmModel)}
                      disabled={testStatus.llm?.loading || !geminiKeyInput.trim()}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.llm?.loading && llmProvider === 'gemini' ? 'Testing...' : 'Test Gemini'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveSummarizationModel('gemini', geminiLlmModel)}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700 }}
                    >
                      {llmProvider === 'gemini' ? '✓ Selected' : 'Use Gemini LLM'}
                    </button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                      Model Variant:
                    </label>
                    <select
                      className="form-control"
                      value={geminiLlmModel}
                      onChange={(e) => {
                        const m = e.target.value;
                        setGeminiLlmModel(m);
                        if (llmProvider === 'gemini') {
                          handleSaveSummarizationModel('gemini', m);
                        }
                      }}
                      style={{ fontSize: '0.84rem', padding: '7px 10px', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                    >
                      <option value="gemini-3.8-flash">gemini-3.8-flash (Fast, High Quality Executive Output)</option>
                      <option value="gemini-3.5-pro">gemini-3.5-pro (Deep Multi-Hour Analytical Synthesis)</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                      Uses the Gemini key configured above. Credentials persist automatically in <code>.env</code> and environment variables.
                    </span>
                  </div>
                </div>
              </div>

              {/* 2.B: Local LLM (llama.cpp with Vulkan GPU Auto-Acceleration) */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: (llmProvider === 'local' || llmProvider === 'local_whisper') ? '2px solid #10b981' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px',
                  marginBottom: '14px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Server size={16} color="#10b981" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Local LLM (llama.cpp with Vulkan GPU Auto-Acceleration)
                    </span>
                    <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 600 }}>
                      100% Offline
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestSummarizationEngine('local', localLlmModel)}
                      disabled={testStatus.llm?.loading}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.llm?.loading && (llmProvider === 'local' || llmProvider === 'local_whisper') ? 'Testing...' : 'Test Local LLM'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveSummarizationModel('local', localLlmModel)}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700, background: '#10b981', borderColor: '#10b981' }}
                    >
                      {(llmProvider === 'local' || llmProvider === 'local_whisper') ? '✓ Selected' : 'Use Local LLM'}
                    </button>
                  </div>
                </div>

                <div style={{ background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px', padding: '8px 12px', marginBottom: '10px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  <strong style={{ color: '#10b981' }}>Hardware Auto-Detection:</strong> When a GPU supporting Vulkan (Intel, AMD, NVIDIA, or Apple) is present, llama.cpp automatically shifts inference to Vulkan GPU layers (<code>n_gpu_layers = -1</code>) for fast offline processing, or seamlessly falls back to optimized multi-threaded CPU.
                </div>

                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Local Model Architecture:
                  </label>
                  <select
                    className="form-control"
                    value={localLlmModel}
                    onChange={(e) => {
                      const m = e.target.value;
                      setLocalLlmModel(m);
                      if (llmProvider === 'local' || llmProvider === 'local_whisper') {
                        handleSaveSummarizationModel('local', m);
                      }
                    }}
                    style={{ fontSize: '0.84rem', padding: '7px 10px', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                  >
                    <option value="qwen2.5-1.5b">Qwen2.5-1.5B-Instruct (~1.0 GB GGUF, High accuracy for meeting minutes & tables)</option>
                    <option value="qwen2.5-0.5b">Qwen2.5-0.5B-Instruct (~0.4 GB GGUF, Ultra-lightweight for very low RAM)</option>
                    <option value="gemma-2-2b">Gemma-2-2B-IT (~1.6 GB GGUF, Google family local instruction model)</option>
                  </select>
                </div>
              </div>

              {/* 2.C: Custom LLM (OpenRouter / DeepSeek / Ollama / LM Studio) */}
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  border: llmProvider === 'openai_compatible' ? '2px solid #f59e0b' : '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '16px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Globe size={16} color="#f59e0b" />
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      Custom / Other LLM (OpenRouter, DeepSeek, Ollama, LM Studio)
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleTestSummarizationEngine('openai_compatible', customModel)}
                      disabled={testStatus.llm?.loading || !customBaseUrl.trim()}
                      style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                    >
                      {testStatus.llm?.loading && llmProvider === 'openai_compatible' ? 'Testing...' : 'Test Connection'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleSaveSummarizationModel('openai_compatible', customModel)}
                      style={{ fontSize: '0.75rem', padding: '4px 12px', fontWeight: 700, background: '#f59e0b', borderColor: '#f59e0b' }}
                    >
                      {llmProvider === 'openai_compatible' ? '✓ Selected' : 'Use Custom LLM'}
                    </button>
                  </div>
                </div>

                <div role="group" aria-label="Custom API presets" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                  {CUSTOM_API_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => applyCustomPreset(preset)}
                      style={{ padding: '3px 10px', fontSize: '0.74rem', borderRadius: '14px' }}
                      title={preset.baseUrl ? `Prefill ${preset.baseUrl}` : 'Clear all fields'}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', marginBottom: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                      Base URL:
                    </label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="https://openrouter.ai/api/v1"
                      value={customBaseUrl}
                      onChange={(e) => setCustomBaseUrl(e.target.value)}
                      style={{ fontFamily: 'monospace', fontSize: '0.84rem', padding: '7px 10px' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                      Model ID:
                    </label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder={customModelPlaceholder}
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      style={{ fontFamily: 'monospace', fontSize: '0.84rem', padding: '7px 10px' }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    API Key (Optional for local Ollama / LM Studio):
                  </label>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <input
                      type={showCustomKey ? 'text' : 'password'}
                      className="form-control"
                      placeholder="Paste Custom API Key (optional)"
                      value={customKeyInput}
                      onChange={(e) => setCustomKeyInput(e.target.value)}
                      style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.84rem', padding: '7px 10px' }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowCustomKey(!showCustomKey)}
                      title={showCustomKey ? 'Hide key' : 'Show key'}
                      style={{ padding: '7px 10px' }}
                    >
                      {showCustomKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* LLM Status & Feedback banner */}
              {(llmFeedback || testStatus.llm?.message) && (
                <div style={{
                  marginTop: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  background: (llmFeedback || testStatus.llm?.success) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: (llmFeedback || testStatus.llm?.success) ? '#10b981' : '#ef4444',
                  border: (llmFeedback || testStatus.llm?.success) ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  {(llmFeedback || testStatus.llm?.success) ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                  <span>{llmFeedback || testStatus.llm?.message}</span>
                </div>
              )}
            </div>

            {/* ========================================================
                ENVIRONMENT VARIABLES & GITHUB SECURITY CARD
                Confirms secrets are stored in .env and strictly excluded from git
                ======================================================== */}
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={16} color="#10b981" />
                  <div>
                    <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Environment Variables & GitHub Security
                    </span>
                    <span style={{ fontSize: '0.74rem', color: '#10b981', display: 'block' }}>
                      🔒 Secrets stored in <code>.env</code> & excluded from GitHub commits via <code>.gitignore</code>
                    </span>
                  </div>
                </div>
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
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '10px 0 8px 0', lineHeight: 1.4 }}>
                    Environment keys detected by server process. Any changes saved above sync into <code>os.environ</code> and the local <code>.env</code> file.
                  </div>
                  {envKeys ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
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
                            {info.source && <span style={{ fontSize: '0.66rem', color: 'var(--text-secondary)', opacity: 0.8 }}>Source: {info.source}</span>}
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
