import React from 'react';
import { Moon, Sun, Cloud, Mic, Settings } from 'lucide-react';

export default function Header({ theme, toggleTheme, onOpenGDrive, onOpenSettings }) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="logo-img-container" title="Eminence AI Transcription Hub">
          <img src="/eminence_logo.png" alt="Eminence Logo" className="logo-img" />
          <div className="transcription-sign-badge" title="Live Transcription Engine Active">
            <Mic size={13} color="#ffffff" />
            <span className="sign-pulse"></span>
          </div>
        </div>
        <div>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 800, letterSpacing: '-0.02em', margin: 0, display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span>Eminence Transcription & Meeting Minutes AI</span>
            <div className="transcription-pill">
              <span className="live-dot"></span>
              <div className="sound-wave-bars">
                <span></span><span></span><span></span><span></span>
              </div>
              <span>AI Transcription</span>
            </div>
            <span className="org-badge">EASD</span>
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '4px 0 0 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Eminence Associates for Social Development</span>
            <span style={{ opacity: 0.4 }}>•</span>
            <span style={{ color: 'var(--eminence-cerulean)', fontWeight: 600 }}>Groq Whisper & Dual Language Executive Minutes</span>
          </p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        {/* Quick Theme Toggle In Place */}
        <button
          className="btn btn-secondary"
          onClick={toggleTheme}
          title="Toggle Light / Dark Mode"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px', fontSize: '0.85rem' }}
        >
          {theme === 'light' ? (
            <>
              <Moon size={16} color="var(--eminence-blue)" /> <span>Dark Mode</span>
            </>
          ) : (
            <>
              <Sun size={16} color="#f59e0b" /> <span>Light Mode</span>
            </>
          )}
        </button>

        {/* Secondary Settings Menu */}
        <button
          className="btn btn-secondary"
          onClick={onOpenSettings}
          title="Open Settings & Font Engine"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', fontSize: '0.85rem' }}
        >
          <Settings size={16} /> <span>Settings</span>
        </button>

        <button className="btn btn-primary" onClick={onOpenGDrive} style={{ padding: '8px 14px', fontSize: '0.85rem' }}>
          <Cloud size={16} /> GDrive Sync
        </button>
      </div>
    </header>
  );
}

