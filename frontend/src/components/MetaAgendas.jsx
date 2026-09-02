import React from 'react';
import { Calendar, Plus, Trash2, Clock, MapPin, FileText, CheckCircle2 } from 'lucide-react';

export default function MetaAgendas({ meta, setMeta, agendas, setAgendas }) {
  const handleAddAgenda = () => {
    setAgendas([...agendas, 'New Agenda Point']);
  };

  const handleUpdateAgenda = (idx, value) => {
    const next = [...agendas];
    next[idx] = value;
    setAgendas(next);
  };

  const handleRemoveAgenda = (idx) => {
    setAgendas(agendas.filter((_, i) => i !== idx));
  };

  // Convert Date Picker (YYYY-MM-DD) to formal date "DD Month, YYYY"
  const handleDatePickerChange = (e) => {
    const raw = e.target.value;
    if (!raw) return;
    const parts = raw.split('-');
    if (parts.length === 3) {
      const dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
      const formatted = dateObj.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'long',
        year: 'numeric'
      });
      setMeta({ ...meta, date: formatted });
    }
  };

  const handleSetToday = () => {
    const today = new Date();
    const formatted = today.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
    setMeta({ ...meta, date: formatted });
  };

  return (
    <div className="card" id="section-meta">
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Calendar size={20} color="var(--accent-color)" /> 4. Meeting Metadata & Agendas
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
        Configure meeting date using the calendar module or manual text, title, location, and dynamic agendas.
      </p>

      <div className="grid-2col">
        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FileText size={15} color="var(--accent-color)" /> Meeting Title / Type:
          </label>
          <input
            type="text"
            className="form-control"
            value={meta.title}
            onChange={(e) => setMeta({ ...meta, title: e.target.value })}
          />
        </div>

        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <MapPin size={15} color="var(--accent-color)" /> Location:
          </label>
          <input
            type="text"
            className="form-control"
            value={meta.location}
            onChange={(e) => setMeta({ ...meta, location: e.target.value })}
          />
        </div>

        {/* Date Selection Module: Manual + Calendar Picker */}
        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Calendar size={15} color="var(--accent-color)" /> Date (Calendar Module or Manual):
            </label>
            <button
              className="btn btn-secondary btn-sm"
              style={{ padding: '2px 8px', fontSize: '0.75rem' }}
              onClick={handleSetToday}
            >
              <CheckCircle2 size={12} /> Set Today
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 130px', gap: '10px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. 29 August, 2026"
              value={meta.date}
              onChange={(e) => setMeta({ ...meta, date: e.target.value })}
            />
            <input
              type="date"
              className="form-control"
              title="Pick date from calendar module"
              style={{ cursor: 'pointer' }}
              onChange={handleDatePickerChange}
            />
          </div>
          <small style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '4px', display: 'block' }}>
            Pick from calendar module or type any custom date format manually.
          </small>
        </div>

        {/* Time Field */}
        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={15} color="var(--accent-color)" /> Time:
          </label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. 11:00 AM - 01:00 PM"
            value={meta.time}
            onChange={(e) => setMeta({ ...meta, time: e.target.value })}
          />
        </div>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '20px 0' }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Meeting Agendas</h3>
        <button className="btn btn-secondary btn-sm" onClick={handleAddAgenda}>
          <Plus size={14} /> Add Agenda Point
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {agendas.map((item, idx) => {
          const displayVal = String(item || '').replace(/^(?:\d+[\.\)\:\-]\s*|\[\d+\]\s*|[•\-\*\t]+\s*)+/g, '').trim();
          return (
            <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '0.85rem', width: '20px' }}>{idx + 1}.</span>
              <input
                type="text"
                className="form-control"
                value={displayVal}
                onChange={(e) => handleUpdateAgenda(idx, e.target.value)}
              />
              <button className="btn btn-danger btn-sm" onClick={() => handleRemoveAgenda(idx)}>
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
