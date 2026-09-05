import React from 'react';
import DOMPurify from 'dompurify';
import { FileDown, Cloud, FileText, CheckCircle2, Table, Layers, Landmark, BookOpen, Newspaper, Feather, Check } from 'lucide-react';

export default function DocumentPreview({
  meta = {},
  agendas = [],
  discussions = [],
  decisions = '',
  attendance = [],
  banglaTranscript = '',
  englishTranscript = '',
  templates = [],
  activeTemplateId,
  documentType = 'meeting_minutes',
  customSectionsData = {},
  customTablesData = {},
  settings = {},
  onDownloadDocx,
  onOpenGDrive,
  isGenerating
}) {
  const sanitize = (text) => DOMPurify.sanitize(text || '');

  const activeTemplate = (templates || []).find((t) => t.id === activeTemplateId) || {
    id: 'easd_default_minutes',
    name: 'EASD Meeting Minutes'
  };

  const isEasdMinutes = activeTemplate.id === 'easd_default_minutes' || documentType === 'meeting_minutes';
  const isGovtReport = documentType === 'bangladesh_govt_report' || activeTemplate.doc_type === 'bangladesh_govt_report';
  const isJournal = documentType === 'journal' || activeTemplate.doc_type === 'journal';
  const isNews = documentType === 'news' || activeTemplate.doc_type === 'news';
  const isBlog = documentType === 'blog' || activeTemplate.doc_type === 'blog';
  const isCustomUploaded = !isEasdMinutes && !isGovtReport && !isJournal && !isNews && !isBlog;

  const fontClass = isGovtReport
    ? `font-${settings.banglaFont || 'nikosh'}`
    : `font-${settings.englishFont || 'times_new_roman'}`;
  const scaleClass = `doc-scale-${settings.docScale || 'standard'}`;

  const cleanAgenda = (text) => {
    if (!text) return '';
    return String(text).replace(/^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\t]+\s*)+/g, '').trim();
  };

  const cleanDetailsHtml = (details) => {
    if (!details) return '';
    const lines = String(details).split('\n');
    const cleaned = lines
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return '';
        const content = trimmed.replace(/^(?:[•\-\*\t\s]|\d+[\.\)\:\-]\s*)+/g, '').trim();
        return content ? `• ${content}` : '';
      })
      .filter(Boolean);
    return DOMPurify.sanitize(cleaned.join('<br/>'));
  };

  const handleDownloadTranscriptOnly = () => {
    if (!banglaTranscript && !englishTranscript) {
      alert('No transcripts available to download.');
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    const title = meta.title || 'Meeting';
    const content = [
      `============================================================`,
      `  TRANSCRIPT EXPORT: ${title}`,
      `  Date: ${meta.date || today} | Venue: ${meta.location || 'N/A'}`,
      `============================================================\n`,
      `--- BANGLA TRANSCRIPT (বাংলা ট্রান্সক্রিপ্ট) ---`,
      banglaTranscript || '(No Bangla transcript generated)',
      `\n------------------------------------------------------------\n`,
      `--- ENGLISH TRANSCRIPT ---`,
      englishTranscript || '(No English transcript generated)',
      `\n============================================================`
    ].join('\n');

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Transcript_${title.replace(/[^a-zA-Z0-9_\-]/g, '_')}_${today}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="card" id="section-export" style={{ marginBottom: '40px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
            <FileText size={20} color="var(--accent-color)" /> Preview
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', marginTop: '2px' }}>
            Current Output: <strong>{activeTemplate.name}</strong> • Live formatted document preview & 1-click export
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleDownloadTranscriptOnly}
            title="Download transcript text only (.txt)"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}
          >
            <FileText size={15} /> Transcript (.txt)
          </button>
          <button className="btn btn-primary btn-sm" onClick={onDownloadDocx} disabled={isGenerating} style={{ fontWeight: 700 }}>
            <FileDown size={15} /> {isGenerating ? 'Generating Word...' : 'Download .docx'}
          </button>
          {isEasdMinutes && (
            <button className="btn btn-success btn-sm" onClick={onOpenGDrive} style={{ fontWeight: 700 }}>
              <Cloud size={15} /> GDrive Sync
            </button>
          )}
        </div>
      </div>

      {/* A4 Paper Container with Authentic Word Styling and Dynamic Font Engine */}
      <div
        className={`docx-preview-paper ${fontClass} ${scaleClass}`}
        style={{
          background: '#ffffff',
          color: '#1e293b',
          borderRadius: '8px',
          boxShadow: '0 12px 36px rgba(0,0,0,0.25), 0 0 1px 1px rgba(0,0,0,0.08)',
          maxWidth: '960px',
          margin: '0 auto',
          lineHeight: '1.55'
        }}
      >
        {/* ========================================================================= */}
        {/* 1. BANGLADESH GOVERNMENT NOTHI FORMAT PREVIEW                             */}
        {/* ========================================================================= */}
        {isGovtReport && (
          <div>
            {/* Government Crest / Header */}
            <div style={{ textAlign: 'center', marginBottom: '20px', borderBottom: '2px solid #047857', paddingBottom: '14px' }}>
              <div style={{ fontSize: '1.45rem', fontWeight: 'bold', color: '#047857', letterSpacing: '0.5px', marginBottom: '4px' }}>
                গণপ্রজাতন্ত্রী বাংলাদেশ সরকার
              </div>
              <div style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '2px' }}>
                {sanitize(meta.ministry || 'স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়')}
              </div>
              <div style={{ fontSize: '1rem', color: '#334155' }}>
                {sanitize(meta.department || 'স্বাস্থ্য সেবা বিভাগ')}
              </div>
              <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '2px' }}>
                www.dghs.gov.bd
              </div>
            </div>

            {/* Split Memo No & Date Line */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', fontSize: '0.98rem', fontWeight: 600, color: '#1e293b' }}>
              <div>স্মারক নম্বর: {sanitize(meta.memo_no || '৪৫.০০.০০০০.০০১.২৪.০০১.২৬-')}</div>
              <div>তারিখ: {sanitize(meta.date || '০২ সেপ্টেম্বর, ২০২৬')}</div>
            </div>

            {/* Subject Line */}
            <div style={{ marginBottom: '22px', fontSize: '1.08rem', fontWeight: 'bold', borderBottom: '1.5px solid #cbd5e1', paddingBottom: '10px' }}>
              বিষয়: <span style={{ textDecoration: 'underline' }}>{sanitize(meta.subject || meta.title || 'নথি প্রতিবেদন প্রসঙ্গে।')}</span>
            </div>

            {/* Section 1: Background */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#047857', marginBottom: '6px' }}>
                ১. পটভূমি ও ভূমিকা:
              </h4>
              <div style={{ fontSize: '0.98rem', lineHeight: '1.7', color: '#334155', textAlign: 'justify' }}>
                {sanitize(meta.background || meta.overview || 'প্রশাসনিক পর্যালোচনা সভার পটভূমি, উদ্দেশ্য এবং সার্বিক কর্মপরিধি।')}
              </div>
            </div>

            {/* Section 2: Observations */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#047857', marginBottom: '6px' }}>
                ২. বিশদ পর্যবেক্ষণ ও তথ্য-উপাত্ত:
              </h4>
              <div
                style={{ fontSize: '0.98rem', lineHeight: '1.7', color: '#334155' }}
                dangerouslySetInnerHTML={{
                  __html: cleanDetailsHtml(meta.observations || '• মাঠ পর্যায়ের প্রাথমিক উপাত্ত সংগ্রহ সম্পন্ন হয়েছে।\n• বিভিন্ন জেলায় স্বাস্থ্যসেবা কার্যক্রমের অগ্রগতি ইতিবাচক।')
                }}
              />
            </div>

            {/* Section 3: Decisions */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#047857', marginBottom: '6px' }}>
                ৩. সভায় গৃহীত সিদ্ধান্তসমূহ:
              </h4>
              <div
                style={{ fontSize: '0.98rem', lineHeight: '1.7', color: '#334155' }}
                dangerouslySetInnerHTML={{
                  __html: cleanDetailsHtml(meta.decisions || '• স্বাস্থ্য পরীক্ষার ডাটাবেজ নিয়মিত হালনাগাদ করার সিদ্ধান্ত গৃহীত হয়।\n• আগামী ত্রৈমাসিকে জেলা সমন্বয় সভা আহ্বান করা হবে।')
                }}
              />
            </div>

            {/* Section 4: Recommendations */}
            <div style={{ marginBottom: '22px' }}>
              <h4 style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#047857', marginBottom: '6px' }}>
                ৪. কৌশলগত সুপারিশমালা:
              </h4>
              <div
                style={{ fontSize: '0.98rem', lineHeight: '1.7', color: '#334155' }}
                dangerouslySetInnerHTML={{
                  __html: cleanDetailsHtml(meta.recommendations || '• আধুনিক ডিজিটাল মনিটরিং ব্যবস্থা সম্প্রসারণ করা প্রয়োজন।\n• জনবল সংকট নিরসনে দ্রুত পদক্ষেপ গ্রহণ সমীচীন।')
                }}
              />
            </div>

            {/* Section 5: Action Matrix Table */}
            {meta.action_matrix && meta.action_matrix.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#047857', marginBottom: '8px' }}>
                  বাস্তবায়ন কর্মপরিকল্পনা:
                </h4>
                <div className="table-responsive">
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.92rem', border: '1px solid #000' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', borderBottom: '1.5px solid #000' }}>
                        <th style={{ padding: '8px 10px', border: '1px solid #000', width: '60px', textAlign: 'center' }}>ক্রমিক</th>
                        <th style={{ padding: '8px 10px', border: '1px solid #000' }}>কার্যক্রম / সিদ্ধান্ত</th>
                        <th style={{ padding: '8px 10px', border: '1px solid #000', width: '220px' }}>বাস্তবায়নকারী কর্তৃপক্ষ</th>
                        <th style={{ padding: '8px 10px', border: '1px solid #000', width: '130px', textAlign: 'center' }}>সময়সীমা</th>
                      </tr>
                    </thead>
                    <tbody>
                      {meta.action_matrix.map((row, rIdx) => (
                        <tr key={rIdx}>
                          <td style={{ padding: '8px 10px', border: '1px solid #000', textAlign: 'center', fontWeight: 'bold' }}>{row.sn}</td>
                          <td style={{ padding: '8px 10px', border: '1px solid #000' }}>{row.action}</td>
                          <td style={{ padding: '8px 10px', border: '1px solid #000' }}>{row.authority}</td>
                          <td style={{ padding: '8px 10px', border: '1px solid #000', textAlign: 'center' }}>{row.deadline}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Section 6: Official Signatory & Distribution Block */}
            <div style={{ marginTop: '36px', display: 'flex', justifyContent: 'flex-end' }}>
              <div style={{ textAlign: 'center', width: '280px', fontSize: '0.95rem', color: '#1e293b' }}>
                <div style={{ fontStyle: 'italic', color: '#64748b', marginBottom: '4px' }}>(স্বাক্ষরিত)</div>
                <div style={{ fontWeight: 'bold' }}>{sanitize(meta.signatory || 'দায়িত্বপ্রাপ্ত কর্মকর্তা')}</div>
                <div style={{ fontSize: '0.88rem', color: '#475569' }}>যুগ্মসচিব / উপপরিচালক</div>
                <div style={{ fontSize: '0.88rem', color: '#475569' }}>{sanitize(meta.department || 'স্বাস্থ্য সেবা বিভাগ')}</div>
                <div style={{ fontSize: '0.88rem', color: '#475569' }}>ফোন: ০২-xxxxxxx</div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 2. EASD OFFICIAL MEETING MINUTES FORMAT PREVIEW                           */}
        {/* ========================================================================= */}
        {isEasdMinutes && (
          <div>
            {/* Header Logo Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '2.5px solid #004b87', paddingBottom: '12px' }}>
              <img src="/template_logo.jpeg" alt="EASD Header Banner" style={{ maxHeight: '58px', objectFit: 'contain' }} onError={(e) => { e.target.style.display = 'none'; }} />
              <img src="/eminence_logo.png" alt="Eminence Seal" style={{ maxHeight: '58px', width: '58px', objectFit: 'contain' }} />
            </div>

            {/* Document Title & Meta */}
            <div style={{ marginBottom: '22px' }}>
              <div style={{ fontSize: '1.35rem', fontWeight: 'bold', marginBottom: '4px', color: '#000000' }}>
                {sanitize(meta.title || 'Weekly Strategic, Programmatic and Presentation Review Meeting')}
              </div>
              <div style={{ fontSize: '1rem', color: '#333333', marginBottom: '10px' }}>
                {sanitize(meta.location || 'Emenance, Mohakhali, DOHS')}
              </div>
              <div style={{ fontWeight: 'bold', fontSize: '0.98rem', borderBottom: '2px solid #cbd5e1', paddingBottom: '10px', color: '#000000' }}>
                Date: {sanitize(meta.date || '22 August, 2026')} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Time: {sanitize(meta.time || '11:00 AM - 01:00 PM')}
              </div>
            </div>

            {/* Meeting Agenda */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#000000', marginBottom: '8px' }}>
                Meeting Agenda:
              </h3>
              <ol style={{ paddingLeft: '22px', margin: 0, fontSize: '0.98rem', color: '#111827', lineHeight: '1.65' }}>
                {(agendas || []).map((ag, i) => (
                  <li key={i}>{cleanAgenda(ag)}</li>
                ))}
              </ol>
            </div>

            {/* 4-Topic Discussions Table with Exact Template Color #E36C0A */}
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#000000', marginBottom: '8px' }}>
                Agenda-Wise Meeting Discussions
              </h3>
              <div className="table-responsive">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.94rem', border: '1px solid #000000' }}>
                  <thead>
                    <tr style={{ background: '#E36C0A', color: '#FFFFFF', borderBottom: '1.5px solid #000000' }}>
                      <th style={{ width: '45px', padding: '10px 8px', border: '1px solid #000000', textAlign: 'center', color: '#FFFFFF', fontWeight: 'bold' }}>SN</th>
                      <th style={{ width: '220px', padding: '10px 8px', border: '1px solid #000000', color: '#FFFFFF', fontWeight: 'bold' }}>Discussion Points</th>
                      <th style={{ padding: '10px 8px', border: '1px solid #000000', color: '#FFFFFF', fontWeight: 'bold' }}>Major Discussions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(discussions || []).map((row, i) => (
                      <tr key={i} style={{ background: i % 2 === 1 ? '#fafafa' : '#ffffff' }}>
                        <td style={{ padding: '10px 8px', border: '1px solid #000000', textAlign: 'center', fontWeight: 'bold' }}>{row.sn}</td>
                        <td style={{ padding: '10px 8px', border: '1px solid #000000', fontWeight: 'bold' }}>{row.topic}</td>
                        <td style={{ padding: '10px 8px', border: '1px solid #000000', lineHeight: '1.6' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(row.details) }} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Major Strategic Decisions */}
            {decisions && (
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#000000', marginBottom: '8px' }}>
                  Major Strategic Decisions:
                </h3>
                <div style={{ fontSize: '0.98rem', lineHeight: '1.65', color: '#111827' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(decisions) }} />
              </div>
            )}

            {/* Attendance Checklist (21 Members) with Exact Template Color #E36C0A */}
            {attendance && attendance.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#000000', marginBottom: '8px' }}>
                  Attendance Checklist (21 Members):
                </h3>
                <div className="table-responsive">
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', border: '1px solid #000000' }}>
                    <thead>
                      <tr style={{ background: '#E36C0A', color: '#FFFFFF' }}>
                        <th style={{ width: '50px', padding: '6px 8px', border: '1px solid #000000', textAlign: 'center', color: '#FFFFFF', fontWeight: 'bold' }}>Serial</th>
                        <th style={{ padding: '6px 10px', border: '1px solid #000000', color: '#FFFFFF', fontWeight: 'bold' }}>Name</th>
                        <th style={{ width: '110px', padding: '6px 8px', border: '1px solid #000000', textAlign: 'center', color: '#FFFFFF', fontWeight: 'bold' }}>Participation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendance.map((m, i) => {
                        const isPresent = m.participation === 'Yes';
                        return (
                          <tr key={i} style={{ background: i % 2 === 1 ? '#fafafa' : '#ffffff' }}>
                            <td style={{ padding: '5px 8px', border: '1px solid #000000', textAlign: 'center', fontWeight: 'bold' }}>{m.serial}</td>
                            <td style={{ padding: '5px 10px', border: '1px solid #000000' }}>{m.name}</td>
                            <td style={{ padding: '5px 8px', border: '1px solid #000000', textAlign: 'center' }}>
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontWeight: '700',
                                fontSize: '0.82rem',
                                background: isPresent ? '#dcfce7' : '#fee2e2',
                                color: isPresent ? '#166534' : '#991b1b',
                                border: isPresent ? '1px solid #86efac' : '1px solid #fca5a5'
                              }}>
                                {isPresent ? '✓ Yes' : '✕ No'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 3. ACADEMIC & SCIENTIFIC JOURNAL FORMAT PREVIEW                           */}
        {/* ========================================================================= */}
        {isJournal && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: '24px', borderBottom: '2px solid #003366', paddingBottom: '16px' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '8px', lineHeight: '1.3' }}>
                {sanitize(meta.title || 'Epidemiological Trends and Public Health Interventions in Urban Communities')}
              </h1>
              <div style={{ fontSize: '1.02rem', fontStyle: 'italic', color: '#334155', marginBottom: '4px' }}>
                {sanitize(meta.authors || 'EASD Research & Evaluation Wing')}
              </div>
              <div style={{ fontSize: '0.88rem', color: '#64748b' }}>
                Eminence Associates for Social Development • Published: {sanitize(meta.date || 'September 2026')}
              </div>
            </div>

            {/* Abstract Box */}
            <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderLeft: '4px solid #003366', padding: '16px 20px', borderRadius: '6px', marginBottom: '24px' }}>
              <h4 style={{ fontWeight: 'bold', fontSize: '1.02rem', color: '#003366', marginBottom: '6px' }}>
                Abstract
              </h4>
              <p style={{ fontSize: '0.94rem', lineHeight: '1.65', color: '#334155', textAlign: 'justify', margin: 0 }}>
                {sanitize(meta.abstract || 'Background: This study evaluates community-based health interventions across urban and semi-urban clusters. Methods: Mixed-method evaluation with structured observational indicators. Results: Marked improvement in awareness and operational service delivery benchmarks. Conclusion: Strategic policy integration is essential for sustainable outcomes.')}
              </p>
              <div style={{ marginTop: '10px', fontSize: '0.88rem', color: '#475569' }}>
                <strong>Keywords:</strong> {sanitize(meta.keywords || 'Public Health, Health Systems, Community Interventions, NCDs')}
              </div>
            </div>

            {/* Journal Sections */}
            {(activeTemplate.sections || []).map((sec, idx) => {
              if (sec.id === 'abstract') return null;
              const content = meta[sec.id] || (customSectionsData && customSectionsData[sec.id]) || '';
              return (
                <div key={idx} style={{ marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '1.12rem', fontWeight: 'bold', color: '#003366', marginBottom: '6px', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
                    {sec.title}
                  </h3>
                  {content ? (
                    <div style={{ fontSize: '0.96rem', lineHeight: '1.65', color: '#334155', textAlign: 'justify' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(content) }} />
                  ) : (
                    <p style={{ fontStyle: 'italic', color: '#94a3b8', fontSize: '0.9rem' }}>
                      Detailed empirical findings and discussion synthesized from research transcript...
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 4. PRESS RELEASE & NEWS STORY FORMAT PREVIEW                              */}
        {/* ========================================================================= */}
        {isNews && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '2px solid #dc2626', paddingBottom: '10px' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 'bold', color: '#dc2626', letterSpacing: '1px', textTransform: 'uppercase' }}>
                FOR IMMEDIATE RELEASE
              </span>
              <span style={{ fontSize: '0.88rem', color: '#64748b' }}>
                {sanitize(meta.date || 'September 2, 2026')}
              </span>
            </div>

            <h1 style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '10px', lineHeight: '1.3' }}>
              {sanitize(meta.title || 'EASD Unveils Landmark Community Health Initiative')}
            </h1>

            <div style={{ fontSize: '0.98rem', fontWeight: 'bold', color: '#0284c7', marginBottom: '18px' }}>
              {sanitize(meta.dateline || 'DHAKA, Bangladesh')} —
            </div>

            {/* Lead & Story Body */}
            {(activeTemplate.sections || []).map((sec, idx) => {
              const content = meta[sec.id] || (customSectionsData && customSectionsData[sec.id]) || '';
              return (
                <div key={idx} style={{ marginBottom: '18px' }}>
                  <h3 style={{ fontSize: '1.08rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '6px' }}>
                    {sec.title}
                  </h3>
                  {content ? (
                    <div style={{ fontSize: '0.96rem', lineHeight: '1.65', color: '#334155' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(content) }} />
                  ) : (
                    <p style={{ fontStyle: 'italic', color: '#94a3b8', fontSize: '0.9rem' }}>
                      Story details populated from press conference / event recording...
                    </p>
                  )}
                </div>
              );
            })}

            <div style={{ textAlign: 'center', margin: '30px 0 16px 0', color: '#94a3b8', fontWeight: 'bold', letterSpacing: '2px' }}>
              ### (END) ###
            </div>

            {/* Boilerplate */}
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '14px 18px', borderRadius: '6px', fontSize: '0.88rem', color: '#475569' }}>
              <strong>Media Contact:</strong> {sanitize(meta.media_contact || 'Communications Directorate, Eminence (media@eminence-bd.org)')}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 5. DIGITAL BLOG POST FORMAT PREVIEW                                       */}
        {/* ========================================================================= */}
        {isBlog && (
          <div>
            <div style={{ marginBottom: '22px', borderBottom: '2px solid #8b5cf6', paddingBottom: '16px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#8b5cf6', textTransform: 'uppercase', letterSpacing: '1px' }}>
                THOUGHT LEADERSHIP BLOG
              </span>
              <h1 style={{ fontSize: '1.65rem', fontWeight: 'bold', color: '#0f172a', margin: '8px 0 10px 0', lineHeight: '1.3' }}>
                {sanitize(meta.title || 'Transforming Public Health from the Grassroots: 5 Key Lessons')}
              </h1>
              <div style={{ fontSize: '0.92rem', color: '#64748b' }}>
                By <strong>{sanitize(meta.author || 'EASD Thought Leadership Team')}</strong> • {sanitize(meta.date || 'September 2026')} • 5 min read
              </div>
            </div>

            {/* Blog Sections */}
            {(activeTemplate.sections || []).map((sec, idx) => {
              const content = meta[sec.id] || (customSectionsData && customSectionsData[sec.id]) || '';
              return (
                <div key={idx} style={{ marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#6d28d9', marginBottom: '8px' }}>
                    {sec.title}
                  </h3>
                  {content ? (
                    <div style={{ fontSize: '0.98rem', lineHeight: '1.7', color: '#334155' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(content) }} />
                  ) : (
                    <p style={{ fontStyle: 'italic', color: '#94a3b8', fontSize: '0.9rem' }}>
                      Insights and core takeaways synthesized from podcast / notes...
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 6. CUSTOM UPLOADED DOCX TEMPLATE PREVIEW                                 */}
        {/* ========================================================================= */}
        {isCustomUploaded && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: '24px', borderBottom: '2px solid #003366', paddingBottom: '16px' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#003366', marginBottom: '8px' }}>
                {sanitize(meta.title || activeTemplate.name)}
              </h1>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', flexWrap: 'wrap', fontSize: '0.95rem', color: '#475569' }}>
                {meta.date && <span><strong>Date:</strong> {sanitize(meta.date)}</span>}
                {meta.location && <span><strong>Location:</strong> {sanitize(meta.location)}</span>}
                {meta.author && <span><strong>Prepared By:</strong> {sanitize(meta.author)}</span>}
                {meta.reference && <span><strong>Reference:</strong> {sanitize(meta.reference)}</span>}
              </div>
            </div>

            {/* Dynamic Sections */}
            {(activeTemplate.sections || []).map((sec, idx) => {
              const content = meta[sec.id] || (customSectionsData && customSectionsData[sec.id]) || '';
              return (
                <div key={idx} style={{ marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#003366', marginBottom: '6px', borderBottom: '1px solid #cbd5e1', paddingBottom: '4px' }}>
                    {sec.title}
                  </h3>
                  {content ? (
                    <div style={{ fontSize: '0.96rem', lineHeight: '1.65', color: '#334155' }} dangerouslySetInnerHTML={{ __html: cleanDetailsHtml(content) }} />
                  ) : (
                    <p style={{ fontStyle: 'italic', color: '#94a3b8', fontSize: '0.9rem' }}>
                      Section populated from speech recording synthesis...
                    </p>
                  )}
                </div>
              );
            })}

            {/* Dynamic Tables */}
            {(activeTemplate.tables || []).map((tbl, tIdx) => {
              const rows = (customTablesData && customTablesData[tbl.id]) || [];
              return (
                <div key={tIdx} style={{ marginTop: '24px', marginBottom: '24px' }}>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#003366', marginBottom: '8px' }}>
                    {tbl.title || `Table ${tIdx + 1}`}
                  </h4>
                  <div className="table-responsive">
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.92rem', border: '1px solid #000' }}>
                      <thead>
                        <tr style={{ background: '#f8fafc', borderBottom: '1.5px solid #000' }}>
                          {(tbl.columns || []).map((col, cIdx) => (
                            <th key={cIdx} style={{ padding: '8px 10px', border: '1px solid #000' }}>
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.length > 0 ? (
                          rows.map((r, rIdx) => (
                            <tr key={rIdx}>
                              {(tbl.columns || []).map((col, cIdx) => (
                                <td key={cIdx} style={{ padding: '8px 10px', border: '1px solid #000' }}>
                                  {typeof r === 'object' ? r[col] || r[col.toLowerCase()] || '' : r}
                                </td>
                              ))}
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={(tbl.columns || []).length} style={{ padding: '12px', border: '1px solid #000', textAlign: 'center', color: '#94a3b8', fontStyle: 'italic' }}>
                              Table rows will be automatically populated from audio data synthesis.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
