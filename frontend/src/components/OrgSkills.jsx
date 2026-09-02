import React from 'react';
import { Building, Wand2 } from 'lucide-react';

export default function OrgSkills({ orgContext, setOrgContext, customSkills, setCustomSkills }) {
  return (
    <div class="grid-2col">
      <div class="card">
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Building size={20} color="var(--accent-color)" /> Organization & Company Context
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
          Provide background about EASD, team, projects, and domain terms to guide AI accuracy.
        </p>
        <div class="form-group">
          <label>Company Background & Team Info:</label>
          <textarea
            class="form-control"
            rows={12}
            placeholder="e.g. EASD / Emenance is a development team based in Mohakhali, DOHS working on strategic programmatic reviews, community health, and AI projects. Key acronyms include: EASD, TJ, DOHS..."
            value={orgContext}
            onChange={(e) => setOrgContext(e.target.value)}
          />
        </div>
      </div>

      <div class="card">
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Wand2 size={20} color="var(--accent-color)" /> Custom AI Skills & Guidelines
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
          Add specialized prompting skills, extraction rules, and formatting instructions.
        </p>
        <div class="form-group">
          <label>Custom Prompting Skills & Guidelines:</label>
          <textarea
            class="form-control"
            rows={12}
            placeholder="e.g.
- Skill 1: Extract action items into structured bullet points starting with '• '.
- Skill 2: Standardize all dates to 'DD Month YY' format.
- Skill 3: Translate technical terms accurately into Bangla script while preserving English acronyms.
- Skill 4: Highlight key assigned tasks for each member."
            value={customSkills}
            onChange={(e) => setCustomSkills(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
