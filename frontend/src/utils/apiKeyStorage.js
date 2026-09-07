// Centralized API Key Management & Provider Storage

export const PROVIDERS = [
  {
    id: 'local_whisper',
    name: 'Local Whisper (Offline & Free)',
    shortName: 'Local Whisper',
    tag: '⚡ 100% Free / Auto-Detects Bangla & English',
    badgeColor: '#10b981',
    defaultSTT: 'whisper-small-int8',
    defaultLLM: 'gemini-3.7-flash',
    defaultBaseUrl: '',
    placeholder: 'No API Key required (Offline Engine)',
    keyPrefix: '',
    docsUrl: ''
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    shortName: 'Gemini',
    tag: '⭐ Recommended (Default)',
    badgeColor: '#0284c7',
    defaultSTT: 'gemini-3.5-flash-lite',
    defaultLLM: 'gemini-3.7-flash',
    defaultBaseUrl: '',
    placeholder: 'Paste Google Gemini key (e.g. AIzaSy...)',
    keyPrefix: 'AIzaSy',
    docsUrl: 'https://aistudio.google.com/app/apikey'
  },
  {
    id: 'custom',
    name: 'Custom API (Local / Remote)',
    shortName: 'Custom API',
    tag: 'Self-Hosted / OpenAI-Compatible',
    badgeColor: '#10b981',
    defaultSTT: 'whisper-large-v3-turbo',
    defaultLLM: 'llama3.3',
    defaultBaseUrl: 'http://localhost:11434/v1',
    placeholder: 'Optional Bearer Token or API key',
    keyPrefix: '',
    docsUrl: 'https://ollama.com/'
  },
  {
    id: 'groq',
    name: 'Groq Cloud',
    shortName: 'Groq',
    tag: 'Ultra-Fast Whisper',
    badgeColor: '#8b5cf6',
    defaultSTT: 'whisper-large-v3-turbo',
    defaultLLM: 'llama-3.3-70b-versatile',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    placeholder: 'Paste Groq API key (e.g. gsk_...)',
    keyPrefix: 'gsk_',
    docsUrl: 'https://console.groq.com/keys'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    shortName: 'GPT-4o',
    tag: 'Flagship & Whisper',
    badgeColor: '#059669',
    defaultSTT: 'whisper-1',
    defaultLLM: 'gpt-4o-mini',
    defaultBaseUrl: 'https://api.openai.com/v1',
    placeholder: 'Paste OpenAI key (e.g. sk-proj-... or sk-...)',
    keyPrefix: 'sk-',
    docsUrl: 'https://platform.openai.com/api-keys'
  },
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    shortName: 'Claude',
    tag: 'Executive Reasoning',
    badgeColor: '#d97706',
    defaultSTT: 'gemini-3.5-flash-lite',
    defaultLLM: 'claude-3-5-sonnet-20241022',
    defaultBaseUrl: '',
    placeholder: 'Paste Anthropic key (e.g. sk-ant-api03-...)',
    keyPrefix: 'sk-ant-',
    docsUrl: 'https://console.anthropic.com/'
  }
];

export const detectProviderFromKey = (keyVal) => {
  const trimmed = (keyVal || '').trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('AIzaSy') || trimmed.startsWith('AQ.')) return 'gemini';
  if (trimmed.startsWith('sk-ant-')) return 'anthropic';
  if (trimmed.startsWith('sk-proj-') || (trimmed.startsWith('sk-') && !trimmed.startsWith('sk-ant-'))) return 'openai';
  if (trimmed.startsWith('gsk_')) return 'groq';
  return null;
};

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

// --- CUSTOM NAMED APIS MANAGEMENT ---

export const getSavedCustomApis = () => {
  try {
    const saved = localStorage.getItem('easd_custom_apis_list');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch (e) {
    console.warn('Failed to load custom APIs list:', e);
  }
  return [];
};

export const saveCustomApi = ({ id, name, baseUrl, apiKey = '', modelName = '', transcriptionModel = '' }) => {
  try {
    const list = getSavedCustomApis();
    const cleanName = (name || '').trim() || 'Custom API';
    const cleanUrl = (baseUrl || '').trim() || 'http://localhost:11434/v1';
    const cleanKey = (apiKey || '').trim();
    const cleanModel = (modelName || '').trim() || 'llama3.3';
    const cleanSTT = (transcriptionModel || '').trim();

    const targetId = id || `custom_${Date.now()}`;
    const entry = {
      id: targetId,
      name: cleanName,
      provider: 'custom',
      baseUrl: cleanUrl,
      apiKey: cleanKey,
      modelName: cleanModel,
      transcriptionModel: cleanSTT,
      updatedAt: new Date().toISOString()
    };

    const idx = list.findIndex((item) => item.id === targetId);
    if (idx >= 0) {
      list[idx] = entry;
    } else {
      list.push(entry);
    }

    localStorage.setItem('easd_custom_apis_list', JSON.stringify(list));
    return entry;
  } catch (e) {
    console.error('Failed to save custom API:', e);
    return null;
  }
};

export const deleteCustomApi = (id) => {
  try {
    const list = getSavedCustomApis();
    const filtered = list.filter((item) => item.id !== id);
    localStorage.setItem('easd_custom_apis_list', JSON.stringify(filtered));
    return true;
  } catch (e) {
    console.error('Failed to delete custom API:', e);
    return false;
  }
};

export const activateCustomApi = (customApiOrId, setAiConfig) => {
  let customApi = customApiOrId;
  if (typeof customApiOrId === 'string') {
    const list = getSavedCustomApis();
    customApi = list.find((item) => item.id === customApiOrId);
  }

  if (!customApi) return null;

  try {
    localStorage.setItem('aiProvider', 'custom');
    localStorage.setItem('apiKey', customApi.apiKey || '');
    localStorage.setItem('baseUrl', customApi.baseUrl || 'http://localhost:11434/v1');
    localStorage.setItem('modelName', customApi.modelName || 'llama3.3');
    localStorage.setItem('summarizationModel', customApi.modelName || 'llama3.3');
    localStorage.setItem('transcriptionModel', customApi.transcriptionModel || 'whisper-large-v3-turbo');
    localStorage.setItem('activeCustomApiId', customApi.id);
    localStorage.setItem('activeCustomApiName', customApi.name);
  } catch (e) {}

  const newConfig = {
    provider: 'custom',
    name: customApi.name,
    customName: customApi.name,
    customApiId: customApi.id,
    apiKey: customApi.apiKey || '',
    baseUrl: customApi.baseUrl || 'http://localhost:11434/v1',
    modelName: customApi.modelName || 'llama3.3',
    summarizationModel: customApi.modelName || 'llama3.3',
    transcriptionModel: customApi.transcriptionModel || 'whisper-large-v3-turbo'
  };

  if (typeof setAiConfig === 'function') {
    setAiConfig((prev) => ({
      ...prev,
      ...newConfig
    }));
  }

  return newConfig;
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
    return `${p.shortName} API`;
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
  { id: 'whisper-small-int8', label: '⚡ Local Whisper Small (Offline & Free)', shortLabel: 'Local Whisper', provider: 'local_whisper', icon: '🎙️' },
  { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite', shortLabel: 'Gemini 3.5 STT', provider: 'gemini', icon: '🎙️' },
  { id: 'whisper-large-v3-turbo', label: 'Groq Whisper Turbo', shortLabel: 'Groq Whisper Turbo', provider: 'groq', icon: '🎙️' },
  { id: 'whisper-large-v3', label: 'Whisper Large v3', shortLabel: 'Whisper Large v3', provider: 'groq', icon: '🎙️' },
  { id: 'whisper-1', label: 'OpenAI Whisper', shortLabel: 'OpenAI Whisper', provider: 'openai', icon: '🎙️' }
];

export const QUICK_LLM_MODELS = [
  { id: 'gemini-3.7-flash', label: 'Gemini 3.7 Flash (⭐ Recommended)', shortLabel: 'Gemini 3.7 Flash', provider: 'gemini', icon: '⚡' },
  { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite (Fast)', shortLabel: 'Gemini 3.5 Lite', provider: 'gemini', icon: '⚡' },
  { id: 'llama-3.3-70b-versatile', label: 'Groq Llama 3.3', shortLabel: 'Groq Llama 3.3', provider: 'groq', icon: '⚡' },
  { id: 'gpt-4o', label: 'GPT-4o', shortLabel: 'GPT-4o', provider: 'openai', icon: '⚡' }
];

// --- SERVER PERSISTENCE & TWO-WAY API TESTING ---

export const loadServerSettings = async () => {
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
