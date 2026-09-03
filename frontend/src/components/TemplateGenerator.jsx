import React, { useState, useRef } from 'react';
import axios from 'axios';
import {
  FileCode,
  Upload,
  Sparkles,
  Plus,
  Trash2,
  Check,
  Layers,
  FileText,
  Edit3,
  Save,
  CheckCircle2,
  RefreshCw,
  FolderOpen,
  HelpCircle,
  Cpu,
  BookOpen,
  Newspaper,
  Feather,
  Landmark,
  X,
  CopyPlus,
  ShieldCheck
} from 'lucide-react';
import AiDirectivesEditor from './AiDirectivesEditor';

export default function TemplateGenerator({
  templates = [],
  activeTemplateId,
  onSelectTemplate,
  onTemplatesUpdated,
  documentType = 'meeting_minutes',
  onSelectDocumentType
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [generalizingStatus, setGeneralizingStatus] = useState('');
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const DOC_TYPE_OPTIONS = [
    { id: 'meeting_minutes', label: 'Meeting minutes (Attendance block)', icon: FileText },
    { id: 'journal', label: 'Journal (Academic / Research Paper)', icon: BookOpen },
    { id: 'news', label: 'News (Press Release / Story)', icon: Newspaper },
    { id: 'blog', label: 'Blog (Digital Article / Thought Leadership)', icon: Feather },
    { id: 'bangladesh_govt_report', label: 'Report-Bangladesh government structure (Official Nothi)', icon: Landmark }
  ];

  const activeTemplate = templates.find((t) => t.id === activeTemplateId) || templates[0] || {};

  // Handle uploading and generalizing any DOCX document
  const handleUploadAndGeneralize = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.docx') && !file.name.toLowerCase().endsWith('.doc')) {
      alert('Please upload a Microsoft Word document (.docx) to generalize.');
      return;
    }

    setIsUploading(true);
    setGeneralizingStatus(`⚡ Analyzing '${file.name}', extracting document schema, Context, Rules, and Requirements...`);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', documentType || 'custom');

    try {
      const res = await axios.post('/api/generalize_template', formData);
      setIsUploading(false);
      setGeneralizingStatus('');

      if (res.data?.status === 'success' && res.data.template) {
        const newTpl = res.data.template;
        if (onTemplatesUpdated) {
          await onTemplatesUpdated();
        }
        if (onSelectTemplate) {
          onSelectTemplate(newTpl.id);
        }
        setEditingTemplate(newTpl);
        setShowEditor(true);
        alert(`Successfully extracted '${newTpl.name}' with auto-generated Context, Rules, and Requirements! It is now active.`);
      }
    } catch (err) {
      setIsUploading(false);
      setGeneralizingStatus('');
      alert('Failed to generalize template: ' + (err.response?.data?.detail || err.message));
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Delete a custom template
  const handleDeleteTemplate = async (e, tplId) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this custom template?')) return;

    try {
      const res = await axios.post('/api/delete_template', { template_id: tplId });
      if (res.data?.status === 'success') {
        if (activeTemplateId === tplId && onSelectTemplate) {
          onSelectTemplate('easd_default_minutes');
        }
        if (onTemplatesUpdated) {
          await onTemplatesUpdated();
        }
      }
    } catch (err) {
      alert('Error deleting template: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Open Template in Visual Editor
  const handleOpenEditor = (tpl) => {
    setEditingTemplate(JSON.parse(JSON.stringify(tpl)));
    setShowEditor(true);
  };

  // Save as a separate new custom template (NEVER overwrites existing template)
  const handleSaveAsNewTemplate = async (sourceTemplate = null) => {
    const target = sourceTemplate || editingTemplate;
    if (!target) return;
    
    let suggestedName = target.name || 'New Template';
    if (!suggestedName.toLowerCase().includes('custom') && !suggestedName.toLowerCase().includes('copy')) {
      suggestedName = `${suggestedName} (Custom)`;
    }
    const newName = window.prompt('Enter name for the new template copy (will not overwrite):', suggestedName);
    if (!newName || !newName.trim()) return;

    try {
      const payload = {
        ...target,
        name: newName.trim(),
        save_as_new: true
      };
      delete payload.id; // Ensure brand new ID is generated
      payload.is_builtin = false;
      payload.is_default = false;
      payload.category = payload.category || 'Custom Templates';

      const res = await axios.post('/api/save_template', payload);
      if (res.data?.status === 'success' && res.data.template) {
        const createdTpl = res.data.template;
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
        if (onTemplatesUpdated) {
          await onTemplatesUpdated();
        }
        if (onSelectTemplate) {
          onSelectTemplate(createdTpl.id);
        }
        setShowEditor(false);
        alert(`Saved new template '${createdTpl.name}'! Existing templates remained untouched.`);
      }
    } catch (err) {
      alert('Error saving as new template: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Save changes to custom template (protects built-in defaults)
  const handleSaveTemplate = async () => {
    if (!editingTemplate) return;
    if (editingTemplate.is_builtin) {
      // Built-in templates are read-only defaults: route to Save as New
      return handleSaveAsNewTemplate(editingTemplate);
    }
    try {
      const res = await axios.post('/api/save_template', editingTemplate);
      if (res.data?.status === 'success') {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
        if (onTemplatesUpdated) {
          await onTemplatesUpdated();
        }
        setShowEditor(false);
      }
    } catch (err) {
      alert('Error saving template: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Section manipulation in editor
  const handleAddSection = () => {
    if (!editingTemplate) return;
    const newSec = {
      id: `section_${(editingTemplate.sections || []).length + 1}`,
      title: `New Section ${(editingTemplate.sections || []).length + 1}`,
      type: 'bullets',
      prompt: 'Synthesize relevant points into crisp formal bullet points.'
    };
    setEditingTemplate({
      ...editingTemplate,
      sections: [...(editingTemplate.sections || []), newSec]
    });
  };

  const handleRemoveSection = (idx) => {
    if (!editingTemplate) return;
    const updated = (editingTemplate.sections || []).filter((_, i) => i !== idx);
    setEditingTemplate({ ...editingTemplate, sections: updated });
  };

  // Field manipulation in editor
  const handleAddField = () => {
    if (!editingTemplate) return;
    const newField = {
      key: `field_${(editingTemplate.fields || []).length + 1}`,
      label: `Field ${(editingTemplate.fields || []).length + 1}`,
      type: 'text',
      default: ''
    };
    setEditingTemplate({
      ...editingTemplate,
      fields: [...(editingTemplate.fields || []), newField]
    });
  };

  const handleRemoveField = (idx) => {
    if (!editingTemplate) return;
    const updated = (editingTemplate.fields || []).filter((_, i) => i !== idx);
    setEditingTemplate({ ...editingTemplate, fields: updated });
  };

  return (
    <div className="card" id="section-templates" style={{ marginBottom: '24px' }}>
      {/* Top Header & Document Type Dropdown */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <FileCode size={20} color="var(--accent-color)" /> 📑 AI Document Template & Directives Studio
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Upload any <code>.docx</code> template or select a document type. The AI dynamically adapts its <strong>Context, Rules, and Requirements</strong>.
          </p>
        </div>

        {/* Upload Button */}
        <div>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleUploadAndGeneralize}
            accept=".docx,.doc"
            style={{ display: 'none' }}
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, padding: '8px 16px' }}
          >
            <Upload size={16} />
            {isUploading ? 'Generalizing Template...' : '⚡ Upload .DOCX Template'}
          </button>
        </div>
      </div>

      {/* Document Type Selector Bar */}
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '14px 16px',
          marginBottom: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={16} color="var(--accent-color)" /> Select Document Type (ডকুমেন্ট টাইপ):
          </label>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Automatically adapts UI workspaces, tabs, and AI schema
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
          {DOC_TYPE_OPTIONS.map((opt) => {
            const isTypeActive = documentType === opt.id;
            const Icon = opt.icon;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  if (onSelectDocumentType) onSelectDocumentType(opt.id);
                  // Also pick matching template if available
                  const match = templates.find((t) => t.doc_type === opt.id);
                  if (match && onSelectTemplate) {
                    onSelectTemplate(match.id);
                  }
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  fontSize: '0.82rem',
                  fontWeight: isTypeActive ? 700 : 500,
                  border: isTypeActive ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                  background: isTypeActive ? 'rgba(14, 165, 233, 0.12)' : 'var(--bg-primary)',
                  color: isTypeActive ? 'var(--accent-color)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={16} />
                <span>{opt.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Generalizing Notice */}
      {isUploading && (
        <div
          style={{
            padding: '12px 16px',
            marginBottom: '16px',
            background: 'rgba(14, 165, 233, 0.1)',
            border: '1px solid var(--accent-color)',
            borderRadius: '10px',
            fontSize: '0.88rem',
            color: 'var(--accent-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}
        >
          <RefreshCw size={18} className="spin-animation" />
          <span>{generalizingStatus}</span>
        </div>
      )}

      {/* Active Template Banner with 3 Directives Overview */}
      <div
        style={{
          padding: '16px',
          background: 'var(--bg-secondary)',
          borderRadius: '12px',
          border: '1px solid var(--border-color)',
          marginBottom: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={22} color="var(--accent-color)" />
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Active Document Template
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {activeTemplate.name || 'EASD Meeting Minutes'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleOpenEditor(activeTemplate)}
              style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600 }}
            >
              <Edit3 size={14} /> Edit Directives & Schema
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => handleSaveAsNewTemplate(activeTemplate)}
              title="Save current directives as a new custom template (preserves original)"
              style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600 }}
            >
              <CopyPlus size={14} /> Save as New Template
            </button>
          </div>
        </div>

        {/* Interactive 3 Directives Preview Block */}
        <AiDirectivesEditor
          context={activeTemplate.context || ''}
          rules={activeTemplate.rules || ''}
          requirements={activeTemplate.requirements || ''}
          onChange={(newDirectives) => {
            const updated = { ...activeTemplate, ...newDirectives };
            // Only auto-save if this is a custom template, protecting official built-ins
            if (!activeTemplate.is_builtin && onTemplatesUpdated) {
              axios.post('/api/save_template', updated).then(() => onTemplatesUpdated());
            }
          }}
        />
      </div>

      {/* Template Library Grid */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={15} /> Available Templates Registry:
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
          {templates.map((tpl) => {
            const isSelected = tpl.id === activeTemplateId;
            return (
              <div
                key={tpl.id}
                onClick={() => onSelectTemplate && onSelectTemplate(tpl.id)}
                style={{
                  padding: '14px',
                  borderRadius: '10px',
                  border: isSelected ? '2px solid var(--accent-color)' : '1px solid var(--border-color)',
                  background: isSelected ? 'rgba(14, 165, 233, 0.08)' : 'var(--bg-primary)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '8px'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', marginBottom: '6px' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.92rem', color: isSelected ? 'var(--accent-color)' : 'var(--text-primary)' }}>
                      {tpl.name}
                    </div>
                    {isSelected && (
                      <span
                        style={{
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          background: 'var(--accent-color)',
                          color: '#fff'
                        }}
                      >
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                    {tpl.description || 'Custom template extracted from uploaded document.'}
                  </p>

                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'var(--bg-secondary)', borderRadius: '4px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                      📂 {tpl.category || 'Custom'}
                    </span>
                    <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'var(--bg-secondary)', borderRadius: '4px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                      📑 {(tpl.sections || []).length} Sections
                    </span>
                    {(tpl.tables || []).length > 0 && (
                      <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'var(--bg-secondary)', borderRadius: '4px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                        📊 {(tpl.tables || []).length} Tables
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '6px', paddingTop: '6px', borderTop: '1px solid var(--border-color)' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleOpenEditor(tpl);
                    }}
                    style={{ fontSize: '0.75rem', padding: '3px 8px' }}
                  >
                    <Edit3 size={12} /> Edit
                  </button>
                  {!tpl.is_builtin && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={(e) => handleDeleteTemplate(e, tpl.id)}
                      style={{ fontSize: '0.75rem', padding: '3px 8px', color: '#ef4444' }}
                    >
                      <Trash2 size={12} /> Delete
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Template Visual Schema & Directives Editor Modal */}
      {showEditor && editingTemplate && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '20px'
          }}
        >
          <div
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              maxWidth: '850px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
                    <Edit3 size={18} color="var(--accent-color)" /> Configure Template & AI Directives
                  </h3>
                  {editingTemplate.is_builtin && (
                    <span style={{ padding: '2px 8px', borderRadius: '12px', background: 'rgba(234, 179, 8, 0.15)', color: '#eab308', border: '1px solid rgba(234, 179, 8, 0.3)', fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <ShieldCheck size={12} /> Official Built-in (Protected)
                    </span>
                  )}
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px', marginBottom: 0 }}>
                  {editingTemplate.is_builtin
                    ? 'Built-in official templates cannot be overwritten. Saving will create a new custom template.'
                    : 'Customize Context, Rules, Requirements, and schema sections.'}
                </p>
              </div>
              <button
                onClick={() => setShowEditor(false)}
                className="btn btn-secondary btn-sm"
                style={{ padding: '4px 8px' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Template Basic Info */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Template Name
                </label>
                <input
                  type="text"
                  value={editingTemplate.name || ''}
                  onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Document Type
                </label>
                <select
                  value={editingTemplate.doc_type || 'custom'}
                  onChange={(e) => setEditingTemplate({ ...editingTemplate, doc_type: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem'
                  }}
                >
                  <option value="meeting_minutes">Meeting minutes</option>
                  <option value="journal">Journal</option>
                  <option value="news">News</option>
                  <option value="blog">Blog</option>
                  <option value="bangladesh_govt_report">Report-Bangladesh government structure</option>
                  <option value="custom">Custom Template</option>
                </select>
              </div>
            </div>

            {/* Reusable 3-Component AI Directives Block */}
            <div>
              <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', display: 'block', marginBottom: '8px' }}>
                ⚡ 3 Core AI Directives (Context, Rules, Requirements)
              </label>
              <AiDirectivesEditor
                context={editingTemplate.context || ''}
                rules={editingTemplate.rules || ''}
                requirements={editingTemplate.requirements || ''}
                onChange={(newDirectives) => {
                  setEditingTemplate({
                    ...editingTemplate,
                    ...newDirectives
                  });
                }}
              />
            </div>

            {/* Sections Editor */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  📑 Template Sections ({(editingTemplate.sections || []).length})
                </label>
                <button
                  type="button"
                  onClick={handleAddSection}
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <Plus size={12} /> Add Section
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(editingTemplate.sections || []).map((sec, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '10px',
                      background: 'var(--bg-secondary)',
                      borderRadius: '8px',
                      border: '1px solid var(--border-color)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px'
                    }}
                  >
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <input
                        type="text"
                        value={sec.title || ''}
                        onChange={(e) => {
                          const updated = [...(editingTemplate.sections || [])];
                          updated[idx].title = e.target.value;
                          setEditingTemplate({ ...editingTemplate, sections: updated });
                        }}
                        placeholder="Section Title"
                        style={{
                          flex: 1,
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--text-primary)',
                          fontSize: '0.82rem',
                          fontWeight: 600
                        }}
                      />
                      <select
                        value={sec.type || 'text'}
                        onChange={(e) => {
                          const updated = [...(editingTemplate.sections || [])];
                          updated[idx].type = e.target.value;
                          setEditingTemplate({ ...editingTemplate, sections: updated });
                        }}
                        style={{
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--text-primary)',
                          fontSize: '0.8rem'
                        }}
                      >
                        <option value="text">Paragraph Text</option>
                        <option value="bullets">Bullet Points</option>
                        <option value="list">Numbered List</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => handleRemoveSection(idx)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#ef4444',
                          cursor: 'pointer',
                          padding: '4px'
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                {editingTemplate.is_builtin ? (
                  <span style={{ color: '#eab308', display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <ShieldCheck size={14} /> Official default template is protected from being overwritten.
                  </span>
                ) : (
                  <span>Custom template: update it or create a new template copy.</span>
                )}
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEditor(false)}
                >
                  Cancel
                </button>

                {/* Dedicated Separate 'Save as New Template' Button */}
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleSaveAsNewTemplate(editingTemplate)}
                  title="Save as a brand new template copy - will NOT overwrite any existing templates"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, borderColor: 'var(--accent-color)', color: 'var(--accent-color)' }}
                >
                  <CopyPlus size={16} /> Save as New Template
                </button>

                {!editingTemplate.is_builtin && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleSaveTemplate}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}
                  >
                    <Save size={16} />
                    {saveSuccess ? 'Saved!' : 'Update Template'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
