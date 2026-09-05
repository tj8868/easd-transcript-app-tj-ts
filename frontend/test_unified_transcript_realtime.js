// Automated verification for Single Unified Transcript Section & High-Visibility Real-Time Speech Monitor
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log("=== Testing Single Unified Transcript & Real-Time Speech Monitor ===");

// 1. Verify Transcripts.jsx content
const transcriptsPath = path.join(__dirname, 'src', 'components', 'Transcripts.jsx');
const transcriptsCode = fs.readFileSync(transcriptsPath, 'utf8');

// Check 1: Must NOT have dual columns or separate Bangla and English textareas
if (transcriptsCode.includes('grid-2col')) {
  console.error("FAIL: Transcripts.jsx still contains 'grid-2col' dual split!");
  process.exit(1);
} else {
  console.log("✓ PASS: Dual column 'grid-2col' removed from Transcripts.jsx");
}

if (transcriptsCode.includes('Bangla Transcript (বাংলা ট্রান্সক্রিপ্ট):') || transcriptsCode.includes('English Transcript:')) {
  console.error("FAIL: Transcripts.jsx still contains separate Bangla/English section headings!");
  process.exit(1);
} else {
  console.log("✓ PASS: Separate Bangla and English section headers successfully removed");
}

// Check 2: Must have 1 unified transcript textarea
if (!transcriptsCode.includes('id="unified-transcript-textarea"')) {
  console.error("FAIL: Transcripts.jsx missing unified-transcript-textarea!");
  process.exit(1);
} else {
  console.log("✓ PASS: 1 unified transcript textarea present in Transcripts.jsx");
}

// Check 3: Must have single Copy, Download, and Clear buttons
if (!transcriptsCode.includes('handleCopy') || !transcriptsCode.includes('handleDownload') || !transcriptsCode.includes('handleClear')) {
  console.error("FAIL: Transcripts.jsx missing unified action handlers!");
  process.exit(1);
} else {
  console.log("✓ PASS: Unified Copy, Download, and Clear action handlers present");
}

// 2. Verify LiveRecordStudio.jsx content
const liveStudioPath = path.join(__dirname, 'src', 'components', 'LiveRecordStudio.jsx');
const liveStudioCode = fs.readFileSync(liveStudioPath, 'utf8');

// Check 4: Must have High-Visibility Real-Time Speech Monitor
if (!liveStudioCode.includes('id="realtime-speech-monitor"') || !liveStudioCode.includes('id="live-speech-stream-display"')) {
  console.error("FAIL: LiveRecordStudio.jsx missing realtime-speech-monitor or live-speech-stream-display!");
  process.exit(1);
} else {
  console.log("✓ PASS: High-visibility real-time speech monitor container present");
}

// Check 5: Must have real-time interim speech highlighting
if (!liveStudioCode.includes('interimText') || !liveStudioCode.includes('#34d399')) {
  console.error("FAIL: LiveRecordStudio.jsx missing glowing real-time interim speech highlighting!");
  process.exit(1);
} else {
  console.log("✓ PASS: Glowing real-time interim speech highlighting present");
}

// Check 6: Must have language switcher pills (Auto, Bangla, English)
if (!liveStudioCode.includes('handleLanguageChange') || !liveStudioCode.includes('🇧🇩 বাংলা')) {
  console.error("FAIL: LiveRecordStudio.jsx missing language switcher pills!");
  process.exit(1);
} else {
  console.log("✓ PASS: Real-time language switcher pills (Auto, Bangla, English) present");
}

// Check 7: Must have live sync to transcript
if (!liveStudioCode.includes('onLiveTranscriptSync')) {
  console.error("FAIL: LiveRecordStudio.jsx missing onLiveTranscriptSync callback!");
  process.exit(1);
} else {
  console.log("✓ PASS: onLiveTranscriptSync callback connected for real-time speech streaming");
}

// 3. Verify App.jsx consolidation
const appPath = path.join(__dirname, 'src', 'App.jsx');
const appCode = fs.readFileSync(appPath, 'utf8');

if (!appCode.includes('const [transcript, setTranscript] = useState') || !appCode.includes('onLiveTranscriptSync={handleLiveTranscriptSync}')) {
  console.error("FAIL: App.jsx missing consolidated transcript state or live sync handler!");
  process.exit(1);
} else {
  console.log("✓ PASS: App.jsx unified transcript state and live sync connected");
}

// Check 8: NavTabs.jsx has singular 'Transcript'
const navTabsPath = path.join(__dirname, 'src', 'components', 'NavTabs.jsx');
const navTabsCode = fs.readFileSync(navTabsPath, 'utf8');
if (!navTabsCode.includes("label: 'Transcript'")) {
  console.error("FAIL: NavTabs.jsx missing singular 'Transcript' label!");
  process.exit(1);
} else {
  console.log("✓ PASS: NavTabs.jsx correctly updated to singular 'Transcript'");
}

console.log("\n=== ALL 8 UNIFIED REAL-TIME TRANSCRIPT TESTS PASSED ===");
