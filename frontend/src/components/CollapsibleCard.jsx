import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function CollapsibleCard({
  id,
  title,
  icon: Icon,
  badge,
  summary,
  isCollapsed = true,
  onToggle,
  children
}) {
  return (
    <div className="collapsible-card" id={id}>
      <div
        className="collapsible-header"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        aria-expanded={!isCollapsed}
        aria-controls={`${id}-content`}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {Icon && <Icon size={20} color="var(--accent-color)" />}
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              {title}
            </h2>
          </div>
          {badge && (
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: '12px',
                background: 'rgba(16, 185, 129, 0.15)',
                color: 'var(--accent-color)',
                fontWeight: 600,
                border: '1px solid rgba(16, 185, 129, 0.3)'
              }}
            >
              {badge}
            </span>
          )}
          {isCollapsed && summary && (
            <span
              style={{
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                marginLeft: '6px'
              }}
            >
              • {summary}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', flexShrink: 0 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>
            {isCollapsed ? 'Expand' : 'Collapse'}
          </span>
          {isCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
        </div>
      </div>

      {!isCollapsed && (
        <div id={`${id}-content`} className="collapsible-body">
          {children}
        </div>
      )}
    </div>
  );
}
