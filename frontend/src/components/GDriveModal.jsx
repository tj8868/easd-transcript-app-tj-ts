import React, { useState } from 'react';
import { Cloud, X, Check, AlertCircle } from 'lucide-react';

export default function GDriveModal({ isOpen, onClose, onUpload, status }) {
  const [token, setToken] = useState(localStorage.getItem('gdriveToken') || '');

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (!token.trim()) {
      alert('Please enter a valid Google OAuth Access Token.');
      return;
    }
    localStorage.setItem('gdriveToken', token.trim());
    onUpload(token.trim());
  };

  return (
    <div class="modal">
      <div class="modal-content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Cloud size={20} color="var(--accent-color)" /> Send to Google Drive
          </h3>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }} onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div class="form-group">
          <label>Google OAuth Access Token:</label>
          <input
            type="password"
            class="form-control"
            placeholder="Paste Google Drive OAuth Access Token..."
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
            Obtain access token via Google OAuth2 authorization flow or console.
          </small>
        </div>

        <div class="form-group">
          <label>Destination Folder Name:</label>
          <input type="text" class="form-control" value="EASD - meeting minutes" readOnly />
          <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
            Target folder inside Google Drive root.
          </small>
        </div>

        {status && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              marginTop: '12px',
              background: status.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : status.type === 'error' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(99, 102, 241, 0.2)',
              color: status.type === 'success' ? '#10b981' : status.type === 'error' ? '#ef4444' : 'var(--text-primary)'
            }}
          >
            {status.message}
            {status.link && (
              <div style={{ marginTop: '4px' }}>
                <a href={status.link} target="_blank" rel="noreferrer" style={{ color: '#10b981', fontWeight: 'bold' }}>
                  Open File in Google Drive ↗
                </a>
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
          <button class="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button class="btn btn-success" onClick={handleConfirm}>
            <Cloud size={16} /> Upload Now
          </button>
        </div>
      </div>
    </div>
  );
}
