import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Header from './components/Header';
import NavTabs from './components/NavTabs';
import MediaInput from './components/MediaInput';
import LiveTranscription from './components/LiveTranscription';
import TemplateGenerator from './components/TemplateGenerator';
import AiSkillsSelector from './components/AiSkillsSelector';
import Transcripts from './components/Transcripts';
import MetaAgendas from './components/MetaAgendas';
import Discussions from './components/Discussions';
import Attendance from './components/Attendance';
import GovtReportForm from './components/GovtReportForm';
import ArticleReportForm from './components/ArticleReportForm';
import DocumentPreview from './components/DocumentPreview';
import GDriveModal from './components/GDriveModal';
import SettingsModal, { ACCENT_PALETTES } from './components/SettingsModal';

const DEFAULT_AGENDAS = [
  'Review of previous meeting minutes & action items',
  'Field survey dataset analysis & programmatic milestones',
  'Task assignments and operational deadlines',
  'Key strategic & administrative decisions'
];

const DEFAULT_DISCUSSIONS = [
  { sn: '1', topic: 'Followup from previous meeting', details: '• Reviewed progress of ongoing items from the last session with responsible leads.\n• Outstanding deliverables tracked; bottlenecks identified and escalated.' },
  { sn: '2', topic: 'Action items', details: '• Concrete action directives issued with named responsible owners.\n• Quality benchmarks and compliance requirements confirmed per action item.' },
  { sn: '3', topic: 'Task Assignments', details: '• Specific tasks allocated to named team leads with agreed delivery timelines.\n• Workstream ownership confirmed by the meeting chair.' },
  { sn: '4', topic: 'Meeting Decisions', details: '• All formally approved strategic and institutional decisions adopted in this session.\n• Locked submission deadlines and next strategic review date confirmed.' }
];

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [activeSection, setActiveSection] = useState('section-input');

  // Secondary Settings State (Font Engine, Accent Colors, Typography Scale)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('appSettings');
      return saved
        ? JSON.parse(saved)
        : {
            accentColor: '#0284c7',
            banglaFont: 'nikosh',
            englishFont: 'times_new_roman',
            docScale: 'standard'
          };
    } catch (e) {
      return {
        accentColor: '#0284c7',
        banglaFont: 'nikosh',
        englishFont: 'times_new_roman',
        docScale: 'standard'
      };
    }
  });

  const [selectedFile, setSelectedFile] = useState(null);
  const [directText, setDirectText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Document Type & Template State
  const [documentType, setDocumentType] = useState(localStorage.getItem('documentType') || 'meeting_minutes');
  const [templates, setTemplates] = useState([]);
  const [activeTemplateId, setActiveTemplateId] = useState(localStorage.getItem('activeTemplateId') || 'easd_default_minutes');
  const [customSectionsData, setCustomSectionsData] = useState({});
  const [customTablesData, setCustomTablesData] = useState({});

  const [aiConfig, setAiConfig] = useState({
    provider: localStorage.getItem('aiProvider') || 'groq',
    apiKey: localStorage.getItem('apiKey') || '',
    baseUrl: localStorage.getItem('baseUrl') || 'https://api.groq.com/openai/v1',
    transcriptionModel: localStorage.getItem('transcriptionModel') || 'whisper-large-v3-turbo',
    summarizationModel: localStorage.getItem('summarizationModel') || 'openai/gpt-oss-120b',
    modelName: localStorage.getItem('summarizationModel') || 'openai/gpt-oss-120b',
    showKey: false
  });

  const [orgContext, setOrgContext] = useState(
    localStorage.getItem('orgContext') ||
    'Eminence Associates for Social Development (www.eminence-bd.org) is a non-profit organization working on public health, nutrition, education, and social development programs in Bangladesh. The EASD team conducts weekly strategic programmatic reviews at Mohakhali DOHS, Dhaka.'
  );

  const [activeSkills, setActiveSkills] = useState(() => {
    try {
      const saved = localStorage.getItem('activeSkills');
      return saved ? JSON.parse(saved) : ['gemini_audio', 'claude_action_items', 'bangla_standardizer'];
    } catch (e) {
      return ['gemini_audio', 'claude_action_items', 'bangla_standardizer'];
    }
  });

  const [customSkillsList, setCustomSkillsList] = useState(() => {
    try {
      const saved = localStorage.getItem('customSkillsList');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  });

  const [banglaTranscript, setBanglaTranscript] = useState('');
  const [englishTranscript, setEnglishTranscript] = useState('');

  // Comprehensive Metadata state for all document types
  const [meta, setMeta] = useState({
    title: 'Weekly Strategic, Programmatic and Presentation Review Meeting',
    location: 'Eminence Conference Room, Mohakhali DOHS, Dhaka',
    date: '29 August, 2026',
    time: '11:00 AM - 01:00 PM',
    ministry: 'স্বাস্থ্য ও পরিবার কল্যাণ মন্ত্রণালয়',
    department: 'স্বাস্থ্য সেবা বিভাগ / DGHS',
    memo_no: '৪৫.০০.০০০০.০০১.২৪.০০১.২৬-',
    subject: 'জাতীয় স্বাস্থ্য নীতি ও প্রোগ্রাম বাস্তবায়ন পর্যালোচনা প্রতিবেদন প্রসঙ্গে।',
    background: '',
    observations: '',
    decisions: '',
    recommendations: '',
    signatory: '',
    action_matrix: [
      { sn: '১', action: 'স্বাস্থ্য পরীক্ষা ও প্রাথমিক তথ্যভাণ্ডার হালনাগাদকরণ', authority: 'সিভিল সার্জন কার্যালয় ও স্বাস্থ্য কমপ্লেক্স', deadline: '৩০ সেপ্টেম্বর, ২০২৬' },
      { sn: '২', action: 'প্রশিক্ষণ ও সচেতনতা বৃদ্ধি কার্যক্রম জোরদারকরণ', authority: 'প্রশিক্ষণ উইং, ডিজিএইচএস', deadline: '১৫ অক্টোবর, ২০২৬' }
    ]
  });

  const [agendas, setAgendas] = useState(DEFAULT_AGENDAS);
  const [discussions, setDiscussions] = useState(DEFAULT_DISCUSSIONS);
  const [decisions, setDecisions] = useState('• All agenda points reviewed and approved by the meeting chair.\n• Next review meeting scheduled for next week.');
  const [attendance, setAttendance] = useState([]);

  const [isGDriveOpen, setIsGDriveOpen] = useState(false);
  const [gdriveStatus, setGdriveStatus] = useState(null);

  // Sync Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Sync LocalStorage
  useEffect(() => {
    localStorage.setItem('aiProvider', aiConfig.provider);
    localStorage.setItem('apiKey', aiConfig.apiKey);
    localStorage.setItem('baseUrl', aiConfig.baseUrl);
    localStorage.setItem('transcriptionModel', aiConfig.transcriptionModel || '');
    localStorage.setItem('summarizationModel', aiConfig.summarizationModel || '');
    localStorage.setItem('modelName', aiConfig.summarizationModel || '');
  }, [aiConfig]);

  useEffect(() => {
    localStorage.setItem('orgContext', orgContext);
  }, [orgContext]);

  useEffect(() => {
    localStorage.setItem('documentType', documentType);
  }, [documentType]);

  useEffect(() => {
    localStorage.setItem('activeTemplateId', activeTemplateId);
  }, [activeTemplateId]);

  useEffect(() => {
    localStorage.setItem('customSkillsList', JSON.stringify(customSkillsList));
  }, [customSkillsList]);

  useEffect(() => {
    localStorage.setItem('activeSkills', JSON.stringify(activeSkills));
  }, [activeSkills]);

  // Sync Settings & Dynamic Accent Colors
  useEffect(() => {
    localStorage.setItem('appSettings', JSON.stringify(settings));
    if (settings.accentColor) {
      document.documentElement.style.setProperty('--accent-color', settings.accentColor);
      const matched = ACCENT_PALETTES.find((p) => p.hex.toLowerCase() === settings.accentColor.toLowerCase());
      const glow = matched ? matched.glow : `${settings.accentColor}40`;
      document.documentElement.style.setProperty('--accent-glow', glow);
      document.documentElement.style.setProperty('--accent-border', `${settings.accentColor}80`);
    }
  }, [settings]);

  // Load Templates from backend via secure POST
  const loadTemplates = async () => {
    try {
      const res = await axios.post('/api/templates');
      if (res.data?.status === 'success' && res.data.templates) {
        setTemplates(res.data.templates);
      }
    } catch (err) {
      console.warn('Failed to load templates via POST, trying fallback:', err);
      try {
        const res = await axios.get('/api/templates');
        if (res.data?.status === 'success' && res.data.templates) {
          setTemplates(res.data.templates);
        }
      } catch (e) {}
    }
  };

  useEffect(() => {
    loadTemplates();

    axios
      .post('/api/template_members')
      .then((res) => {
        if (res.data && res.data.members) setAttendance(res.data.members);
      })
      .catch((e) => console.log('Member load fallback'));

    axios
      .post('/api/skills')
      .then((res) => {
        if (res.data?.skills && Array.isArray(res.data.skills)) {
          setCustomSkillsList(res.data.skills);
        }
      })
      .catch((e) => console.log('Skills load fallback'));

    axios
      .post('/api/default_config')
      .then((res) => {
        if (res.data && res.data.api_key) {
          setAiConfig((prev) => {
            if (!prev.apiKey) {
              return {
                ...prev,
                provider: res.data.provider || prev.provider,
                apiKey: res.data.api_key,
                summarizationModel: res.data.summarization_model || prev.summarizationModel,
                transcriptionModel: res.data.transcription_model || prev.transcriptionModel
              };
            }
            return prev;
          });
        }
      })
      .catch((err) => console.log('Default config check notice:', err));
  }, []);

  const scrollToSection = (sectionId) => {
    setActiveSection(sectionId);
    const elem = document.getElementById(sectionId);
    if (elem) {
      const topOffset = 90;
      const elementPosition = elem.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - topOffset;
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  const toggleTheme = () => setTheme(theme === 'light' ? 'dark' : 'light');

  // Handle selecting a Document Type
  const handleSelectDocumentType = (newDocType) => {
    setDocumentType(newDocType);
    // Find matching template
    const match = templates.find((t) => t.doc_type === newDocType);
    if (match) {
      setActiveTemplateId(match.id);
      if (match.name) setMeta((prev) => ({ ...prev, title: match.name }));
    }
  };

  // Handle selecting an active template
  const handleSelectTemplate = (tplId) => {
    setActiveTemplateId(tplId);
    const tpl = templates.find((t) => t.id === tplId);
    if (tpl) {
      if (tpl.doc_type) setDocumentType(tpl.doc_type);
      if (tpl.name) setMeta((prev) => ({ ...prev, title: tpl.name }));
    }
  };

  // Populate extracted summary fields into states
  const applyExtractedSummary = (s) => {
    if (!s) return;
    setMeta((prev) => ({
      ...prev,
      title: s.title || prev.title,
      location: s.location || prev.location,
      date: s.date || prev.date,
      time: s.time || prev.time,
      ministry: s.ministry || prev.ministry,
      department: s.department || prev.department,
      memo_no: s.memo_no || prev.memo_no,
      subject: s.subject || s.title || prev.subject,
      background: s.background || prev.background,
      observations: s.observations || prev.observations,
      decisions: s.decisions || prev.decisions,
      recommendations: s.recommendations || prev.recommendations,
      signatory: s.signatory || prev.signatory,
      action_matrix: s.action_matrix || prev.action_matrix,
      ...s
    }));

    if (s.agendas && s.agendas.length > 0) setAgendas(s.agendas);
    if (s.discussions && s.discussions.length > 0) setDiscussions(s.discussions);
    if (s.decisions) setDecisions(s.decisions);
    if (s.attendance && s.attendance.length > 0) setAttendance(s.attendance);
    if (s.sections_data) setCustomSectionsData(s.sections_data);
    if (s.tables_data) setCustomTablesData(s.tables_data);
  };

  // AI Process Request
  const handleProcessAi = async () => {
    if (!selectedFile && !directText.trim()) {
      alert('Please select an audio/video/text file or paste draft text.');
      return;
    }

    setIsProcessing(true);
    const formData = new FormData();
    formData.append('provider', aiConfig.provider);
    formData.append('api_key', aiConfig.apiKey.trim());
    formData.append('base_url', aiConfig.baseUrl.trim());
    formData.append('model_name', aiConfig.summarizationModel || aiConfig.modelName);
    formData.append('transcription_model', aiConfig.transcriptionModel || '');
    formData.append('summarization_model', aiConfig.summarizationModel || '');
    formData.append('org_context', orgContext);
    formData.append('template_id', activeTemplateId || 'easd_default_minutes');
    
    const activeSkillPrompts = activeSkills.map((sId) => {
      const found = customSkillsList.find((c) => c.id === sId);
      if (found) return `[${found.category} Skill] ${found.name}: ${found.prompt}`;
      return `[Skill: ${sId}]`;
    }).join('\n');
    formData.append('custom_skills', activeSkillPrompts);

    if (selectedFile) formData.append('file', selectedFile);
    if (directText.trim()) formData.append('text_content', directText.trim());

    try {
      const res = await axios.post('/api/transcribe_and_summarize', formData);
      setIsProcessing(false);

      if (res.data && res.data.status === 'success') {
        const payload = res.data.data;
        setBanglaTranscript(payload.bangla_transcript || '');
        setEnglishTranscript(payload.english_transcript || '');

        if (payload.doc_type) setDocumentType(payload.doc_type);
        if (payload.summary) {
          applyExtractedSummary(payload.summary);
        }
        alert('Document synthesized successfully into active template format! Scrolled down to Document Preview.');
        scrollToSection('section-export');
      } else {
        alert('Processing failed: ' + (res.data?.detail || 'Unknown error'));
      }
    } catch (err) {
      setIsProcessing(false);
      alert('AI Server Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Summarize Transcript with selected model
  const handleSummarizeTranscript = async (transcriptText, selectedModel = 'default') => {
    setIsSummarizing(true);
    let chosenProvider = aiConfig.provider;
    let chosenModelName = aiConfig.summarizationModel || aiConfig.modelName;

    if (selectedModel === 'groq') {
      chosenProvider = 'groq';
      chosenModelName = 'openai/gpt-oss-120b';
    } else if (selectedModel === 'gemini') {
      chosenProvider = 'gemini';
      chosenModelName = 'gemini-2.5-flash';
    } else if (selectedModel === 'claude') {
      chosenProvider = 'anthropic';
      chosenModelName = 'claude-3-5-sonnet-20241022';
    } else if (selectedModel === 'openai') {
      chosenProvider = 'openai';
      chosenModelName = 'gpt-4o';
    }

    const formData = new FormData();
    formData.append('transcript', transcriptText);
    formData.append('provider', chosenProvider);
    formData.append('api_key', aiConfig.apiKey.trim());
    formData.append('base_url', aiConfig.baseUrl.trim());
    formData.append('model_name', chosenModelName);
    formData.append('summarization_model', chosenModelName);
    formData.append('org_context', orgContext);
    formData.append('template_id', activeTemplateId || 'easd_default_minutes');

    const activeSkillPrompts = activeSkills.map((sId) => {
      const found = customSkillsList.find((c) => c.id === sId);
      if (found) return `[${found.category} Skill] ${found.name}: ${found.prompt}`;
      return `[Skill: ${sId}]`;
    }).join('\n');
    formData.append('custom_skills', activeSkillPrompts);

    try {
      const res = await axios.post('/api/summarize_transcript', formData);
      setIsSummarizing(false);

      if (res.data && res.data.status === 'success') {
        const payload = res.data.data;
        if (payload.bangla_transcript) setBanglaTranscript(payload.bangla_transcript);
        if (payload.english_transcript) setEnglishTranscript(payload.english_transcript);
        if (payload.doc_type) setDocumentType(payload.doc_type);
        if (payload.summary) {
          applyExtractedSummary(payload.summary);
        }
        alert('Raw transcript structured and fitted to active template successfully!');
        scrollToSection('section-export');
      } else {
        alert('Fit to Template failed: ' + (res.data?.detail || 'Unknown error'));
      }
    } catch (err) {
      setIsSummarizing(false);
      alert('Fit to Template Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Recording Processed with AI handler
  const handleRecordingProcessed = (payload) => {
    if (!payload) return;
    if (payload.bangla_transcript) setBanglaTranscript(payload.bangla_transcript);
    if (payload.english_transcript) setEnglishTranscript(payload.english_transcript);
    if (payload.doc_type) setDocumentType(payload.doc_type);
    if (payload.summary) {
      applyExtractedSummary(payload.summary);
    }
  };

  // Live Transcription Handlers
  const handleSendToBangla = (text) => {
    setBanglaTranscript((prev) => (prev ? `${prev}\n\n${text}` : text));
    alert('Live text appended to Bangla Transcript.');
  };

  const handleSendToEnglish = (text) => {
    setEnglishTranscript((prev) => (prev ? `${prev}\n\n${text}` : text));
    alert('Live text appended to English Transcript.');
  };

  // Download DOCX (Supports default EASD, Bangladesh Govt Nothi, Journal, News, Blog, and custom templates)
  const handleDownloadDocx = async () => {
    setIsGenerating(true);
    const isEasdDefault = activeTemplateId === 'easd_default_minutes';

    const docPayload = {
      ...meta,
      title: meta.title,
      location: meta.location,
      date: meta.date,
      time: meta.time,
      ministry: meta.ministry,
      department: meta.department,
      memo_no: meta.memo_no,
      subject: meta.subject || meta.title,
      background: meta.background,
      observations: meta.observations,
      decisions: meta.decisions,
      recommendations: meta.recommendations,
      signatory: meta.signatory,
      action_matrix: meta.action_matrix,
      agendas: agendas || [],
      discussions: discussions || [],
      attendance: attendance || [],
      sections_data: customSectionsData || {},
      tables_data: customTablesData || {},
      bangla_transcript: banglaTranscript || '',
      english_transcript: englishTranscript || ''
    };

    try {
      let res;
      if (isEasdDefault) {
        res = await axios.post('/api/generate_docx', docPayload, { responseType: 'blob' });
      } else {
        res = await axios.post('/api/generate_custom_docx', {
          template_id: activeTemplateId,
          doc_data: docPayload
        }, { responseType: 'blob' });
      }

      setIsGenerating(false);

      let filename = 'EASD-Document.docx';
      const disposition = res.headers['content-disposition'];
      if (disposition) {
        const match = disposition.match(/filename="?([^";\n]+)"?/);
        if (match) filename = match[1];
      } else {
        const activeTpl = templates.find((t) => t.id === activeTemplateId);
        const namePart = (activeTpl?.name || 'Document').replace(/\s+/g, '_');
        filename = `${namePart}.docx`;
      }

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setIsGenerating(false);
      alert('Error generating DOCX: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Upload Google Drive
  const handleUploadGDrive = async (token) => {
    setGdriveStatus({ type: 'info', message: "Uploading .docx to Google Drive folder 'EASD - meeting minutes'..." });
    const payload = {
      doc_data: {
        title: meta.title,
        location: meta.location,
        date: meta.date,
        time: meta.time,
        agendas: agendas || [],
        discussions: discussions || [],
        decisions: decisions || '',
        attendance: attendance || [],
        bangla_transcript: banglaTranscript || '',
        english_transcript: englishTranscript || ''
      },
      access_token: token,
      folder_name: 'EASD - meeting minutes'
    };

    try {
      const res = await axios.post('/api/upload_gdrive', payload);
      if (res.data && res.data.status === 'success') {
        setGdriveStatus({
          type: 'success',
          message: `Success! File uploaded (ID: ${res.data.gdrive.id})`,
          link: res.data.gdrive.webViewLink
        });
      } else {
        setGdriveStatus({ type: 'error', message: 'Upload failed: ' + (res.data?.detail || 'Unknown error') });
      }
    } catch (err) {
      setGdriveStatus({ type: 'error', message: 'Upload Error: ' + (err.response?.data?.detail || err.message) });
    }
  };

  const activeTemplate = templates.find((t) => t.id === activeTemplateId) || templates[0] || {};
  const isMeetingMinutes = documentType === 'meeting_minutes';
  const isGovtReport = documentType === 'bangladesh_govt_report';

  return (
    <div className="app-container">
      <Header
        theme={theme}
        toggleTheme={toggleTheme}
        onOpenGDrive={() => setIsGDriveOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />
      <NavTabs
        activeSection={activeSection}
        scrollToSection={scrollToSection}
        documentType={documentType}
      />

      {/* SINGLE-PAGE SCROLLING LAYOUT */}
      <main style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {/* 1. Input & AI Model */}
        <MediaInput
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          directText={directText}
          setDirectText={setDirectText}
          aiConfig={aiConfig}
          setAiConfig={setAiConfig}
          templates={templates}
          activeTemplateId={activeTemplateId}
          onSelectTemplate={handleSelectTemplate}
          onProcessAi={handleProcessAi}
          isProcessing={isProcessing}
        />

        {/* 2. Real-Time Live Microphone Auto-Queue Transcription Studio */}
        <LiveTranscription
          aiConfig={aiConfig}
          orgContext={orgContext}
          activeSkills={activeSkills}
          customSkillsList={customSkillsList}
          activeTemplateId={activeTemplateId}
          onSendToBangla={handleSendToBangla}
          onSendToEnglish={handleSendToEnglish}
          onFitToTemplate={(text) => handleSummarizeTranscript(text, 'default')}
          onRecordingProcessed={handleRecordingProcessed}
          scrollToSection={scrollToSection}
        />

        {/* 3. AI Document Template Generator & 3 Directives Studio */}
        <TemplateGenerator
          templates={templates}
          activeTemplateId={activeTemplateId}
          onSelectTemplate={handleSelectTemplate}
          onTemplatesUpdated={loadTemplates}
          documentType={documentType}
          onSelectDocumentType={handleSelectDocumentType}
        />

        {/* 4. AI Skills & Directives */}
        <AiSkillsSelector
          activeSkills={activeSkills}
          setActiveSkills={setActiveSkills}
          customSkillsList={customSkillsList}
          setCustomSkillsList={setCustomSkillsList}
          orgContext={orgContext}
          setOrgContext={setOrgContext}
        />

        {/* 5. Dual Transcripts & AI Summarizer */}
        <Transcripts
          banglaTranscript={banglaTranscript}
          setBanglaTranscript={setBanglaTranscript}
          englishTranscript={englishTranscript}
          setEnglishTranscript={setEnglishTranscript}
          onSummarizeTranscript={handleSummarizeTranscript}
          isSummarizing={isSummarizing}
        />

        {/* DYNAMIC DOCUMENT TYPE FORMS */}

        {/* Form Mode A: Meeting Minutes */}
        {isMeetingMinutes && (
          <>
            <MetaAgendas
              meta={meta}
              setMeta={setMeta}
              agendas={agendas}
              setAgendas={setAgendas}
            />
            <Discussions
              discussions={discussions}
              setDiscussions={setDiscussions}
              decisions={decisions}
              setDecisions={setDecisions}
            />
            <Attendance
              attendance={attendance}
              setAttendance={setAttendance}
            />
          </>
        )}

        {/* Form Mode B: Bangladesh Government Nothi Report */}
        {isGovtReport && (
          <div id="section-govt-form">
            <GovtReportForm
              formData={meta}
              onChange={setMeta}
            />
          </div>
        )}

        {/* Form Mode C: Journal, News, Blog, or Custom Article */}
        {!isMeetingMinutes && !isGovtReport && (
          <div id="section-article-form">
            <ArticleReportForm
              docType={documentType}
              templateInfo={activeTemplate}
              formData={meta}
              onChange={setMeta}
            />
          </div>
        )}

        {/* 6. Live Document Preview & Export */}
        <DocumentPreview
          meta={meta}
          agendas={agendas}
          discussions={discussions}
          decisions={decisions}
          attendance={attendance}
          banglaTranscript={banglaTranscript}
          englishTranscript={englishTranscript}
          templates={templates}
          activeTemplateId={activeTemplateId}
          documentType={documentType}
          customSectionsData={customSectionsData}
          customTablesData={customTablesData}
          settings={settings}
          onDownloadDocx={handleDownloadDocx}
          onOpenGDrive={() => setIsGDriveOpen(true)}
          isGenerating={isGenerating}
        />
      </main>

      <GDriveModal
        isOpen={isGDriveOpen}
        onClose={() => setIsGDriveOpen(false)}
        onUpload={handleUploadGDrive}
        status={gdriveStatus}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        theme={theme}
        setTheme={setTheme}
        settings={settings}
        setSettings={setSettings}
      />
    </div>
  );
}
