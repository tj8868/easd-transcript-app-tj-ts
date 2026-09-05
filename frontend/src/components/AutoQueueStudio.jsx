import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Mic,
  Plus,
  Play,
  Pause,
  Square,
  Sparkles,
  Layers,
  FileAudio,
  Download,
  Trash2,
  Volume2,
  UploadCloud,
  FolderOpen,
  Upload
} from 'lucide-react';

export default function AutoQueueStudio({
  aiConfig,
  orgContext,
  activeSkills,
  customSkillsList,
  activeTemplateId,
  onRecordingProcessed,
  scrollToSection
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [statusText, setStatusText] = useState('Ready to record or upload');
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordingsQueue, setRecordingsQueue] = useState([]);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef(null);

  const mediaRecorderRef = useRef(null);
  const currentChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);
  const streamRef = useRef(null);
  const isRecordingRef = useRef(false);
  const isPausedRef = useRef(false);
  const timerIntervalRef = useRef(null);
  const currentTakeSecondsRef = useRef(0);

  useEffect(() => {
    isRecordingRef.current = isRecording;
    isPausedRef.current = isPaused;
  }, [isRecording, isPaused]);

  useEffect(() => {
    return () => {
      recordingsQueue.forEach((item) => {
        if (item.url) URL.revokeObjectURL(item.url);
      });
    };
  }, []);

  const formatTime = (totalSec) => {
    const hrs = Math.floor(totalSec / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;
    if (hrs > 0) {
      return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleAddFiles = (files) => {
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
        isUpload: true
      });
    });
    setRecordingsQueue((prev) => [...prev, ...newItems]);
    setStatusText(`✓ Added ${newItems.length} file(s) to queue`);
  };

  const totalQueuedSeconds = recordingsQueue.reduce((acc, curr) => acc + (curr.duration || 0), 0);

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

  const startRecordingTake = async () => {
    try {
      setStatusText('Requesting mic...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

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

      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);

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
          setStatusText(`✓ Take #${partIndex} saved to queue (${formatTime(duration)})`);
        }
      };

      mediaRecorder.start(1000);
      setIsRecording(true);
      setIsPaused(false);
      const nextPartNum = recordingsQueue.length + 1;
      setStatusText(`Recording Take #${nextPartNum}...`);
    } catch (err) {
      console.error('Mic access error:', err);
      alert('Microphone access is needed to record takes. Please check browser permissions.');
      setStatusText('Mic Blocked');
    }
  };

  const togglePauseTake = () => {
    if (!isRecording) return;
    if (!isPaused) {
      setIsPaused(true);
      setStatusText('Paused');
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.pause();
      }
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    } else {
      setIsPaused(false);
      setStatusText(`Recording Take #${recordingsQueue.length + 1}...`);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
        mediaRecorderRef.current.resume();
      }
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          const updated = prev + 1;
          currentTakeSecondsRef.current = updated;
          return updated;
        });
      }, 1000);
    }
  };

  const stopRecordingTake = () => {
    setIsRecording(false);
    setIsPaused(false);
    isRecordingRef.current = false;
    isPausedRef.current = false;
    setAudioLevel(0);

    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (audioContextRef.current) audioContextRef.current.close().catch(() => {});

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
  };

  const handleRemoveTake = (id) => {
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

  const handleClearQueue = () => {
    recordingsQueue.forEach((item) => {
      if (item.url) URL.revokeObjectURL(item.url);
    });
    setRecordingsQueue([]);
    setRecordingSeconds(0);
    setStatusText('Queue cleared');
  };

  const handleTranscribeAll = async () => {
    if (recordingsQueue.length === 0) {
      alert('No recordings in queue. Please record at least one take first.');
      return;
    }

    setIsTranscribing(true);
    setStatusText(`⚡ Sending ${recordingsQueue.length} takes to AI Transcription...`);

    const formData = new FormData();
    formData.append('provider', aiConfig.provider || 'groq');
    formData.append('api_key', (aiConfig.apiKey || '').trim());
    formData.append('base_url', (aiConfig.baseUrl || '').trim());
    formData.append('model_name', aiConfig.summarizationModel || aiConfig.modelName || 'openai/gpt-oss-120b');
    formData.append('transcription_model', aiConfig.transcriptionModel || 'whisper-large-v3-turbo');
    formData.append('summarization_model', aiConfig.summarizationModel || 'openai/gpt-oss-120b');
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
        alert('All queued takes successfully transcribed! Scrolled to Document Preview.');
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

  return (
    <div className="card" id="section-queue">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
            <UploadCloud size={20} color="var(--accent-color)" /> Upload
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', marginTop: '2px' }}>
            Upload audio & video files (Drag & Drop) or record takes for batch AI transcription
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {!isRecording ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={startRecordingTake}
              style={{ padding: '8px 16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {recordingsQueue.length > 0 ? (
                <>
                  <Plus size={15} /> Record Take #{recordingsQueue.length + 1}
                </>
              ) : (
                <>
                  <Mic size={15} /> Record Take
                </>
              )}
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={togglePauseTake}
                style={{ padding: '8px 12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                {isPaused ? <Play size={14} color="var(--accent-color)" /> : <Pause size={14} />}
                {isPaused ? 'Resume' : 'Pause'}
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={stopRecordingTake}
                style={{
                  padding: '8px 14px',
                  fontWeight: 700,
                  background: 'rgba(239, 68, 68, 0.2)',
                  color: '#ef4444',
                  borderColor: '#ef4444',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Square size={13} fill="#ef4444" /> Save Take
              </button>
            </div>
          )}

          {recordingsQueue.length > 0 && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleTranscribeAll}
              disabled={isTranscribing || isRecording}
              style={{ padding: '8px 16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Sparkles size={14} />
              {isTranscribing ? 'Transcribing...' : `⚡ Transcribe All (${recordingsQueue.length})`}
            </button>
          )}
        </div>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
          if (e.dataTransfer && e.dataTransfer.files) {
            handleAddFiles(e.dataTransfer.files);
          }
        }}
        onClick={() => fileInputRef.current?.click()}
        style={{
          cursor: 'pointer',
          padding: '16px 14px',
          borderRadius: '12px',
          border: isDragging ? '2px dashed #10b981' : '1.5px dashed var(--border-color)',
          background: isDragging ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 0, 0, 0.22)',
          boxShadow: isDragging ? '0 0 16px rgba(16, 185, 129, 0.35)' : 'none',
          textAlign: 'center',
          marginBottom: '12px',
          transition: 'all 0.2s ease',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px'
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="audio/*,video/*,.mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,.mp4,.mkv,.mov,.webm,.avi"
          style={{ display: 'none' }}
          onChange={(e) => handleAddFiles(e.target.files)}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <UploadCloud size={24} color={isDragging ? 'var(--accent-color)' : 'var(--text-secondary)'} />
          <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {isDragging ? 'Drop audio or video files here!' : 'Drag & Drop Audio / Video Files Here, or Click to Browse'}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          Drop files directly into the multi-take queue shelf for <strong>⚡ Transcribe All</strong> (Supports MP3, WAV, M4A, MOV, MP4, WebM)
        </p>
      </div>

      {/* Status Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
          padding: '8px 12px',
          background: 'var(--bg-secondary)',
          borderRadius: '10px',
          fontSize: '0.82rem',
          flexWrap: 'wrap',
          gap: '8px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '0.75rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              background: isRecording ? (isPaused ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.25)') : 'rgba(16, 185, 129, 0.2)',
              color: isRecording ? (isPaused ? '#f59e0b' : '#ef4444') : '#10b981',
              border: `1px solid ${isRecording ? (isPaused ? '#f59e0b' : '#ef4444') : '#10b981'}`
            }}
          >
            {isRecording ? (isPaused ? '⏸ PAUSED' : '● REC') : '✓ READY'}
          </span>
          <span style={{ fontWeight: 600 }}>{statusText}</span>

          {isRecording && (
            <span
              style={{
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
                fontSize: '0.8rem',
                fontWeight: 700,
                fontFamily: 'monospace'
              }}
            >
              Take Time: {formatTime(recordingSeconds)}
            </span>
          )}

          {recordingsQueue.length > 0 && (
            <span
              style={{
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(16, 185, 129, 0.15)',
                color: 'var(--accent-color)',
                fontSize: '0.78rem',
                fontWeight: 600
              }}
            >
              Queue: {recordingsQueue.length} Take{recordingsQueue.length > 1 ? 's' : ''} • Total {formatTime(totalQueuedSeconds)}
            </span>
          )}
        </div>

        {isRecording && !isPaused && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Volume2 size={15} color={audioLevel > 60 ? '#ef4444' : 'var(--accent-color)'} />
            <div style={{ width: '70px', height: '6px', background: 'var(--border-color)', borderRadius: '3px', overflow: 'hidden' }}>
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

      {/* Queued Takes Shelf */}
      {recordingsQueue.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
          {recordingsQueue.map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                background: 'var(--bg-secondary)',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                gap: '8px',
                minWidth: 0
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                <FileAudio size={16} color="var(--accent-color)" />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {item.name} ({formatTime(item.duration)})
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Saved at {item.timestamp}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                <audio src={item.url} controls style={{ height: '26px', width: '120px' }} />
                <button
                  onClick={() => handleDownloadTake(item)}
                  title="Download take"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '2px' }}
                >
                  <Download size={14} />
                </button>
                <button
                  onClick={() => handleRemoveTake(item.id)}
                  title="Remove take"
                  disabled={isRecording}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem', background: 'rgba(0,0,0,0.1)', borderRadius: '10px', border: '1px dashed var(--border-color)' }}>
          No audio takes queued yet. Click <strong>Record Take</strong> above to record segments of speech without losing earlier parts.
        </div>
      )}

      {recordingsQueue.length > 0 && (
        <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleClearQueue}
            disabled={isRecording}
            style={{ fontSize: '0.78rem' }}
          >
            <Trash2 size={13} /> Clear All Takes
          </button>
        </div>
      )}
    </div>
  );
}
