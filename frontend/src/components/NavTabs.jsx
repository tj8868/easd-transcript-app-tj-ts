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

export default function NavTabs({ activeSection, scrollToSection, documentType = 'meeting_minutes', hasGeneratedOutput = false }) {
  const getSectionsForDocType = () => {
    // 1. Record & Upload (Hero), 2. Transcript, 3. Template (with embedded Skills)
    const baseSections = [
      { id: 'section-live', label: 'Record & Upload', icon: Radio },
      { id: 'section-transcripts', label: 'Transcript', icon: FileText },
      { id: 'section-templates', label: 'Templates & Skills', icon: Layers },
    ];

    let sections = [];
    if (documentType === 'meeting_minutes') {
      sections = [
        ...baseSections,
        { id: 'section-meta', label: 'Agendas', icon: Calendar },
        { id: 'section-discussions', label: 'Discussions', icon: MessageSquare },
        { id: 'section-attendance', label: 'Attendance', icon: Users }
      ];
    } else if (documentType === 'bangladesh_govt_report') {
      sections = [
        ...baseSections,
        { id: 'section-govt-form', label: 'Report', icon: Landmark }
      ];
    } else {
      sections = [
        ...baseSections,
        { id: 'section-article-form', label: 'Document', icon: FileText }
      ];
    }

    if (hasGeneratedOutput) {
      sections.push({ id: 'section-export', label: 'Preview', icon: FileText });
    }

    return sections;
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
