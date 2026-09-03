import React, { useState } from 'react';
import { Languages, Copy, Check, Sparkles, Wand2, RefreshCw, Download, FileText } from 'lucide-react';

export default function Transcripts({
  banglaTranscript,
  setBanglaTranscript,
  englishTranscript,
  setEnglishTranscript,
  onSummarizeTranscript,
  isSummarizing
}) {
  const [copiedBangla, setCopiedBangla] = useState(false);
  const [copiedEnglish, setCopiedEnglish] = useState(false);
  const [copiedBoth, setCopiedBoth] = useState(false);
  const [downloadedBoth, setDownloadedBoth] = useState(false);
  const [summarizeModel, setSummarizeModel] = useState('default');

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

  const handleCopyBangla = () => {
    if (!banglaTranscript) {
      alert('Bangla transcript is empty.');
      return;
    }
    navigator.clipboard.writeText(banglaTranscript);
    setCopiedBangla(true);
    setTimeout(() => setCopiedBangla(false), 2000);
  };

  const handleCopyEnglish = () => {
    if (!englishTranscript) {
      alert('English transcript is empty.');
      return;
    }
    navigator.clipboard.writeText(englishTranscript);
    setCopiedEnglish(true);
    setTimeout(() => setCopiedEnglish(false), 2000);
  };

  const handleCopyBoth = () => {
    const text = `=== BANGLA TRANSCRIPT ===\n${banglaTranscript}\n\n=== ENGLISH TRANSCRIPT ===\n${englishTranscript}`;
    navigator.clipboard.writeText(text);
    setCopiedBoth(true);
    setTimeout(() => setCopiedBoth(false), 2000);
  };

  const handleDownloadBoth = () => {
    if (!banglaTranscript && !englishTranscript) {
      alert('Transcripts are empty. Nothing to download.');
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    const content = [
      `============================================================`,
      `  EASD MEETING TRANSCRIPT - EXPORTED ON ${today}`,
      `============================================================\n`,
      `--- BANGLA TRANSCRIPT (বাংলা ট্রান্সক্রিপ্ট) ---`,
      banglaTranscript || '(No Bangla transcript generated)',
      `\n------------------------------------------------------------\n`,
      `--- ENGLISH TRANSCRIPT ---`,
      englishTranscript || '(No English transcript generated)',
      `\n============================================================`
    ].join('\n');

    downloadTextFile(`EASD_Meeting_Transcripts_${today}.txt`, content);
    setDownloadedBoth(true);
    setTimeout(() => setDownloadedBoth(false), 2000);
  };

  const handleDownloadBangla = () => {
    if (!banglaTranscript) {
      alert('Bangla transcript is empty.');
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    downloadTextFile(`EASD_Bangla_Transcript_${today}.txt`, banglaTranscript);
  };

  const handleDownloadEnglish = () => {
    if (!englishTranscript) {
      alert('English transcript is empty.');
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    downloadTextFile(`EASD_English_Transcript_${today}.txt`, englishTranscript);
  };

  const handleTriggerSummarize = () => {
    const textToSummarize = englishTranscript.trim() || banglaTranscript.trim();
    if (!textToSummarize) {
      alert('Please enter or generate a transcript first to summarize.');
      return;
    }
    onSummarizeTranscript(textToSummarize, summarizeModel);
  };

  return (
    <div className="card" id="section-transcripts">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Languages size={20} color="var(--accent-color)" /> 3. Dual Transcripts & AI Summarizer
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Review, manually edit, copy individual transcripts, or trigger specialized AI models to restructure transcripts into the official template.
          </p>
        </div>

        {/* Action Buttons: Download & Copy Transcripts */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleDownloadBoth}
            title="Download full transcripts as a clean text file (.txt)"
            style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600 }}
          >
            {downloadedBoth ? <Check size={14} /> : <Download size={14} />}
            {downloadedBoth ? 'Downloaded Transcript!' : '📥 Download Transcript (.txt)'}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleCopyBoth}
            title="Copy combined transcripts"
            style={{ fontSize: '0.78rem' }}
          >
            {copiedBoth ? <Check size={14} color="var(--success-color)" /> : <Copy size={14} />}
            {copiedBoth ? 'Copied Both Transcripts!' : '📋 Copy Transcripts'}
          </button>
        </div>
      </div>

      <div className="grid-2col">
        <div className="form-group" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', margin: 0, fontWeight: 700 }}>
              <span>🇧🇩</span> Bangla Transcript (বাংলা ট্রান্সক্রিপ্ট):
            </label>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleDownloadBangla}
                title="Download Bangla transcript as .txt"
                style={{ padding: '3px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <Download size={12} /> .txt
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCopyBangla}
                style={{ padding: '3px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                {copiedBangla ? <Check size={12} color="var(--success-color)" /> : <Copy size={12} />}
                {copiedBangla ? 'Copied Bangla!' : 'Copy Bangla'}
              </button>
            </div>
          </div>
          <textarea
            className="form-control"
            rows={10}
            style={{ fontFamily: "'Hind Siliguri', sans-serif", fontSize: '1rem', lineHeight: '1.6' }}
            placeholder="বাংলা ট্রান্সক্রিপ্ট এখানে আসবে... (সম্পাদনাযোগ্য)"
            value={banglaTranscript}
            onChange={(e) => setBanglaTranscript(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', margin: 0, fontWeight: 700 }}>
              <span>🇬🇧</span> English Transcript:
            </label>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleDownloadEnglish}
                title="Download English transcript as .txt"
                style={{ padding: '3px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <Download size={12} /> .txt
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCopyEnglish}
                style={{ padding: '3px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                {copiedEnglish ? <Check size={12} color="var(--success-color)" /> : <Copy size={12} />}
                {copiedEnglish ? 'Copied English!' : 'Copy English'}
              </button>
            </div>
          </div>
          <textarea
            className="form-control"
            rows={10}
            style={{ fontSize: '0.95rem', lineHeight: '1.6' }}
            placeholder="English transcript will appear here... (Fully editable)"
            value={englishTranscript}
            onChange={(e) => setEnglishTranscript(e.target.value)}
          />
        </div>
      </div>

      {/* Dedicated Fit to Template Control Bar */}
      <div style={{ marginTop: '16px', padding: '16px 20px', borderRadius: '14px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Wand2 size={18} color="var(--accent-color)" />
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>⚡ Fit Extracted Text to EASD Template</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Automatically fits raw text into structured Tables, Agendas, Decisions & Attendance for .docx.</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <select
            className="form-control"
            style={{ width: 'auto', padding: '8px 12px', fontSize: '0.85rem' }}
            value={summarizeModel}
            onChange={(e) => setSummarizeModel(e.target.value)}
          >
            <option value="default">Use Configured Provider (GPT-OSS-120B)</option>
            <option value="groq">Groq Cloud (openai/gpt-oss-120b)</option>
            <option value="gemini">Google Gemini (Flash 2.5 / 2.0)</option>
            <option value="openai">OpenAI (GPT-4o)</option>
            <option value="claude">Anthropic Claude 3.5 Sonnet</option>
            <option value="local">Fast Local Semantic Synthesizer</option>
          </select>

          <button
            className="btn btn-primary btn-sm"
            onClick={handleTriggerSummarize}
            disabled={isSummarizing}
            style={{ padding: '8px 18px', fontWeight: 700 }}
          >
            {isSummarizing ? <RefreshCw size={14} className="spin" /> : <Sparkles size={14} />}
            {isSummarizing ? 'Fitting to Template...' : '⚡ Fit to Template'}
          </button>
        </div>
      </div>
    </div>
  );
}
