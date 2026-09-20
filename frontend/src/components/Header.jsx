import React from 'react';
import { Moon, Sun, Mic, Settings } from 'lucide-react';

export default function Header({
  theme,
  toggleTheme,
  onOpenSettings,
  customLogo
}) {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="logo-img-container" title="eCommunicator">
          <img src={customLogo || '/eminence_logo.png'} alt="eCommunicator Logo" className="logo-img" />
          <div className="transcription-sign-badge" title="Live Transcription Engine Active">
            <Mic size={13} color="#ffffff" />
            <span className="sign-pulse"></span>
          </div>
        </div>
        <div className="brand-text">
          <h1 className="brand-title">
            <span className="brand-name">eCommunicator</span>
          </h1>
        </div>
      </div>
      <div className="header-actions">
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

        {/* Primary Settings Button */}
        <button
          className="btn btn-primary header-btn"
          onClick={onOpenSettings}
          title="Open Settings, AI Engines, Cloud Sync & Font Engine"
        >
          <Settings size={15} /> <span className="btn-label-desktop">Settings</span>
        </button>
      </div>
    </header>
  );
}

