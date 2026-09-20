import React, { useState } from 'react';
import {
  Cloud,
  Download,
  Link as LinkIcon,
  X,
  AlertCircle,
  Check,
  RefreshCw,
  FileAudio
} from 'lucide-react';

const PROVIDERS = [
  {
    id: 'gdrive',
    name: 'Google Drive',
    icon: '☁️',
    color: '#34a853',
    placeholder: 'Paste Google Drive share link (e.g. https://drive.google.com/file/d/...)',
    hint: 'Ensure link permission is set to "Anyone with the link can view".',
    sampleUrl: 'https://drive.google.com/file/d/1sample_easd_audio/view?usp=sharing'
  },
  {
    id: 'dropbox',
    name: 'Dropbox',
    icon: '📦',
    color: '#0061fe',
    placeholder: 'Paste Dropbox shared link (e.g. https://www.dropbox.com/s/...)',
    hint: 'Paste standard Dropbox link or shared file link.',
    sampleUrl: 'https://www.dropbox.com/s/sample_meeting/meeting_recording.mp3?dl=0'
  },
  {
    id: 'onedrive',
    name: 'OneDrive',
    icon: '🔷',
    color: '#0078d4',
    placeholder: 'Paste OneDrive link (e.g. https://1drv.ms/u/... or onedrive.live.com)',
    hint: 'Paste any public or organization shared link.',
    sampleUrl: 'https://1drv.ms/u/s!sample_audio_take'
  }
];

export default function CloudImportModal({
  isOpen,
  onClose,
  initialProvider = 'gdrive',
  onImportFiles
}) {
  const [activeProvider, setActiveProvider] = useState(initialProvider);
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  if (!isOpen) return null;

  const currentProvider = PROVIDERS.find((p) => p.id === activeProvider) || PROVIDERS[0];

  const handleImport = async (targetUrl = url) => {
    const inputUrl = (targetUrl || '').trim();
    if (!inputUrl) {
      setError('Please paste a valid cloud link or URL.');
      return;
    }

    setError('');
    setSuccessMsg('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/import_cloud_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: inputUrl,
          provider: activeProvider
        })
      });

      if (!response.ok) {
        let errData = {};
        try {
          errData = await response.json();
        } catch {}
        throw new Error(errData.detail || `Failed to fetch file (HTTP ${response.status})`);
      }

      // Extract filename from header or URL
      let filename = response.headers.get('X-File-Name');
      if (!filename) {
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename=["']?([^"';]+)["']?/i);
        if (match) filename = match[1];
      }
      if (!filename) {
        const urlParts = inputUrl.split('?')[0].split('/');
        const lastPart = urlParts[urlParts.length - 1];
        if (lastPart && /\.[a-zA-Z0-9]+$/.test(lastPart)) {
          filename = decodeURIComponent(lastPart);
        } else {
          filename = `${currentProvider.id}_import_${Date.now()}.mp3`;
        }
      }

      const blob = await response.blob();
      const mimeType = blob.type || 'audio/mpeg';
      const file = new File([blob], filename, { type: mimeType });

      setSuccessMsg(`✓ Successfully imported "${filename}" (${(blob.size / (1024 * 1024)).toFixed(2)} MB)!`);
      
      setTimeout(() => {
        if (onImportFiles) {
          onImportFiles([file]);
        }
        setIsLoading(false);
        setUrl('');
        setSuccessMsg('');
        onClose();
      }, 500);
    } catch (err) {
      console.error('Cloud import error:', err);
      setError(err.message || 'Failed to download and import file from cloud link.');
      setIsLoading(false);
    }
  };

  const handlePasteClipboard = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          setUrl(text.trim());
          setError('');
        }
      }
    } catch {
      setError('Could not access clipboard. Please paste manually into the box.');
    }
  };

  return (
    <div className="modal" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-content cloud-import-modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '580px', width: '100%', borderRadius: '20px' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                background: 'var(--accent-blue-gradient)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 14px rgba(2, 132, 199, 0.35)'
              }}
            >
              <Cloud size={20} color="#ffffff" />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                Cloud File Ingestion
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Import recordings & documents from Google Drive, Dropbox, or OneDrive
              </p>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={onClose}
            style={{ padding: '6px', borderRadius: '8px', border: 'none', background: 'transparent' }}
            title="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Cloud Provider Tabs */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '8px',
            background: 'var(--bg-primary)',
            padding: '6px',
            borderRadius: '14px',
            border: '1px solid var(--border-color)',
            marginBottom: '20px'
          }}
        >
          {PROVIDERS.map((p) => {
            const isActive = activeProvider === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setActiveProvider(p.id);
                  setError('');
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '10px 8px',
                  borderRadius: '10px',
                  border: isActive ? `1.5px solid ${p.color}` : '1.5px solid transparent',
                  background: isActive ? 'var(--bg-secondary)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: isActive ? '0 4px 12px rgba(0,0,0,0.15)' : 'none'
                }}
              >
                <span>{p.icon}</span>
                <span>{p.name}</span>
              </button>
            );
          })}
        </div>

        {/* Input Area */}
        <div className="form-group" style={{ marginBottom: '14px' }}>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.86rem', fontWeight: 700 }}>
              <LinkIcon size={14} color="var(--accent-color)" />
              {currentProvider.name} Shareable Link
            </span>
            <button
              type="button"
              onClick={handlePasteClipboard}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-color)',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              📋 Paste from Clipboard
            </button>
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              className="form-control"
              placeholder={currentProvider.placeholder}
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError('');
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleImport();
                }
              }}
              disabled={isLoading}
              style={{ paddingRight: url ? '36px' : '14px' }}
            />
            {url && (
              <button
                type="button"
                onClick={() => setUrl('')}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer'
                }}
              >
                <X size={15} />
              </button>
            )}
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
            ℹ️ {currentProvider.hint}
          </p>
        </div>

        {/* Status Messages */}
        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '14px'
            }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#10b981',
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '14px'
            }}
          >
            <Check size={16} style={{ flexShrink: 0 }} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '18px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleImport()}
            disabled={isLoading || !url.trim()}
            style={{ minWidth: '160px', justifyContent: 'center' }}
          >
            {isLoading ? (
              <>
                <RefreshCw size={16} className="spin-anim" />
                <span>Importing...</span>
              </>
            ) : (
              <>
                <Download size={16} />
                <span>Fetch & Ingest</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
