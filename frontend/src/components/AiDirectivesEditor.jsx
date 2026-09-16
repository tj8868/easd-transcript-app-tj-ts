import React, { useState } from 'react';
import {
  HelpCircle,
  BookOpen,
  ShieldCheck,
  CheckSquare,
  Sparkles,
  Copy,
  Check,
  Info,
  X
} from 'lucide-react';

/**
 * Reusable AI Directives Editor Component
 * Manages the 3 essential AI Directives:
 * 1. Context: What the template is for, its background, purpose, and target audience.
 * 2. Rules: Formatting and writing guidelines, tone, constraints, dos and don'ts.
 * 3. Requirements: Mandatory fields, key sections, specific outputs needed.
 * 
 * Each directive has a dedicated (?) button providing detailed explanations and copyable examples.
 */
function DirectiveBlock({
  icon: IconComponent,
  title,
  helpKey,
  onOpenHelp,
  description,
  value,
  onChange,
  disabled,
  placeholder
}) {
  return (
    <div
      style={{
        background: 'var(--bg-card, rgba(15, 28, 63, 0.6))',
        border: '1px solid var(--border-color)',
        borderRadius: '14px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--accent-color)', display: 'flex', alignItems: 'center' }}>
          <IconComponent size={17} />
        </span>
        <label style={{ fontSize: '0.92rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          {title}
          <button
            type="button"
            onClick={() => onOpenHelp(helpKey)}
            style={{
              background: 'rgba(2, 132, 199, 0.12)',
              border: '1.5px solid var(--accent-border, rgba(2, 132, 199, 0.4))',
              borderRadius: '6px',
              padding: '2px 5px',
              color: 'var(--accent-color)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 1
            }}
            title={`What is ${title}? Click for explanation and examples`}
          >
            <HelpCircle size={14} />
          </button>
        </label>
      </div>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '0 0 4px 0' }}>
        {description}
      </p>
      <textarea
        value={value}
        onChange={onChange}
        disabled={disabled}
        placeholder={placeholder}
        className="form-control"
        style={{
          width: '100%',
          minHeight: '110px',
          fontSize: '0.86rem',
          resize: 'vertical',
          border: '1.5px solid var(--accent-border)',
          background: 'var(--bg-secondary)',
          color: 'var(--text-primary)'
        }}
      />
    </div>
  );
}

export default function AiDirectivesEditor({
  context = '',
  rules = '',
  requirements = '',
  onChange,
  readOnly = false,
  className = ''
}) {
  const [activeHelpModal, setActiveHelpModal] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  const handleTextChange = (field, value) => {
    if (onChange) {
      onChange({
        context: field === 'context' ? value : context,
        rules: field === 'rules' ? value : rules,
        requirements: field === 'requirements' ? value : requirements
      });
    }
  };

  const handleCopyExample = (key, text) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const HELP_DEFINITIONS = {
    context: {
      title: 'Context (উদ্দেশ্য ও প্রেক্ষাপট)',
      icon: BookOpen,
      color: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
      description:
        'Context explains the overarching purpose, background, institutional role, and target audience of this template. It guides the AI to adopt the correct perspective and domain understanding.',
      whyImportant:
        'Without context, the AI treats the text as generic words. With context, it understands whether this is for an executive board, government ministry, research journal, or general public.',
      examples: [
        {
          label: 'Meeting Minutes Context Example',
          text: 'Official strategic, programmatic, and review meetings conducted by EASD. Designed for executive directors, project managers, and organizational stakeholders.'
        },
        {
          label: 'Bangladesh Government Report Context Example',
          text: 'Official administrative memo and inspection report for ministries and directorates under the Government of the People\'s Republic of Bangladesh. Adheres to standard Bangladesh Secretariat Instructions.'
        },
        {
          label: 'Academic Journal Context Example',
          text: 'Peer-reviewed empirical research paper in public health and epidemiology intended for scientific reviewers, researchers, and policy advisors.'
        }
      ]
    },
    rules: {
      title: 'Rules (নিয়মাবলী ও লেখার শৈলী)',
      icon: ShieldCheck,
      color: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
      description:
        'Rules define strict styling constraints, tone of voice, formatting instructions, language guidelines (Bangla/English), and clear dos & don\'ts.',
      whyImportant:
        'Rules prevent the AI from hallucinations, awkward phrasing, or unstructured outputs by enforcing exact bullet conventions, formal registers, and length constraints.',
      examples: [
        {
          label: 'Executive Minutes Rules Example',
          text: '1. Write in formal executive tone.\n2. Must maintain exactly 4 thematic discussion rows (Followup, Action items, Task assignments, Decisions).\n3. Every bullet must start with a single bullet symbol ("• ").\n4. Maintain bilingual accuracy in English and Bengali.'
        },
        {
          label: 'Government Secretariat Rules Example',
          text: '1. Header must state "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার".\n2. Use standard administrative Bengali terminology (e.g. বিষয়, স্মারক নং, পটভূমি, পর্যবেক্ষণ, সিদ্ধান্ত ও সুপারিশমালা).\n3. All recommendations must be numbered sequentially with accountable wings.\n4. Avoid conversational tone.'
        },
        {
          label: 'News Story Rules Example',
          text: '1. Follow inverted pyramid structure with 5 Ws in the lead paragraph.\n2. Use objective, crisp third-person journalism.\n3. Include direct quotes with verified speaker attributions.\n4. End with institutional boilerplate.'
        }
      ]
    },
    requirements: {
      title: 'Requirements (আবশ্যকীয় উপাদান ও ফিল্ড)',
      icon: CheckSquare,
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      description:
        'Requirements specify the mandatory fields, crucial data points, required tables, and essential outputs that must be extracted from the transcript or audio.',
      whyImportant:
        'Requirements guarantee that critical metadata (e.g., Memo numbers, dates, decisions, attendees) is never omitted during AI synthesis.',
      examples: [
        {
          label: 'Meeting Minutes Requirements Example',
          text: '- Meeting Title, Venue, Date, and Time.\n- 4 to 5 high-level Agenda items.\n- Discussion matrix covering all 4 core themes.\n- Member attendance checklist.\n- Formally approved decisions list.'
        },
        {
          label: 'Govt Nothi Requirements Example',
          text: '- Ministry and Directorate Name.\n- Official Memo / Nothi Reference Number (স্মারক নং).\n- Date (Bangla and Gregorian).\n- Subject (বিষয়) in one clear line.\n- Background (পটভূমি), Observations (পর্যবেক্ষণ), Decisions, and Recommendations.\n- Signatory authority block.'
        },
        {
          label: 'Journal Article Requirements Example',
          text: '- Article Title, Authors, and Institutional Affiliation.\n- 150-250 word structured Abstract & Keywords.\n- Introduction, Methodology, Results, Discussion, Conclusion.\n- Structured References / Bibliography.'
        }
      ]
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* 3 Component Cards Grid */}
      {/* 3 Interactive Cards for Directives */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <DirectiveBlock
          icon={BookOpen}
          title="1. Context (Purpose)"
          helpKey="context"
          onOpenHelp={setActiveHelpModal}
          description="Explain what this template is for, its role, and target audience."
          value={context}
          onChange={(e) => handleTextChange('context', e.target.value)}
          disabled={readOnly}
          placeholder="e.g. Official review meetings conducted by EASD for executive leadership and program directors..."
        />

        <DirectiveBlock
          icon={ShieldCheck}
          title="2. Rules (Guidelines)"
          helpKey="rules"
          onOpenHelp={setActiveHelpModal}
          description="Formatting rules, tone of voice, language rules, and constraints."
          value={rules}
          onChange={(e) => handleTextChange('rules', e.target.value)}
          disabled={readOnly}
          placeholder="1. Write in formal institutional tone.\n2. Keep bullet points prefixed with '• '.\n3. Maintain bilingual accuracy..."
        />

        <DirectiveBlock
          icon={CheckSquare}
          title="3. Requirements (Mandatory)"
          helpKey="requirements"
          onOpenHelp={setActiveHelpModal}
          description="Mandatory fields, key sections, and essential outputs required."
          value={requirements}
          onChange={(e) => handleTextChange('requirements', e.target.value)}
          disabled={readOnly}
          placeholder="- Document Title, Date, Location.\n- 4-5 core Agenda points.\n- Key decisions and responsible owners..."
        />
      </div>

      {/* Interactive Help & Examples Modal */}
      {activeHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl flex flex-col">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-900/95 backdrop-blur-md z-10">
              <div className="flex items-center gap-3">
                <div
                  className={`p-2.5 rounded-xl border ${HELP_DEFINITIONS[activeHelpModal].color}`}
                >
                  {React.createElement(HELP_DEFINITIONS[activeHelpModal].icon, { size: 22 })}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">
                    {HELP_DEFINITIONS[activeHelpModal].title}
                  </h3>
                  <span className="text-xs text-slate-400">AI Directive Guide & Best Practices</span>
                </div>
              </div>
              <button
                onClick={() => setActiveHelpModal(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5">
              {/* Description */}
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Info size={14} className="text-blue-400" /> Definition
                </h4>
                <p className="text-sm text-slate-300 leading-relaxed">
                  {HELP_DEFINITIONS[activeHelpModal].description}
                </p>
                <p className="text-xs text-slate-400 mt-2 italic">
                  💡 {HELP_DEFINITIONS[activeHelpModal].whyImportant}
                </p>
              </div>

              {/* Concrete Examples */}
              <div>
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Concrete Examples (Click to Use / Copy)
                </h4>
                <div className="space-y-3">
                  {HELP_DEFINITIONS[activeHelpModal].examples.map((ex, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 hover:border-slate-700 transition-all"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-medium text-blue-400">{ex.label}</span>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              handleTextChange(activeHelpModal, ex.text);
                              setActiveHelpModal(null);
                            }}
                            className="text-xs px-2.5 py-1 rounded bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-500/30 font-medium transition-colors"
                          >
                            Apply to Field
                          </button>
                          <button
                            type="button"
                            onClick={() => handleCopyExample(`${activeHelpModal}_${idx}`, ex.text)}
                            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                            title="Copy to clipboard"
                          >
                            {copiedKey === `${activeHelpModal}_${idx}` ? (
                              <Check size={14} className="text-emerald-400" />
                            ) : (
                              <Copy size={14} />
                            )}
                          </button>
                        </div>
                      </div>
                      <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80">
                        {ex.text}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-800 flex justify-end bg-slate-900/90 sticky bottom-0">
              <button
                type="button"
                onClick={() => setActiveHelpModal(null)}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
