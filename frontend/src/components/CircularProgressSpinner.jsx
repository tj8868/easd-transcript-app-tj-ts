import React, { useState, useEffect } from 'react';

/**
 * Reusable Circular Progress Spinner with animated spinning ring and live percentage.
 * Follows DRY principle: Reused across Transcript box (Stage 3) and Document Preview (Stage 5).
 */
export default function CircularProgressSpinner({
  progress, // number 0-100 or undefined for simulated smooth progress
  title = 'Processing...',
  subtitle = '',
  color = '#0284c7',
  glowColor = 'rgba(2, 132, 199, 0.4)',
  size = 88,
  strokeWidth = 6
}) {
  const [simulatedProgress, setSimulatedProgress] = useState(12);

  // Smooth simulated progress if explicit progress is not provided
  useEffect(() => {
    if (typeof progress === 'number') {
      setSimulatedProgress(Math.min(100, Math.max(0, Math.round(progress))));
      return;
    }

    setSimulatedProgress(10);
    const interval = setInterval(() => {
      setSimulatedProgress((prev) => {
        if (prev < 70) {
          return prev + Math.max(1, Math.floor((75 - prev) * 0.12));
        } else if (prev < 90) {
          return prev + 1;
        } else if (prev < 98) {
          // Asymptotic micro-increments so it NEVER freezes or gets stuck at 94%
          return Math.random() > 0.45 ? prev + 1 : prev;
        }
        return prev;
      });
    }, 450);

    return () => clearInterval(interval);
  }, [progress]);

  const activePct = typeof progress === 'number' ? Math.round(progress) : simulatedProgress;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (activePct / 100) * circumference;

  return (
    <div
      className="circular-progress-overlay"
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(10, 14, 23, 0.72)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        borderRadius: '12px',
        zIndex: 25,
        padding: '20px',
        textAlign: 'center',
        animation: 'fadeIn 0.25s ease'
      }}
    >
      <div style={{ position: 'relative', width: size, height: size, marginBottom: '14px' }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          style={{ transform: 'rotate(-90deg)' }}
        >
          {/* Background Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="transparent"
            stroke="rgba(255, 255, 255, 0.12)"
            strokeWidth={strokeWidth}
          />
          {/* Animated Progress Ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="transparent"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{
              transition: 'stroke-dashoffset 0.4s ease',
              filter: `drop-shadow(0 0 8px ${glowColor})`
            }}
          />
        </svg>

        {/* Center Percentage Display */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column'
          }}
        >
          <span
            style={{
              fontSize: size > 80 ? '1.15rem' : '0.95rem',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.02em',
              lineHeight: 1
            }}
          >
            {activePct}%
          </span>
        </div>
      </div>

      {/* Status Titles */}
      <div style={{ maxWidth: '360px' }}>
        <h4
          style={{
            margin: '0 0 4px 0',
            fontSize: '0.96rem',
            fontWeight: 700,
            color: '#f0f6fc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <span
            style={{
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: color,
              boxShadow: `0 0 10px ${color}`,
              animation: 'pulse 1.2s infinite'
            }}
          />
          {title}
        </h4>
        {subtitle && (
          <p
            style={{
              margin: 0,
              fontSize: '0.78rem',
              color: 'var(--text-secondary, #8b949e)',
              lineHeight: 1.35
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}
