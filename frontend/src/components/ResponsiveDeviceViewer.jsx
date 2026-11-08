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

const MODE_TABS = [
  { id: 'all', Icon: LayoutGrid, label: '3-Device View' },
  { id: 'mobile', Icon: Smartphone, label: 'Mobile (375px)' },
  { id: 'tablet', Icon: Tablet, label: 'Tablet (768px)' },
  { id: 'desktop', Icon: Monitor, label: 'Desktop (1200px)' }
];

const TOOL_BUTTON_STYLE = {
  background: '#1e293b', border: '1px solid #334155', color: '#cbd5e1', padding: '6px 10px',
  borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.78rem'
};

// Title row above each device in the 3-device view.
function DeviceLabel({ Icon, color, label, size }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 6px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color, fontWeight: 700, fontSize: '0.88rem' }}>
        <Icon size={16} /> {label}
      </div>
      <span style={{ fontSize: '0.72rem', background: '#334155', color: '#94a3b8', padding: '2px 8px', borderRadius: '12px' }}>
        {size}
      </span>
    </div>
  );
}

// One device in the 3-device view: label row + device frame (notch / camera / browser bar) + iframe.
function SideBySideDevice({ Icon, color, label, width, height, iframeHeight, frameStyle, chrome, iframeKey, src, title }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <DeviceLabel Icon={Icon} color={color} label={label} size={`${width} × ${height} px`} />
      <div style={{ width: `${width}px`, height: `${height}px`, overflow: 'hidden', display: 'flex', flexDirection: 'column', ...frameStyle }}>
        {chrome}
        <iframe key={iframeKey} src={src} title={title}
          style={{ width: `${width}px`, height: `${iframeHeight}px`, border: 'none', background: '#ffffff' }} />
      </div>
    </div>
  );
}

// Single focused device: caption + frame + iframe (mobile / tablet / desktop).
function FocusedDevice({ caption, width, height, frameStyle, chrome, iframeKey, src, title }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
      <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
        {caption} ({width} × {height} px)
      </span>
      <div style={{ width: `${width}px`, height: `${height}px`, overflow: 'hidden', ...frameStyle }}>
        {chrome}
        <iframe key={iframeKey} src={src} title={title}
          style={chrome ? { width: '100%', flex: 1, border: 'none' } : { width: '100%', height: '100%', border: 'none' }} />
      </div>
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
          {MODE_TABS.map(({ id, Icon, label }) => {
            const active = deviceMode === id;
            return (
              <button
                key={id}
                onClick={() => setDeviceMode(id)}
                style={{
                  padding: id === 'all' ? '6px 14px' : '6px 12px',
                  fontSize: '0.8rem',
                  fontWeight: active || id === 'all' ? 700 : 500,
                  borderRadius: '7px',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.15s ease',
                  background: active ? '#0ea5e9' : 'transparent',
                  color: active ? '#ffffff' : '#94a3b8'
                }}
              >
                <Icon size={14} />
                <span>{label}</span>
              </button>
            );
          })}
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
              style={TOOL_BUTTON_STYLE}
              title="Rotate Device"
            >
              <RotateCw size={13} />
              <span>{isLandscape ? 'Landscape' : 'Portrait'}</span>
            </button>
          )}

          <button
            onClick={handleRefresh}
            style={TOOL_BUTTON_STYLE}
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
            <SideBySideDevice Icon={Smartphone} color="#0ea5e9" label="1. Mobile View" width={375} height={812}
              iframeHeight={788} iframeKey={`mobile-${refreshKey}`} src={frameUrl} title="Mobile Preview (375px)"
              frameStyle={{ background: '#000000', borderRadius: '40px', position: 'relative',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 10px #1e293b, 0 0 0 12px #334155' }}
              chrome={
                <div style={{ height: '24px', background: '#0f172a', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 20 }}>
                  <div style={{ width: '80px', height: '14px', background: '#000', borderRadius: '0 0 10px 10px' }}></div>
                </div>
              } />

            <SideBySideDevice Icon={Tablet} color="#38bdf8" label="2. Tablet View" width={768} height={1024}
              iframeHeight={1008} iframeKey={`tablet-${refreshKey}`} src={frameUrl} title="Tablet Preview (768px)"
              frameStyle={{ background: '#000000', borderRadius: '28px', position: 'relative',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 12px #1e293b, 0 0 0 14px #334155' }}
              chrome={
                <div style={{ height: '16px', background: '#0f172a', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                  <div style={{ width: '6px', height: '6px', background: '#334155', borderRadius: '50%' }}></div>
                </div>
              } />

            <SideBySideDevice Icon={Monitor} color="#60a5fa" label="3. Desktop View" width={1200} height={820}
              iframeHeight={784} iframeKey={`desktop-${refreshKey}`} src={frameUrl} title="Desktop Preview (1200px)"
              frameStyle={{ background: '#0f172a', borderRadius: '14px',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px #334155' }}
              chrome={
                <div style={{ height: '36px', background: '#1e293b', display: 'flex', alignItems: 'center', padding: '0 12px', gap: '12px', borderBottom: '1px solid #334155' }}>
                  <WindowControlDots />
                  <div style={{ flex: 1, maxWidth: '500px', margin: '0 auto', background: '#0f172a', borderRadius: '6px', padding: '3px 12px',
                    fontSize: '0.72rem', color: '#94a3b8', textAlign: 'center', border: '1px solid #334155' }}>
                    https://codespaces.github.dev/easd-minutes/
                  </div>
                </div>
              } />
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 2: SINGLE DEVICE FOCUSED (MOBILE / TABLET / DESKTOP)                  */}
        {/* ========================================================================= */}
        {deviceMode === 'mobile' && (
          <FocusedDevice caption="Focused Mobile Device View" width={mobileWidth} height={mobileHeight}
            iframeKey={`mobile-focus-${refreshKey}-${orientation}`} src={frameUrl} title="Focused Mobile View"
            frameStyle={{ background: '#000', borderRadius: isLandscape ? '24px' : '40px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 10px #1e293b' }} />
        )}

        {deviceMode === 'tablet' && (
          <FocusedDevice caption="Focused Tablet View" width={tabletWidth} height={tabletHeight}
            iframeKey={`tablet-focus-${refreshKey}-${orientation}`} src={frameUrl} title="Focused Tablet View"
            frameStyle={{ background: '#000', borderRadius: '24px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 12px #1e293b' }} />
        )}

        {deviceMode === 'desktop' && (
          <FocusedDevice caption="Focused Desktop View" width={desktopWidth} height={desktopHeight}
            iframeKey={`desktop-focus-${refreshKey}`} src={frameUrl} title="Focused Desktop View"
            frameStyle={{ background: '#0f172a', borderRadius: '12px', display: 'flex', flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 1px #334155' }}
            chrome={
              <div style={{ height: '34px', background: '#1e293b', display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px' }}>
                <WindowControlDots />
              </div>
            } />
        )}
      </div>
    </div>
  );
}
