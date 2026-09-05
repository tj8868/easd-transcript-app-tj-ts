import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  X, Sliders, Type, Palette, Monitor, Check, Sparkles, Smartphone, Apple,
  Terminal, ShieldCheck, RefreshCw, AlertTriangle, CheckCircle, FileText,
  Activity, Key, Plus, Trash2, Eye, EyeOff, CheckCircle2, Copy, Clipboard,
  Zap, ChevronDown, ChevronUp, Cpu, Server, Globe, ExternalLink
} from 'lucide-react';
import {
  getSavedCustomApis,
  saveCustomApi,
  deleteCustomApi,
  activateCustomApi,
  activateProvider,
  saveKeyForProvider,
  getSavedKeyForProvider,
  getActiveApiDisplayName,
  PROVIDERS
} from '../utils/apiKeyStorage';

export const ACCENT_PALETTES = [
  { id: 'cerulean', name: 'Eminence Cerulean', hex: '#0284c7', glow: 'rgba(2, 132, 199, 0.25)' },
  { id: 'govt_emerald', name: 'Govt Secretariat Emerald', hex: '#047857', glow: 'rgba(4, 120, 87, 0.25)' },
  { id: 'royal_navy', name: 'EASD Royal Navy', hex: '#004b87', glow: 'rgba(0, 75, 135, 0.25)' },
  { id: 'sunset_orange', name: 'Eminence Orange', hex: '#ea580c', glow: 'rgba(234, 88, 12, 0.25)' },
  { id: 'royal_violet', name: 'Thought Leadership Violet', hex: '#7c3aed', glow: 'rgba(124, 58, 237, 0.25)' },
  { id: 'crimson_red', name: 'Crimson Red', hex: '#dc2626', glow: 'rgba(220, 38, 38, 0.25)' }
];

export const BANGLA_FONTS = [
  { id: 'nikosh', name: 'Nikosh (Official Bangladesh Govt Secretariat Standard)', fontStack: "'Nikosh', 'NikoshBAN', 'SolaimanLipi', 'Hind Siliguri', sans-serif" },
  { id: 'nikosh_ban', name: 'NikoshBAN (Govt Bilingual Standard with English Glyphs)', fontStack: "'NikoshBAN', 'Nikosh', 'Hind Siliguri', sans-serif" },
  { id: 'kalpurush', name: 'Kalpurush (Classic Standard Unicode Bangla)', fontStack: "'Kalpurush', 'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'hind_siliguri', name: 'Hind Siliguri (Modern Clean Web Bangla)', fontStack: "'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'solaiman_lipi', name: 'SolaimanLipi (Traditional Clean Typography)', fontStack: "'SolaimanLipi', 'Hind Siliguri', sans-serif" }
];

export const ENGLISH_FONTS = [
  { id: 'times_new_roman', name: 'Times New Roman (Microsoft Standard Serif - Official Minutes)', fontStack: "'Times New Roman', Times, serif" },
  { id: 'calibri', name: 'Calibri (Microsoft Standard Sans-Serif - Corporate Briefs)', fontStack: "'Calibri', 'Segoe UI', Arial, sans-serif" },
  { id: 'arial', name: 'Arial (Microsoft High-Legibility Sans-Serif)', fontStack: "Arial, Helvetica, sans-serif" },
  { id: 'inter', name: 'Inter (Modern UI & Presentation Font)', fontStack: "'Inter', system-ui, sans-serif" },
  { id: 'nikosh_ban_en', name: 'NikoshBAN (Bangladesh Govt English Standard)', fontStack: "'NikoshBAN', 'Times New Roman', serif" }
];

export default function SettingsModal({
  isOpen,
  onClose,
  theme,
  setTheme,
  settings,
  setSettings,
  aiConfig = { provider: 'gemini', model: 'gemini-2.5-flash', apiKey: '' },
  setAiConfig = () => {}
}) {
  const [activeTab, setActiveTab] = useState('keys');
  const [auditData, setAuditData] = useState(null);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Gemini (Default) State
  const [geminiKeyInput, setGeminiKeyInput] = useState(() => getSavedKeyForProvider('gemini') || (aiConfig?.provider === 'gemini' ? aiConfig?.apiKey : '') || '');
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [geminiFeedback, setGeminiFeedback] = useState('');

  // Custom Named APIs State
  const [customApisList, setCustomApisList] = useState(() => getSavedCustomApis());
  const [customName, setCustomName] = useState('');
  const [customBaseUrl, setCustomBaseUrl] = useState('http://localhost:11434/v1');
  const [customApiKey, setCustomApiKey] = useState('');
  const [customModel, setCustomModel] = useState('llama3.3');
  const [showCustomKey, setShowCustomKey] = useState(false);
  const [customFeedback, setCustomFeedback] = useState('');

  // Secondary Provider Keys State (Groq, OpenAI, Anthropic)
  const [otherProvider, setOtherProvider] = useState('groq');
  const [otherKey, setOtherKey] = useState(() => getSavedKeyForProvider('groq') || '');
  const [showOtherKey, setShowOtherKey] = useState(false);
  const [otherFeedback, setOtherFeedback] = useState('');
  const [showOtherProviders, setShowOtherProviders] = useState(false);

  const [envKeys, setEnvKeys] = useState(null);
  const [loadingEnvKeys, setLoadingEnvKeys] = useState(false);
  const [showEnvKeys, setShowEnvKeys] = useState(false);
  const [testStatus, setTestStatus] = useState({});

  useEffect(() => {
    if (isOpen) {
      fetchEnvKeys();
      setCustomApisList(getSavedCustomApis());
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
    setGeminiFeedback('✅ Google Gemini saved and activated as default engine!');
    setTimeout(() => setGeminiFeedback(''), 4000);
  };

  const handleTestActiveEngine = async () => {
    setTestStatus(prev => ({ ...prev, active_engine: { loading: true, message: 'Testing active engine connection...' } }));
    try {
      const p = aiConfig?.provider || 'gemini';
      const k = aiConfig?.apiKey || getSavedKeyForProvider(p) || '';
      const u = aiConfig?.baseUrl || '';
      const res = await axios.post('/api/verify_key', {
        provider: p,
        api_key: k,
        base_url: u
      });
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        active_engine: {
          loading: false,
          success: isValid,
          message: (res.data?.message || (isValid ? 'Active engine verified & connected!' : 'Verification failed.')) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        active_engine: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Connection test error'
        }
      }));
    }
  };

  const handleTestGemini = async () => {
    setTestStatus(prev => ({ ...prev, gemini: { loading: true, message: 'Verifying Google Gemini Key...' } }));
    try {
      const res = await axios.post('/api/verify_key', {
        provider: 'gemini',
        api_key: geminiKeyInput.trim()
      });
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        gemini: {
          loading: false,
          success: isValid,
          message: (res.data?.message || (isValid ? 'Gemini connected successfully!' : 'Verification failed.')) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        gemini: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Connection error'
        }
      }));
    }
  };

  const handleSaveCustomApi = () => {
    const nameTrimmed = customName.trim();
    if (!nameTrimmed) {
      setCustomFeedback('⚠️ Please enter an API Name (e.g. "Office Ollama").');
      return;
    }
    const saved = saveCustomApi({
      name: nameTrimmed,
      baseUrl: customBaseUrl.trim() || 'http://localhost:11434/v1',
      apiKey: customApiKey.trim(),
      modelName: customModel.trim() || 'llama3.3',
      transcriptionModel: 'whisper-large-v3-turbo'
    });
    if (saved) {
      const updated = getSavedCustomApis();
      setCustomApisList(updated);
      activateCustomApi(saved.id, setAiConfig);
      setCustomName('');
      setCustomApiKey('');
      setCustomFeedback(`✅ Saved & Activated "${saved.name}"!`);
      setTimeout(() => setCustomFeedback(''), 4000);
    }
  };

  const handleActivateCustom = (item) => {
    activateCustomApi(item.id, setAiConfig);
    setCustomFeedback(`✅ Activated "${item.name}" as active engine!`);
    setTimeout(() => setCustomFeedback(''), 4000);
  };

  const handleDeleteCustom = (id) => {
    deleteCustomApi(id);
    const updated = getSavedCustomApis();
    setCustomApisList(updated);
    if (aiConfig.customApiId === id || (aiConfig.provider === 'custom' && !updated.length)) {
      activateProvider('gemini', setAiConfig);
    }
  };

  const handleTestCustom = async (itemOrNew) => {
    const keyId = itemOrNew.id || 'custom_new';
    setTestStatus(prev => ({ ...prev, [keyId]: { loading: true, message: 'Testing endpoint connection...' } }));
    try {
      const res = await axios.post('/api/verify_key', {
        provider: 'custom',
        api_key: itemOrNew.apiKey || '',
        base_url: itemOrNew.baseUrl || 'http://localhost:11434/v1'
      });
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        [keyId]: {
          loading: false,
          success: isValid,
          message: (res.data?.message || (isValid ? 'Custom endpoint connected!' : 'Connection failed.')) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        [keyId]: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Connection error'
        }
      }));
    }
  };

  const handleTestOtherProvider = async () => {
    setTestStatus(prev => ({ ...prev, [otherProvider]: { loading: true, message: `Testing ${otherProvider.toUpperCase()}...` } }));
    try {
      const res = await axios.post('/api/verify_key', {
        provider: otherProvider,
        api_key: otherKey.trim()
      });
      const isValid = Boolean(res.data?.valid || res.data?.success);
      const lat = res.data?.latency_ms ? ` (${res.data.latency_ms}ms)` : '';
      setTestStatus(prev => ({
        ...prev,
        [otherProvider]: {
          loading: false,
          success: isValid,
          message: (res.data?.message || (isValid ? `${otherProvider.toUpperCase()} key verified!` : 'Verification failed.')) + lat
        }
      }));
    } catch (err) {
      setTestStatus(prev => ({
        ...prev,
        [otherProvider]: {
          loading: false,
          success: false,
          message: err.response?.data?.detail || err.message || 'Connection error'
        }
      }));
    }
  };

  const handleSaveOtherProvider = () => {
    const clean = otherKey.trim();
    saveKeyForProvider(otherProvider, clean);
    activateProvider(otherProvider, setAiConfig);
    setOtherFeedback(`✅ ${otherProvider.toUpperCase()} saved & activated!`);
    setTimeout(() => setOtherFeedback(''), 4000);
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

        {/* Tab Navigation */}
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
                    Provider: <strong>{aiConfig.provider?.toUpperCase()}</strong> • Model: <code>{aiConfig.summarizationModel || aiConfig.modelName || 'gemini-2.5-flash'}</code>
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
                  <Zap size={14} color="var(--accent-color)" /> {testStatus.active_engine?.loading ? 'Testing API...' : '⚡ Test Active API'}
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
                  <span style={{ fontSize: '1.2rem' }}>⭐</span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Google Gemini API (Default Engine)
                    </h4>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      High-speed Gemini 2.5 Flash for audio transcription and executive synthesis.
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
                    <Zap size={14} /> {testStatus.gemini?.loading ? 'Testing...' : 'Test Gemini API'}
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

            {/* SECTION 2: CUSTOM API SETUP (LOCAL OLLAMA / CUSTOM ENDPOINT) */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: '2px solid #10b981',
                borderRadius: '12px',
                padding: '18px 20px',
                marginBottom: '20px',
                boxShadow: '0 4px 16px rgba(16, 185, 129, 0.12)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ background: '#10b981', color: '#ffffff', borderRadius: '8px', padding: '6px', display: 'flex' }}>
                    <Server size={18} />
                  </div>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      Add Custom API
                    </h4>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      Connect local Ollama, LM Studio, vLLM, DeepSeek, or any OpenAI-compatible custom server.
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                {/* 1. Custom API Name */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    API Name: <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    id="customApiNameInput"
                    className="form-control"
                    placeholder="e.g. Office Ollama, DeepSeek Gateway, Local vLLM"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    style={{ fontSize: '0.85rem', padding: '8px 12px' }}
                  />
                  <small style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    This name will appear on the front page top API button.
                  </small>
                </div>

                {/* 2. Custom Base URL */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Base URL / Endpoint: <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    id="customApiUrlInput"
                    className="form-control"
                    placeholder="http://localhost:11434/v1"
                    value={customBaseUrl}
                    onChange={(e) => setCustomBaseUrl(e.target.value)}
                    style={{ fontSize: '0.85rem', fontFamily: 'monospace', padding: '8px 12px' }}
                  />
                  <small style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Target OpenAI-compatible endpoint URL.
                  </small>
                </div>

                {/* 3. Custom API Key / Bearer Token */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    API Key / Bearer Token: (Optional)
                  </label>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <input
                      type={showCustomKey ? 'text' : 'password'}
                      id="customApiKeyInput"
                      className="form-control"
                      placeholder="Leave blank for local Ollama without auth"
                      value={customApiKey}
                      onChange={(e) => setCustomApiKey(e.target.value)}
                      style={{ flex: 1, fontSize: '0.85rem', fontFamily: 'monospace', padding: '8px 12px' }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowCustomKey(!showCustomKey)}
                      style={{ padding: '8px 10px' }}
                    >
                      {showCustomKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* 4. Custom Model Name */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, display: 'block', marginBottom: '4px' }}>
                    Model Identifier:
                  </label>
                  <input
                    type="text"
                    id="customApiModelInput"
                    className="form-control"
                    placeholder="llama3.3, deepseek-r1, qwen2.5"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    style={{ fontSize: '0.85rem', fontFamily: 'monospace', padding: '8px 12px' }}
                  />
                </div>
              </div>

              {/* Action row & Feedback */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', paddingTop: '6px', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: customFeedback.startsWith('✅') ? '#10b981' : testStatus.custom_new?.success ? '#10b981' : '#ef4444' }}>
                  {customFeedback || testStatus.custom_new?.message || ''}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    id="testCustomNewBtn"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleTestCustom({ id: 'custom_new', baseUrl: customBaseUrl, apiKey: customApiKey })}
                    disabled={testStatus.custom_new?.loading}
                    style={{ padding: '7px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Zap size={14} /> {testStatus.custom_new?.loading ? 'Testing...' : 'Test API Endpoint'}
                  </button>
                  <button
                    type="button"
                    id="saveCustomApiBtn"
                    className="btn btn-primary btn-sm"
                    onClick={handleSaveCustomApi}
                    style={{ padding: '7px 16px', fontWeight: 700, background: '#10b981', borderColor: '#10b981' }}
                  >
                    <Check size={15} /> Save & Activate Custom API
                  </button>
                </div>
              </div>
            </div>

            {/* SECTION 3: SAVED CUSTOM APIS VAULT */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <label style={{ fontSize: '0.9rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Key size={15} color="var(--accent-color)" /> Saved Custom APIs & Engines:
                </label>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  {customApisList.length} saved custom API{customApisList.length === 1 ? '' : 's'}
                </span>
              </div>

              {customApisList.length === 0 ? (
                <div style={{ padding: '14px', borderRadius: '10px', background: 'var(--bg-secondary)', border: '1px dashed var(--border-color)', textAlign: 'center', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                  No custom APIs saved yet. Fill out the form above to add a named custom API (e.g. "Office Ollama").
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {customApisList.map((item) => {
                    const isItemActive = aiConfig.provider === 'custom' && (aiConfig.customApiId === item.id || aiConfig.customName === item.name);
                    const itemTest = testStatus[item.id];
                    return (
                      <div
                        key={item.id}
                        style={{
                          padding: '12px 16px',
                          borderRadius: '10px',
                          border: isItemActive ? '2px solid #10b981' : '1px solid var(--border-color)',
                          background: isItemActive ? 'rgba(16, 185, 129, 0.08)' : 'var(--bg-secondary)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '8px'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <strong style={{ fontSize: '0.92rem', color: 'var(--text-primary)' }}>{item.name}</strong>
                              <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 700 }}>
                                CUSTOM API
                              </span>
                              {isItemActive && (
                                <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '10px', background: '#10b981', color: '#ffffff', fontWeight: 700 }}>
                                  Active Now
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                              Endpoint: <code>{item.baseUrl}</code> • Model: <code>{item.modelName}</code>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            {!isItemActive ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleActivateCustom(item)}
                                style={{ fontSize: '0.78rem', padding: '4px 10px', fontWeight: 700 }}
                              >
                                Activate
                              </button>
                            ) : (
                              <span style={{ fontSize: '0.78rem', color: '#10b981', fontWeight: 700, padding: '4px 8px' }}>
                                ✓ Active
                              </span>
                            )}
                            <button
                              type="button"
                              id={`testCustomVaultBtn_${item.id}`}
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleTestCustom(item)}
                              disabled={itemTest?.loading}
                              style={{ fontSize: '0.78rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                            >
                              <Zap size={12} /> {itemTest?.loading ? 'Testing...' : 'Test API'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteCustom(item.id)}
                              style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '6px' }}
                              title="Delete this custom API"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </div>

                        {itemTest?.message && (
                          <div style={{
                            padding: '6px 10px',
                            borderRadius: '6px',
                            fontSize: '0.76rem',
                            fontWeight: 600,
                            background: itemTest.success ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                            color: itemTest.success ? '#10b981' : '#ef4444',
                            border: itemTest.success ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(239, 68, 68, 0.25)'
                          }}>
                            {itemTest.message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* SECTION 4: STANDARD PROVIDERS (COLLAPSIBLE) */}
            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden', marginBottom: '14px' }}>
              <div
                onClick={() => setShowOtherProviders(!showOtherProviders)}
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
                  <Globe size={14} color="var(--accent-color)" /> Other Cloud Providers (Groq, OpenAI, Anthropic)
                </span>
                {showOtherProviders ? <ChevronUp size={16} color="var(--text-secondary)" /> : <ChevronDown size={16} color="var(--text-secondary)" />}
              </div>

              {showOtherProviders && (
                <div style={{ padding: '14px 16px', borderTop: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                    {['groq', 'openai', 'anthropic'].map((pId) => (
                      <button
                        key={pId}
                        type="button"
                        className={`btn ${otherProvider === pId ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                        onClick={() => {
                          setOtherProvider(pId);
                          setOtherKey(getSavedKeyForProvider(pId) || '');
                          setOtherFeedback('');
                        }}
                      >
                        {pId.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
                    <input
                      type={showOtherKey ? 'text' : 'password'}
                      className="form-control"
                      placeholder={`Paste ${otherProvider.toUpperCase()} Key...`}
                      value={otherKey}
                      onChange={(e) => setOtherKey(e.target.value)}
                      style={{ flex: 1, fontSize: '0.85rem', fontFamily: 'monospace', padding: '8px 12px' }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowOtherKey(!showOtherKey)}
                      style={{ padding: '8px 10px' }}
                    >
                      {showOtherKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                    <button
                      type="button"
                      id="testOtherProviderBtn"
                      className="btn btn-secondary btn-sm"
                      onClick={handleTestOtherProvider}
                      disabled={testStatus[otherProvider]?.loading || !otherKey.trim()}
                      style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    >
                      <Zap size={13} /> {testStatus[otherProvider]?.loading ? 'Testing...' : 'Test Key'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleSaveOtherProvider}
                      style={{ padding: '8px 14px' }}
                    >
                      Save & Activate
                    </button>
                  </div>
                  {testStatus[otherProvider]?.message && (
                    <div style={{ fontSize: '0.8rem', color: testStatus[otherProvider].success ? '#10b981' : '#ef4444', fontWeight: 600, marginBottom: '6px' }}>
                      {testStatus[otherProvider].message}
                    </div>
                  )}
                  {otherFeedback && <div style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>{otherFeedback}</div>}
                </div>
              )}
            </div>

            {/* SECTION 5: SYSTEM & .ENV DETECTED KEYS (COLLAPSIBLE) */}
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
                  <Terminal size={14} color="var(--accent-color)" /> System & .env Detected Environment Variables
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
                <Sparkles size={14} color="var(--accent-color)" /> Bangladesh Government / Bangla Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {BANGLA_FONTS.map((font) => (
                  <div
                    key={font.id}
                    onClick={() => handleSelectBangla(font.id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: currentBangla === font.id ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                      background: currentBangla === font.id ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
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
                        নমুনা: গণপ্রজাতন্ত্রী বাংলাদেশ সরকার — স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়
                      </div>
                    </div>
                    {currentBangla === font.id && <Check size={18} color="var(--accent-color)" />}
                  </div>
                ))}
              </div>
            </div>

            {/* English Font Selector */}
            <div className="form-group" style={{ marginTop: '20px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={14} color="var(--accent-color)" /> English Document & Minutes Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {ENGLISH_FONTS.map((font) => (
                  <div
                    key={font.id}
                    onClick={() => handleSelectEnglish(font.id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: currentEnglish === font.id ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                      background: currentEnglish === font.id ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
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
                        Sample: Weekly Strategic, Programmatic and Review Meeting Minutes
                      </div>
                    </div>
                    {currentEnglish === font.id && <Check size={18} color="var(--accent-color)" />}
                  </div>
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
              {/* Windows */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#0284c7' }}>
                  <Monitor size={18} /> Windows Portable (.exe & .bat)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Run `python build_windows_exe.py` to generate a standalone portable `.exe` or use `Launch_App.bat` for instant zero-dependency launch.
                </div>
              </div>

              {/* Linux */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#f59e0b' }}>
                  <Terminal size={18} /> Linux (Ubuntu / Debian / AppImage / Docker)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Runs natively with Python 3.11+ & Uvicorn. Packaged as a standalone Linux ELF binary via PyInstaller or self-contained Docker container.
                </div>
              </div>

              {/* macOS */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#a855f7' }}>
                  <Apple size={18} /> macOS (.app & .dmg Bundle)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Compiles into a native `.app` bundle using PyInstaller on macOS with WebKit native windowing (pywebview).
                </div>
              </div>

              {/* Android & iOS */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#10b981' }}>
                  <Smartphone size={18} /> Android (APK) & iOS (PWA / Mobile Web)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Built as a Progressive Web App (PWA) with offline support or compiled into an Android APK via Capacitor using `build_android_apk.py`.
                </div>
              </div>
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
                  {/* Security Score */}
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>Security Score</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: auditData.security?.score >= 90 ? '#10b981' : '#f59e0b', marginTop: '2px' }}>
                      {auditData.security?.score ?? 100}/100
                    </div>
                    <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: '4px', background: auditData.security?.status === 'SECURE' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)', color: auditData.security?.status === 'SECURE' ? '#10b981' : '#f59e0b', fontWeight: 700 }}>
                      {auditData.security?.status ?? 'SECURE'}
                    </span>
                  </div>

                  {/* Toolchains */}
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>OCR & Media Engine</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: auditData.toolchains?.tesseract_ocr?.found ? '#10b981' : '#3b82f6', marginTop: '4px' }}>
                      {auditData.toolchains?.tesseract_ocr?.found ? 'OCR Ready' : 'AI Vision'}
                    </div>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                      FFmpeg: {auditData.toolchains?.ffmpeg?.found ? 'Active' : 'Missing'}
                    </span>
                  </div>

                  {/* Build Health */}
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>Frontend Build</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: auditData.build?.frontend_dist_exists ? '#10b981' : '#ef4444', marginTop: '4px' }}>
                      {auditData.build?.frontend_dist_exists ? 'Compiled' : 'Not Built'}
                    </div>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                      Dist: {auditData.build?.frontend_dist_age_hours != null ? `${auditData.build.frontend_dist_age_hours}h ago` : 'Ready'}
                    </span>
                  </div>

                  {/* Tasks / Code Debt */}
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>Code Backlog</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
                      {auditData.tasks?.total_code_debt_items ?? 0}
                    </div>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                      Active TODOs
                    </span>
                  </div>
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
                      <span><strong>OCR Engine:</strong> {auditData.toolchains?.tesseract_ocr?.found ? 'Tesseract Local Active' : 'Gemini/OpenAI Vision Active'}</span>
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
                      <Sparkles size={15} color="#f59e0b" /> Daily Improvement Recommendations
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
