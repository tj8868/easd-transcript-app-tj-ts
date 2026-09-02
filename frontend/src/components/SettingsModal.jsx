import React, { useState } from 'react';
import { X, Sliders, Type, Palette, Monitor, Check, Sparkles, Smartphone, Apple, Terminal } from 'lucide-react';

export const ACCENT_PALETTES = [
  { id: 'cerulean', name: 'Eminence Cerulean', hex: '#0284c7', glow: 'rgba(2, 132, 199, 0.25)' },
  { id: 'govt_emerald', name: 'Govt Secretariat Emerald', hex: '#047857', glow: 'rgba(4, 120, 87, 0.25)' },
  { id: 'royal_navy', name: 'EASD Royal Navy', hex: '#004b87', glow: 'rgba(0, 75, 135, 0.25)' },
  { id: 'sunset_orange', name: 'Eminence Orange', hex: '#ea580c', glow: 'rgba(234, 88, 12, 0.25)' },
  { id: 'royal_violet', name: 'Thought Leadership Violet', hex: '#7c3aed', glow: 'rgba(124, 58, 237, 0.25)' },
  { id: 'crimson_red', name: 'Crimson Red', hex: '#dc2626', glow: 'rgba(220, 38, 38, 0.25)' }
];

export const BANGLA_FONTS = [
  { id: 'nikosh', name: 'Nikosh (Official Bangladesh Govt Secretariat Standard)', fontStack: "'Nikosh', 'NikoshBAN', 'SolaimanLipi', 'Hind Siliguri', sans-serif" },
  { id: 'nikosh_ban', name: 'NikoshBAN (Govt Bilingual Standard with English Glyphs)', fontStack: "'NikoshBAN', 'Nikosh', 'Hind Siliguri', sans-serif" },
  { id: 'kalpurush', name: 'Kalpurush (Classic Standard Unicode Bangla)', fontStack: "'Kalpurush', 'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'hind_siliguri', name: 'Hind Siliguri (Modern Clean Web Bangla)', fontStack: "'Hind Siliguri', 'SolaimanLipi', sans-serif" },
  { id: 'solaiman_lipi', name: 'SolaimanLipi (Traditional Clean Typography)', fontStack: "'SolaimanLipi', 'Hind Siliguri', sans-serif" }
];

export const ENGLISH_FONTS = [
  { id: 'times_new_roman', name: 'Times New Roman (Microsoft Standard Serif - Official Minutes)', fontStack: "'Times New Roman', Times, serif" },
  { id: 'calibri', name: 'Calibri (Microsoft Standard Sans-Serif - Corporate Briefs)', fontStack: "'Calibri', 'Segoe UI', Arial, sans-serif" },
  { id: 'arial', name: 'Arial (Microsoft High-Legibility Sans-Serif)', fontStack: "Arial, Helvetica, sans-serif" },
  { id: 'inter', name: 'Inter (Modern UI & Presentation Font)', fontStack: "'Inter', system-ui, sans-serif" },
  { id: 'nikosh_ban_en', name: 'NikoshBAN (Bangladesh Govt English Standard)', fontStack: "'NikoshBAN', 'Times New Roman', serif" }
];

export default function SettingsModal({
  isOpen,
  onClose,
  theme,
  setTheme,
  settings,
  setSettings
}) {
  const [activeTab, setActiveTab] = useState('fonts');

  if (!isOpen) return null;

  const currentAccent = settings.accentColor || '#0284c7';
  const currentBangla = settings.banglaFont || 'nikosh';
  const currentEnglish = settings.englishFont || 'times_new_roman';
  const currentScale = settings.docScale || 'standard';

  const handleSelectAccent = (colorHex) => {
    setSettings({ ...settings, accentColor: colorHex });
  };

  const handleSelectBangla = (fontId) => {
    setSettings({ ...settings, banglaFont: fontId });
  };

  const handleSelectEnglish = (fontId) => {
    setSettings({ ...settings, englishFont: fontId });
  };

  return (
    <div className="modal" onClick={onClose} style={{ zIndex: 1100 }}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '680px', width: '92%', maxHeight: '90vh', overflowY: 'auto', padding: '24px 28px' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ background: 'rgba(2, 132, 199, 0.15)', padding: '8px', borderRadius: '10px', color: 'var(--accent-color)' }}>
              <Sliders size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>System Settings & Preferences</h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Configure Font Engine, Appearance, Accent Colors, and Cross-Platform Setup.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
          <button
            className={`btn ${activeTab === 'fonts' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('fonts')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Type size={14} /> Font Engine (Microsoft & Govt)
          </button>
          <button
            className={`btn ${activeTab === 'appearance' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('appearance')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Palette size={14} /> Appearance & Accent Colors
          </button>
          <button
            className={`btn ${activeTab === 'platforms' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setActiveTab('platforms')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Monitor size={14} /> Cross-Platform Package
          </button>
        </div>

        {/* TAB 1: FONT ENGINE */}
        {activeTab === 'fonts' && (
          <div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-color)', padding: '12px 16px', borderRadius: '10px', marginBottom: '18px', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              💡 <strong>Standards-Compliant Font Engine</strong>: Uses official Microsoft Office typographic standards (`Times New Roman`, `Calibri`) and Bangladesh Secretariat Government standards (`Nikosh`, `NikoshBAN`, `Kalpurush`). Applied live to document preview and `.docx` export.
            </div>

            {/* Bangla / Govt Font Selector */}
            <div className="form-group">
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={14} color="var(--accent-color)" /> Bangladesh Government / Bangla Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {BANGLA_FONTS.map((font) => (
                  <div
                    key={font.id}
                    onClick={() => handleSelectBangla(font.id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: currentBangla === font.id ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                      background: currentBangla === font.id ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        {font.name}
                      </div>
                      <div style={{ fontFamily: font.fontStack, fontSize: '0.92rem', color: 'var(--accent-color)', marginTop: '2px' }}>
                        নমুনা: গণপ্রজাতন্ত্রী বাংলাদেশ সরকার — স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়
                      </div>
                    </div>
                    {currentBangla === font.id && <Check size={18} color="var(--accent-color)" />}
                  </div>
                ))}
              </div>
            </div>

            {/* English Font Selector */}
            <div className="form-group" style={{ marginTop: '20px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={14} color="var(--accent-color)" /> English Document & Minutes Font Standard:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {ENGLISH_FONTS.map((font) => (
                  <div
                    key={font.id}
                    onClick={() => handleSelectEnglish(font.id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: currentEnglish === font.id ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                      background: currentEnglish === font.id ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        {font.name}
                      </div>
                      <div style={{ fontFamily: font.fontStack, fontSize: '0.92rem', color: 'var(--accent-color)', marginTop: '2px' }}>
                        Sample: Weekly Strategic, Programmatic and Review Meeting Minutes
                      </div>
                    </div>
                    {currentEnglish === font.id && <Check size={18} color="var(--accent-color)" />}
                  </div>
                ))}
              </div>
            </div>

            {/* Document Scale */}
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>Document Preview Typography Scale:</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                {[
                  { id: 'compact', label: 'Compact (9.5pt / Dense)' },
                  { id: 'standard', label: 'Standard (10.5pt / Word Default)' },
                  { id: 'large', label: 'Large (12pt / High Legibility)' }
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`btn ${currentScale === s.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                    style={{ flex: 1 }}
                    onClick={() => setSettings({ ...settings, docScale: s.id })}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: APPEARANCE & ACCENT COLORS */}
        {activeTab === 'appearance' && (
          <div>
            {/* Theme Toggle inside Settings */}
            <div className="form-group">
              <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>Base Workspace Theme:</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  className={`btn ${theme === 'dark' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setTheme('dark')}
                >
                  🌙 Dark Studio Theme
                </button>
                <button
                  type="button"
                  className={`btn ${theme === 'light' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1 }}
                  onClick={() => setTheme('light')}
                >
                  ☀️ Light Executive Theme
                </button>
              </div>
            </div>

            {/* Accent Color Palette Selector */}
            <div className="form-group" style={{ marginTop: '22px' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Palette size={14} color="var(--accent-color)" /> Accent Color & Dynamic Glow:
              </label>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                Sets the active highlight color across buttons, form borders, active tabs, and input focus rings.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px' }}>
                {ACCENT_PALETTES.map((pal) => (
                  <div
                    key={pal.id}
                    onClick={() => handleSelectAccent(pal.hex)}
                    style={{
                      padding: '12px',
                      borderRadius: '12px',
                      border: currentAccent === pal.hex ? `2px solid ${pal.hex}` : '1px solid var(--border-color)',
                      background: currentAccent === pal.hex ? 'rgba(255, 255, 255, 0.06)' : 'var(--bg-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: pal.hex,
                        boxShadow: `0 0 10px ${pal.glow}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff'
                      }}
                    >
                      {currentAccent === pal.hex && <Check size={14} />}
                    </div>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {pal.name}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Consistent Textbox Preview */}
            <div className="form-group" style={{ marginTop: '24px', background: 'rgba(255, 255, 255, 0.02)', padding: '16px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Consistent Form Control & Textbox Preview:
              </label>
              <input
                type="text"
                className="form-control"
                style={{ fontSize: '0.9rem' }}
                placeholder="Click here to test the consistent focus ring and accent glow..."
                defaultValue="Consistent input field with smooth accent glow border"
              />
            </div>
          </div>
        )}

        {/* TAB 3: CROSS-PLATFORM ARCHITECTURE */}
        {activeTab === 'platforms' && (
          <div>
            <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', marginBottom: '14px', lineHeight: '1.6' }}>
              This single repository structure is built using a decoupled <strong>FastAPI Backend + React Frontend</strong> architecture designed for 100% cross-platform parity across all major operating systems:
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Windows */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#0284c7' }}>
                  <Monitor size={18} /> Windows Portable (.exe & .bat)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Run `python build_windows_exe.py` to generate a standalone portable `.exe` or use `Launch_App.bat` for instant zero-dependency launch.
                </div>
              </div>

              {/* Linux */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#f59e0b' }}>
                  <Terminal size={18} /> Linux (Ubuntu / Debian / AppImage / Docker)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Runs natively with Python 3.11+ & Uvicorn. Packaged as a standalone Linux ELF binary via PyInstaller or self-contained Docker container.
                </div>
              </div>

              {/* macOS */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#a855f7' }}>
                  <Apple size={18} /> macOS (.app & .dmg Bundle)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Compiles into a native `.app` bundle using PyInstaller on macOS with WebKit native windowing (pywebview).
                </div>
              </div>

              {/* Android & iOS */}
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, color: '#10b981' }}>
                  <Smartphone size={18} /> Android (APK) & iOS (PWA / Mobile Web)
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Built as a Progressive Web App (PWA) with offline support or compiled into an Android APK via Capacitor using `build_android_apk.py`.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button className="btn btn-primary" onClick={onClose} style={{ padding: '8px 20px' }}>
            Save & Apply Settings
          </button>
        </div>
      </div>
    </div>
  );
}
