import React from 'react';
import {
  FileText,
  Calendar,
  Layers,
  Sparkles,
  BookOpen,
  Newspaper,
  Feather,
  Plus,
  Trash2,
  ListOrdered
} from 'lucide-react';

/**
 * Reusable schema-driven Form Component for Journal, News, Blog, and custom article formats.
 */
export default function ArticleReportForm({
  docType = 'journal',
  templateInfo = {},
  formData = {},
  onChange
}) {
  const handleChange = (field, value) => {
    onChange({ ...formData, [field]: value });
  };

  const fields = templateInfo.fields || [
    { key: 'title', label: 'Title / Headline', type: 'text' },
    { key: 'date', label: 'Date', type: 'text' }
  ];

  const sections = templateInfo.sections || [];

  const getDocTypeIcon = () => {
    switch (docType) {
      case 'journal':
        return <BookOpen size={24} className="text-indigo-400" />;
      case 'news':
        return <Newspaper size={24} className="text-amber-400" />;
      case 'blog':
        return <Feather size={24} className="text-purple-400" />;
      default:
        return <FileText size={24} className="text-blue-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-slate-800/80 rounded-xl border border-slate-700">
              {getDocTypeIcon()}
            </div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                {templateInfo.category || 'Article Document'}
              </span>
              <h2 className="text-xl font-bold text-white tracking-tight">
                {templateInfo.name || 'Document Editor'}
              </h2>
            </div>
          </div>
          <span className="text-xs px-3 py-1 bg-slate-800 border border-slate-700 text-slate-300 rounded-full font-medium">
            {docType.toUpperCase()}
          </span>
        </div>

        {/* Dynamic Fields Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fields.map((fld) => (
            <div
              key={fld.key}
              className={fld.key === 'title' ? 'md:col-span-2' : ''}
            >
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
                <FileText size={13} className="text-blue-400" />
                {fld.label || fld.key}
              </label>
              <input
                type="text"
                value={formData[fld.key] || ''}
                onChange={(e) => handleChange(fld.key, e.target.value)}
                placeholder={`Enter ${fld.label || fld.key}...`}
                className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-sans"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Dynamic Sections Content */}
      <div className="grid grid-cols-1 gap-5">
        {sections.map((sec, idx) => (
          <div
            key={sec.id || idx}
            className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-lg space-y-2 hover:border-slate-700 transition-all"
          >
            <div className="flex items-center justify-between">
              <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">
                  {idx + 1}
                </span>
                {sec.title}
              </label>
              <span className="text-[11px] text-slate-400 uppercase tracking-wider bg-slate-800/80 px-2 py-0.5 rounded">
                {sec.type || 'text'}
              </span>
            </div>
            {sec.prompt && (
              <p className="text-xs text-slate-400 italic">
                {sec.prompt}
              </p>
            )}
            <textarea
              value={formData[sec.id] || ''}
              onChange={(e) => handleChange(sec.id, e.target.value)}
              placeholder={`Write or synthesize ${sec.title}...`}
              className="w-full min-h-[110px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y font-sans leading-relaxed"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
