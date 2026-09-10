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
import {
  getActiveApiDisplayName,
  getSavedKeyForProvider,
  QUICK_STT_MODELS,
  QUICK_LLM_MODELS,
  testAiEngine,
  saveServerSettings
} from '../utils/apiKeyStorage';

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
  onRecordingStateChange,
  onLiveInterimChange,
  scrollToSection,
  onOpenSettings,
  directText = '',
  setDirectText,
  selectedFile,
  setSelectedFile,
  onProcessAi,
  isProcessing = false,
  isAutoTranscribing = false,
  setIsAutoTranscribing
}) {
  // Engine Verification & Direct Text State
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState(null);
  const [showDirectTextInput, setShowDirectTextInput] = useState(Boolean(directText));

  // Decoupled STT & LLM Two-Way Testing State
  const [testingSTT, setTestingSTT] = useState(false);
  const [sttTestResult, setSttTestResult] = useState(null);
  const [testingLLM, setTestingLLM] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState(null);
  const [showAdvancedEngineSettings, setShowAdvancedEngineSettings] = useState(false);

  // Recording & Live State
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [language, setLanguage] = useState('auto'); // Default to 'auto' for any language (Bengali, English, Hindi, Arabic, etc.)
  const [engineStatus, setEngineStatus] = useState('webkitSpeechRecognition (Auto)');
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
  const autoChunkTimerRef = useRef(null);
  const isStreamingChunkRef = useRef(false);
  const currentTakeSecondsRef = useRef(0);
  const isRecordingRef = useRef(false);
  const isPausedRef = useRef(false);
  const isStartingRecognitionRef = useRef(false);
  const languageRef = useRef('auto');
  const restartTimerRef = useRef(null);
  const lastSpeechTimestampRef = useRef(Date.now());
  const fileInputRef = useRef(null);
  const transcriptBottomRef = useRef(null);
  const liveTranscriptForTakeRef = useRef('');

  useEffect(() => {
    isRecordingRef.current = isRecording;
    isPausedRef.current = isPaused;
  }, [isRecording, isPaused]);

  useEffect(() => {
    languageRef.current = language;
  }, [language]);

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
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
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

  const handleTestSTT = async () => {
    setTestingSTT(true);
    setSttTestResult(null);
    try {
      const prov = aiConfig?.transcriptionProvider || (aiConfig?.transcriptionModel?.includes('whisper') ? 'groq' : (aiConfig?.provider || 'groq'));
      const res = await testAiEngine({
        test_type: 'stt',
        stt_provider: prov,
        stt_model: aiConfig?.transcriptionModel || 'whisper-large-v3-turbo',
        stt_api_key: aiConfig?.transcriptionApiKey || aiConfig?.apiKey || '',
        base_url: aiConfig?.baseUrl || ''
      });
      setTestingSTT(false);
      const stt = res.stt || {};
      setSttTestResult({
        success: Boolean(stt.success),
        message: (stt.message || (stt.success ? 'STT engine connected!' : 'STT error')) + (stt.latency_ms ? ` (${stt.latency_ms}ms)` : ''),
        latency_ms: stt.latency_ms
      });
      setTimeout(() => setSttTestResult(null), 8000);
    } catch (e) {
      setTestingSTT(false);
      setSttTestResult({ success: false, message: e.message || 'STT test failed' });
      setTimeout(() => setSttTestResult(null), 8000);
    }
  };

  const handleTestLLM = async () => {
    setTestingLLM(true);
    setLlmTestResult(null);
    try {
      const prov = aiConfig?.summarizationProvider || (aiConfig?.summarizationModel?.includes('gemini') ? 'gemini' : (aiConfig?.provider || 'gemini'));
      const res = await testAiEngine({
        test_type: 'llm',
        llm_provider: prov,
        llm_model: aiConfig?.summarizationModel || 'gemini-3.7-flash',
        llm_api_key: aiConfig?.summarizationApiKey || aiConfig?.apiKey || '',
        base_url: aiConfig?.baseUrl || ''
      });
      setTestingLLM(false);
      const llm = res.llm || {};
      setLlmTestResult({
        success: Boolean(llm.success),
        message: (llm.message || (llm.success ? 'LLM engine connected!' : 'LLM error')) + (llm.latency_ms ? ` (${llm.latency_ms}ms)` : ''),
        latency_ms: llm.latency_ms
      });
      setTimeout(() => setLlmTestResult(null), 8000);
    } catch (e) {
      setTestingLLM(false);
      setLlmTestResult({ success: false, message: e.message || 'LLM test failed' });
      setTimeout(() => setLlmTestResult(null), 8000);
    }
  };

  const handleSelectSTTModel = (model) => {
    if (!setAiConfig) return;
    const updated = {
      ...aiConfig,
      transcriptionModel: model.id,
      transcriptionProvider: model.provider
    };
    setAiConfig(updated);
    try {
      localStorage.setItem('transcriptionModel', model.id);
      saveServerSettings({
        transcription_provider: model.provider,
        transcription_model: model.id
      });
    } catch (e) {}
  };

  const handleSelectLLMModel = (model) => {
    if (!setAiConfig) return;
    const updated = {
      ...aiConfig,
      summarizationModel: model.id,
      summarizationProvider: model.provider,
      modelName: model.id
    };
    setAiConfig(updated);
    try {
      localStorage.setItem('summarizationModel', model.id);
      localStorage.setItem('modelName', model.id);
      saveServerSettings({
        summarization_provider: model.provider,
        summarization_model: model.id
      });
    } catch (e) {}
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

  // --- Robust Continuous webkitSpeechRecognition Engine ---
  const restartSpeechRecognition = (delay = 150) => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    restartTimerRef.current = setTimeout(() => {
      if (!isRecordingRef.current || isPausedRef.current) return;
      try {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.onend = null;
            recognitionRef.current.onerror = null;
            recognitionRef.current.onresult = null;
            recognitionRef.current.abort();
          } catch (e) {}
          recognitionRef.current = null;
        }
        const rec = initSpeechRecognition(languageRef.current);
        if (rec) {
          recognitionRef.current = rec;
          isStartingRecognitionRef.current = true;
          rec.start();
        }
      } catch (e) {
        console.warn('SpeechRecognition restart notice:', e);
        isStartingRecognitionRef.current = false;
        // Schedule fallback retry if still recording
        if (isRecordingRef.current && !isPausedRef.current) {
          restartTimerRef.current = setTimeout(() => {
            if (isRecordingRef.current && !isPausedRef.current) {
              restartSpeechRecognition(100);
            }
          }, 600);
        }
      }
    }, delay);
  };

  const initSpeechRecognition = (langOverride = null) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('SpeechRecognition not supported in this browser. Please use Google Chrome, Microsoft Edge, or a Chromium-based browser.');
      setStatusText('SpeechRecognition requires Chrome or Edge browser');
      return null;
    }
    const recognition = new SpeechRecognition();
    const activeLang = langOverride || languageRef.current || language;
    if (activeLang === 'bn') {
      recognition.lang = 'bn-BD';
    } else if (activeLang === 'en') {
      recognition.lang = 'en-US';
    } else {
      // Auto / Multilingual: use user's browser locale or fallback to English/Bengali bilingual detection
      recognition.lang = navigator.language || 'en-US';
    }
    recognition.continuous = true;
    recognition.interimResults = true; // Enables live typing as you speak
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isStartingRecognitionRef.current = false;
      lastSpeechTimestampRef.current = Date.now();
      setEngineStatus(`SpeechRecognition (${recognition.lang})`);
      setStatusText(`Live speech recognition active (${recognition.lang})`);
    };

    recognition.onresult = (event) => {
      lastSpeechTimestampRef.current = Date.now();
      let finalChunk = '';
      let liveText = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalChunk += transcriptPart;
        } else {
          liveText += transcriptPart;
        }
      }

      console.log("Live Text:", liveText || finalChunk);

      if (finalChunk.trim()) {
        const timeTag = formatTime(currentTakeSecondsRef.current || 0);
        const speaker = activeSpeakerRef.current || 'Speaker 1';
        const formattedLine = `[${timeTag}] ${speaker}: ${finalChunk.trim()}`;
        setLiveTranscript((prev) => {
          const updated = prev ? `${prev}\n${formattedLine}` : formattedLine;
          if (onLiveTranscriptSync) onLiveTranscriptSync(updated);
          if (onAppendToTranscript) onAppendToTranscript(formattedLine);
          return updated;
        });
        if (onLiveInterimChange) onLiveInterimChange('');
      }

      setInterimText(liveText);
      if (onLiveInterimChange && liveText) {
        const timeTag = formatTime(currentTakeSecondsRef.current || 0);
        const speaker = activeSpeakerRef.current || 'Speaker 1';
        onLiveInterimChange(`[${timeTag}] ${speaker}: ${liveText.trim()}`);
      }
    };

    recognition.onerror = (event) => {
      isStartingRecognitionRef.current = false;
      if (event.error === 'no-speech') {
        // 'no-speech' is a normal silence pause fired by Chrome before onend
        return;
      }
      if (event.error === 'aborted') {
        return;
      }
      console.warn('Speech recognition notice:', event.error);
      setEngineStatus(`Speech Notice: ${event.error} — Reconnecting`);
      if (isRecordingRef.current && !isPausedRef.current) {
        restartSpeechRecognition(300);
      }
    };

    recognition.onend = () => {
      isStartingRecognitionRef.current = false;
      if (isRecordingRef.current && !isPausedRef.current) {
        // Seamlessly auto-restart using fresh SpeechRecognition instance after micro-pause
        restartSpeechRecognition(150);
      }
    };

    return recognition;
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    languageRef.current = newLang;
    if (isRecordingRef.current) {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.onend = null;
          recognitionRef.current.abort();
        } catch (e) {}
        recognitionRef.current = null;
      }
      restartSpeechRecognition(100);
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
      lastSpeechTimestampRef.current = Date.now();
      setRecordingSeconds(0);
      setLiveTranscript('');
      setInterimText('');
      liveTranscriptForTakeRef.current = '';

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);

      // Start periodic live audio chunk auto-previewing via backend Gemini STT as a safety net
      autoChunkTimerRef.current = setInterval(async () => {
        if (!isRecordingRef.current || isPausedRef.current) return;
        if (isStreamingChunkRef.current) return;
        if (currentChunksRef.current.length === 0) return;

        const silenceDuration = Date.now() - (lastSpeechTimestampRef.current || 0);
        const isRecognitionStalled = (!liveTranscriptForTakeRef.current || liveTranscriptForTakeRef.current.trim().length < 5);

        // Keep browser recognition alive if stalled or silent
        if ((isRecognitionStalled || silenceDuration > 5000) && !isStartingRecognitionRef.current) {
          restartSpeechRecognition(100);
        }

        // If browser speech recognition hasn't caught text or only caught silence, stream chunk to backend
        if (isRecognitionStalled) {
          try {
            isStreamingChunkRef.current = true;
            const mime = mimeType || 'audio/webm';
            const chunkBlob = new Blob(currentChunksRef.current, { type: mime });
            if (chunkBlob.size > 2000) {
              const formData = new FormData();
              const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
              formData.append('chunk', chunkBlob, `live_stream.${ext}`);
              formData.append('language', languageRef.current || 'bn');
              formData.append('provider', aiConfig?.transcriptionProvider || 'gemini');
              formData.append('model_name', aiConfig?.transcriptionModel || 'gemini-3.5-transcribe');

              const res = await axios.post('/api/live_transcribe_chunk', formData);
              if (res.data && res.data.text && res.data.text.trim()) {
                const chunkTxt = res.data.text.trim();
                const speaker = activeSpeakerRef.current || 'Speaker 1';
                const formatted = chunkTxt.startsWith('[') ? chunkTxt : `[${formatTime(currentTakeSecondsRef.current || 0)}] ${speaker}: ${chunkTxt}`;
                setLiveTranscript((prev) => {
                  if (prev && prev.includes(chunkTxt)) return prev;
                  return prev ? `${prev}\n${formatted}` : formatted;
                });
                liveTranscriptForTakeRef.current = formatted;
                setEngineStatus('Gemini AI Live Stream (Auto-Preview)');
                if (onLiveTranscriptSync) onLiveTranscriptSync(formatted);
                if (onAppendToTranscript) onAppendToTranscript(formatted);
              }
            }
          } catch (err) {
            console.warn('Live chunk auto-preview notice:', err);
          } finally {
            isStreamingChunkRef.current = false;
          }
        }
      }, 4500);

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

      mediaRecorder.onstop = async () => {
        const mime = mimeType || 'audio/webm';
        const blob = new Blob(currentChunksRef.current, { type: mime });
        const url = URL.createObjectURL(blob);
        const durationSec = currentTakeSecondsRef.current || 1;
        const takeNum = recordingsQueue.length + 1;
        let capturedTranscript = (liveTranscriptForTakeRef.current || '').trim();
        const takeId = 'take_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);

        const newTake = {
          id: takeId,
          name: `Take #${takeNum}`,
          blob: blob,
          url: url,
          duration: durationSec,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          size: (blob.size / (1024 * 1024)).toFixed(2) + ' MB',
          transcript: capturedTranscript,
          isUpload: false,
          isAutoTranscribing: true
        };

        setRecordingsQueue((prev) => [...prev, newTake]);

        // AUTOACTIVATE: Immediately activate and scroll to Initial Transcript section
        if (scrollToSection) {
          scrollToSection('section-transcripts');
        }
        if (setIsAutoTranscribing) {
          setIsAutoTranscribing(true);
        }

        setStatusText(`⚡ Auto-transcribing Take #${takeNum} (100% Raw Speech • Diarization • Timestamps)...`);
        try {
          const resolvedSttProv = aiConfig?.transcriptionProvider || 'gemini';
          let sttKey = (
            aiConfig?.transcriptionApiKey ||
            getSavedKeyForProvider(resolvedSttProv) ||
            (resolvedSttProv === 'gemini' ? getSavedKeyForProvider('gemini') : getSavedKeyForProvider('groq')) ||
            (aiConfig?.apiKey || '')
          ).trim();

          // Ensure HuggingFace token never bleeds into Gemini calls
          if (resolvedSttProv === 'gemini' && sttKey.startsWith('hf_')) {
            sttKey = getSavedKeyForProvider('gemini') || '';
          }

          const defaultSttModel = resolvedSttProv === 'gemini' ? 'gemini-3.5-transcribe' : (resolvedSttProv === 'whisperx' ? 'pyannote/speaker-diarization-community-1' : 'whisper-large-v3-turbo');
          const chosenSttModel = aiConfig?.transcriptionModel || defaultSttModel;

          const formData = new FormData();
          const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
          formData.append('file', blob, `take_${takeNum}.${ext}`);
          formData.append('language', languageRef.current || 'auto');
          formData.append('provider', resolvedSttProv);
          formData.append('api_key', sttKey);
          formData.append('model_name', chosenSttModel);

          const res = await axios.post('/api/transcribe_take', formData);
          if (res.data && res.data.transcript && res.data.transcript.trim()) {
            const aiTranscript = res.data.transcript.trim();
            setLiveTranscript((prev) => (prev ? `${prev}\n\n${aiTranscript}` : aiTranscript));
            liveTranscriptForTakeRef.current = aiTranscript;
            setEngineStatus(`${resolvedSttProv.toUpperCase()} Raw Diarized STT`);
            if (onAppendToTranscript) {
              onAppendToTranscript(aiTranscript);
            } else if (onLiveTranscriptSync) {
              onLiveTranscriptSync(aiTranscript);
            }

            setRecordingsQueue((prev) =>
              prev.map((t) => (t.id === takeId ? { ...t, transcript: aiTranscript, isAutoTranscribing: false } : t))
            );
            setStatusText(`✓ Take #${takeNum} auto-transcribed with speaker diarization & timestamps!`);
          } else {
            if (capturedTranscript) {
              if (onAppendToTranscript) onAppendToTranscript(capturedTranscript);
              else if (onLiveTranscriptSync) onLiveTranscriptSync(capturedTranscript);
            }
            setRecordingsQueue((prev) =>
              prev.map((t) => (t.id === takeId ? { ...t, isAutoTranscribing: false } : t))
            );
            setStatusText(`✓ Take #${takeNum} saved to queue`);
          }
        } catch (err) {
          console.warn('Take auto-transcribe error:', err);
          if (capturedTranscript) {
            if (onAppendToTranscript) onAppendToTranscript(capturedTranscript);
            else if (onLiveTranscriptSync) onLiveTranscriptSync(capturedTranscript);
          }
          setRecordingsQueue((prev) =>
            prev.map((t) => (t.id === takeId ? { ...t, isAutoTranscribing: false } : t))
          );
          setStatusText(`✓ Take #${takeNum} saved to queue`);
        } finally {
          if (setIsAutoTranscribing) {
            setIsAutoTranscribing(false);
          }
        }
      };

      mediaRecorder.start(250);

      // Start Live Speech Recognition
      const recognition = initSpeechRecognition(languageRef.current);
      if (recognition) {
        recognitionRef.current = recognition;
        isStartingRecognitionRef.current = true;
        try {
          recognition.start();
        } catch (e) {
          console.warn('Immediate recognition start notice, scheduling restart:', e);
          restartSpeechRecognition(200);
        }
      }

      setIsRecording(true);
      setIsPaused(false);
      if (onRecordingStateChange) onRecordingStateChange(true);
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
      setIsPaused(false);
      isPausedRef.current = false;
      if (onRecordingStateChange) onRecordingStateChange(true);
      restartSpeechRecognition(100);
      setStatusText('● Recording & live transcribing resumed');
    } else {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.onend = null;
          recognitionRef.current.onerror = null;
          recognitionRef.current.abort();
        } catch (e) {}
        recognitionRef.current = null;
      }
      setIsPaused(true);
      isPausedRef.current = true;
      if (onRecordingStateChange) onRecordingStateChange(false);
      setStatusText('⏸ Recording paused');
    }
  };

  const handleStopAndSaveTake = () => {
    stopLiveInternal();
    setIsRecording(false);
    setIsPaused(false);
    if (onRecordingStateChange) onRecordingStateChange(false);
    if (onLiveInterimChange) onLiveInterimChange('');
    setStatusText('Processing recorded take...');
  };

  const stopLiveInternal = () => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (autoChunkTimerRef.current) {
      clearInterval(autoChunkTimerRef.current);
      autoChunkTimerRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.abort();
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
    setInterimText('');
    if (onLiveInterimChange) onLiveInterimChange('');
    if (onRecordingStateChange) onRecordingStateChange(false);
    isStartingRecognitionRef.current = false;
  };

  // --- Add Uploaded Audio/Video Files to Queue & Autoactivate Initial Transcript ---
  const handleAddUploadedFiles = async (files) => {
    if (!files || files.length === 0) return;
    const newItems = [];
    const mediaFiles = [];

    Array.from(files).forEach((file, fIdx) => {
      if (setSelectedFile && fIdx === 0) {
        setSelectedFile(file);
      }
      const isMedia =
        file.type.startsWith('audio/') ||
        file.type.startsWith('video/') ||
        /\.(mp3|wav|m4a|aac|ogg|webm|mp4|mov|mkv|flac)$/i.test(file.name);

      const url = URL.createObjectURL(file);
      const itemId = 'upload_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7) + '_' + fIdx;

      const itemObj = {
        id: itemId,
        blob: file,
        url: url,
        duration: 0,
        name: file.name.replace(/\.[^/.]+$/, ''),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
        transcript: '',
        isUpload: true,
        isAutoTranscribing: isMedia
      };

      newItems.push(itemObj);
      if (isMedia) {
        mediaFiles.push(itemObj);
      }

      // If text file (.txt), automatically read and append text
      if (!isMedia && file.name.toLowerCase().endsWith('.txt')) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          const txt = ev.target?.result;
          if (txt && typeof txt === 'string' && txt.trim()) {
            if (onAppendToTranscript) onAppendToTranscript(txt.trim());
            else if (onLiveTranscriptSync) onLiveTranscriptSync(txt.trim());
          }
        };
        reader.readAsText(file);
      }
    });

    setRecordingsQueue((prev) => [...prev, ...newItems]);

    // AUTOACTIVATE: Immediately activate and scroll to Initial Transcript section!
    if (scrollToSection) {
      scrollToSection('section-transcripts');
    }

    if (mediaFiles.length > 0) {
      if (setIsAutoTranscribing) setIsAutoTranscribing(true);
      setStatusText(`⚡ Auto-transcribing ${mediaFiles.length} uploaded media file(s) into raw diarized transcript...`);

      const resolvedSttProv = aiConfig?.transcriptionProvider || 'gemini';
      const sttKey = (
        aiConfig?.transcriptionApiKey ||
        getSavedKeyForProvider(resolvedSttProv) ||
        (resolvedSttProv === 'gemini' ? getSavedKeyForProvider('gemini') : getSavedKeyForProvider('groq')) ||
        (aiConfig?.apiKey || '')
      ).trim();

      for (const item of mediaFiles) {
        try {
          const formData = new FormData();
          formData.append('file', item.blob, item.blob.name || `${item.name}.mp3`);
          formData.append('language', languageRef.current || 'bn');
          formData.append('provider', resolvedSttProv);
          formData.append('api_key', sttKey);
          formData.append('model_name', aiConfig?.transcriptionModel || (resolvedSttProv === 'gemini' ? 'gemini-3.6-flash' : 'whisper-large-v3-turbo'));

          const res = await axios.post('/api/transcribe_take', formData);
          if (res.data && res.data.transcript && res.data.transcript.trim()) {
            const aiTranscript = res.data.transcript.trim();
            setLiveTranscript((prev) => (prev ? `${prev}\n\n${aiTranscript}` : aiTranscript));
            if (onAppendToTranscript) {
              onAppendToTranscript(aiTranscript);
            } else if (onLiveTranscriptSync) {
              onLiveTranscriptSync(aiTranscript);
            }

            setRecordingsQueue((prev) =>
              prev.map((t) => (t.id === item.id ? { ...t, transcript: aiTranscript, isAutoTranscribing: false } : t))
            );
            setStatusText(`✓ ${item.name} auto-transcribed with speaker diarization & timestamps!`);
          } else {
            setRecordingsQueue((prev) =>
              prev.map((t) => (t.id === item.id ? { ...t, isAutoTranscribing: false } : t))
            );
          }
        } catch (err) {
          console.warn('Upload auto-transcribe error for item:', item.name, err);
          setRecordingsQueue((prev) =>
            prev.map((t) => (t.id === item.id ? { ...t, isAutoTranscribing: false } : t))
          );
        }
      }
      if (setIsAutoTranscribing) setIsAutoTranscribing(false);
      setStatusText(`✓ Uploaded media auto-transcribed into 100% raw initial transcript!`);
    } else {
      setStatusText(`✓ Added ${newItems.length} file(s) to queue`);
    }
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

    const resolvedSttProv = aiConfig?.transcriptionProvider || 'gemini';
    const resolvedSumProv = aiConfig?.summarizationProvider || 'gemini';

    const sttKey = (
      aiConfig?.transcriptionApiKey ||
      getSavedKeyForProvider(resolvedSttProv) ||
      (resolvedSttProv === 'gemini' ? getSavedKeyForProvider('gemini') : getSavedKeyForProvider('groq')) ||
      (aiConfig?.apiKey || '')
    ).trim();

    const sumKey = (
      aiConfig?.summarizationApiKey ||
      getSavedKeyForProvider(resolvedSumProv) ||
      getSavedKeyForProvider('gemini') ||
      (aiConfig?.apiKey || '')
    ).trim();

    const formData = new FormData();
    formData.append('provider', resolvedSumProv);
    formData.append('api_key', sumKey || sttKey);
    formData.append('base_url', (aiConfig?.baseUrl || '').trim());
    formData.append('model_name', aiConfig?.summarizationModel || 'gemini-3.7-flash');
    formData.append('transcription_provider', resolvedSttProv);
    formData.append('transcription_api_key', sttKey);
    formData.append('transcription_model', aiConfig?.transcriptionModel || (resolvedSttProv === 'gemini' ? 'gemini-2.5-flash' : (resolvedSttProv === 'whisperx' ? 'pyannote/speaker-diarization-community-1' : 'whisper-large-v3-turbo')));
    formData.append('summarization_provider', resolvedSumProv);
    formData.append('summarization_api_key', sumKey);
    formData.append('summarization_model', aiConfig?.summarizationModel || 'gemini-3.7-flash');
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
      {/* 1. HERO ACTION BUTTONS: RECORD & UPLOAD (FRONT & CENTER AT THE VERY TOP ON ALL DEVICES) */}
      <div className="hero-actions-container">
        {/* CARD 1: RECORD BUTTON */}
        <div className={`hero-action-card record-card ${isRecording ? 'is-recording' : ''}`}>
          {/* Top visual button */}
          {!isRecording ? (
            <button
              type="button"
              onClick={handleStartRecording}
              aria-label="Start recording meeting"
              title="Click to start recording"
              className="hero-action-circle-btn record-circle"
            >
              <Mic size={36} color="#ffffff" strokeWidth={2.4} />
            </button>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                type="button"
                onClick={handleStopAndSaveTake}
                aria-label="Stop recording and save take"
                className="hero-action-circle-btn stop-circle"
                title="Stop recording and save take"
              >
                <Square size={26} fill="#ffffff" color="#ffffff" />
              </button>

              <button
                type="button"
                onClick={handleTogglePause}
                className="btn btn-secondary"
                style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '50%',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}
                title={isPaused ? 'Resume recording' : 'Pause recording'}
              >
                {isPaused ? <Play size={18} color="var(--accent-color)" /> : <Pause size={18} />}
              </button>
            </div>
          )}

          {/* Text Information */}
          <div className="hero-action-text">
            <h3 className="hero-action-title">
              <span>Record</span>
              {isRecording && (
                <span
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: isPaused ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                    color: isPaused ? '#f59e0b' : '#ef4444'
                  }}
                >
                  {isPaused ? 'PAUSED' : formatTime(recordingSeconds)}
                </span>
              )}
            </h3>
            <p className="hero-action-desc">
              {isRecording
                ? 'Microphone is active. Speak naturally, then click Stop when finished.'
                : 'Speak live into your microphone to record consultations or meeting discussions.'}
            </p>
          </div>

          {/* Audio Visualizer Level if recording */}
          {isRecording && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', justifyContent: 'center' }}>
              <Volume2 size={16} color="#ef4444" />
              <div style={{ width: '130px', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
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

          {/* Primary Action Button (Doctor-Friendly) */}
          <div className="hero-btn-container">
            {!isRecording ? (
              <button
                type="button"
                onClick={handleStartRecording}
                className="btn hero-btn record-btn"
              >
                <Mic size={18} />
                <span>Record</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopAndSaveTake}
                className="btn hero-btn stop-btn"
              >
                <Square size={16} fill="#ffffff" />
                <span>Stop & Save</span>
              </button>
            )}
          </div>
        </div>

        {/* CARD 2: UPLOAD BUTTON */}
        <div
          className={`hero-action-card upload-card drop-zone ${isDragging ? 'dragging' : ''}`}
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
          style={{ cursor: 'pointer' }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="audio/*,video/*,image/*,.pdf,.doc,.docx,.txt,.srt,.vtt,.hevc,.mov,.mp4,.m4a,.wav,.mp3"
            style={{ display: 'none' }}
            onChange={(e) => handleAddUploadedFiles(e.target.files)}
          />

          {/* Top visual button */}
          <div className="hero-action-circle-btn upload-circle">
            <UploadCloud size={36} color="#ffffff" strokeWidth={2.4} />
          </div>

          {/* Text Information */}
          <div className="hero-action-text">
            <h3 className="hero-action-title">
              <span>Upload</span>
            </h3>
            <p className="hero-action-desc">
              {isDragging
                ? 'Drop your audio recording, voice memo or document here!'
                : 'Select an audio file, iPhone voice memo, or meeting document.'}
            </p>
          </div>

          {/* File Support Tag */}
          <div className="hero-file-tag">
            MP3, WAV, M4A, Voice Memos & Docs
          </div>

          {/* Primary Action Button (Doctor-Friendly) */}
          <div className="hero-btn-container">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="btn hero-btn upload-btn"
            >
              <UploadCloud size={18} />
              <span>Upload</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. TARGET DOCUMENT FORMAT SELECTOR (COMPACT SUB-BAR) */}
      {templates && templates.length > 0 && (
        <div className="hero-format-bar">
          <label className="hero-format-label">
            <FileCode size={15} color="var(--accent-color)" />
            <span>Document Format:</span>
          </label>
          <select
            className="form-control hero-format-select"
            value={activeTemplateId || 'easd_default_minutes'}
            onChange={(e) => onSelectTemplate && onSelectTemplate(e.target.value)}
          >
            {templates.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name} {tpl.is_builtin ? '(Standard Official Template)' : '(Custom)'}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 3. DIRECT DRAFT TEXT & DOCUMENT SYNTHESIS DRAWER */}
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
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', flexWrap: 'wrap' }}>
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
                { id: 'auto', label: '🌐 Auto (Any Language)' },
                { id: 'bn', label: '🇧🇩 বাংলা' },
                { id: 'en', label: '🇬🇧 English' },
                { id: 'multilingual', label: '🌍 Multilingual' }
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
            ) : !interimText ? (
              <span style={{ color: 'rgba(148, 163, 184, 0.75)', fontStyle: 'italic', fontSize: '1.05rem' }}>
                {isRecording
                  ? '🎙️ Listening... Speak naturally into your microphone. Words appear here live as you speak in authentic Bengali (বাংলা).'
                  : 'Click Record above to start live speech recognition. Words stream here in real time as you speak.'}
              </span>
            ) : null}

            {interimText && (
              <div style={{ marginTop: liveTranscript ? '8px' : '0px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#38bdf8', fontSize: '0.98rem', fontFamily: 'monospace', fontWeight: 700 }}>
                  [{formatTime(currentTakeSecondsRef.current || 0)}]
                </span>
                <span style={{ color: '#34d399', fontWeight: 700, fontSize: '1.08rem' }}>
                  {activeSpeaker}:
                </span>
                <span
                  style={{
                    color: '#f8fafc',
                    background: 'rgba(56, 189, 248, 0.12)',
                    padding: '3px 10px',
                    borderRadius: '6px',
                    border: '1px solid rgba(56, 189, 248, 0.35)',
                    fontWeight: 600,
                    fontSize: '1.25rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {interimText}
                  <span
                    style={{
                      display: 'inline-block',
                      width: '2px',
                      height: '1.15rem',
                      background: '#38bdf8',
                      animation: 'pulse 0.8s infinite'
                    }}
                  />
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
                ⚡ Engine: <strong style={{ color: 'var(--text-primary)' }}>{engineStatus}</strong>
              </span>
              <span>
                {((liveTranscript || '') + ' ' + (interimText || '')).trim() ? ((liveTranscript || '') + ' ' + (interimText || '')).trim().split(/\s+/).length : 0} words captured
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
                  ) : item.isAutoTranscribing ? (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.82rem',
                        color: '#38bdf8',
                        background: 'rgba(56, 189, 248, 0.1)',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid rgba(56, 189, 248, 0.25)'
                      }}
                    >
                      <Sparkles size={14} className="spin" />
                      <span>⚡ Auto-transcribing take with Gemini AI in authentic Bengali script...</span>
                    </div>
                  ) : (
                    item.transcript && (
                      <div
                        style={{
                          fontSize: '0.86rem',
                          color: '#f8fafc',
                          background: 'rgba(0,0,0,0.25)',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          whiteSpace: 'pre-wrap',
                          maxHeight: '80px',
                          overflowY: 'auto',
                          fontFamily: "'Hind Siliguri', 'Inter', sans-serif",
                          lineHeight: '1.6'
                        }}
                      >
                        <strong style={{ color: 'var(--accent-color)', marginRight: '6px' }}>Captured Speech: </strong>
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

      {/* ADVANCED AI ENGINE SETTINGS (COLLAPSED BY DEFAULT FOR DOCTORS & NON-TECHNICAL USERS) */}
      <div style={{ marginTop: '22px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <button
            type="button"
            onClick={() => setShowAdvancedEngineSettings((prev) => !prev)}
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '20px',
              transition: 'all 0.15s ease'
            }}
          >
            <Cpu size={13} color="var(--accent-color)" />
            {showAdvancedEngineSettings ? 'Hide AI Engine Settings ▲' : '⚙️ Advanced AI Engine Settings (For Administrators) ▼'}
          </button>
        </div>

        {showAdvancedEngineSettings && (
          <div style={{ marginTop: '12px' }}>
            {/* INTEGRATED AI ENGINE COMMAND BAR */}
            <div
              style={{
                background: 'var(--bg-secondary)',
                border: '1.5px solid var(--border-color)',
                borderRadius: '14px',
                padding: '14px 18px',
                marginBottom: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              {/* Row 1: Engine Provider Badge, Status, Two-Way Test API & Configure Buttons */}
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
                    STT: {aiConfig?.transcriptionModel || 'whisper-large-v3-turbo'} | LLM: {aiConfig?.summarizationModel || 'gemini-3.7-flash'}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  {/* Direct STT Engine Test Button */}
                  <button
                    id="frontPageTestSttBtn"
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestSTT}
                    disabled={testingSTT}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontWeight: 700,
                      fontSize: '0.78rem',
                      padding: '6px 12px',
                      background: sttTestResult?.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(139, 92, 246, 0.12)',
                      borderColor: sttTestResult?.success ? 'rgba(16, 185, 129, 0.4)' : 'rgba(139, 92, 246, 0.3)'
                    }}
                    title="Actively send synthetic audio to test transcription model"
                  >
                    <Mic size={13} color="#8b5cf6" />
                    {testingSTT ? 'Testing STT...' : sttTestResult?.success ? `STT OK (${sttTestResult.latency_ms || 280}ms)` : '⚡ Test STT'}
                  </button>

                  {/* Direct LLM Engine Test Button */}
                  <button
                    id="frontPageTestLlmBtn"
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={handleTestLLM}
                    disabled={testingLLM}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontWeight: 700,
                      fontSize: '0.78rem',
                      padding: '6px 12px',
                      background: llmTestResult?.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(2, 132, 199, 0.12)',
                      borderColor: llmTestResult?.success ? 'rgba(16, 185, 129, 0.4)' : 'rgba(2, 132, 199, 0.3)'
                    }}
                    title="Actively send test prompt to verify summary model"
                  >
                    <Zap size={13} color="var(--accent-color)" />
                    {testingLLM ? 'Testing LLM...' : llmTestResult?.success ? `LLM OK (${llmTestResult.latency_ms || 320}ms)` : '⚡ Test LLM'}
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

              {/* Live Test Status Alerts */}
              {(sttTestResult || llmTestResult || verifyStatus) && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {sttTestResult && (
                    <div
                      style={{
                        padding: '7px 12px',
                        borderRadius: '8px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        background: sttTestResult.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: sttTestResult.success ? '#10b981' : '#ef4444',
                        border: sttTestResult.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      {sttTestResult.success ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                      <span><strong>STT Test:</strong> {sttTestResult.message}</span>
                    </div>
                  )}
                  {llmTestResult && (
                    <div
                      style={{
                        padding: '7px 12px',
                        borderRadius: '8px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        background: llmTestResult.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: llmTestResult.success ? '#10b981' : '#ef4444',
                        border: llmTestResult.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      {llmTestResult.success ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                      <span><strong>LLM Test:</strong> {llmTestResult.message}</span>
                    </div>
                  )}
                  {verifyStatus && (
                    <div
                      style={{
                        padding: '7px 12px',
                        borderRadius: '8px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        background: verifyStatus.valid || verifyStatus.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: verifyStatus.valid || verifyStatus.success ? '#10b981' : '#ef4444',
                        border: verifyStatus.valid || verifyStatus.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      {verifyStatus.valid || verifyStatus.success ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                      <span>{verifyStatus.message}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Row 2: Interactive STT Model Selection Buttons */}
              <div style={{ background: 'rgba(0, 0, 0, 0.12)', borderRadius: '12px', padding: '12px', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    <Mic size={14} color="#8b5cf6" /> 🎙️ Transcription STT Model:
                  </label>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                    Active: <strong style={{ color: 'var(--text-primary)' }}>{aiConfig?.transcriptionModel || 'whisper-large-v3-turbo'}</strong>
                  </span>
                </div>

                {/* Quick Segmented Buttons for STT */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {QUICK_STT_MODELS.map((item) => {
                    const isSelected = (aiConfig?.transcriptionModel || 'whisper-large-v3-turbo') === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => handleSelectSTTModel(item)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 13px',
                          borderRadius: '8px',
                          fontSize: '0.78rem',
                          fontWeight: isSelected ? 800 : 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          background: isSelected ? 'rgba(139, 92, 246, 0.22)' : 'rgba(255, 255, 255, 0.04)',
                          color: isSelected ? '#a78bfa' : 'var(--text-secondary)',
                          border: isSelected ? '1.5px solid #8b5cf6' : '1px solid var(--border-color)',
                          boxShadow: isSelected ? '0 0 12px rgba(139, 92, 246, 0.35)' : 'none'
                        }}
                      >
                        <span>{item.icon}</span>
                        <span>{item.shortLabel}</span>
                        {isSelected && <Check size={13} color="#a78bfa" />}
                      </button>
                    );
                  })}

                  {/* STT Dropdown for other/custom models */}
                  <select
                    className="form-control"
                    style={{ fontSize: '0.76rem', padding: '5px 8px', fontWeight: 600, maxWidth: '170px', height: '32px' }}
                    value={aiConfig?.transcriptionModel || 'whisper-large-v3-turbo'}
                    onChange={(e) => setAiConfig && setAiConfig({ ...aiConfig, transcriptionModel: e.target.value })}
                  >
                    <option value="whisper-large-v3-turbo">More STT options...</option>
                    {((MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).stt || []).map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Row 3: Interactive Summary LLM Model Selection Buttons */}
              <div style={{ background: 'rgba(0, 0, 0, 0.12)', borderRadius: '12px', padding: '12px', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    <Cpu size={14} color="var(--accent-color)" /> ⚡ Summary LLM Model:
                  </label>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                    Active: <strong style={{ color: 'var(--text-primary)' }}>{aiConfig?.summarizationModel || 'gemini-3.7-flash'}</strong>
                  </span>
                </div>

                {/* Quick Segmented Buttons for LLM */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  {QUICK_LLM_MODELS.map((item) => {
                    const isSelected = (aiConfig?.summarizationModel || 'gemini-3.7-flash') === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => handleSelectLLMModel(item)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 13px',
                          borderRadius: '8px',
                          fontSize: '0.78rem',
                          fontWeight: isSelected ? 800 : 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          background: isSelected ? 'rgba(2, 132, 199, 0.22)' : 'rgba(255, 255, 255, 0.04)',
                          color: isSelected ? 'var(--accent-color)' : 'var(--text-secondary)',
                          border: isSelected ? '1.5px solid var(--accent-color)' : '1px solid var(--border-color)',
                          boxShadow: isSelected ? '0 0 12px rgba(2, 132, 199, 0.35)' : 'none'
                        }}
                      >
                        <span>{item.icon}</span>
                        <span>{item.shortLabel}</span>
                        {isSelected && <Check size={13} color="var(--accent-color)" />}
                      </button>
                    );
                  })}

                  {/* LLM Dropdown for other/custom models */}
                  <select
                    className="form-control"
                    style={{ fontSize: '0.76rem', padding: '5px 8px', fontWeight: 600, maxWidth: '170px', height: '32px' }}
                    value={aiConfig?.summarizationModel || 'gemini-3.7-flash'}
                    onChange={(e) => setAiConfig && setAiConfig({ ...aiConfig, summarizationModel: e.target.value, modelName: e.target.value })}
                  >
                    <option value="gemini-3.7-flash">More LLM options...</option>
                    {((MODEL_OPTIONS_BY_PROVIDER[aiConfig?.provider || 'gemini'] || MODEL_OPTIONS_BY_PROVIDER.groq).llm || []).map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

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
                marginBottom: '8px',
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
          </div>
        )}
      </div>
    </div>
  );
}
