import React from 'react';
import {
  Radio,
  Layers,
  Languages,
  Upload,
  UploadCloud,
  Cpu,
  FileCode,
  Sparkles,
  Calendar,
  MessageSquare,
  Users,
  FileText,
  Landmark
} from 'lucide-react';

export default function NavTabs({ activeSection, scrollToSection, documentType = 'meeting_minutes' }) {
  const getSectionsForDocType = () => {
    // 1. Record & Engine (Unified Hero), 2. Transcript, 3. Templates, 4. Skills
    const baseSections = [
      { id: 'section-live', label: 'Record & Engine', icon: Radio },
      { id: 'section-transcripts', label: 'Transcript', icon: FileText },
      { id: 'section-templates', label: 'Templates', icon: FileCode },
      { id: 'section-skills', label: 'Skills', icon: Sparkles },
    ];

    if (documentType === 'meeting_minutes') {
      return [
        ...baseSections,
        { id: 'section-meta', label: 'Agendas', icon: Calendar },
        { id: 'section-discussions', label: 'Discussions', icon: MessageSquare },
        { id: 'section-attendance', label: 'Attendance', icon: Users },
        { id: 'section-export', label: 'Preview', icon: FileText }
      ];
    } else if (documentType === 'bangladesh_govt_report') {
      return [
        ...baseSections,
        { id: 'section-govt-form', label: 'Report', icon: Landmark },
        { id: 'section-export', label: 'Preview', icon: FileText }
      ];
    } else {
      return [
        ...baseSections,
        { id: 'section-article-form', label: 'Document', icon: FileText },
        { id: 'section-export', label: 'Preview', icon: FileText }
      ];
    }
  };

  const currentSections = getSectionsForDocType();

  return (
    <nav className="nav-tabs sticky-navbar" aria-label="Section Navigation">
      {currentSections.map((sec) => {
        const Icon = sec.icon;
        const isActive = activeSection === sec.id;
        return (
          <button
            key={sec.id}
            className={`tab-btn ${isActive ? 'active' : ''}`}
            onClick={() => scrollToSection(sec.id)}
            aria-current={isActive ? 'true' : undefined}
          >
            <Icon size={16} />
            <span>{sec.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
