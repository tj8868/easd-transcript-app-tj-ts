import React, { useState } from 'react';
import {
  Smartphone,
  Tablet,
  Monitor,
  LayoutGrid,
  RefreshCw,
  X,
  Maximize2,
  ZoomIn,
  ZoomOut,
  RotateCw,
  ExternalLink
} from 'lucide-react';

function WindowControlDots() {
  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
      <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }} />
      <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10b981' }} />
    </div>
  );
}

export default function ResponsiveDeviceViewer({ onClose, initialMode = 'all' }) {
  const [deviceMode, setDeviceMode] = useState(initialMode); // 'all', 'mobile', 'tablet', 'desktop'
  const [zoomScale, setZoomScale] = useState(0.75); // Scale for 3-device side-by-side mode
  const [orientation, setOrientation] = useState('portrait'); // 'portrait' or 'landscape'
  const [refreshKey, setRefreshKey] = useState(0);

  // Compute target URL for iframes with ?view=frame to suppress nested chrome
  const getFrameUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set('view', 'frame');
    return url.toString();
  };

  const frameUrl = getFrameUrl();

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  const toggleOrientation = () => {
    setOrientation((prev) => (prev === 'portrait' ? 'landscape' : 'portrait'));
  };

  // Device dimensions
  const isLandscape = orientation === 'landscape';
  const mobileWidth = isLandscape ? 812 : 375;
  const mobileHeight = isLandscape ? 375 : 812;

  const tabletWidth = isLandscape ? 1024 : 768;
  const tabletHeight = isLandscape ? 768 : 1024;

  const desktopWidth = 1200;
  const desktopHeight = 820;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#090d16',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
      }}
    >
      {/* Top Inspection & Control Toolbar */}
      <header
        style={{
          background: '#0f172a',
          borderBottom: '1px solid #1e293b',
          padding: '10px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          zIndex: 10
        }}
      >
        {/* Left branding & Mode Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              padding: '6px 10px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #0ea5e9, #3b82f6)',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <LayoutGrid size={16} />
            <span>Responsive Visualizer</span>
          </div>

          <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
            Codespaces Multi-Device Simulator & Responsiveness Inspector
          </span>
        </div>

        {/* Center: Device View Mode Switcher */}
        <div
          style={{
            display: 'inline-flex',
            background: '#1e293b',
            padding: '3px',
            borderRadius: '10px',
            border: '1px solid #334155'
          }}
        >
          <button
            onClick={() => setDeviceMode('all')}
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              fontWeight: 700,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              background: deviceMode === 'all' ? '#0ea5e9' : 'transparent',
              color: deviceMode === 'all' ? '#ffffff' : '#94a3b8'
            }}
          >
            <LayoutGrid size={14} />
            <span>⚡ 3-Device View</span>
          </button>

          <button
            onClick={() => setDeviceMode('mobile')}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: deviceMode === 'mobile' ? 700 : 500,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              background: deviceMode === 'mobile' ? '#0ea5e9' : 'transparent',
              color: deviceMode === 'mobile' ? '#ffffff' : '#94a3b8'
            }}
          >
            <Smartphone size={14} />
            <span>Mobile (375px)</span>
          </button>

          <button
            onClick={() => setDeviceMode('tablet')}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: deviceMode === 'tablet' ? 700 : 500,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              background: deviceMode === 'tablet' ? '#0ea5e9' : 'transparent',
              color: deviceMode === 'tablet' ? '#ffffff' : '#94a3b8'
            }}
          >
            <Tablet size={14} />
            <span>Tablet (768px)</span>
          </button>

          <button
            onClick={() => setDeviceMode('desktop')}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: deviceMode === 'desktop' ? 700 : 500,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              background: deviceMode === 'desktop' ? '#0ea5e9' : 'transparent',
              color: deviceMode === 'desktop' ? '#ffffff' : '#94a3b8'
            }}
          >
            <Monitor size={14} />
            <span>Desktop (1200px)</span>
          </button>
        </div>

        {/* Right Tools: Scale, Rotate, Refresh, Close */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {deviceMode === 'all' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                background: '#1e293b',
                padding: '3px 8px',
                borderRadius: '8px',
                border: '1px solid #334155',
                fontSize: '0.78rem',
                color: '#cbd5e1'
              }}
            >
              <span>Scale:</span>
              <button
                onClick={() => setZoomScale((s) => Math.max(0.4, Number((s - 0.1).toFixed(2))))}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px' }}
                title="Zoom Out"
              >
                <ZoomOut size={13} />
              </button>
              <span style={{ fontWeight: 700, minWidth: '35px', textAlign: 'center' }}>
                {Math.round(zoomScale * 100)}%
              </span>
              <button
                onClick={() => setZoomScale((s) => Math.min(1.2, Number((s + 0.1).toFixed(2))))}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px' }}
                title="Zoom In"
              >
                <ZoomIn size={13} />
              </button>
              <button
                onClick={() => setZoomScale(0.75)}
                style={{ background: 'none', border: 'none', color: '#0ea5e9', cursor: 'pointer', padding: '2px 4px', fontSize: '0.7rem' }}
                title="Reset Fit"
              >
                Fit
              </button>
            </div>
          )}

          {deviceMode !== 'desktop' && deviceMode !== 'all' && (
            <button
              onClick={toggleOrientation}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                color: '#cbd5e1',
                padding: '6px 10px',
                borderRadius: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '0.78rem'
              }}
              title="Rotate Device"
            >
              <RotateCw size={13} />
              <span>{isLandscape ? 'Landscape' : 'Portrait'}</span>
            </button>
          )}

          <button
            onClick={handleRefresh}
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              color: '#cbd5e1',
              padding: '6px 10px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.78rem'
            }}
            title="Reload App Frames"
          >
            <RefreshCw size={13} />
            <span>Reload</span>
          </button>

          <button
            onClick={onClose}
            style={{
              background: '#ef4444',
              border: 'none',
              color: '#ffffff',
              padding: '6px 12px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
              fontSize: '0.8rem'
            }}
            title="Return to Standard View"
          >
            <X size={15} />
            <span>Exit Preview</span>
          </button>
        </div>
      </header>

      {/* Main Canvas Area */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          background: 'radial-gradient(ellipse at center, #1e293b 0%, #090d16 100%)',
          padding: '24px',
          display: 'flex',
          justifyContent: deviceMode === 'all' ? 'flex-start' : 'center',
          alignItems: 'flex-start',
          gap: '32px'
        }}
      >
        {/* ========================================================================= */}
        {/* VIEW 1: ALL 3 DEVICES SIDE-BY-SIDE (MOBILE, TABLET, DESKTOP)              */}
        {/* ========================================================================= */}
        {deviceMode === 'all' && (
          <div
            style={{
              display: 'flex',
              gap: '36px',
              alignItems: 'flex-start',
              transform: `scale(${zoomScale})`,
              transformOrigin: 'top left',
              transition: 'transform 0.15s ease'
            }}
          >
            {/* 1. MOBILE DEVICE COMPONENT */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#0ea5e9', fontWeight: 700, fontSize: '0.88rem' }}>
                  <Smartphone size={16} /> 1. Mobile View
                </div>
                <span style={{ fontSize: '0.72rem', background: '#334155', color: '#94a3b8', padding: '2px 8px', borderRadius: '12px' }}>
                  375 × 812 px
                </span>
              </div>

              {/* Realistic Mobile Frame */}
              <div
                style={{
                  width: '375px',
                  height: '812px',
                  background: '#000000',
                  borderRadius: '40px',
                  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 10px #1e293b, 0 0 0 12px #334155',
                  overflow: 'hidden',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column'
                }}
              >
                {/* Mobile Speaker / Camera Notch */}
                <div
                  style={{
                    height: '24px',
                    background: '#0f172a',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 20
                  }}
                >
                  <div style={{ width: '80px', height: '14px', background: '#000', borderRadius: '0 0 10px 10px' }}></div>
                </div>

                <iframe
                  key={`mobile-${refreshKey}`}
                  src={frameUrl}
                  title="Mobile Preview (375px)"
                  style={{
                    width: '375px',
                    height: '788px',
                    border: 'none',
                    background: '#ffffff'
                  }}
                />
              </div>
            </div>

            {/* 2. TABLET DEVICE COMPONENT */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontWeight: 700, fontSize: '0.88rem' }}>
                  <Tablet size={16} /> 2. Tablet View
                </div>
                <span style={{ fontSize: '0.72rem', background: '#334155', color: '#94a3b8', padding: '2px 8px', borderRadius: '12px' }}>
                  768 × 1024 px
                </span>
              </div>

              {/* Realistic Tablet Frame */}
              <div
                style={{
                  width: '768px',
                  height: '1024px',
                  background: '#000000',
                  borderRadius: '28px',
                  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 12px #1e293b, 0 0 0 14px #334155',
                  overflow: 'hidden',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column'
                }}
              >
                {/* Camera dot */}
                <div style={{ height: '16px', background: '#0f172a', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                  <div style={{ width: '6px', height: '6px', background: '#334155', borderRadius: '50%' }}></div>
                </div>

                <iframe
                  key={`tablet-${refreshKey}`}
                  src={frameUrl}
                  title="Tablet Preview (768px)"
                  style={{
                    width: '768px',
                    height: '1008px',
                    border: 'none',
                    background: '#ffffff'
                  }}
                />
              </div>
            </div>

            {/* 3. DESKTOP DEVICE COMPONENT */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#60a5fa', fontWeight: 700, fontSize: '0.88rem' }}>
                  <Monitor size={16} /> 3. Desktop View
                </div>
                <span style={{ fontSize: '0.72rem', background: '#334155', color: '#94a3b8', padding: '2px 8px', borderRadius: '12px' }}>
                  1200 × 820 px
                </span>
              </div>

              {/* Browser Window Chrome */}
              <div
                style={{
                  width: '1200px',
                  height: '820px',
                  background: '#0f172a',
                  borderRadius: '14px',
                  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px #334155',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column'
                }}
              >
                {/* Browser Title Bar */}
                <div
                  style={{
                    height: '36px',
                    background: '#1e293b',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '0 12px',
                    gap: '12px',
                    borderBottom: '1px solid #334155'
                  }}
                >
                  <WindowControlDots />
                  <div
                    style={{
                      flex: 1,
                      maxWidth: '500px',
                      margin: '0 auto',
                      background: '#0f172a',
                      borderRadius: '6px',
                      padding: '3px 12px',
                      fontSize: '0.72rem',
                      color: '#94a3b8',
                      textAlign: 'center',
                      border: '1px solid #334155'
                    }}
                  >
                    https://codespaces.github.dev/easd-minutes/
                  </div>
                </div>

                <iframe
                  key={`desktop-${refreshKey}`}
                  src={frameUrl}
                  title="Desktop Preview (1200px)"
                  style={{
                    width: '1200px',
                    height: '784px',
                    border: 'none',
                    background: '#ffffff'
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 2: SINGLE DEVICE FOCUSED (MOBILE / TABLET / DESKTOP)                  */}
        {/* ========================================================================= */}
        {deviceMode === 'mobile' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              Focused Mobile Device View ({mobileWidth} × {mobileHeight} px)
            </span>
            <div
              style={{
                width: `${mobileWidth}px`,
                height: `${mobileHeight}px`,
                background: '#000',
                borderRadius: isLandscape ? '24px' : '40px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 10px #1e293b',
                overflow: 'hidden'
              }}
            >
              <iframe
                key={`mobile-focus-${refreshKey}-${orientation}`}
                src={frameUrl}
                title="Focused Mobile View"
                style={{ width: '100%', height: '100%', border: 'none' }}
              />
            </div>
          </div>
        )}

        {deviceMode === 'tablet' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              Focused Tablet View ({tabletWidth} × {tabletHeight} px)
            </span>
            <div
              style={{
                width: `${tabletWidth}px`,
                height: `${tabletHeight}px`,
                background: '#000',
                borderRadius: '24px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 12px #1e293b',
                overflow: 'hidden'
              }}
            >
              <iframe
                key={`tablet-focus-${refreshKey}-${orientation}`}
                src={frameUrl}
                title="Focused Tablet View"
                style={{ width: '100%', height: '100%', border: 'none' }}
              />
            </div>
          </div>
        )}

        {deviceMode === 'desktop' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              Focused Desktop View ({desktopWidth} × {desktopHeight} px)
            </span>
            <div
              style={{
                width: `${desktopWidth}px`,
                height: `${desktopHeight}px`,
                background: '#0f172a',
                borderRadius: '12px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px #334155',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <div
                style={{
                  height: '34px',
                  background: '#1e293b',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 12px',
                  gap: '8px'
                }}
              >
                <WindowControlDots />
              </div>
              <iframe
                key={`desktop-focus-${refreshKey}`}
                src={frameUrl}
                title="Focused Desktop View"
                style={{ width: '100%', flex: 1, border: 'none' }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
