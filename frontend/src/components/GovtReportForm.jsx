import React from 'react';
import {
  Landmark,
  FileText,
  Calendar,
  Layers,
  CheckCircle2,
  ListOrdered,
  UserCheck,
  Plus,
  Trash2,
  Building2,
  FileSpreadsheet
} from 'lucide-react';

export default function GovtReportForm({
  formData,
  onChange,
  onAiEnhance
}) {
  const handleChange = (field, value) => {
    onChange({ ...formData, [field]: value });
  };

  const actionMatrix = formData.action_matrix || [
    { sn: '১', action: 'স্বাস্থ্য পরীক্ষা ও প্রাথমিক তথ্যভাণ্ডার হালনাগাদকরণ', authority: 'সিভিল সার্জন কার্যালয় ও স্বাস্থ্য কমপ্লেক্স', deadline: '৩০ সেপ্টেম্বর, ২০২৬' },
    { sn: '২', action: 'প্রশিক্ষণ ও সচেতনতা বৃদ্ধি কার্যক্রম জোরদারকরণ', authority: 'প্রশিক্ষণ উইং, ডিজিএইচএস', deadline: '১৫ অক্টোবর, ২০২৬' }
  ];

  const handleActionMatrixChange = (index, field, value) => {
    const updated = [...actionMatrix];
    updated[index] = { ...updated[index], [field]: value };
    handleChange('action_matrix', updated);
  };

  const handleAddActionRow = () => {
    const nextSn = String(actionMatrix.length + 1);
    handleChange('action_matrix', [
      ...actionMatrix,
      { sn: nextSn, action: '', authority: '', deadline: '' }
    ]);
  };

  const handleRemoveActionRow = (index) => {
    if (actionMatrix.length <= 1) return;
    const updated = actionMatrix.filter((_, i) => i !== index);
    handleChange('action_matrix', updated);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Bangladesh Govt Official Header Card */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400">
              <Landmark size={28} />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                Government of the People's Republic of Bangladesh
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                গণপ্রজাতন্ত্রী বাংলাদেশ সরকার নোথি / স্মারক প্রতিবেদন
              </h2>
            </div>
          </div>
          <span className="text-xs px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded-full font-medium">
            Secretariat Nothi Standard
          </span>
        </div>

        {/* Form Fields Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
          {/* Ministry */}
          <div>
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
              <Building2 size={14} className="text-emerald-400" />
              মন্ত্রণালয় / বিভাগ (Ministry / Division)
            </label>
            <input
              type="text"
              value={formData.ministry || 'স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়'}
              onChange={(e) => handleChange('ministry', e.target.value)}
              placeholder="e.g. স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয় / Ministry of Health"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-sans"
            />
          </div>

          {/* Department */}
          <div>
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
              <Building2 size={14} className="text-emerald-400" />
              অধিদপ্তর / সংস্থা (Department / Directorate)
            </label>
            <input
              type="text"
              value={formData.department || 'স্বাস্থ্য সেবা বিভাগ / DGHS'}
              onChange={(e) => handleChange('department', e.target.value)}
              placeholder="e.g. Directorate General of Health Services"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-sans"
            />
          </div>

          {/* Memo No */}
          <div>
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
              <FileText size={14} className="text-emerald-400" />
              স্মারক নম্বর (Memo / Nothi Reference No)
            </label>
            <input
              type="text"
              value={formData.memo_no || '৪৫.০০.০০০০.০০১.২৪.০০১.২৬-'}
              onChange={(e) => handleChange('memo_no', e.target.value)}
              placeholder="e.g. ৪৫.০০.০০০০.০০১.২৪.০০১.২৬-১২৪"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-sans"
            />
          </div>

          {/* Date */}
          <div>
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
              <Calendar size={14} className="text-emerald-400" />
              তারিখ (Date - Bangla & Gregorian)
            </label>
            <input
              type="text"
              value={formData.date || '০২ সেপ্টেম্বর, ২০২৬ / 02 September 2026'}
              onChange={(e) => handleChange('date', e.target.value)}
              placeholder="e.g. ০২ সেপ্টেম্বর, ২০২৬ / 02 September 2026"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-sans"
            />
          </div>

          {/* Subject */}
          <div className="md:col-span-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-1.5">
              <FileText size={14} className="text-emerald-400" />
              বিষয় (Subject / Focus)
            </label>
            <input
              type="text"
              value={formData.subject || formData.title || ''}
              onChange={(e) => {
                handleChange('subject', e.target.value);
                handleChange('title', e.target.value);
              }}
              placeholder="e.g. জাতীয় স্বাস্থ্য নীতি ও প্রোগ্রাম বাস্তবায়ন পর্যালোচনা প্রতিবেদন প্রসঙ্গে।"
              className="w-full bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-slate-100 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-sans"
            />
          </div>
        </div>
      </div>

      {/* Sections Grid */}
      <div className="grid grid-cols-1 gap-6">
        {/* 1. Background & Introduction */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                ১
              </span>
              ১. পটভূমি ও ভূমিকা (Background & Introduction)
            </label>
          </div>
          <textarea
            value={formData.background || ''}
            onChange={(e) => handleChange('background', e.target.value)}
            placeholder="প্রশাসনিক পটভূমি, পর্যালোচনা সভার প্রেক্ষাপট এবং আইনি ভিত্তি..."
            className="w-full min-h-[100px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-sans leading-relaxed"
          />
        </div>

        {/* 2. Detailed Observations */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                ২
              </span>
              ২. বিশদ পর্যবেক্ষণ ও তথ্য-উপাত্ত (Observations & Findings)
            </label>
          </div>
          <textarea
            value={formData.observations || ''}
            onChange={(e) => handleChange('observations', e.target.value)}
            placeholder="• মাঠ পর্যায়ের মূল পর্যবেক্ষণ ও মূল্যায়িত উপাত্তসমূহ..."
            className="w-full min-h-[120px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-sans leading-relaxed"
          />
        </div>

        {/* 3. Decisions Taken */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                ৩
              </span>
              ৩. সভায় গৃহীত সিদ্ধান্তসমূহ (Decisions Taken)
            </label>
          </div>
          <textarea
            value={formData.decisions || ''}
            onChange={(e) => handleChange('decisions', e.target.value)}
            placeholder="• আনুষ্ঠানিকভাবে অনুমোদিত সিদ্ধান্ত এবং নির্দেশনা..."
            className="w-full min-h-[100px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-sans leading-relaxed"
          />
        </div>

        {/* 4. Strategic Recommendations */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                ৪
              </span>
              ৪. কৌশলগত সুপারিশমালা (Policy & Operational Recommendations)
            </label>
          </div>
          <textarea
            value={formData.recommendations || ''}
            onChange={(e) => handleChange('recommendations', e.target.value)}
            placeholder="• ভবিষ্যৎ কর্মপরিকল্পনা ও মন্ত্রণালয় পর্যায়ের সুনির্দিষ্ট সুপারিশমালা..."
            className="w-full min-h-[110px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-sans leading-relaxed"
          />
        </div>

        {/* 5. Implementation Action Matrix Table */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <FileSpreadsheet size={18} className="text-emerald-400" />
              বাস্তবায়ন কর্মপরিকল্পনা (Implementation Action Matrix)
            </label>
            <button
              type="button"
              onClick={handleAddActionRow}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 rounded-lg transition-colors"
            >
              <Plus size={14} /> Add Row
            </button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold uppercase">
                  <th className="py-2.5 px-3 w-16">ক্রমিক</th>
                  <th className="py-2.5 px-3">কার্যক্রম / সিদ্ধান্ত</th>
                  <th className="py-2.5 px-3">বাস্তবায়নকারী কর্তৃপক্ষ</th>
                  <th className="py-2.5 px-3">সময়সীমা</th>
                  <th className="py-2.5 px-3 w-12 text-center">Delete</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {actionMatrix.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="py-2 px-3 font-medium text-slate-300">
                      <input
                        type="text"
                        value={row.sn || ''}
                        onChange={(e) => handleActionMatrixChange(idx, 'sn', e.target.value)}
                        className="w-10 bg-slate-950/70 border border-slate-800 rounded px-1.5 py-1 text-center text-slate-200"
                      />
                    </td>
                    <td className="py-2 px-3">
                      <input
                        type="text"
                        value={row.action || ''}
                        onChange={(e) => handleActionMatrixChange(idx, 'action', e.target.value)}
                        placeholder="কার্যক্রম বিবরণ..."
                        className="w-full bg-slate-950/70 border border-slate-800 rounded px-2.5 py-1 text-slate-200"
                      />
                    </td>
                    <td className="py-2 px-3">
                      <input
                        type="text"
                        value={row.authority || ''}
                        onChange={(e) => handleActionMatrixChange(idx, 'authority', e.target.value)}
                        placeholder="দায়িত্বপ্রাপ্ত শাখা / কর্মকর্তা..."
                        className="w-full bg-slate-950/70 border border-slate-800 rounded px-2.5 py-1 text-slate-200"
                      />
                    </td>
                    <td className="py-2 px-3">
                      <input
                        type="text"
                        value={row.deadline || ''}
                        onChange={(e) => handleActionMatrixChange(idx, 'deadline', e.target.value)}
                        placeholder="সময়সীমা..."
                        className="w-full bg-slate-950/70 border border-slate-800 rounded px-2.5 py-1 text-slate-200"
                      />
                    </td>
                    <td className="py-2 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => handleRemoveActionRow(idx)}
                        disabled={actionMatrix.length <= 1}
                        className="p-1 rounded text-rose-400 hover:text-rose-300 hover:bg-rose-500/20 disabled:opacity-30 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 6. Signatory Block */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-2">
          <label className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <span className="w-6 h-6 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
              ৫
            </span>
            ৫. স্বাক্ষরকারী ও অনুলিপি বিতরণ (Signatory & Distribution Block)
          </label>
          <textarea
            value={formData.signatory || ''}
            onChange={(e) => handleChange('signatory', e.target.value)}
            placeholder="স্বাক্ষরকারী কর্মকর্তার পদবী ও অনুলিপি সদয় জ্ঞাতার্থে ও কার্যার্থে তালিকা..."
            className="w-full min-h-[90px] bg-slate-950/70 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-sans leading-relaxed"
          />
        </div>
      </div>
    </div>
  );
}
