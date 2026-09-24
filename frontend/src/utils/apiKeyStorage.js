// Centralized API Key Management & Provider Storage (Gemini, Local Whisper, OpenAI-compatible custom endpoint)

export const PROVIDERS = [
  {
    id: 'gemini',
    name: 'Google Gemini (Live & Flash)',
    shortName: 'Gemini',
    tag: 'Default (Live Audio STT & Flash Minutes)',
    badgeColor: '#0284c7',
    defaultSTT: 'gemini-3.5-transcribe',
    defaultLLM: 'gemini-3.8-flash',
    defaultBaseUrl: '',
    placeholder: 'Paste Google Gemini key (e.g. AIzaSy...)',
    keyPrefix: 'AIzaSy',
    docsUrl: 'https://aistudio.google.com/app/apikey'
  },
  {
    id: 'local_whisper',
    name: 'Local Whisper (Offline & Hardware-Adaptive)',
    shortName: 'Local Whisper',
    tag: 'Offline Fallback (Auto Hardware Sizing)',
    badgeColor: '#10b981',
    defaultSTT: 'auto',
    defaultLLM: 'local_synthesis',
    defaultBaseUrl: '',
    placeholder: 'No API Key required (Offline Engine)',
    keyPrefix: '',
    docsUrl: ''
  },
  {
    id: 'openai_compatible',
    name: 'Custom / OpenRouter / Local (OpenAI-Compatible)',
    shortName: 'Custom API',
    tag: 'OpenRouter, DeepSeek, Ollama, LM Studio, or any OpenAI-compatible endpoint',
    badgeColor: '#f59e0b',
    defaultSTT: '',
    defaultLLM: '',
    defaultBaseUrl: '',
    placeholder: 'Paste API key (leave blank for local Ollama/LM Studio)',
    keyPrefix: '',
    docsUrl: 'https://openrouter.ai/docs'
  }
];

// Quick presets for the OpenAI-compatible custom endpoint: they only prefill the Settings fields.
export const CUSTOM_API_PRESETS = [
  { id: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', model: 'deepseek/deepseek-v4.1-flash', key: null },
  { id: 'deepseek', label: 'DeepSeek (direct)', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat', key: null },
  { id: 'ollama', label: 'Ollama (local)', baseUrl: 'http://localhost:11434/v1', model: 'llama3.1', key: 'ollama' },
  { id: 'lmstudio', label: 'LM Studio (local)', baseUrl: 'http://localhost:1234/v1', model: '', key: null },
  { id: 'other', label: 'Other / custom', baseUrl: '', model: '', key: '' }
];


export const getSavedKeyForProvider = (providerId) => {
  try {
    const direct = localStorage.getItem(`apiKey_${providerId}`);
    if (direct && direct.trim()) return direct.trim();

    // Check in easd_api_keys_list
    const saved = localStorage.getItem('easd_api_keys_list');
    if (saved) {
      const list = JSON.parse(saved);
      const found = list.find((k) => k.provider === providerId);
      if (found && found.key && found.key.trim()) return found.key.trim();
    }

    // Check if active provider matches
    const activeProvider = localStorage.getItem('aiProvider') || 'gemini';
    if (activeProvider === providerId) {
      const activeKey = localStorage.getItem('apiKey');
      if (activeKey && activeKey.trim()) return activeKey.trim();
    }
  } catch (e) {}
  return '';
};

export const getSavedBaseUrlForProvider = (providerId) => {
  try {
    const direct = localStorage.getItem(`baseUrl_${providerId}`);
    if (direct) return direct;
    const providerObj = PROVIDERS.find((p) => p.id === providerId);
    return providerObj ? providerObj.defaultBaseUrl : '';
  } catch (e) {}
  return '';
};

export const saveKeyForProvider = (providerId, keyVal, baseUrl = '') => {
  try {
    const trimmed = (keyVal || '').trim();
    localStorage.setItem(`apiKey_${providerId}`, trimmed);
    if (baseUrl) {
      localStorage.setItem(`baseUrl_${providerId}`, baseUrl);
    }

    // Update keys list
    let list = [];
    try {
      const saved = localStorage.getItem('easd_api_keys_list');
      if (saved) list = JSON.parse(saved);
    } catch (e) {}

    const idx = list.findIndex((k) => k.provider === providerId);
    if (idx >= 0) {
      list[idx].key = trimmed;
      if (baseUrl) list[idx].baseUrl = baseUrl;
    } else {
      const providerObj = PROVIDERS.find((p) => p.id === providerId);
      list.push({
        id: providerId,
        name: `${providerObj?.name || providerId} Key`,
        provider: providerId,
        key: trimmed,
        baseUrl: baseUrl || '',
        masked: true,
        isActive: false
      });
    }
    localStorage.setItem('easd_api_keys_list', JSON.stringify(list));
  } catch (e) {
    console.error('Failed to save key for provider:', e);
  }
};


export const getActiveApiDisplayName = (aiConfig) => {
  if (!aiConfig) {
    const savedCustomName = localStorage.getItem('activeCustomApiName');
    const savedProv = localStorage.getItem('aiProvider') || 'gemini';
    if (savedProv === 'custom' && savedCustomName) return savedCustomName;
    const found = PROVIDERS.find((p) => p.id === savedProv);
    return found ? `${found.shortName} API` : 'Gemini API';
  }

  if (aiConfig.provider === 'custom') {
    if (aiConfig.customName && aiConfig.customName.trim()) return aiConfig.customName.trim();
    if (aiConfig.name && aiConfig.name.trim()) return aiConfig.name.trim();
    const savedCustomName = localStorage.getItem('activeCustomApiName');
    if (savedCustomName && savedCustomName.trim()) return savedCustomName.trim();
    return 'Custom API';
  }

  const p = PROVIDERS.find((prov) => prov.id === aiConfig.provider);
  if (p) {
    return p.shortName.endsWith('API') ? p.shortName : `${p.shortName} API`;
  }
  return 'Gemini API';
};

export const activateProvider = (providerId, setAiConfig) => {
  const providerObj = PROVIDERS.find((p) => p.id === providerId) || PROVIDERS[0];
  const savedKey = getSavedKeyForProvider(providerId);
  const savedBaseUrl = getSavedBaseUrlForProvider(providerId) || providerObj.defaultBaseUrl;

  try {
    localStorage.setItem('aiProvider', providerId);
    localStorage.setItem('apiKey', savedKey);
    localStorage.setItem('baseUrl', savedBaseUrl);
    localStorage.setItem('transcriptionModel', providerObj.defaultSTT);
    localStorage.setItem('summarizationModel', providerObj.defaultLLM);
    localStorage.setItem('modelName', providerObj.defaultLLM);
    localStorage.removeItem('activeCustomApiId');
    localStorage.removeItem('activeCustomApiName');
  } catch (e) {}

  if (typeof setAiConfig === 'function') {
    setAiConfig((prev) => ({
      ...prev,
      provider: providerId,
      name: providerObj.name,
      customName: '',
      customApiId: null,
      apiKey: savedKey,
      baseUrl: savedBaseUrl,
      transcriptionModel: providerObj.defaultSTT,
      summarizationModel: providerObj.defaultLLM,
      modelName: providerObj.defaultLLM
    }));
  }

  return {
    provider: providerId,
    apiKey: savedKey,
    baseUrl: savedBaseUrl,
    transcriptionModel: providerObj.defaultSTT,
    summarizationModel: providerObj.defaultLLM
  };
};

// --- QUICK SELECTION BUTTON CONFIGURATIONS ---

export const QUICK_STT_MODELS = [
  { id: 'gemini-3.5-transcribe', label: 'Gemini 3.5 Transcribe Live (Default Cloud)', shortLabel: 'Gemini 3.5 Transcribe', provider: 'gemini' },
  { id: 'auto', label: 'Local Whisper (Hardware Adaptive Fallback)', shortLabel: 'Local Whisper', provider: 'local_whisper' }
];

export const QUICK_LLM_MODELS = [
  { id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash (Fast Executive Synthesis - Low)', shortLabel: 'Gemini Flash 3.8 Low', provider: 'gemini' },
  { id: 'local_synthesis', label: 'Local Deep Semantic Synthesis (Offline)', shortLabel: 'Local Synthesis', provider: 'local_whisper' }
];

// --- SERVER PERSISTENCE & TWO-WAY API TESTING ---

const loadServerSettings = async () => {
  try {
    const res = await fetch('/api/settings');
    if (res.ok) {
      const data = await res.json();
      if (data.status === 'success' && data.settings) {
        return data.settings;
      }
    }
  } catch (e) {
    console.warn('Failed to load settings from server:', e);
  }
  return null;
};

export const saveServerSettings = async (settings) => {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (res.ok) {
      const data = await res.json();
      return data;
    }
  } catch (e) {
    console.error('Failed to save settings to server:', e);
  }
  return null;
};

export const testAiEngine = async ({
  test_type = 'both',
  stt_provider,
  stt_model,
  stt_api_key,
  llm_provider,
  llm_model,
  llm_api_key,
  base_url
}) => {
  try {
    const res = await fetch('/api/test_engine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        test_type,
        stt_provider,
        stt_model,
        stt_api_key,
        llm_provider,
        llm_model,
        llm_api_key,
        base_url
      })
    });
    const data = await res.json();
    return data;
  } catch (e) {
    return {
      status: 'error',
      message: e.message || 'Connection failed'
    };
  }
};
