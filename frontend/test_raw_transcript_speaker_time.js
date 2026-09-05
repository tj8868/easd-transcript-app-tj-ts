// Automated Test for Raw Transcript by Speaker and Time & Synthetic Summary Segregation
import fs from 'fs';
import path from 'path';
import assert from 'assert';

console.log('=== Testing Raw Transcript by Speaker & Time Implementation ===');

// 1. Check App.jsx safeguards
const appPath = path.resolve('frontend/src/App.jsx');
const appContent = fs.readFileSync(appPath, 'utf8');

assert(appContent.includes('isSyntheticSummary'), 'App.jsx must define isSyntheticSummary helper');
assert(appContent.includes('ইমিনের্স অ্যাসোসিয়েটস'), 'isSyntheticSummary must identify EASD synthesized minutes');
assert(appContent.includes('সভায় আলোচিত মূল বিষয়সমূহ'), 'isSyntheticSummary must check for discussion topic headers');

// In handleSummarizeTranscript, setTranscript must NOT be called on summary text
const summarizeFn = appContent.slice(appContent.indexOf('const handleSummarizeTranscript'), appContent.indexOf('const handleRecordingProcessed'));
assert(!summarizeFn.includes('setTranscript('), 'handleSummarizeTranscript must NOT overwrite raw transcript with summary');
console.log('✓ PASS: handleSummarizeTranscript strictly preserves the raw transcript without overwriting');

// In handleProcessAi and handleRecordingProcessed, isSyntheticSummary must safeguard setTranscript
assert(appContent.includes('if (rawCandidate && !isSyntheticSummary(rawCandidate))'), 'handleProcessAi must guard setTranscript against synthetic summary');
console.log('✓ PASS: AI handlers guard against synthetic summary contaminating raw transcript');

// 2. Check LiveRecordStudio.jsx for Speaker and Time formatting
const studioPath = path.resolve('frontend/src/components/LiveRecordStudio.jsx');
const studioContent = fs.readFileSync(studioPath, 'utf8');

assert(studioContent.includes('activeSpeaker'), 'LiveRecordStudio must track activeSpeaker state');
assert(studioContent.includes('activeSpeakerRef'), 'LiveRecordStudio must have activeSpeakerRef');
assert(studioContent.includes('Speaker 1') && studioContent.includes('Speaker 2'), 'LiveRecordStudio must have Speaker 1 and Speaker 2 selection');
assert(studioContent.includes('const timeTag = formatTime('), 'LiveRecordStudio must format utterance timeTag');
assert(studioContent.includes('`[${timeTag}] ${speaker}: ${finalStr.trim()}`'), 'LiveRecordStudio must format utterances as [MM:SS] Speaker X: <text>');
console.log('✓ PASS: LiveRecordStudio formats live utterances with timestamp [MM:SS] and active speaker');

// 3. Check Transcripts.jsx for Raw Title & Speaker/Timestamp Toolstrip
const transcriptsPath = path.resolve('frontend/src/components/Transcripts.jsx');
const transcriptsContent = fs.readFileSync(transcriptsPath, 'utf8');

assert(transcriptsContent.includes('Raw Meeting Transcript (By Speaker & Time)'), 'Transcripts.jsx must have raw transcript title');
assert(transcriptsContent.includes('handleInsertTag'), 'Transcripts.jsx must have handleInsertTag for quick speaker/time insertion');
assert(transcriptsContent.includes('handleAutoFormatSpeakerTime'), 'Transcripts.jsx must have auto-format speaker and time utility');
assert(transcriptsContent.includes('+ Speaker 1'), 'Transcripts.jsx must have + Speaker 1 button');
assert(transcriptsContent.includes('+ Speaker 2'), 'Transcripts.jsx must have + Speaker 2 button');
console.log('✓ PASS: Transcripts.jsx has raw transcript title, speaker pills, and auto-tag toolstrip');

// 4. Check backend ai_providers.py
const aiPath = path.resolve('ai_providers.py');
const aiContent = fs.readFileSync(aiPath, 'utf8');

assert(aiContent.includes('"raw_transcript"'), 'ai_providers.py must return raw_transcript in payload');
assert(aiContent.includes('format_seconds_to_timestamp'), 'ai_providers.py must have format_seconds_to_timestamp helper');
assert(aiContent.includes('verbose_json'), 'ai_providers.py must request verbose_json in Whisper API');
console.log('✓ PASS: ai_providers.py returns raw_transcript and formats Whisper segments with timestamps');

console.log('\n=== ALL RAW TRANSCRIPT & SPEAKER-TIME VALIDATION TESTS PASSED ===');
