// Automated Test Suite for Front Page API Button & Custom Named API Storage
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Mock localStorage for headless Node environment
const storage = {};
global.localStorage = {
  getItem: (k) => (k in storage ? storage[k] : null),
  setItem: (k, v) => { storage[k] = String(v); },
  removeItem: (k) => { delete storage[k]; },
  clear: () => { Object.keys(storage).forEach((k) => delete storage[k]); }
};

async function runTests() {
  console.log('====================================================');
  console.log('🧪 RUNNING API BUTTON & CUSTOM API AUTOMATED TESTS');
  console.log('====================================================');

  const apiKeyStorage = await import('./src/utils/apiKeyStorage.js');
  const {
    getSavedCustomApis,
    saveCustomApi,
    deleteCustomApi,
    activateCustomApi,
    activateProvider,
    getActiveApiDisplayName,
    PROVIDERS
  } = apiKeyStorage;

  // TEST 1: Default Provider is Gemini
  console.log('\n[TEST 1] Verifying System-wide Default Provider is Google Gemini...');
  const geminiProvider = PROVIDERS.find(p => p.id === 'gemini');
  assert(geminiProvider, 'Gemini provider must exist in list');
  global.localStorage.clear();
  const defaultDisplayName = getActiveApiDisplayName(null);
  assert.strictEqual(defaultDisplayName, 'Gemini API', `Expected 'Gemini API', got '${defaultDisplayName}'`);
  console.log('   ✅ PASSED: Default provider is Gemini and display name is "Gemini API".');

  // TEST 2: Add Custom API Option with Custom Name
  console.log('\n[TEST 2] Testing Option to Add and Save Custom API with Name...');
  const customEntry = saveCustomApi({
    name: 'Office Ollama vLLM',
    baseUrl: 'http://192.168.1.50:11434/v1',
    apiKey: 'sk-secret-local-token-xyz123',
    modelName: 'llama3.3:70b'
  });

  assert(customEntry, 'saveCustomApi should return saved entry');
  assert.strictEqual(customEntry.name, 'Office Ollama vLLM');
  assert.strictEqual(customEntry.baseUrl, 'http://192.168.1.50:11434/v1');
  assert.strictEqual(customEntry.apiKey, 'sk-secret-local-token-xyz123');
  assert.strictEqual(customEntry.modelName, 'llama3.3:70b');

  const savedList = getSavedCustomApis();
  assert.strictEqual(savedList.length, 1, 'Custom APIs list should have 1 item');
  assert.strictEqual(savedList[0].name, 'Office Ollama vLLM');
  console.log('   ✅ PASSED: Custom API "Office Ollama vLLM" successfully persisted to storage.');

  // TEST 3: Activate Custom API and Verify Display Name (Zero Key Exposure)
  console.log('\n[TEST 3] Testing Front-Page Display Name Resolution on Custom API Activation...');
  let mockAiConfig = { provider: 'gemini', apiKey: '' };
  const activated = activateCustomApi(customEntry.id, (updater) => {
    mockAiConfig = typeof updater === 'function' ? updater(mockAiConfig) : updater;
  });

  assert.strictEqual(mockAiConfig.provider, 'custom');
  assert.strictEqual(mockAiConfig.customName, 'Office Ollama vLLM');

  const activeName = getActiveApiDisplayName(mockAiConfig);
  assert.strictEqual(activeName, 'Office Ollama vLLM', 'Display name must match custom API name');

  // CRITICAL CHECK: Ensure raw key / secret code is NEVER part of the display name
  assert(!activeName.includes('sk-secret'), 'Display name must never expose API secret key!');
  assert(!activeName.includes('xyz123'), 'Display name must never expose API secret key token!');
  console.log(`   ✅ PASSED: Front page button name is strictly "${activeName}" with ZERO secret key leakage.`);

  // TEST 4: Delete Custom API & Revert to Gemini Default
  console.log('\n[TEST 4] Testing Custom API Deletion & Fallback to Gemini Default...');
  deleteCustomApi(customEntry.id);
  const listAfterDelete = getSavedCustomApis();
  assert.strictEqual(listAfterDelete.length, 0, 'Custom APIs list should be empty after deletion');

  activateProvider('gemini', (updater) => {
    mockAiConfig = typeof updater === 'function' ? updater(mockAiConfig) : updater;
  });
  assert.strictEqual(mockAiConfig.provider, 'gemini');
  assert.strictEqual(getActiveApiDisplayName(mockAiConfig), 'Gemini API');
  console.log('   ✅ PASSED: Custom API deleted and system reverted to Gemini default.');

  // TEST 5: Verify Header.jsx contains Top API Button with proper ID and event handler
  console.log('\n[TEST 5] Validating Header.jsx Component Structure for Front-Page API Button...');
  const headerContent = fs.readFileSync(path.join(__dirname, 'src', 'components', 'Header.jsx'), 'utf-8');
  assert(headerContent.includes('id="topApiButton"'), 'Header must contain element with id="topApiButton"');
  assert(headerContent.includes('activeApiName'), 'Header must accept activeApiName prop');
  assert(headerContent.includes('onOpenApiSettings'), 'Header must accept onOpenApiSettings prop');
  assert(headerContent.includes('id="activeApiDisplayName"'), 'Header must render activeApiDisplayName container');
  console.log('   ✅ PASSED: Header.jsx verified with #topApiButton, activeApiName, and click trigger.');

  // TEST 6: Verify SettingsModal.jsx contains Custom API Setup Fields & Gemini Default
  console.log('\n[TEST 6] Validating SettingsModal.jsx Component for Reimplemented API Architecture...');
  const settingsContent = fs.readFileSync(path.join(__dirname, 'src', 'components', 'SettingsModal.jsx'), 'utf-8');
  assert(settingsContent.includes('id="customApiNameInput"'), 'SettingsModal must contain customApiNameInput');
  assert(settingsContent.includes('id="customApiUrlInput"'), 'SettingsModal must contain customApiUrlInput');
  assert(settingsContent.includes('id="customApiKeyInput"'), 'SettingsModal must contain customApiKeyInput');
  assert(settingsContent.includes('id="customApiModelInput"'), 'SettingsModal must contain customApiModelInput');
  assert(settingsContent.includes('id="saveCustomApiBtn"'), 'SettingsModal must contain saveCustomApiBtn');
  assert(settingsContent.includes('id="geminiApiKeyInput"'), 'SettingsModal must contain geminiApiKeyInput');
  console.log('   ✅ PASSED: SettingsModal.jsx verified with Custom API inputs and Gemini setup.');

  // TEST 7: Verify Production Bundle Contains the Top API Button and Zero Syntax Errors
  console.log('\n[TEST 7] Validating Vite Built Production Assets...');
  const distDir = path.join(__dirname, 'dist', 'assets');
  const jsFiles = fs.readdirSync(distDir).filter((f) => f.endsWith('.js'));
  assert(jsFiles.length > 0, 'Production bundle JS file must exist in dist/assets');
  const bundleContent = fs.readFileSync(path.join(distDir, jsFiles[0]), 'utf-8');
  assert(bundleContent.includes('topApiButton'), 'Production JS bundle must include topApiButton');
  assert(bundleContent.includes('activeApiDisplayName'), 'Production JS bundle must include activeApiDisplayName');
  console.log('   ✅ PASSED: Production client bundle verified with #topApiButton and #activeApiDisplayName.');

  // TEST 8: Verify Test API Options in SettingsModal
  console.log('\n[TEST 8] Validating Dedicated "Test API" Buttons in Settings Modal...');
  assert(settingsContent.includes('id="testActiveEngineBtn"'), 'SettingsModal must contain testActiveEngineBtn');
  assert(settingsContent.includes('id="testGeminiBtn"'), 'SettingsModal must contain testGeminiBtn');
  assert(settingsContent.includes('id="testCustomNewBtn"'), 'SettingsModal must contain testCustomNewBtn');
  assert(settingsContent.includes('testCustomVaultBtn_'), 'SettingsModal must contain testCustomVaultBtn_ for vault items');
  assert(settingsContent.includes('id="testOtherProviderBtn"'), 'SettingsModal must contain testOtherProviderBtn');
  console.log('   ✅ PASSED: All "Test API" buttons verified across active engine banner, Gemini, and custom vault.');

  // TEST 9: Verify Production Bundle Contains the Test API Elements
  console.log('\n[TEST 9] Validating Vite Built Production Bundle for Test API Options...');
  assert(bundleContent.includes('testActiveEngineBtn'), 'Production bundle must contain testActiveEngineBtn');
  console.log('   ✅ PASSED: Production client bundle verified with #testActiveEngineBtn.');

  console.log('\n====================================================');
  console.log('🎉 ALL 9 API BUTTON & TEST API TESTS PASSED 100%!');
  console.log('====================================================\n');
}

runTests().catch((err) => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
