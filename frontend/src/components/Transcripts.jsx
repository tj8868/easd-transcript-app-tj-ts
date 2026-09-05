import React, { useState } from 'react';
import { FileText, Copy, Check, Download, Trash2, Mic, Radio, Sparkles } from 'lucide-react';

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
      `  EASD MEETING TRANSCRIPT - EXPORTED ON ${today}`,
      `============================================================\n`,
      currentText,
      `\n============================================================`
    ].join('\n');

    downloadTextFile(`EASD_Meeting_Transcript_${today}.txt`, content);
    setDownloaded(true);
    setTimeout(() => setDownloaded(false), 2000);
  };

  const handleClear = () => {
    if (window.confirm('Are you sure you want to clear the transcript?')) {
      handleTextChange('');
    }
  };

  return (
    <div className="card" id="section-transcripts" style={{ border: isRecording ? '1.5px solid var(--accent-color)' : '1.5px solid var(--border-color)', transition: 'border-color 0.25s ease' }}>
      {/* Header & Controls Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
              <FileText size={20} color="var(--accent-color)" /> Transcript
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
            Unified transcript generated directly from what you say and recorded takes (fully editable)
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleDownload}
            disabled={!currentText}
            title="Download transcript as a clean text file (.txt)"
            style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600 }}
          >
            {downloaded ? <Check size={14} /> : <Download size={14} />}
            {downloaded ? 'Downloaded!' : '📥 Download (.txt)'}
          </button>
          
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            disabled={!currentText}
            title="Copy entire transcript to clipboard"
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

      {/* Single Unified Transcript Area */}
      <div className="form-group" style={{ marginBottom: 0 }}>
        <textarea
          id="unified-transcript-textarea"
          className="form-control"
          rows={12}
          style={{
            fontFamily: "'Hind Siliguri', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
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
              ? '🎙️ Listening... Whatever you say into the microphone is streaming live into this transcript...'
              : 'Your live transcript generated from speech will stream and appear here in real time... You can also type or edit directly anytime.'
          }
          value={currentText}
          onChange={(e) => handleTextChange(e.target.value)}
        />
      </div>

      {/* Footer Meta */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
        <span>Supports both Bangla (বাংলা) and English verbatim speech.</span>
        <span>{wordCount} words | {charCount} characters</span>
      </div>
    </div>
  );
}
