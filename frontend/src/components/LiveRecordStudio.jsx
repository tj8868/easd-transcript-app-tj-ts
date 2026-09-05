import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Mic,
  Radio,
  Play,
  Pause,
  Square,
  Volume2,
  Copy,
  Check,
  Trash2,
  Send,
  Globe,
  UploadCloud,
  FolderOpen,
  Download,
  Sparkles,
  Edit2,
  FileAudio,
  Plus,
  Users,
  Cpu,
  Key,
  Zap,
  CheckCircle,
  AlertTriangle,
  FileCode,
  Edit3,
  ChevronDown,
  ChevronUp,
  FileText
} from 'lucide-react';
import { MODEL_OPTIONS_BY_PROVIDER } from './MediaInput';
import { getActiveApiDisplayName, getSavedKeyForProvider } from '../utils/apiKeyStorage';

export default function LiveRecordStudio({
  aiConfig,
  setAiConfig,
  orgContext,
  activeSkills,
  customSkillsList,
  activeTemplateId,
  onSelectTemplate,
  templates = [],
  onRecordingProcessed,
  onLiveTranscriptSync,
  onAppendToTranscript,
  onSendToBangla,
  onSendToEnglish,
  scrollToSection,
  onOpenSettings,
  directText = '',
  setDirectText,
  selectedFile,
  setSelectedFile,
  onProcessAi,
  isProcessing = false
}) {
  // Engine Verification & Direct Text State
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState(null);
  const [showDirectTextInput, setShowDirectTextInput] = useState(Boolean(directText));

  // Recording & Live State
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [language, setLanguage] = useState('auto'); // 'auto', 'bn', 'en'
  const [activeSpeaker, setActiveSpeaker] = useState('Speaker 1');
  const activeSpeakerRef = useRef('Speaker 1');
  const [liveTranscript, setLiveTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [statusText, setStatusText] = useState('Ready to record');
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isCopied, setIsCopied] = useState(false);
  const [proTranscription, setProTranscription] = useState(true);

  // Multi-take Queue State
  const [recordingsQueue, setRecordingsQueue] = useState([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [editingTakeId, setEditingTakeId] = useState(null);
  const [editingTakeName, setEditingTakeName] = useState('');
  const [editingTakeTranscript, setEditingTakeTranscript] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  // Refs
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const currentChunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const currentTakeSecondsRef = useRef(0);
  const isRecordingRef = useRef(false);
  const isPausedRef = useRef(false);
  const isStartingRecognitionRef = useRef(false);
  const fileInputRef = useRef(null);
  const transcriptBottomRef = useRef(null);
  const liveTranscriptForTakeRef = useRef('');

  useEffect(() => {
    isRecordingRef.current = isRecording;
    isPausedRef.current = isPaused;
  }, [isRecording, isPaused]);

  useEffect(() => {
    liveTranscriptForTakeRef.current = liveTranscript;
  }, [liveTranscript]);

  useEffect(() => {
    activeSpeakerRef.current = activeSpeaker;
  }, [activeSpeaker]);

  useEffect(() => {
    if (transcriptBottomRef.current) {
      transcriptBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveTranscript, interimText]);

  useEffect(() => {
    return () => {
      stopLiveInternal();
      recordingsQueue.forEach((item) => {
        if (item.url) URL.revokeObjectURL(item.url);
      });
    };
  }, []);

  const handleVerifyKey = async () => {
    setVerifying(true);
    setVerifyStatus(null);
    try {
      const p = aiConfig?.provider || 'gemini';
      const k = aiConfig?.apiKey?.trim() || getSavedKeyForProvider(p) || '';
      const u = aiConfig?.baseUrl || '';
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

  const formatTime = (totalSec) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const getSupportedMimeType = () => {
    if (typeof MediaRecorder === 'undefined') return '';
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/aac',
      'audio/ogg;codecs=opus',
      'audio/wav'
    ];
    for (const t of types) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return '';
  };

  // --- webkitSpeechRecognition Speech Detection Setup ---
  const initSpeechRecognition = (langOverride = null) => {
    // Explicitly prioritize webkitSpeechRecognition
    const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('webkitSpeechRecognition not supported in this browser. Please use Google Chrome, Microsoft Edge, or a Chromium-based browser for live speech recognition.');
      setStatusText('webkitSpeechRecognition requires Chrome or Edge browser');
      return null;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    const activeLang = langOverride || language;
    if (activeLang === 'bn') {
      recognition.lang = 'bn-BD';
    } else if (activeLang === 'en') {
      recognition.lang = 'en-US';
    } else {
      const userLang = navigator.language || 'bn-BD';
      recognition.lang = userLang.startsWith('bn') ? 'bn-BD' : 'en-US';
    }

    recognition.onstart = () => {
      isStartingRecognitionRef.current = false;
      setStatusText(`webkitSpeechRecognition active (${recognition.lang})`);
    };

    recognition.onresult = (event) => {
      let finalStr = '';
      let interimStr = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalStr += transcriptPart + ' ';
        } else {
          interimStr += transcriptPart;
        }
      }
      if (finalStr.trim()) {
        const timeTag = formatTime(currentTakeSecondsRef.current || 0);
        const speaker = activeSpeakerRef.current || 'Speaker 1';
        const formattedLine = `[${timeTag}] ${speaker}: ${finalStr.trim()}`;
        setLiveTranscript((prev) => {
          const updated = prev ? `${prev}\n${formattedLine}` : formattedLine;
          if (onLiveTranscriptSync) {
            onLiveTranscriptSync(updated);
          }
          if (onAppendToTranscript) {
            onAppendToTranscript(formattedLine);
          }
          return updated;
        });
      }
      setInterimText(interimStr);
    };

    recognition.onerror = (event) => {
      isStartingRecognitionRef.current = false;
      if (event.error === 'no-speech') return;
      console.warn('Speech recognition notice:', event.error);
    };

    recognition.onend = () => {
      isStartingRecognitionRef.current = false;
      if (isRecordingRef.current && !isPausedRef.current) {
        try {
          isStartingRecognitionRef.current = true;
          recognition.start();
        } catch (e) {
          isStartingRecognitionRef.current = false;
        }
      }
    };

    return recognition;
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    if (isRecordingRef.current && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      setTimeout(() => {
        if (isRecordingRef.current && !isPausedRef.current) {
          const rec = initSpeechRecognition(newLang);
          if (rec) {
            recognitionRef.current = rec;
            try {
              rec.start();
            } catch (err) {}
          }
        }
      }, 100);
    }
  };

  // --- Start Unified Recording & Live Transcribing ---
  const handleStartRecording = async () => {
    try {
      setStatusText('Requesting microphone...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

      // Setup audio visualizer
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const audioCtx = new AudioContext();
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        analyserRef.current = analyser;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        const updateLevel = () => {
          if (!analyserRef.current || !isRecordingRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
          const avg = sum / bufferLength;
          setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (err) {
        console.warn('Visualizer notice:', err);
      }

      currentChunksRef.current = [];
      currentTakeSecondsRef.current = 0;
      setRecordingSeconds(0);
      setLiveTranscript('');
      setInterimText('');

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);

      // Start MediaRecorder
      const mimeType = getSupportedMimeType();
      const options = mimeType ? { mimeType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          currentChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mime = mimeType || 'audio/webm';
        const blob = new Blob(currentChunksRef.current, { type: mime });
        const url = URL.createObjectURL(blob);
        const durationSec = currentTakeSecondsRef.current || 1;
        const takeNum = recordingsQueue.length + 1;
        const capturedTranscript = (liveTranscriptForTakeRef.current || '').trim();

        const newTake = {
          id: 'take_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7),
          name: `Take #${takeNum}`,
          blob: blob,
          url: url,
          duration: durationSec,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          size: (blob.size / (1024 * 1024)).toFixed(2) + ' MB',
          transcript: capturedTranscript,
          isUpload: false
        };

        setRecordingsQueue((prev) => [...prev, newTake]);
        if (capturedTranscript && onLiveTranscriptSync) {
          onLiveTranscriptSync(capturedTranscript);
        }
        setStatusText(`✓ Take #${takeNum} saved automatically to queue!`);
      };

      mediaRecorder.start(250);

      // Start Live Speech Recognition
      const recognition = initSpeechRecognition();
      if (recognition) {
        recognitionRef.current = recognition;
        isStartingRecognitionRef.current = true;
        recognition.start();
      }

      setIsRecording(true);
      setIsPaused(false);
      setStatusText('● Recording & live transcribing in progress...');
    } catch (err) {
      console.error('Error starting live record:', err);
      setStatusText('Microphone permission denied or unavailable');
      alert('Microphone error: ' + err.message);
    }
  };

  const handleTogglePause = () => {
    if (!isRecording) return;
    if (isPaused) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
        mediaRecorderRef.current.resume();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch (e) {}
      }
      setIsPaused(false);
      setStatusText('● Recording & live transcribing resumed');
    } else {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
      setIsPaused(true);
      setStatusText('⏸ Recording paused');
    }
  };

  const handleStopAndSaveTake = () => {
    stopLiveInternal();
    setIsRecording(false);
    setIsPaused(false);
    setStatusText('Processing recorded take...');
  };

  const stopLiveInternal = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try {
        audioContextRef.current.close();
      } catch (e) {}
    }
    setAudioLevel(0);
  };

  // --- Add Uploaded Audio/Video Files to Queue ---
  const handleAddUploadedFiles = (files) => {
    if (!files || files.length === 0) return;
    const newItems = [];
    Array.from(files).forEach((file, fIdx) => {
      if (setSelectedFile && fIdx === 0) {
        setSelectedFile(file);
      }
      const url = URL.createObjectURL(file);
      newItems.push({
        id: 'upload_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7) + '_' + fIdx,
        blob: file,
        url: url,
        duration: 0,
        name: file.name.replace(/\.[^/.]+$/, ''),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
        transcript: '',
        isUpload: true
      });
    });
    setRecordingsQueue((prev) => [...prev, ...newItems]);
    setStatusText(`✓ Added ${newItems.length} file(s) to multi-take queue`);
  };

  // --- Multi-Take Edit, Delete, Download ---
  const handleStartEditTake = (take) => {
    setEditingTakeId(take.id);
    setEditingTakeName(take.name);
    setEditingTakeTranscript(take.transcript || '');
  };

  const handleSaveEditTake = (takeId) => {
    setRecordingsQueue((prev) =>
      prev.map((item) => {
        if (item.id === takeId) {
          return {
            ...item,
            name: editingTakeName.trim() || item.name,
            transcript: editingTakeTranscript.trim()
          };
        }
        return item;
      })
    );
    setEditingTakeId(null);
  };

  const handleDeleteTake = (takeId) => {
    setRecordingsQueue((prev) => {
      const item = prev.find((t) => t.id === takeId);
      if (item && item.url) URL.revokeObjectURL(item.url);
      return prev.filter((t) => t.id !== takeId);
    });
  };

  const handleDownloadTake = (item) => {
    if (!item || !item.url) return;
    const mime = item.blob.type || 'audio/webm';
    const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
    const a = document.createElement('a');
    a.href = item.url;
    a.download = `Meeting_${item.name.replace(/\s+/g, '_')}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleClearAllTakes = () => {
    if (!window.confirm('Are you sure you want to clear all queued takes?')) return;
    recordingsQueue.forEach((item) => {
      if (item.url) URL.revokeObjectURL(item.url);
    });
    setRecordingsQueue([]);
    setStatusText('All takes cleared');
  };

  // --- Batch Transcribe All Takes ---
  const handleTranscribeAllTakes = async () => {
    if (recordingsQueue.length === 0) {
      alert('No takes in queue. Please record a take or upload an audio file first.');
      return;
    }

    setIsTranscribing(true);
    setStatusText(`⚡ Sending ${recordingsQueue.length} takes to AI Transcription...`);

    const formData = new FormData();
    formData.append('provider', aiConfig?.provider || 'groq');
    formData.append('api_key', (aiConfig?.apiKey || '').trim());
    formData.append('base_url', (aiConfig?.baseUrl || '').trim());
    formData.append('model_name', aiConfig?.summarizationModel || aiConfig?.modelName || 'openai/gpt-oss-120b');
    formData.append('transcription_model', aiConfig?.transcriptionModel || 'whisper-large-v3-turbo');
    formData.append('summarization_model', aiConfig?.summarizationModel || 'openai/gpt-oss-120b');
    formData.append('org_context', orgContext || '');
    formData.append('template_id', activeTemplateId || 'easd_default_minutes');

    const activeSkillPrompts = (activeSkills || []).map((sId) => {
      const found = (customSkillsList || []).find((c) => c.id === sId);
      if (found) return `[${found.category} Skill] ${found.name}: ${found.prompt}`;
      return `[Skill: ${sId}]`;
    }).join('\n');
    formData.append('custom_skills', activeSkillPrompts);

    recordingsQueue.forEach((item, index) => {
      if (item.blob instanceof File) {
        formData.append('files', item.blob);
      } else {
        const mime = item.blob.type || 'audio/webm';
        const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
        const audioFile = new File([item.blob], `take_${index + 1}_${Date.now()}.${ext}`, { type: mime });
        formData.append('files', audioFile);
      }
    });

    try {
      const res = await axios.post('/api/transcribe_and_summarize', formData);
      setIsTranscribing(false);

      if (res.data && res.data.status === 'success') {
        const payload = res.data.data;
        if (onRecordingProcessed) {
          onRecordingProcessed(payload);
        }
        setStatusText(`✓ All ${recordingsQueue.length} takes transcribed successfully!`);
        alert('All queued takes transcribed! Scrolled to Document Preview.');
        if (scrollToSection) scrollToSection('section-export');
      } else {
        setStatusText('Notice on completion');
        alert('Notice: ' + (res.data?.detail || 'Unknown response'));
      }
    } catch (err) {
      setIsTranscribing(false);
      setStatusText('Transcription Error');
      alert('AI Server Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  // --- Live Transcript Utilities ---
  const handleCopyLive = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleClearLive = () => {
    if (window.confirm('Clear the live spoken transcript?')) {
      setLiveTranscript('');
      setInterimText('');
      if (onLiveTranscriptSync) onLiveTranscriptSync('');
    }
  };

  const handleScrollToTranscript = () => {
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  const handleSendBangla = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    if (onLiveTranscriptSync) onLiveTranscriptSync(text);
    else if (onSendToBangla) onSendToBangla(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  const handleSendEnglish = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    if (onLiveTranscriptSync) onLiveTranscriptSync(text);
    else if (onSendToEnglish) onSendToEnglish(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  return (
    <div className="card" id="section-live" style={{ border: '1.5px solid var(--border-color)', position: 'relative' }}>
      {/* 4-Layer Architecture Workflow Tracker Banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 14px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: '8px',
          marginBottom: '16px',
          fontSize: '0.74rem',
          color: 'var(--text-secondary)',
          flexWrap: 'wrap'
        }}
      >
        <span style={{ fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.3px' }}>LAYER STACK:</span>
        <span style={{ color: '#34d399', fontWeight: 700, background: 'rgba(16, 185, 129, 0.15)', padding: '1px 7px', borderRadius: '4px' }}>
          1. Record / Listen & Determine Language
        </span>
        <span style={{ opacity: 0.5 }}>→</span>
        <span style={{ color: '#38bdf8', fontWeight: 600 }}>2. Transcribe Audio</span>
        <span style={{ opacity: 0.5 }}>→</span>
        <span style={{ color: 'var(--text-secondary)' }}>3. Raw Transcription</span>
        <span style={{ opacity: 0.5 }}>→</span>
        <span style={{ color: 'var(--text-secondary)' }}>4. Template Fillup via Skills</span>
      </div>

      {/* INTEGRATED AI ENGINE COMMAND BAR */}
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1.5px solid var(--border-color)',
          borderRadius: '14px',
          padding: '14px 18px',
          marginBottom: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}
      >
        {/* Row 1: Engine Provider Badge, Status, Test API & Configure Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.96rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-primary)' }}>
              <Cpu size={18} color="var(--accent-color)" /> Active AI Engine: {getActiveApiDisplayName(aiConfig)}
            </span>
            <span
              style={{
                fontSize: '0.74rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(2, 132, 199, 0.15)',
                color: 'var(--accent-color)',
                border: '1px solid rgba(2, 132, 199, 0.3)'
              }}
            >
              Provider: {aiConfig?.provider?.toUpperCase() || 'GEMINI'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              id="frontPageTestApiBtn"
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleVerifyKey}
              disabled={verifying}
              style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 700, fontSize: '0.78rem', padding: '6px 13px', background: 'rgba(2, 132, 199, 0.08)' }}
              title="Test connection to active API"
            >
              <Zap size={13} color="var(--accent-color)" /> {verifying ? 'Testing API...' : '⚡ Test API'}
            </button>
            {onOpenSettings && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onOpenSettings}
                style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 700, fontSize: '0.78rem', padding: '6px 13px' }}
              >
                <Key size={13} /> Configure / Switch APIs
              </button>
            )}
          </div>
        </div>

        {/* Live Test Status Alert on Front Page */}
        {verifyStatus && (
          <div
            style={{
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
            }}
          >
            {verifyStatus.valid || verifyStatus.success ? <CheckCircle size={15} /> : <AlertTriangle size={15} />}
            <span>{verifyStatus.message}</span>
          </div>
        )}

        {/* Row 2: STT Model, LLM Model, and Target Template Dropdowns */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px' }}>
          {/* STT Model */}
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              <Mic size={13} color="var(--accent-color)" /> STT Transcription Model:
            </label>
            <select
              className="form-control"
              style={{ fontSize: '0.8rem', padding: '6px 8px', fontWeight: 600 }}
              value={aiConfig?.transcriptionModel || (MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).stt[0]?.value}
              onChange={(e) => setAiConfig && setAiConfig({ ...aiConfig, transcriptionModel: e.target.value })}
            >
              {((MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).stt || []).map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* LLM Model */}
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              <Cpu size={13} color="var(--accent-color)" /> LLM Summarization Model:
            </label>
            <select
              className="form-control"
              style={{ fontSize: '0.8rem', padding: '6px 8px', fontWeight: 600 }}
              value={aiConfig?.summarizationModel || aiConfig?.modelName || (MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).llm[0]?.value}
              onChange={(e) => setAiConfig && setAiConfig({ ...aiConfig, summarizationModel: e.target.value, modelName: e.target.value })}
            >
              {((MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).llm || []).map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Target Document Template Format */}
          {templates && templates.length > 0 && (
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                <FileCode size={13} color="var(--accent-color)" /> Target Document Template:
              </label>
              <select
                className="form-control"
                style={{ fontSize: '0.8rem', padding: '6px 8px', fontWeight: 600 }}
                value={activeTemplateId || 'easd_default_minutes'}
                onChange={(e) => onSelectTemplate && onSelectTemplate(e.target.value)}
              >
                {templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name} {tpl.is_builtin ? '(Built-in)' : '(Custom)'}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* FRONT SCREEN: One Block Record, One Block Upload */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '20px',
          maxWidth: '720px',
          margin: '0 auto 16px auto',
          width: '100%',
          boxSizing: 'border-box'
        }}
      >
        {/* BLOCK 1: RECORD */}
        <div
          style={{
            background: isRecording ? 'rgba(239, 68, 68, 0.08)' : 'var(--bg-secondary)',
            border: isRecording ? '2px solid rgba(239, 68, 68, 0.45)' : '1.5px solid var(--border-color)',
            borderRadius: '16px',
            padding: '28px 20px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '14px',
            boxShadow: isRecording ? '0 0 25px rgba(239, 68, 68, 0.25)' : 'var(--card-shadow)',
            transition: 'all 0.25s ease',
            boxSizing: 'border-box'
          }}
        >
          {!isRecording ? (
            <button
              onClick={handleStartRecording}
              aria-label="Start recording"
              style={{
                width: '76px',
                height: '76px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 8px 30px rgba(239, 68, 68, 0.5), 0 0 0 6px rgba(239, 68, 68, 0.15)',
                transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            >
              <Mic size={34} color="#ffffff" strokeWidth={2.2} />
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <button
                onClick={handleStopAndSaveTake}
                aria-label="Stop and save take"
                style={{
                  width: '76px',
                  height: '76px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 0 35px rgba(239, 68, 68, 0.7), 0 0 0 6px rgba(239, 68, 68, 0.25)',
                  transition: 'all 0.2s ease',
                  animation: 'pulse 1.5s infinite'
                }}
                title="Stop and save take"
              >
                <Square size={28} fill="#ffffff" color="#ffffff" />
              </button>

              <button
                onClick={handleTogglePause}
                className="btn btn-secondary"
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '50%',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                title={isPaused ? 'Resume recording' : 'Pause recording'}
              >
                {isPaused ? <Play size={18} color="var(--accent-color)" /> : <Pause size={18} />}
              </button>
            </div>
          )}

          <div style={{ textAlign: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: isRecording ? '#ef4444' : 'var(--text-primary)' }}>
              {isRecording ? (isPaused ? 'Paused' : `Recording (${formatTime(recordingSeconds)})`) : 'Record'}
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              {isRecording ? 'Click stop square to save take' : 'Click to start live recording'}
            </p>
          </div>

          {isRecording && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <Volume2 size={16} color="#ef4444" />
              <div style={{ width: '120px', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${audioLevel}%`,
                    background: '#ef4444',
                    transition: 'width 0.08s ease'
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* BLOCK 2: UNIVERSAL UPLOAD */}
        <div
          className={`drop-zone ${isDragging ? 'dragging' : ''}`}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
          onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false); }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);
            if (e.dataTransfer && e.dataTransfer.files) {
              handleAddUploadedFiles(e.dataTransfer.files);
            }
          }}
          onClick={() => fileInputRef.current?.click()}
          style={{
            cursor: 'pointer',
            background: isDragging ? 'rgba(16, 185, 129, 0.16)' : 'var(--bg-secondary)',
            border: isDragging ? '2px dashed #10b981' : '1.5px dashed var(--border-color)',
            borderRadius: '16px',
            padding: '28px 20px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '14px',
            boxShadow: isDragging ? '0 0 25px rgba(16, 185, 129, 0.35)' : 'var(--card-shadow)',
            transition: 'all 0.25s ease',
            boxSizing: 'border-box'
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="audio/*,video/*,image/*,.pdf,.doc,.docx,.txt,.srt,.vtt,.hevc,.mov,.mp4,.m4a,.wav,.mp3"
            style={{ display: 'none' }}
            onChange={(e) => handleAddUploadedFiles(e.target.files)}
          />

          <div
            style={{
              width: '76px',
              height: '76px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #0284c7 0%, #004b87 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 30px rgba(2, 132, 199, 0.4), 0 0 0 6px rgba(2, 132, 199, 0.15)',
              transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
          >
            <UploadCloud size={34} color="#ffffff" strokeWidth={2.2} />
          </div>

          <div style={{ textAlign: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Universal Upload
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              {isDragging ? 'Drop audio, video, OCR photos or PDFs here!' : 'Audio, Video, Photos & OCR, PDFs & Docs'}
            </p>
          </div>
        </div>
      </div>

      {/* DIRECT DRAFT TEXT & DOCUMENT SYNTHESIS DRAWER */}
      <div style={{ maxWidth: '720px', margin: '0 auto 18px auto', width: '100%', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button
            type="button"
            onClick={() => setShowDirectTextInput((prev) => !prev)}
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.8rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '20px',
              transition: 'all 0.15s ease'
            }}
          >
            <Edit3 size={13} color="var(--accent-color)" />
            {showDirectTextInput ? 'Hide Draft Text Input ▲' : '📝 Or Paste Draft Notes / Direct Text Directly ▼'}
          </button>
        </div>

        {showDirectTextInput && (
          <div
            style={{
              marginTop: '10px',
              padding: '14px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}
          >
            <label style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
              Paste raw conversation notes, draft bullet points, or transcript text:
            </label>
            <textarea
              className="form-control"
              rows="3"
              value={directText}
              onChange={(e) => setDirectText && setDirectText(e.target.value)}
              placeholder="Paste raw conversation notes, bullet points, or draft text here..."
              style={{ fontSize: '0.84rem', padding: '8px' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={onProcessAi}
                disabled={isProcessing || (!directText.trim() && !selectedFile)}
                style={{ fontWeight: 800, padding: '7px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Sparkles size={14} />
                {isProcessing ? 'Processing with AI...' : '⚡ Generate Meeting Minutes from Draft / Media'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* HIGH-VISIBILITY REAL-TIME SPEECH MONITOR */}
      {(isRecording || liveTranscript || interimText) && (
        <div
          id="realtime-speech-monitor"
          style={{
            background: isRecording
              ? 'linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(8, 14, 26, 0.98) 100%)'
              : 'var(--bg-secondary)',
            border: isRecording
              ? '2px solid rgba(16, 185, 129, 0.55)'
              : '1.5px solid var(--border-color)',
            borderRadius: '16px',
            padding: '20px',
            marginBottom: '20px',
            boxShadow: isRecording
              ? '0 0 35px rgba(16, 185, 129, 0.2), 0 8px 30px rgba(0, 0, 0, 0.4)'
              : 'var(--card-shadow)',
            transition: 'all 0.25s ease',
            position: 'relative'
          }}
        >
          {/* Top Bar: Live Status, Voice Visualizer, Language Pills, Toolbar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '14px',
              flexWrap: 'wrap',
              gap: '12px',
              borderBottom: '1px solid var(--border-color)',
              paddingBottom: '12px'
            }}
          >
            {/* Live Indicator & Volume Level */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '4px 12px',
                  borderRadius: '20px',
                  background: isRecording ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: isRecording ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(16, 185, 129, 0.3)'
                }}
              >
                <span
                  style={{
                    width: '9px',
                    height: '9px',
                    borderRadius: '50%',
                    backgroundColor: isRecording ? '#ef4444' : '#10b981',
                    animation: isRecording && !isPaused ? 'pulse 1.2s infinite' : 'none',
                    boxShadow: isRecording ? '0 0 8px #ef4444' : 'none'
                  }}
                />
                <span style={{ fontSize: '0.82rem', fontWeight: 800, color: isRecording ? '#ef4444' : '#10b981' }}>
                  {isRecording ? (isPaused ? 'PAUSED' : `LIVE SPEECH [${formatTime(recordingSeconds)}]`) : 'LIVE TRANSCRIPT READY'}
                </span>
              </div>

              {isRecording && !isPaused && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Volume2 size={16} color="var(--accent-color)" />
                  <div style={{ width: '90px', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${audioLevel}%`,
                        background: audioLevel > 60 ? '#ef4444' : 'var(--accent-color)',
                        transition: 'width 0.08s ease'
                      }}
                    />
                  </div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Voice</span>
                </div>
              )}
            </div>

            {/* Active Speaker Selector Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Users size={13} color="var(--accent-color)" /> Speaker:
              </span>
              {['Speaker 1', 'Speaker 2', 'Speaker 3'].map((spk) => {
                const isSelected = activeSpeaker === spk;
                return (
                  <button
                    key={spk}
                    type="button"
                    onClick={() => setActiveSpeaker(spk)}
                    style={{
                      padding: '3px 10px',
                      borderRadius: '16px',
                      fontSize: '0.74rem',
                      fontWeight: isSelected ? 700 : 500,
                      border: isSelected ? '1.5px solid #38bdf8' : '1px solid var(--border-color)',
                      background: isSelected ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                      color: isSelected ? '#38bdf8' : 'var(--text-secondary)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {spk}
                  </button>
                );
              })}
            </div>

            {/* Language Selector Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Globe size={13} /> Spoken:
              </span>
              {[
                { id: 'auto', label: 'Auto' },
                { id: 'bn', label: '🇧🇩 বাংলা' },
                { id: 'en', label: '🇬🇧 English' }
              ].map((pill) => {
                const isSelected = language === pill.id;
                return (
                  <button
                    key={pill.id}
                    type="button"
                    onClick={() => handleLanguageChange(pill.id)}
                    style={{
                      padding: '3px 10px',
                      borderRadius: '16px',
                      fontSize: '0.74rem',
                      fontWeight: isSelected ? 700 : 500,
                      border: isSelected ? '1.5px solid var(--accent-color)' : '1px solid var(--border-color)',
                      background: isSelected ? 'var(--accent-glow)' : 'transparent',
                      color: isSelected ? 'var(--accent-color)' : 'var(--text-secondary)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {pill.label}
                  </button>
                );
              })}
            </div>

            {/* Quick Actions: Copy, View in Transcript, Clear */}
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCopyLive}
                disabled={!liveTranscript && !interimText}
                style={{ fontSize: '0.76rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                title="Copy live spoken text"
              >
                {isCopied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                {isCopied ? 'Copied' : 'Copy'}
              </button>

              <button
                className="btn btn-secondary btn-sm"
                onClick={handleScrollToTranscript}
                style={{ fontSize: '0.76rem', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
                title="View in main transcript section"
              >
                <Send size={12} color="var(--accent-color)" /> View in Transcript ↓
              </button>

              {(liveTranscript || interimText) && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleClearLive}
                  style={{ fontSize: '0.76rem', padding: '4px 8px', color: '#f87171' }}
                  title="Clear live monitor"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>

          {/* High-Legibility Real-Time Text Monitor Display */}
          <div
            id="live-speech-stream-display"
            style={{
              minHeight: '120px',
              maxHeight: '260px',
              overflowY: 'auto',
              background: 'rgba(0, 0, 0, 0.45)',
              padding: '18px 20px',
              borderRadius: '12px',
              fontSize: '1.22rem',
              lineHeight: '1.8',
              color: '#f8fafc',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: language === 'bn' ? "'Hind Siliguri', 'Inter', sans-serif" : "'Inter', -apple-system, sans-serif",
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.4)'
            }}
          >
            {liveTranscript ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {liveTranscript.split('\n').map((line, idx) => {
                  const match = line.match(/^(\[\d{2}:\d{2}\])\s*([^:]+):\s*(.*)$/);
                  if (match) {
                    return (
                      <div key={idx} style={{ lineHeight: '1.7' }}>
                        <span style={{ color: '#38bdf8', fontWeight: 700, marginRight: '8px', fontSize: '1.02rem', fontFamily: 'monospace' }}>
                          {match[1]}
                        </span>
                        <span style={{ color: '#34d399', fontWeight: 700, marginRight: '8px', fontSize: '1.08rem' }}>
                          {match[2]}:
                        </span>
                        <span style={{ color: '#f8fafc', fontWeight: 500 }}>
                          {match[3]}
                        </span>
                      </div>
                    );
                  }
                  return (
                    <div key={idx} style={{ color: '#f1f5f9', fontWeight: 500 }}>
                      {line}
                    </div>
                  );
                })}
              </div>
            ) : (
              <span style={{ color: 'rgba(148, 163, 184, 0.75)', fontStyle: 'italic', fontSize: '1.05rem' }}>
                {isRecording
                  ? '🎙️ Listening... Speak naturally into your microphone. Exactly what you say streams here word-by-word with timestamp and speaker attribution.'
                  : 'Click Record above to start live speech recognition. Words stream here in real time by speaker and time.'}
              </span>
            )}

            {interimText && (
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.92rem', fontFamily: 'monospace' }}>
                  [{formatTime(currentTakeSecondsRef.current || 0)}]
                </span>
                <span style={{ color: '#a7f3d0', fontWeight: 700, fontSize: '0.98rem' }}>
                  {activeSpeaker}:
                </span>
                <span
                  style={{
                    color: '#34d399',
                    background: 'rgba(16, 185, 129, 0.15)',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                    fontWeight: 600,
                    animation: 'pulse 1.4s infinite'
                  }}
                >
                  {interimText}
                </span>
              </div>
            )}
            <div ref={transcriptBottomRef} />
          </div>

          {/* Live Sync Status Footer */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', fontSize: '0.76rem', color: 'var(--text-secondary)', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Sparkles size={12} color="var(--accent-color)" />
              Streaming live directly into the single Transcript section below
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span id="speech-engine-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)' }}>
                ⚡ Engine: <strong style={{ color: 'var(--text-primary)' }}>webkitSpeechRecognition</strong>
              </span>
              <span>
                {liveTranscript.trim() ? liveTranscript.trim().split(/\s+/).length : 0} words captured
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Multi-Take Queue Shelf */}
      {recordingsQueue.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileAudio size={16} color="var(--accent-color)" /> Multi-Take Queue ({recordingsQueue.length})
            </h3>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleTranscribeAllTakes}
                disabled={isTranscribing || isRecording}
                style={{ fontWeight: 800, padding: '7px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Sparkles size={14} />
                {isTranscribing ? 'Transcribing...' : `⚡ Transcribe All Takes (${recordingsQueue.length})`}
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleClearAllTakes}
                style={{ fontSize: '0.75rem', padding: '7px 10px', color: '#f87171' }}
              >
                <Trash2 size={13} /> Clear
              </button>
            </div>
          </div>

          {/* List of Take Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '380px', overflowY: 'auto' }}>
            {recordingsQueue.map((item, idx) => {
              const isEditing = editingTakeId === item.id;

              return (
                <div
                  key={item.id}
                  style={{
                    background: 'var(--bg-secondary)',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    border: '1px solid var(--border-color)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          background: 'rgba(16, 185, 129, 0.2)',
                          color: '#34d399',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.75rem',
                          fontWeight: 800
                        }}
                      >
                        {idx + 1}
                      </span>
                      {isEditing ? (
                        <input
                          type="text"
                          className="form-control"
                          value={editingTakeName}
                          onChange={(e) => setEditingTakeName(e.target.value)}
                          style={{ padding: '4px 8px', fontSize: '0.85rem', width: '180px' }}
                        />
                      ) : (
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                          {item.name}
                        </span>
                      )}
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {item.duration ? `(${formatTime(item.duration)})` : ''} • {item.size} • {item.timestamp}
                      </span>
                    </div>

                    {/* Actions: Edit, Download, Delete */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {isEditing ? (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleSaveEditTake(item.id)}
                          style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                        >
                          <Check size={13} /> Save
                        </button>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleStartEditTake(item)}
                          title="Edit take name or transcript"
                          style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                        >
                          <Edit2 size={13} /> Edit
                        </button>
                      )}

                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleDownloadTake(item)}
                        title="Download audio file"
                        style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                      >
                        <Download size={13} />
                      </button>

                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleDeleteTake(item.id)}
                        title="Delete take"
                        style={{ fontSize: '0.75rem', padding: '4px 8px', color: '#f87171' }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Audio Player */}
                  {item.url && (
                    <audio
                      src={item.url}
                      controls
                      style={{ width: '100%', height: '32px', borderRadius: '6px' }}
                    />
                  )}

                  {/* Editable Transcript text if in edit mode or if present */}
                  {isEditing ? (
                    <div>
                      <label style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>Edit Live Transcript Notes:</label>
                      <textarea
                        className="form-control"
                        rows="2"
                        value={editingTakeTranscript}
                        onChange={(e) => setEditingTakeTranscript(e.target.value)}
                        placeholder="Captured speech text..."
                        style={{ fontSize: '0.82rem', padding: '6px' }}
                      />
                    </div>
                  ) : (
                    item.transcript && (
                      <div
                        style={{
                          fontSize: '0.8rem',
                          color: 'var(--text-secondary)',
                          background: 'rgba(0,0,0,0.2)',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          whiteSpace: 'pre-wrap',
                          maxHeight: '60px',
                          overflowY: 'auto'
                        }}
                      >
                        <strong style={{ color: 'var(--accent-color)' }}>Captured Speech: </strong>
                        {item.transcript}
                      </div>
                    )
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
