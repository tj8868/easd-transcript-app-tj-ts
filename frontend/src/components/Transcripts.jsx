import React, { useState } from 'react';
import { FileText, Copy, Check, Download, Trash2, Mic, Radio, Sparkles, User, Users, Clock, Wand2 } from 'lucide-react';

export default function Transcripts({
  transcript = '',
  setTranscript,
  // Backward-compatibility props if needed
  banglaTranscript,
  setBanglaTranscript,
  englishTranscript,
  setEnglishTranscript,
  isRecording = false,
  activeTakeCount = 0
}) {
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  // Derive current active transcript value
  const currentText = transcript || banglaTranscript || englishTranscript || '';

  const handleTextChange = (newVal) => {
    if (setTranscript) {
      setTranscript(newVal);
    }
    if (setBanglaTranscript) {
      setBanglaTranscript(newVal);
    }
    if (setEnglishTranscript) {
      setEnglishTranscript(newVal);
    }
  };

  const wordCount = currentText.trim() ? currentText.trim().split(/\s+/).length : 0;
  const charCount = currentText.length;

  const downloadTextFile = (filename, content) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!currentText) {
      alert('Transcript is empty.');
      return;
    }
    navigator.clipboard.writeText(currentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!currentText) {
      alert('Transcript is empty. Nothing to download.');
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    const content = [
      `============================================================`,
      `  EASD RAW MEETING TRANSCRIPT (BY SPEAKER & TIME) - ${today}`,
      `============================================================\n`,
      currentText,
      `\n============================================================`
    ].join('\n');

    downloadTextFile(`EASD_Raw_Transcript_${today}.txt`, content);
    setDownloaded(true);
    setTimeout(() => setDownloaded(false), 2000);
  };

  const handleClear = () => {
    if (window.confirm('Are you sure you want to clear the raw transcript?')) {
      handleTextChange('');
    }
  };

  // Insert speaker tag or timestamp at cursor or end of transcript
  const handleInsertTag = (tag) => {
    const textarea = document.getElementById('unified-transcript-textarea');
    if (!textarea) {
      handleTextChange(currentText ? `${currentText}\n${tag} ` : `${tag} `);
      return;
    }
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const before = currentText.substring(0, start);
    const after = currentText.substring(end);
    const needsNewline = before.length > 0 && !before.endsWith('\n');
    const insertion = (needsNewline ? '\n' : '') + `${tag} `;
    const updated = before + insertion + after;
    handleTextChange(updated);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + insertion.length, start + insertion.length);
    }, 50);
  };

  // Auto-format plain unformatted text into [MM:SS] Speaker X: lines
  const handleAutoFormatSpeakerTime = () => {
    if (!currentText.trim()) {
      alert('Transcript is empty. Speak or enter raw text to format.');
      return;
    }
    const lines = currentText.split('\n').map((l) => l.trim()).filter(Boolean);
    let currentSpeakerIdx = 1;
    let currentSeconds = 0;
    const formatted = lines.map((line) => {
      if (/^\[\d{2}:\d{2}\]/.test(line)) return line;
      const mins = Math.floor(currentSeconds / 60);
      const secs = currentSeconds % 60;
      const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
      const speakerName = `Speaker ${currentSpeakerIdx}`;
      currentSeconds += 15;
      currentSpeakerIdx = currentSpeakerIdx === 1 ? 2 : 1;
      return `[${timeStr}] ${speakerName}: ${line}`;
    }).join('\n');
    handleTextChange(formatted);
  };

  return (
    <div className="card" id="section-transcripts" style={{ border: isRecording ? '1.5px solid var(--accent-color)' : '1.5px solid var(--border-color)', transition: 'border-color 0.25s ease' }}>
      {/* Header & Controls Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
              <FileText size={20} color="var(--accent-color)" /> Raw Meeting Transcript (By Speaker & Time)
            </h2>

            {isRecording ? (
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '3px 10px',
                  borderRadius: '20px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  color: '#ef4444',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontWeight: 700
                }}
              >
                <span
                  style={{
                    width: '7px',
                    height: '7px',
                    borderRadius: '50%',
                    backgroundColor: '#ef4444',
                    animation: 'pulse 1.2s infinite'
                  }}
                />
                ● Real-Time Speech Active
              </span>
            ) : currentText ? (
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.12)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  fontWeight: 600
                }}
              >
                {wordCount} words • {charCount} characters
              </span>
            ) : null}
          </div>

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', marginTop: '4px', marginBottom: 0 }}>
            Verbatim speech conversation stream. AI synthesized minutes, agendas & decisions compile separately below.
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleDownload}
            disabled={!currentText}
            title="Download raw transcript (.txt)"
            style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600 }}
          >
            {downloaded ? <Check size={14} /> : <Download size={14} />}
            {downloaded ? 'Downloaded!' : '📥 Download (.txt)'}
          </button>
          
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            disabled={!currentText}
            title="Copy raw transcript to clipboard"
            style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '5px' }}
          >
            {copied ? <Check size={14} color="var(--success-color)" /> : <Copy size={14} />}
            {copied ? 'Copied!' : '📋 Copy'}
          </button>

          {currentText && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleClear}
              title="Clear transcript content"
              style={{ fontSize: '0.78rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Trash2 size={13} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Speaker & Timestamp Quick Tags Toolstrip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 12px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          marginBottom: '10px',
          flexWrap: 'wrap'
        }}
      >
        <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Users size={13} color="var(--accent-color)" /> Tag Utterance:
        </span>
        <button
          type="button"
          onClick={() => handleInsertTag('[00:00] Speaker 1:')}
          style={{
            padding: '3px 9px',
            borderRadius: '12px',
            fontSize: '0.72rem',
            fontWeight: 600,
            background: 'rgba(56, 189, 248, 0.15)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            color: '#38bdf8',
            cursor: 'pointer'
          }}
        >
          + Speaker 1
        </button>
        <button
          type="button"
          onClick={() => handleInsertTag('[00:00] Speaker 2:')}
          style={{
            padding: '3px 9px',
            borderRadius: '12px',
            fontSize: '0.72rem',
            fontWeight: 600,
            background: 'rgba(52, 211, 153, 0.15)',
            border: '1px solid rgba(52, 211, 153, 0.3)',
            color: '#34d399',
            cursor: 'pointer'
          }}
        >
          + Speaker 2
        </button>
        <button
          type="button"
          onClick={() => {
            const now = new Date();
            const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
            handleInsertTag(`[${timeStr}] Speaker:`);
          }}
          style={{
            padding: '3px 9px',
            borderRadius: '12px',
            fontSize: '0.72rem',
            fontWeight: 600,
            background: 'rgba(168, 85, 247, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            color: '#c084fc',
            cursor: 'pointer'
          }}
        >
          + Current Time
        </button>
        <button
          type="button"
          onClick={handleAutoFormatSpeakerTime}
          disabled={!currentText.trim()}
          title="Auto-tag paragraphs with timestamps and alternating speakers"
          style={{
            padding: '3px 10px',
            borderRadius: '12px',
            fontSize: '0.72rem',
            fontWeight: 700,
            background: 'var(--accent-glow)',
            border: '1px solid var(--accent-color)',
            color: 'var(--accent-color)',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            marginLeft: 'auto'
          }}
        >
          <Wand2 size={12} /> Auto-Tag Speakers & Time
        </button>
      </div>

      {/* Single Unified Raw Transcript Area */}
      <div className="form-group" style={{ marginBottom: 0 }}>
        <textarea
          id="unified-transcript-textarea"
          className="form-control"
          rows={12}
          style={{
            fontFamily: "'Hind Siliguri', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace",
            fontSize: '1.02rem',
            lineHeight: '1.75',
            padding: '16px',
            borderRadius: '12px',
            background: 'var(--bg-secondary)',
            border: isRecording ? '1.5px solid rgba(16, 185, 129, 0.45)' : '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            transition: 'all 0.2s ease',
            resize: 'vertical'
          }}
          placeholder={
            isRecording
              ? '🎙️ Listening... Real-time speech streams here in [MM:SS] Speaker X: <words> format...'
              : '[00:00] Speaker 1: Speak into microphone or paste raw spoken conversation here by speaker and time...'
          }
          value={currentText}
          onChange={(e) => handleTextChange(e.target.value)}
        />
      </div>

      {/* Footer Meta */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
        <span>Raw verbatim speech formatted by speaker & timestamp.</span>
        <span>{wordCount} words | {charCount} characters</span>
      </div>
    </div>
  );
}
