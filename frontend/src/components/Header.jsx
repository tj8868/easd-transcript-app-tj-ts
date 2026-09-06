import React from 'react';
import { Moon, Sun, Cloud, Mic, Settings, LayoutGrid } from 'lucide-react';

export default function Header({
  theme,
  toggleTheme,
  onOpenGDrive,
  onOpenSettings,
  onOpenDeviceViewer,
  isFrameView = false,
  activeApiName = 'Gemini API',
  onOpenApiSettings
}) {
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
            <span style={{ color: 'var(--eminence-cerulean)', fontWeight: 600 }}>Gemini 3.7 Flash & Dual Language Executive Minutes</span>
          </p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Front Page Top API Button: Shows ONLY the active API name, not the key/code */}
        <button
          id="topApiButton"
          className="btn btn-secondary"
          onClick={onOpenApiSettings || onOpenSettings}
          title={`Active AI Engine: ${activeApiName}. Click to configure or switch APIs.`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            padding: '8px 14px',
            fontSize: '0.85rem',
            fontWeight: 700,
            border: '1px solid var(--accent-color)',
            background: 'rgba(2, 132, 199, 0.10)',
            color: 'var(--text-primary)',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#10b981',
              boxShadow: '0 0 8px #10b981',
              display: 'inline-block'
            }}
          ></span>
          <span style={{ color: 'var(--accent-color)', fontSize: '0.78rem', fontWeight: 800 }}>API:</span>
          <span
            id="activeApiDisplayName"
            style={{
              maxWidth: '150px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: 'var(--text-primary)'
            }}
          >
            {activeApiName}
          </span>
        </button>

        {/* Responsive 3-Device Visualizer Button */}
        {!isFrameView && onOpenDeviceViewer && (
          <button
            className="btn btn-secondary"
            onClick={onOpenDeviceViewer}
            title="Visualize responsive layout in Mobile, Tablet, and Desktop components"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              fontSize: '0.82rem',
              fontWeight: 700,
              border: '1px solid var(--accent-color)',
              color: 'var(--accent-color)',
              background: 'rgba(14, 165, 233, 0.08)'
            }}
          >
            <LayoutGrid size={15} />
            <span>📱 3-Device View</span>
          </button>
        )}

        {/* Quick Theme Toggle In Place */}
        <button
          className="btn btn-secondary"
          onClick={toggleTheme}
          title="Toggle Light / Dark Mode"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', fontSize: '0.85rem' }}
        >
          {theme === 'light' ? (
            <>
              <Moon size={16} color="var(--eminence-blue)" /> <span>Dark</span>
            </>
          ) : (
            <>
              <Sun size={16} color="#f59e0b" /> <span>Light</span>
            </>
          )}
        </button>

        {/* Secondary Settings Menu */}
        <button
          className="btn btn-secondary"
          onClick={onOpenSettings}
          title="Open Settings & Font Engine"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', fontSize: '0.85rem' }}
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

