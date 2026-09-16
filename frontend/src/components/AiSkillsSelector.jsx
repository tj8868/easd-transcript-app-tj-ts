import React, { useState } from 'react';
import axios from 'axios';
import {
  Sparkles,
  Plus,
  Check,
  Trash2,
  Bot,
  Upload,
  Save,
  FileText,
  CheckCircle,
  Zap,
  Edit3,
  RefreshCw,
  FolderOpen
} from 'lucide-react';

const PRESET_SKILLS = [
  {
    id: 'gemini_audio',
    name: 'Gemini Multimodal Speech Transcription',
    category: 'Gemini',
    is_builtin: true,
    description: 'High-fidelity transcription of mixed Bangla + English speech directly from audio/video binaries.',
    prompt: 'Transcribe spoken Bangla phonetics and code-switched English terms with verbatim accuracy.'
  },
  {
    id: 'claude_action_items',
    name: 'Claude Action Item & Deadline Extractor',
    category: 'Claude',
    is_builtin: true,
    description: 'Deep reasoning to extract specific task assignments, responsible owners, and target deadlines.',
    prompt: 'Extract each action item in the format: • [Task Description] - Assigned to: [Name] (Deadline: [Date/Time]).'
  },
  {
    id: 'bangla_standardizer',
    name: 'Eminence Bengali Terminology Standardizer',
    category: 'Language',
    is_builtin: true,
    description: 'Converts spoken Banglish phrases into natural, formal Bengali grammar while retaining organizational acronyms.',
    prompt: 'Ensure Bangla transcript uses formal Bengali script while keeping technical acronyms (e.g. EASD, Eminence, DOHS, NCDs, WASH) intact.'
  },
  {
    id: 'executive_summary',
    name: 'Executive Decisions Synthesizer',
    category: 'Analysis',
    is_builtin: true,
    description: 'Distills multi-hour discussions into concise, bulleted strategic outcomes.',
    prompt: 'Synthesize meeting decisions into crisp, high-impact executive summary points.'
  }
];

function SkillModalDialog({ children }) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '20px'
      }}
    >
      <div className="card" style={{ maxWidth: '500px', width: '100%', padding: '24px', background: 'var(--bg-primary)', borderRadius: '14px' }}>
        {children}
      </div>
    </div>
  );
}

export default function AiSkillsSelector({
  activeSkills,
  setActiveSkills,
  customSkillsList,
  setCustomSkillsList,
  orgContext,
  setOrgContext
}) {
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillCategory, setNewSkillCategory] = useState('Gemini');
  const [newSkillPrompt, setNewSkillPrompt] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingSkill, setEditingSkill] = useState(null);
  const [saveToast, setSaveToast] = useState(false);
  const [isSavingSkill, setIsSavingSkill] = useState(false);

  const toggleSkill = (skillId) => {
    if (activeSkills.includes(skillId)) {
      setActiveSkills(activeSkills.filter((id) => id !== skillId));
    } else {
      setActiveSkills([...activeSkills, skillId]);
    }
  };

  const handleSaveContext = () => {
    localStorage.setItem('orgContext', orgContext);
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 2500);
  };

  // Add Custom Skill with permanent backend + localStorage persistence
  const handleAddCustomSkill = async (e) => {
    e.preventDefault();
    if (!newSkillName.trim() || !newSkillPrompt.trim()) {
      alert('Please provide a skill title and prompt instruction.');
      return;
    }

    const newSkill = {
      id: `custom_${Date.now()}`,
      name: newSkillName.trim(),
      category: newSkillCategory,
      description: 'Custom user-defined AI skill directive.',
      prompt: newSkillPrompt.trim(),
      is_builtin: false
    };

    setIsSavingSkill(true);
    try {
      await axios.post('/api/save_skill', newSkill);
    } catch (err) {
      console.warn('Backend save notice (cached locally):', err);
    } finally {
      setIsSavingSkill(false);
    }

    const updatedList = [...customSkillsList, newSkill];
    setCustomSkillsList(updatedList);
    localStorage.setItem('customSkillsList', JSON.stringify(updatedList));

    const updatedActive = [...activeSkills, newSkill.id];
    setActiveSkills(updatedActive);
    localStorage.setItem('activeSkills', JSON.stringify(updatedActive));

    setNewSkillName('');
    setNewSkillPrompt('');
    setShowAddModal(false);
    alert(`Skill "${newSkill.name}" saved permanently!`);
  };

  // Upload and permanently save AI Skill File (.json, .md, .txt, .yaml)
  const handleSkillFileUpload = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      const content = evt.target.result;
      let skillName = file.name.replace(/\.[^/.]+$/, '');
      let category = 'Gemini';
      let promptText = content;

      // Try JSON parsing
      if (file.name.endsWith('.json')) {
        try {
          const parsed = JSON.parse(content);
          skillName = parsed.name || parsed.title || skillName;
          category = parsed.category || parsed.model || 'Gemini';
          promptText = parsed.prompt || parsed.system_prompt || parsed.instructions || content;
        } catch (err) {
          console.warn('JSON parse warning, using raw content', err);
        }
      }

      if (skillName.toLowerCase().includes('claude') || content.toLowerCase().includes('claude')) {
        category = 'Claude';
      }

      const uploadedSkill = {
        id: `custom_file_${Date.now()}`,
        name: skillName,
        category: category,
        description: `Imported from ${file.name}`,
        prompt: promptText,
        is_builtin: false
      };

      try {
        await axios.post('/api/save_skill', uploadedSkill);
      } catch (err) {
        console.warn('Backend save notice (cached locally):', err);
      }

      const updatedList = [...customSkillsList, uploadedSkill];
      setCustomSkillsList(updatedList);
      localStorage.setItem('customSkillsList', JSON.stringify(updatedList));

      const updatedActive = [...activeSkills, uploadedSkill.id];
      setActiveSkills(updatedActive);
      localStorage.setItem('activeSkills', JSON.stringify(updatedActive));

      alert(`Skill "${skillName}" uploaded and saved permanently!`);
    };

    reader.readAsText(file);
    e.target.value = null; // reset input
  };

  // Delete Custom Skill with permanent deletion from disk + localStorage
  const handleDeleteCustomSkill = async (skillId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this saved custom skill permanently?')) return;

    try {
      await axios.post('/api/delete_skill', { skill_id: skillId });
    } catch (err) {
      console.warn('Backend delete notice:', err);
    }

    const updatedList = customSkillsList.filter((s) => s.id !== skillId);
    setCustomSkillsList(updatedList);
    localStorage.setItem('customSkillsList', JSON.stringify(updatedList));

    const updatedActive = activeSkills.filter((id) => id !== skillId);
    setActiveSkills(updatedActive);
    localStorage.setItem('activeSkills', JSON.stringify(updatedActive));
  };

  // Edit existing custom skill
  const handleSaveEditedSkill = async (e) => {
    e.preventDefault();
    if (!editingSkill) return;

    try {
      await axios.post('/api/save_skill', editingSkill);
    } catch (err) {
      console.warn('Backend save notice:', err);
    }

    const updatedList = customSkillsList.map((s) => (s.id === editingSkill.id ? editingSkill : s));
    setCustomSkillsList(updatedList);
    localStorage.setItem('customSkillsList', JSON.stringify(updatedList));
    setEditingSkill(null);
    alert(`Skill "${editingSkill.name}" updated successfully!`);
  };

  const allSkills = [...PRESET_SKILLS, ...customSkillsList];

  return (
    <div className="card" id="section-skills" style={{ marginBottom: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Sparkles size={20} color="var(--accent-color)" /> 4. AI Skills, Directives & Organization Context
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Specialized AI prompts and reasoning skills are <strong>saved permanently</strong> so you never have to re-upload.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {/* Upload Existing Skill Button */}
          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Upload size={14} /> Upload Skill (.json / .md / .txt)
            <input
              type="file"
              accept=".json,.md,.txt,.yaml,.yml"
              style={{ display: 'none' }}
              onChange={handleSkillFileUpload}
            />
          </label>

          <button className="btn btn-primary btn-sm" onClick={() => setShowAddModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
            <Plus size={14} /> Create AI Skill
          </button>
        </div>
      </div>

      {/* Skills Pill Selection Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px', marginBottom: '20px' }}>
        {allSkills.map((skill) => {
          const isActive = activeSkills.includes(skill.id);
          const isCustom = !skill.is_builtin && !PRESET_SKILLS.some((p) => p.id === skill.id);
          return (
            <div
              key={skill.id}
              onClick={() => toggleSkill(skill.id)}
              style={{
                padding: '12px 14px',
                borderRadius: '10px',
                border: isActive ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                background: isActive ? 'rgba(14, 165, 233, 0.08)' : 'var(--bg-primary)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '8px'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem', color: isActive ? 'var(--accent-color)' : 'var(--text-primary)' }}>
                    {skill.name}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    {isActive ? (
                      <span style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>✓</span>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>Off</span>
                    )}
                  </div>
                </div>

                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '6px 0 8px 0', lineHeight: '1.35' }}>
                  {skill.description || skill.prompt}
                </p>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem' }}>
                  <span
                    style={{
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: skill.category === 'Claude' ? 'rgba(236, 72, 153, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                      color: skill.category === 'Claude' ? '#ec4899' : '#60a5fa',
                      fontWeight: 600
                    }}
                  >
                    {skill.category}
                  </span>

                  {isCustom && (
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingSkill(skill);
                        }}
                        title="Edit Skill Directive"
                        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '2px' }}
                      >
                        <Edit3 size={13} />
                      </button>
                      <button
                        onClick={(e) => handleDeleteCustomSkill(skill.id, e)}
                        title="Delete Skill"
                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Organization Context Box */}
      <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FolderOpen size={16} color="var(--accent-color)" /> Organization Knowledge Context (Auto-Injected into AI Prompts):
          </label>
          <button className="btn btn-secondary btn-sm" onClick={handleSaveContext} style={{ fontSize: '0.78rem', padding: '4px 10px' }}>
            <Save size={14} /> {saveToast ? 'Saved!' : 'Save Context'}
          </button>
        </div>
        <textarea
          className="form-control"
          rows={3}
          style={{ fontSize: '0.85rem', lineHeight: '1.5' }}
          value={orgContext}
          onChange={(e) => setOrgContext(e.target.value)}
          placeholder="Enter institutional background, abbreviations, team member profiles, and ongoing projects..."
        />
      </div>

      {/* Modal: Create New AI Skill */}
      {showAddModal && (
        <SkillModalDialog>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Plus size={18} color="var(--accent-color)" /> Create & Save Custom AI Skill
          </h3>

          <form onSubmit={handleAddCustomSkill}>
            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Skill Title</label>
              <input
                className="form-control"
                type="text"
                placeholder="e.g. Budget & Financial Ledger Extractor"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Category / Model Family</label>
              <select className="form-control" value={newSkillCategory} onChange={(e) => setNewSkillCategory(e.target.value)}>
                <option value="Gemini">Google Gemini Directive</option>
                <option value="Claude">Anthropic Claude Reasoning</option>
                <option value="Groq">Groq High-Speed Prompt</option>
                <option value="OpenAI">OpenAI GPT-4o Schema</option>
                <option value="Domain">Public Health / Domain Specialist</option>
              </select>
            </div>

            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Skill System Prompt Instruction</label>
              <textarea
                className="form-control"
                rows={4}
                placeholder="e.g. Scan the transcript for any budget figures, grants, donor milestones, or procurement amounts and format them into bullet points."
                value={newSkillPrompt}
                onChange={(e) => setNewSkillPrompt(e.target.value)}
                required
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowAddModal(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary btn-sm" disabled={isSavingSkill} style={{ fontWeight: 700 }}>
                <Save size={14} /> {isSavingSkill ? 'Saving...' : 'Save Skill Permanently'}
              </button>
            </div>
          </form>
        </SkillModalDialog>
      )}

      {/* Modal: Edit Existing Custom Skill */}
      {editingSkill && (
        <SkillModalDialog>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Edit3 size={18} color="var(--accent-color)" /> Edit Saved Skill: {editingSkill.name}
          </h3>

          <form onSubmit={handleSaveEditedSkill}>
            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Skill Title</label>
              <input
                className="form-control"
                type="text"
                value={editingSkill.name || ''}
                onChange={(e) => setEditingSkill({ ...editingSkill, name: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Category</label>
              <input
                className="form-control"
                type="text"
                value={editingSkill.category || ''}
                onChange={(e) => setEditingSkill({ ...editingSkill, category: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Skill System Prompt Instruction</label>
              <textarea
                className="form-control"
                rows={4}
                value={editingSkill.prompt || ''}
                onChange={(e) => setEditingSkill({ ...editingSkill, prompt: e.target.value })}
                required
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditingSkill(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary btn-sm" style={{ fontWeight: 700 }}>
                <Save size={14} /> Update & Save
              </button>
            </div>
          </form>
        </SkillModalDialog>
      )}
    </div>
  );
}
