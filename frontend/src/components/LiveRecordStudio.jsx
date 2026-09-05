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
  Plus
} from 'lucide-react';

export default function LiveRecordStudio({
  aiConfig,
  orgContext,
  activeSkills,
  customSkillsList,
  activeTemplateId,
  onRecordingProcessed,
  onSendToBangla,
  onSendToEnglish,
  scrollToSection
}) {
  // Recording & Live State
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [language, setLanguage] = useState('auto'); // 'auto', 'bn', 'en'
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

  // --- Web Speech Recognition Setup ---
  const initSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('Web Speech API not supported in this browser.');
      return null;
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
      const userLang = navigator.language || 'bn-BD';
      recognition.lang = userLang.startsWith('bn') ? 'bn-BD' : 'en-US';
    }

    recognition.onstart = () => {
      isStartingRecognitionRef.current = false;
      setStatusText(`Live speech streaming active (${recognition.lang})`);
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
      if (finalStr) {
        setLiveTranscript((prev) => (prev ? prev + ' ' + finalStr.trim() : finalStr.trim()));
      }
      setInterimText(interimStr);
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech') return;
      console.warn('Speech recognition notice:', event.error);
    };

    recognition.onend = () => {
      if (isRecordingRef.current && !isPausedRef.current && !isStartingRecognitionRef.current) {
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

  const handleSendBangla = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    if (onSendToBangla) onSendToBangla(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  const handleSendEnglish = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    if (onSendToEnglish) onSendToEnglish(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  return (
    <div className="card" id="section-live" style={{ border: '1.5px solid var(--border-color)', position: 'relative' }}>
      {/* FRONT SCREEN: One Block Record, One Block Upload -- Nothing Else */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '20px',
          maxWidth: '720px',
          margin: '0 auto 20px auto',
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

        {/* BLOCK 2: UPLOAD */}
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
            accept="audio/*,video/*,.mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,.mp4,.mkv,.mov,.webm,.avi"
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
              Upload
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              {isDragging ? 'Drop audio or video files here!' : 'Click or drag audio / video files'}
            </p>
          </div>
        </div>
      </div>

      {/* Live Transcribe Box (Visible when recording or when text exists) */}
      {(isRecording || liveTranscript || interimText) && (
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1.5px solid var(--border-color)',
            borderRadius: '12px',
            padding: '16px',
            marginBottom: '16px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Radio size={14} /> Live Speech Transcription (Instant):
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button className="btn btn-secondary btn-sm" onClick={handleCopyLive} style={{ fontSize: '0.75rem', padding: '4px 8px' }}>
                {isCopied ? <Check size={12} color="#10b981" /> : <Copy size={12} />} {isCopied ? 'Copied' : 'Copy'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleSendBangla} style={{ fontSize: '0.75rem', padding: '4px 8px' }}>
                <Send size={12} /> Send to বাংলা
              </button>
              <button className="btn btn-secondary btn-sm" onClick={handleSendEnglish} style={{ fontSize: '0.75rem', padding: '4px 8px' }}>
                <Send size={12} /> Send to English
              </button>
            </div>
          </div>

          <div
            style={{
              minHeight: '80px',
              maxHeight: '180px',
              overflowY: 'auto',
              background: 'rgba(0, 0, 0, 0.25)',
              padding: '12px',
              borderRadius: '8px',
              fontSize: '0.92rem',
              lineHeight: '1.6',
              color: 'var(--text-primary)',
              whiteSpace: 'pre-wrap',
              fontFamily: language === 'bn' ? "'Hind Siliguri', sans-serif" : 'inherit'
            }}
          >
            {liveTranscript ? (
              <span>{liveTranscript}</span>
            ) : (
              <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                Listening for speech... Speak into microphone.
              </span>
            )}
            {interimText && (
              <span style={{ color: 'var(--accent-color)', opacity: 0.85, fontStyle: 'italic' }}>
                {' ' + interimText}
              </span>
            )}
            <div ref={transcriptBottomRef} />
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
