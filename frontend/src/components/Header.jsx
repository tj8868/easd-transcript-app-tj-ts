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
        <div className="brand-text">
          <h1 className="brand-title">
            <span className="brand-name">Eminence Minutes AI</span>
            <div className="transcription-pill">
              <span className="live-dot"></span>
              <div className="sound-wave-bars">
                <span></span><span></span><span></span><span></span>
              </div>
              <span>AI Transcription</span>
            </div>
            <span className="org-badge">EASD</span>
          </h1>
          <p className="brand-subtitle">
            <span>Eminence Associates for Social Development</span>
            <span style={{ opacity: 0.4 }}>•</span>
            <span style={{ color: 'var(--eminence-cerulean)', fontWeight: 600 }}>Automated Voice Minutes & Clinical Documentation</span>
          </p>
        </div>
      </div>
      <div className="header-actions">
        {/* Front Page Top API Button: Shows ONLY the active API name, not the key/code */}
        <button
          id="topApiButton"
          className="btn btn-secondary header-btn"
          onClick={onOpenApiSettings || onOpenSettings}
          title={`Active AI Engine: ${activeApiName}. Click to configure or switch APIs.`}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#10b981',
              boxShadow: '0 0 8px #10b981',
              display: 'inline-block',
              flexShrink: 0
            }}
          ></span>
          <span style={{ color: 'var(--accent-color)', fontSize: '0.78rem', fontWeight: 800 }}>API:</span>
          <span
            id="activeApiDisplayName"
            style={{
              maxWidth: '120px',
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
            className="btn btn-secondary header-btn"
            onClick={onOpenDeviceViewer}
            title="Visualize responsive layout in Mobile, Tablet, and Desktop components"
          >
            <LayoutGrid size={15} />
            <span className="btn-label-desktop">📱 3-Device View</span>
            <span className="btn-label-mobile">📱 3-Device</span>
          </button>
        )}

        {/* Quick Theme Toggle In Place */}
        <button
          className="btn btn-secondary header-btn"
          onClick={toggleTheme}
          title="Toggle Light / Dark Mode"
        >
          {theme === 'light' ? (
            <>
              <Moon size={15} color="var(--eminence-blue)" /> <span className="btn-label-desktop">Dark</span>
            </>
          ) : (
            <>
              <Sun size={15} color="#f59e0b" /> <span className="btn-label-desktop">Light</span>
            </>
          )}
        </button>

        {/* Secondary Settings Menu */}
        <button
          className="btn btn-secondary header-btn"
          onClick={onOpenSettings}
          title="Open Settings & Font Engine"
        >
          <Settings size={15} /> <span className="btn-label-desktop">Settings</span>
        </button>

        <button className="btn btn-primary header-btn" onClick={onOpenGDrive}>
          <Cloud size={15} />
          <span className="btn-label-desktop">GDrive Sync</span>
          <span className="btn-label-mobile">Sync</span>
        </button>
      </div>
    </header>
  );
}

