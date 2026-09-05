import React, { useState, useEffect, useRef } from 'react';
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
  Globe
} from 'lucide-react';

export default function LiveRecording({
  onSendToBangla,
  onSendToEnglish,
  scrollToSection
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [language, setLanguage] = useState('auto'); // 'auto', 'bn', 'en'
  const [liveTranscript, setLiveTranscript] = useState('');
  const [interimText, setInterimText] = useState('');
  const [statusText, setStatusText] = useState('Ready');
  const [detectedLang, setDetectedLang] = useState(null);
  const [isCopied, setIsCopied] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  const recognitionRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animFrameRef = useRef(null);
  const isRecordingRef = useRef(false);
  const isPausedRef = useRef(false);
  const isStartingRecognitionRef = useRef(false);
  const transcriptBottomRef = useRef(null);

  // Auto-scroll transcript box as new speech streams in
  useEffect(() => {
    if (transcriptBottomRef.current) {
      transcriptBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [liveTranscript, interimText]);

  useEffect(() => {
    isRecordingRef.current = isRecording;
    isPausedRef.current = isPaused;
  }, [isRecording, isPaused]);

  // Clean up mic and recognition on unmount
  useEffect(() => {
    return () => {
      stopEngine();
    };
  }, []);

  // Script-based language detector helper
  const detectTextLang = (text) => {
    if (!text) return 'bn';
    const bnChars = (text.match(/[\u0980-\u09FF]/g) || []).length;
    const enChars = (text.match(/[a-zA-Z]/g) || []).length;
    return bnChars > 0 && bnChars >= enChars * 0.25 ? 'bn' : enChars > bnChars ? 'en' : 'bn';
  };

  // Start Web Speech Engine with auto-restart
  const startSpeechEngine = (activeLang) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech Recognition is not supported in this browser. Please use Chrome, Edge, or a Web Speech-compatible browser.');
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

      const chosen = activeLang || language;
      if (chosen === 'en') {
        recognition.lang = 'en-US';
      } else if (chosen === 'bn') {
        recognition.lang = 'bn-BD';
      } else {
        // In auto mode, default to Bangla locale which also accepts English loanwords, or auto-detect
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
          if (interim) {
            setDetectedLang(detectTextLang(interim));
          }
        }
      };

      recognition.onerror = (event) => {
        if (event.error === 'not-allowed') {
          setStatusText('Mic Blocked');
        }
      };

      recognition.onend = () => {
        if (isRecordingRef.current && !isPausedRef.current && !isStartingRecognitionRef.current) {
          isStartingRecognitionRef.current = true;
          setTimeout(() => {
            if (isRecordingRef.current && !isPausedRef.current) {
              try {
                recognition.start();
              } catch (e) {}
            }
            isStartingRecognitionRef.current = false;
          }, 150);
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
    } catch (e) {
      console.warn('Speech engine start notice:', e);
    }
  };

  const startLive = async () => {
    try {
      setStatusText('Connecting...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

      // Audio Level Visualizer
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioCtx();
        audioContextRef.current = ctx;
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 64;
        src.connect(analyser);
        analyserRef.current = analyser;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        const update = () => {
          if (!analyserRef.current || !isRecordingRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
          const avg = sum / bufferLength;
          setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(update);
        };
        update();
      } catch (err) {
        console.warn('Visualizer setup notice:', err);
      }

      startSpeechEngine(language);
      setIsRecording(true);
      setIsPaused(false);
      setStatusText('Listening');
    } catch (err) {
      console.error('Mic access error:', err);
      alert('Microphone permission is required for live transcription. Please allow microphone access in your browser.');
      setStatusText('Blocked');
    }
  };

  const togglePause = () => {
    if (!isRecording) return;
    if (!isPaused) {
      setIsPaused(true);
      setStatusText('Paused');
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
    } else {
      setIsPaused(false);
      setStatusText('Listening');
      startSpeechEngine(language);
    }
  };

  const stopEngine = () => {
    setIsRecording(false);
    setIsPaused(false);
    isRecordingRef.current = false;
    isPausedRef.current = false;
    setAudioLevel(0);
    setInterimText('');
    setStatusText('Ready');

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

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
  };

  const handleLanguageSwitch = (newLang) => {
    setLanguage(newLang);
    if (isRecording && !isPaused) {
      startSpeechEngine(newLang);
    }
  };

  const handleCopy = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleClear = () => {
    setLiveTranscript('');
    setInterimText('');
  };

  const handleSendToBanglaClick = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) {
      alert('Live speech is empty.');
      return;
    }
    onSendToBangla(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  const handleSendToEnglishClick = () => {
    const text = (liveTranscript + (interimText ? ' ' + interimText : '')).trim();
    if (!text) {
      alert('Live speech is empty.');
      return;
    }
    onSendToEnglish(text);
    if (scrollToSection) scrollToSection('section-transcripts');
  };

  return (
    <div className="card" id="section-live">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
            <Radio size={20} color="var(--accent-color)" /> Live Record
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', marginTop: '2px' }}>
            Instant speech transcription in your language as you speak
          </p>
        </div>

        {/* Controls & Language Pills */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Colorblind-safe Language Selector */}
          <div style={{ display: 'inline-flex', background: 'rgba(0, 0, 0, 0.3)', borderRadius: '10px', padding: '3px', border: '1px solid var(--border-color)' }}>
            <button
              className={`toggle-opt ${language === 'auto' ? 'active-yes' : ''}`}
              onClick={() => handleLanguageSwitch('auto')}
              title="Auto-detect spoken language"
              style={{ fontSize: '0.78rem', padding: '4px 8px' }}
            >
              🌐 Auto
            </button>
            <button
              className={`toggle-opt ${language === 'bn' ? 'active-yes' : ''}`}
              onClick={() => handleLanguageSwitch('bn')}
              title="Bangla Speech"
              style={{ fontSize: '0.78rem', padding: '4px 8px' }}
            >
              🇧🇩 বাংলা
            </button>
            <button
              className={`toggle-opt ${language === 'en' ? 'active-yes' : ''}`}
              onClick={() => handleLanguageSwitch('en')}
              title="English Speech"
              style={{ fontSize: '0.78rem', padding: '4px 8px' }}
            >
              🇬🇧 English
            </button>
          </div>

          {!isRecording ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={startLive}
              style={{ padding: '8px 16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Mic size={15} /> Start Live
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '6px' }}>
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
                onClick={stopEngine}
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
                <Square size={13} fill="#ef4444" /> Stop
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Live Status & Audio Meter */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '10px',
          padding: '8px 12px',
          background: 'var(--bg-secondary)',
          borderRadius: '10px',
          fontSize: '0.82rem',
          flexWrap: 'wrap',
          gap: '8px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Accessible indicator with distinct icons + labels (not color alone) */}
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

          {detectedLang && (
            <span
              style={{
                padding: '2px 8px',
                borderRadius: '6px',
                background: 'rgba(59, 130, 246, 0.15)',
                color: '#60a5fa',
                fontSize: '0.75rem',
                fontWeight: 600
              }}
            >
              Speaker: {detectedLang === 'bn' ? 'বাংলা (Bangla)' : 'English'}
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

      {/* Streaming Live Speech Box */}
      <div
        className="form-control"
        style={{
          minHeight: '130px',
          maxHeight: '220px',
          overflowY: 'auto',
          padding: '12px 14px',
          fontFamily: detectedLang === 'bn' || language === 'bn' ? "'Hind Siliguri', sans-serif" : 'inherit',
          fontSize: '0.96rem',
          lineHeight: '1.6',
          whiteSpace: 'pre-wrap',
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '12px',
          border: isRecording ? '1.5px solid var(--accent-color)' : '1px solid var(--border-color)'
        }}
      >
        {liveTranscript || interimText ? (
          <>
            {liveTranscript}
            {interimText && <span style={{ color: 'var(--accent-color)', opacity: 0.9, fontStyle: 'italic' }}> {interimText}</span>}
            <div ref={transcriptBottomRef} />
          </>
        ) : (
          <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            {isRecording
              ? 'Listening... Speak into the microphone. Words will appear here in real-time as you speak.'
              : 'Click "Start Live" and speak. Live transcription in your language will stream here instantly.'}
          </span>
        )}
      </div>

      {/* Quick Action Buttons */}
      <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.78rem' }}
          >
            {isCopied ? <Check size={13} color="var(--success-color)" /> : <Copy size={13} />}
            {isCopied ? 'Copied!' : 'Copy'}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleClear}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.78rem' }}
          >
            <Trash2 size={13} /> Clear
          </button>
        </div>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSendToBanglaClick}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.78rem' }}
          >
            <Send size={13} /> Send to Bangla
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleSendToEnglishClick}
            disabled={!liveTranscript && !interimText}
            style={{ fontSize: '0.78rem' }}
          >
            <Send size={13} /> Send to English
          </button>
        </div>
      </div>
    </div>
  );
}
