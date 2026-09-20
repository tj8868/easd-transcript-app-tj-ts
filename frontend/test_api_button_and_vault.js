// Automated Test Suite for eCommunicator API Architecture & Clean Settings
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
  console.log('🧪 RUNNING eCOMMUNICATOR API & SETTINGS TESTS');
  console.log('====================================================');

  const apiKeyStorage = await import('./src/utils/apiKeyStorage.js');
  const {
    activateProvider,
    getActiveApiDisplayName,
    saveKeyForProvider,
    getSavedKeyForProvider,
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

  // TEST 2: Provider Key Management
  console.log('\n[TEST 2] Testing Key Storage for Providers...');
  saveKeyForProvider('gemini', 'AIzaSyTestKey12345');
  const savedKey = getSavedKeyForProvider('gemini');
  assert.strictEqual(savedKey, 'AIzaSyTestKey12345', 'Saved key must match stored key');
  console.log('   ✅ PASSED: Key successfully saved and retrieved.');

  // TEST 3: Header.jsx Simplification (Controls Buried in Settings)
  console.log('\n[TEST 3] Validating Header.jsx Clean Layout (Controls Buried in Settings)...');
  const headerContent = fs.readFileSync(path.join(__dirname, 'src', 'components', 'Header.jsx'), 'utf-8');
  assert(headerContent.includes('eCommunicator'), 'Header must contain eCommunicator brand');
  assert(!headerContent.includes('id="topApiButton"'), 'Top API Button must NOT be in Header (buried in settings)');
  assert(!headerContent.includes('3-Device View'), '3-Device View must NOT be in Header (buried in settings)');
  assert(headerContent.includes('onOpenSettings'), 'Header must open settings');
  console.log('   ✅ PASSED: Header is clean; technical controls are removed and buried in settings.');

  // TEST 4: SettingsModal.jsx Houses API Vault, 3-Device View & Cloud Sync
  console.log('\n[TEST 4] Validating SettingsModal.jsx Houses Buried Controls...');
  const settingsContent = fs.readFileSync(path.join(__dirname, 'src', 'components', 'SettingsModal.jsx'), 'utf-8');
  assert(settingsContent.includes('onOpenDeviceViewer'), 'SettingsModal must accept onOpenDeviceViewer');
  assert(settingsContent.includes('3-Device View'), 'SettingsModal must contain 3-Device View launcher');
  assert(settingsContent.includes('onOpenGDrive'), 'SettingsModal must accept onOpenGDrive');
  assert(settingsContent.includes('Google Drive Sync'), 'SettingsModal must contain Google Drive Sync launcher');
  assert(settingsContent.includes('Active AI Engine'), 'SettingsModal must contain Active AI Engine banner');
  console.log('   ✅ PASSED: SettingsModal contains API Vault, 3-Device View launcher, and GDrive Sync.');

  console.log('\n====================================================');
  console.log('🎉 ALL eCOMMUNICATOR SETTINGS TESTS PASSED 100%!');
  console.log('====================================================\n');
}

runTests().catch((err) => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
