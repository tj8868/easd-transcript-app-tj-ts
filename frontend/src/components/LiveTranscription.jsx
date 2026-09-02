import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Mic,
  Radio,
  Sparkles,
  Send,
  Copy,
  Check,
  Trash2,
  Globe,
  Play,
  Pause,
  Square,
  Volume2,
  Download,
  FileAudio,
  Plus,
  Layers,
  Clock,
  RotateCcw
} from 'lucide-react';

export default function LiveTranscription({
  aiConfig,
  orgContext,
  activeSkills,
  customSkillsList,
  activeTemplateId,
  onSendToBangla,
  onSendToEnglish,
  onFitToTemplate,
  onRecordingProcessed,
  scrollToSection
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [language, setLanguage] = useState('auto'); // 'auto', 'bn', 'en'
  const [liveTranscript, setLiveTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [statusText, setStatusText] = useState('Ready to record');
  const [detectedLang, setDetectedLang] = useState(null);
  const [isCopied, setIsCopied] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Auto-Queue of recorded segments/takes
  const [recordingsQueue, setRecordingsQueue] = useState([]);
  const [isTranscribingRecorded, setIsTranscribingRecorded] = useState(false);

  const socketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const currentChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const isRecordingRef = useRef(false);
  const isPausedRef = useRef(false);
  const timerIntervalRef = useRef(null);
  const isStartingRecognitionRef = useRef(false);
  const transcriptBottomRef = useRef(null);
  const currentTakeSecondsRef = useRef(0);

  // Auto-scroll transcript box as new speech appears
  useEffect(() => {
    if (transcriptBottomRef.current) {
      transcriptBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveTranscript, interimText]);

  // Keep refs synchronized
  useEffect(() => {
    isRecordingRef.current = isRecording;
    isPausedRef.current = isPaused;
  }, [isRecording, isPaused]);

  // Clean up object URLs on unmount
  useEffect(() => {
    return () => {
      recordingsQueue.forEach((item) => {
        if (item.url) URL.revokeObjectURL(item.url);
      });
    };
  }, []);

  // Language detector helper
  const detectTextLang = (text) => {
    if (!text) return 'bn';
    const bnChars = (text.match(/[\u0980-\u09FF]/g) || []).length;
    const enChars = (text.match(/[a-zA-Z]/g) || []).length;
    return bnChars > 0 && bnChars >= enChars * 0.25 ? 'bn' : enChars > bnChars ? 'en' : 'bn';
  };

  // Format seconds to HH:MM:SS or MM:SS
  const formatTime = (totalSec) => {
    const hrs = Math.floor(totalSec / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;
    if (hrs > 0) {
      return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Calculate total queued duration in seconds
  const totalQueuedSeconds = recordingsQueue.reduce((acc, curr) => acc + (curr.duration || 0), 0);

  // Pick best browser-supported MediaRecorder MIME type
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
      if (MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return '';
  };

  // Start Web Speech recognition engine with safe auto-restart
  const startSpeechEngine = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('Web Speech API is not supported in this browser environment.');
      return;
    }

    try {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
        recognitionRef.current = null;
      }

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      if (language === 'bn') {
        recognition.lang = 'bn-BD';
      } else if (language === 'en') {
        recognition.lang = 'en-US';
      } else {
        recognition.lang = 'bn-BD';
      }

      recognition.onresult = (event) => {
        let interim = '';
        let finalChunk = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const piece = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalChunk += piece + ' ';
          } else {
            interim += piece;
          }
        }

        if (finalChunk) {
          setLiveTranscript((prev) => {
            const updated = (prev ? `${prev} ${finalChunk.trim()}` : finalChunk.trim()).trim();
            setDetectedLang(detectTextLang(updated));
            return updated;
          });
          setInterimText('');
        } else {
          setInterimText(interim);
        }
      };

      recognition.onerror = (event) => {
        console.warn('Speech engine notice:', event.error);
        if (event.error === 'not-allowed') {
          setStatusText('Microphone permission blocked.');
        }
      };

      recognition.onend = () => {
        // Auto-restart recognition while recording continues
        if (isRecordingRef.current && !isPausedRef.current && !isStartingRecognitionRef.current) {
          isStartingRecognitionRef.current = true;
          setTimeout(() => {
            if (isRecordingRef.current && !isPausedRef.current) {
              try {
                recognition.start();
              } catch (e) {}
            }
            isStartingRecognitionRef.current = false;
          }, 200);
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
    } catch (e) {
      console.warn('Speech recognition start failed:', e);
    }
  };

  // Start Live Audio Recording (Adds new take to Auto-Queue without overwriting)
  const startRecording = async () => {
    try {
      setStatusText('Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

      // 1. Audio Visualizer & Level Meter
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
          for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
          }
          const avg = sum / bufferLength;
          setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (err) {
        console.warn('Audio visualizer setup notice:', err);
      }

      // 2. Setup Current Take Chunks & Timer
      currentChunksRef.current = [];
      currentTakeSecondsRef.current = 0;
      setRecordingSeconds(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);

      // 3. Initialize Browser MediaRecorder
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
        if (currentChunksRef.current.length > 0) {
          const actualMime = mimeType || mediaRecorder.mimeType || 'audio/webm';
          const audioBlob = new Blob(currentChunksRef.current, { type: actualMime });
          const audioUrl = URL.createObjectURL(audioBlob);
          const duration = currentTakeSecondsRef.current || 1;
          const partIndex = recordingsQueue.length + 1;

          const newQueueItem = {
            id: `rec_${Date.now()}_${partIndex}`,
            partNumber: partIndex,
            name: `Take #${partIndex}`,
            blob: audioBlob,
            url: audioUrl,
            duration: duration,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          };

          setRecordingsQueue((prev) => [...prev, newQueueItem]);
          setStatusText(`✓ Take #${partIndex} saved to Auto-Queue (${formatTime(duration)}).`);
        }
      };

      mediaRecorder.start(1000);

      // 4. Start Live Web Speech Engine
      startSpeechEngine();

      setIsRecording(true);
      setIsPaused(false);
      const nextPartNum = recordingsQueue.length + 1;
      setStatusText(`● Recording Take #${nextPartNum} (Auto-Queue Active)...`);
    } catch (err) {
      console.error('Microphone access error:', err);
      alert('Microphone access was denied or not found. Please ensure microphone permissions are granted in browser settings.');
      setStatusText('Mic access denied.');
    }
  };

  // Pause / Resume Current Recording Take
  const togglePause = () => {
    if (!isRecording) return;
    if (!isPaused) {
      setIsPaused(true);
      setStatusText('⏸ Recording paused');
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    } else {
      setIsPaused(false);
      setStatusText(`● Recording Take #${recordingsQueue.length + 1}...`);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
        mediaRecorderRef.current.resume();
      }
      startSpeechEngine();
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);
    }
  };

  // Stop Recording (Auto-pushes current take into queue without overwriting previous takes)
  const stopRecording = () => {
    setIsRecording(false);
    setIsPaused(false);
    isRecordingRef.current = false;
    isPausedRef.current = false;
    setAudioLevel(0);
    setInterimText('');

    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }

    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }

    if (socketRef.current) {
      try {
        if (socketRef.current.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({ type: 'stop' }));
          socketRef.current.close();
        }
      } catch (e) {}
    }
  };

  // Remove a single take from the auto-queue
  const handleRemoveQueueItem = (id) => {
    setRecordingsQueue((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target && target.url) URL.revokeObjectURL(target.url);
      const filtered = prev.filter((item) => item.id !== id);
      return filtered.map((item, idx) => ({
        ...item,
        partNumber: idx + 1,
        name: `Take #${idx + 1}`
      }));
    });
  };

  // Clear entire queue and reset
  const handleClearAll = () => {
    recordingsQueue.forEach((item) => {
      if (item.url) URL.revokeObjectURL(item.url);
    });
    setRecordingsQueue([]);
    setLiveTranscript('');
    setInterimText('');
    setRecordingSeconds(0);
    setStatusText('Auto-Queue cleared and reset.');
  };

  // 1-Click Transcribe All Auto-Queued Takes as a Continuous Meeting
  const handleTranscribeAllQueuedTakes = async () => {
    if (recordingsQueue.length === 0) {
      alert('No recordings in the Auto-Queue. Please record some speech first.');
      return;
    }

    setIsTranscribingRecorded(true);
    setStatusText(`⚡ Sending all ${recordingsQueue.length} queued takes (${formatTime(totalQueuedSeconds)}) to AI Speech Model...`);

    const formData = new FormData();
    formData.append('provider', aiConfig.provider || 'groq');
    formData.append('api_key', (aiConfig.apiKey || '').trim());
    formData.append('base_url', (aiConfig.baseUrl || '').trim());
    formData.append('model_name', aiConfig.summarizationModel || aiConfig.modelName || 'openai/gpt-oss-120b');
    formData.append('transcription_model', aiConfig.transcriptionModel || 'whisper-large-v3-turbo');
    formData.append('summarization_model', aiConfig.summarizationModel || 'openai/gpt-oss-120b');
    formData.append('org_context', orgContext || '');

    const activeSkillPrompts = (activeSkills || []).map((sId) => {
      const found = (customSkillsList || []).find((c) => c.id === sId);
      if (found) return `[${found.category} Skill] ${found.name}: ${found.prompt}`;
      return `[Skill: ${sId}]`;
    }).join('\n');
    formData.append('custom_skills', activeSkillPrompts);
    formData.append('template_id', activeTemplateId || 'easd_default_minutes');

    // Append all queued audio blobs in exact sequence
    recordingsQueue.forEach((item, index) => {
      const mime = item.blob.type || 'audio/webm';
      const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
      const audioFile = new File([item.blob], `meeting_take_${index + 1}_${Date.now()}.${ext}`, { type: mime });
      formData.append('files', audioFile);
    });

    try {
      const res = await axios.post('/api/transcribe_and_summarize', formData);
      setIsTranscribingRecorded(false);

      if (res.data && res.data.status === 'success') {
        const payload = res.data.data;
        if (payload.bangla_transcript) {
          setLiveTranscript(payload.bangla_transcript);
          setDetectedLang('bn');
        } else if (payload.english_transcript) {
          setLiveTranscript(payload.english_transcript);
          setDetectedLang('en');
        }

        if (onRecordingProcessed) {
          onRecordingProcessed(payload);
        } else if (onFitToTemplate) {
          onFitToTemplate(payload.bangla_transcript || payload.english_transcript || liveTranscript);
        }

        setStatusText(`✓ All ${recordingsQueue.length} queued takes transcribed & synthesized into minutes!`);
        alert('All queued meeting recordings successfully transcribed with AI! Scrolled to Document Preview.');
        if (scrollToSection) scrollToSection('section-export');
      } else {
        setStatusText('Transcription completed with notices.');
        alert('Processing returned: ' + (res.data?.detail || 'Unknown response'));
      }
    } catch (err) {
      setIsTranscribingRecorded(false);
      setStatusText('AI Transcription Error: ' + (err.response?.data?.detail || err.message));
      alert('AI Server Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Copy live transcript
  const handleCopyLive = () => {
    if (!liveTranscript) return;
    navigator.clipboard.writeText(liveTranscript);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // Send to Bangla Transcript
  const handleSendBangla = () => {
    const fullText = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!fullText) {
      alert('Live transcript is empty.');
      return;
    }
    onSendToBangla(fullText);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  // Send to English Transcript
  const handleSendEnglish = () => {
    const fullText = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!fullText) {
      alert('Live transcript is empty.');
      return;
    }
    onSendToEnglish(fullText);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  // Fit live transcript to template
  const handleFitTemplate = () => {
    const fullText = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!fullText) {
      alert('Live transcript is empty.');
      return;
    }
    onFitToTemplate(fullText);
  };

  // Download all recorded parts
  const handleDownloadPart = (item) => {
    if (!item || !item.url) return;
    const mime = item.blob.type || 'audio/webm';
    const ext = mime.includes('mp4') ? 'mp4' : mime.includes('wav') ? 'wav' : 'webm';
    const a = document.createElement('a');
    a.href = item.url;
    a.download = `EASD_Meeting_${item.name.replace(/\s+/g, '_')}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="card" id="section-live" style={{ marginBottom: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Radio size={20} color="var(--accent-color)" /> 🎙️ Auto-Queue Recording & Transcription Studio
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Continuous recording with <strong>Auto-Queue</strong>: Multiple takes are preserved sequentially so accidental stops never overwrite your work!
          </p>
        </div>

        {/* Controls Bar */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            <Globe size={14} />
            <select
              className="form-control"
              style={{ width: 'auto', padding: '4px 8px', fontSize: '0.8rem' }}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isRecording}
            >
              <option value="auto">Auto-Detect Language</option>
              <option value="bn">Bangla (বাংলা)</option>
              <option value="en">English</option>
            </select>
          </div>

          {!isRecording ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={startRecording}
              style={{ padding: '8px 16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {recordingsQueue.length > 0 ? (
                <>
                  <Plus size={16} /> Record Next Part (#{recordingsQueue.length + 1})
                </>
              ) : (
                <>
                  <Mic size={16} /> Start Recording
                </>
              )}
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={togglePause}
                style={{ padding: '8px 12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                {isPaused ? <Play size={14} color="var(--accent-color)" /> : <Pause size={14} />}
                {isPaused ? 'Resume' : 'Pause'}
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={stopRecording}
                style={{
                  padding: '8px 16px',
                  fontWeight: 700,
                  background: 'rgba(239, 68, 68, 0.2)',
                  color: '#ef4444',
                  borderColor: '#ef4444',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Square size={14} fill="#ef4444" /> Stop & Save Take
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Live Status & Recording Metrics */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
          padding: '10px 14px',
          background: 'var(--bg-secondary)',
          borderRadius: '10px',
          fontSize: '0.85rem',
          flexWrap: 'wrap',
          gap: '8px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: isRecording ? (isPaused ? '#f59e0b' : '#ef4444') : '#10b981',
              boxShadow: isRecording && !isPaused ? '0 0 10px #ef4444' : 'none',
              animation: isRecording && !isPaused ? 'pulse 1.5s infinite' : 'none'
            }}
          />
          <span style={{ fontWeight: 600 }}>{statusText}</span>

          {isRecording && (
            <span
              style={{
                marginLeft: '8px',
                padding: '2px 8px',
                borderRadius: '6px',
                background: isPaused ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                color: isPaused ? '#f59e0b' : '#ef4444',
                fontSize: '0.8rem',
                fontWeight: 700,
                fontFamily: 'monospace'
              }}
            >
              ⏱ Current Take: {formatTime(recordingSeconds)}
            </span>
          )}

          {recordingsQueue.length > 0 && (
            <span
              style={{
                marginLeft: '6px',
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(14, 165, 233, 0.15)',
                color: 'var(--accent-color)',
                fontSize: '0.78rem',
                fontWeight: 600
              }}
            >
              📁 {recordingsQueue.length} Queued Take{recordingsQueue.length > 1 ? 's' : ''} ({formatTime(totalQueuedSeconds)})
            </span>
          )}

          {detectedLang && (
            <span
              style={{
                marginLeft: '6px',
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(59, 130, 246, 0.15)',
                color: '#60a5fa',
                fontSize: '0.75rem',
                fontWeight: 600
              }}
            >
              Detected: {detectedLang === 'bn' ? 'বাংলা (Bangla)' : 'English'}
            </span>
          )}
        </div>

        {isRecording && !isPaused && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Volume2 size={16} color={audioLevel > 60 ? '#ef4444' : 'var(--accent-color)'} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Mic:</span>
            <div style={{ width: '80px', height: '8px', background: 'var(--border-color)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${audioLevel}%`,
                  height: '100%',
                  backgroundColor: audioLevel > 70 ? '#ef4444' : '#10b981',
                  transition: 'width 0.1s ease'
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Real-time Streaming Transcript Output Box */}
      <div
        className="form-control"
        style={{
          minHeight: '140px',
          maxHeight: '240px',
          overflowY: 'auto',
          padding: '14px',
          fontFamily: detectedLang === 'bn' || language === 'bn' ? "'Hind Siliguri', sans-serif" : 'inherit',
          fontSize: '0.95rem',
          lineHeight: '1.6',
          whiteSpace: 'pre-wrap',
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '12px',
          border: isRecording ? '1px solid var(--accent-color)' : '1px solid var(--border-color)'
        }}
      >
        {liveTranscript || interimText ? (
          <>
            {liveTranscript}
            {interimText && <span style={{ color: 'var(--accent-color)', opacity: 0.85, fontStyle: 'italic' }}> {interimText}</span>}
            <div ref={transcriptBottomRef} />
          </>
        ) : (
          <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            {isRecording
              ? 'Listening... Speak into the microphone. Words stream here in real-time and will be saved in your Auto-Queue...'
              : 'Live speech will appear here. All recorded takes auto-queue below so nothing is overwritten if a recording pauses or stops.'}
          </span>
        )}
      </div>

      {/* Auto-Queue Shelf: Displays all sequentially preserved recording takes */}
      {recordingsQueue.length > 0 && (
        <div
          style={{
            marginTop: '14px',
            padding: '14px',
            background: 'rgba(14, 165, 233, 0.06)',
            border: '1px solid rgba(14, 165, 233, 0.25)',
            borderRadius: '12px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--accent-color)" />
              <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                Auto-Queued Recordings ({recordingsQueue.length} Take{recordingsQueue.length > 1 ? 's' : ''} • Total {formatTime(totalQueuedSeconds)})
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {!isRecording && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={startRecording}
                  style={{ fontSize: '0.78rem', padding: '4px 10px', fontWeight: 600 }}
                >
                  <Plus size={14} /> Add Take #{recordingsQueue.length + 1}
                </button>
              )}

              <button
                className="btn btn-primary btn-sm"
                onClick={handleTranscribeAllQueuedTakes}
                disabled={isTranscribingRecorded || isRecording}
                style={{ fontSize: '0.82rem', fontWeight: 700, padding: '6px 14px' }}
              >
                <Sparkles size={14} />
                {isTranscribingRecorded
                  ? 'Transcribing All Takes...'
                  : `⚡ Transcribe All ${recordingsQueue.length} Take${recordingsQueue.length > 1 ? 's' : ''} & Fit Minutes`}
              </button>
            </div>
          </div>

          {/* List of individual takes */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
            {recordingsQueue.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  gap: '8px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                  <FileAudio size={16} color="var(--accent-color)" />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.name} ({formatTime(item.duration)})
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                      Saved at {item.timestamp}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <audio src={item.url} controls style={{ height: '26px', width: '130px' }} />
                  <button
                    onClick={() => handleDownloadPart(item)}
                    title="Download this take"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '2px' }}
                  >
                    <Download size={14} />
                  </button>
                  <button
                    onClick={() => handleRemoveQueueItem(item.id)}
                    title="Remove this take"
                    disabled={isRecording}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px' }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCopyLive}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.8rem' }}
          >
            {isCopied ? <Check size={14} color="var(--success-color)" /> : <Copy size={14} />}
            {isCopied ? 'Copied!' : 'Copy Text'}
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleClearAll}
            disabled={(!liveTranscript && !interimText && recordingsQueue.length === 0) || isRecording}
            style={{ fontSize: '0.8rem' }}
          >
            <Trash2 size={14} /> Clear All & Reset
          </button>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSendBangla}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.8rem' }}
          >
            <Send size={14} /> 📋 Send to Bangla Transcript
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSendEnglish}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.8rem' }}
          >
            <Send size={14} /> 📋 Send to English Transcript
          </button>

          <button
            className="btn btn-primary btn-sm"
            onClick={handleFitTemplate}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.8rem', fontWeight: 700 }}
          >
            <Sparkles size={14} /> ⚡ Fit to Template
          </button>
        </div>
      </div>
    </div>
  );
}
