import React from 'react';
import {
  Upload,
  Mic,
  Sparkles,
  Languages,
  Calendar,
  MessageSquare,
  Users,
  FileText,
  FileCode,
  Landmark,
  BookOpen,
  Newspaper,
  Feather
} from 'lucide-react';

export default function NavTabs({ activeSection, scrollToSection, documentType = 'meeting_minutes' }) {
  const getSectionsForDocType = () => {
    const baseSections = [
      { id: 'section-input', label: '1. Media & AI', icon: Upload },
      { id: 'section-live', label: '2. Live Mic', icon: Mic },
      { id: 'section-templates', label: '3. Templates & 3-Directives', icon: FileCode },
      { id: 'section-transcripts', label: '4. Transcripts', icon: Languages },
    ];

    if (documentType === 'meeting_minutes') {
      return [
        ...baseSections,
        { id: 'section-meta', label: '5. Agendas & Venue', icon: Calendar },
        { id: 'section-discussions', label: '6. 4-Topic Discussions', icon: MessageSquare },
        { id: 'section-attendance', label: '7. Attendance (21 Members)', icon: Users },
        { id: 'section-export', label: '8. Preview & Export', icon: FileText }
      ];
    } else if (documentType === 'bangladesh_govt_report') {
      return [
        ...baseSections,
        { id: 'section-govt-form', label: '5. Govt Nothi Report', icon: Landmark },
        { id: 'section-export', label: '6. Preview & Export', icon: FileText }
      ];
    } else {
      return [
        ...baseSections,
        { id: 'section-article-form', label: '5. Document Content', icon: FileText },
        { id: 'section-export', label: '6. Preview & Export', icon: FileText }
      ];
    }
  };

  const currentSections = getSectionsForDocType();

  return (
    <nav className="nav-tabs sticky-navbar">
      {currentSections.map((sec) => {
        const Icon = sec.icon;
        const isActive = activeSection === sec.id;
        return (
          <button
            key={sec.id}
            className={`tab-btn ${isActive ? 'active' : ''}`}
            onClick={() => scrollToSection(sec.id)}
          >
            <Icon size={15} />
            {sec.label}
          </button>
        );
      })}
    </nav>
  );
}
