import React from 'react';
import { MessageSquare, Plus, Trash2 } from 'lucide-react';

export default function Discussions({ discussions, setDiscussions, decisions, setDecisions }) {
  const handleAddRow = () => {
    setDiscussions([
      ...discussions,
      { sn: (discussions.length + 1).toString(), topic: 'New Discussion Point', details: '• Key discussion notes...' }
    ]);
  };

  const handleUpdateRow = (idx, field, value) => {
    const next = [...discussions];
    next[idx] = { ...next[idx], [field]: value };
    setDiscussions(next);
  };

  const handleRemoveRow = (idx) => {
    setDiscussions(discussions.filter((_, i) => i !== idx));
  };

  return (
    <div className="card" id="section-discussions">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <MessageSquare size={20} color="var(--accent-color)" /> 5. Discussion Points & Major Discussions
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Matches Table 0 structure in DOCX template.
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={handleAddRow}>
          <Plus size={14} /> Add Row
        </button>
      </div>

      <div style={{ overflowX: 'auto', marginBottom: '20px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid var(--border-color)' }}>
          <thead>
            <tr style={{ background: 'var(--bg-secondary)', textAlign: 'left', fontSize: '0.85rem' }}>
              <th style={{ padding: '10px', width: '60px', border: '1px solid var(--border-color)' }}>SN</th>
              <th style={{ padding: '10px', width: '260px', border: '1px solid var(--border-color)' }}>Discussion Points</th>
              <th style={{ padding: '10px', border: '1px solid var(--border-color)' }}>Major Discussions</th>
              <th style={{ padding: '10px', width: '50px', border: '1px solid var(--border-color)' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {discussions.map((item, idx) => (
              <tr key={idx}>
                <td style={{ padding: '8px', border: '1px solid var(--border-color)' }}>
                  <input
                    type="text"
                    className="form-control"
                    value={item.sn}
                    onChange={(e) => handleUpdateRow(idx, 'sn', e.target.value)}
                  />
                </td>
                <td style={{ padding: '8px', border: '1px solid var(--border-color)' }}>
                  <input
                    type="text"
                    className="form-control"
                    value={item.topic}
                    onChange={(e) => handleUpdateRow(idx, 'topic', e.target.value)}
                  />
                </td>
                <td style={{ padding: '8px', border: '1px solid var(--border-color)' }}>
                  <textarea
                    className="form-control"
                    rows={3}
                    value={item.details}
                    onChange={(e) => handleUpdateRow(idx, 'details', e.target.value)}
                  />
                </td>
                <td style={{ padding: '8px', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                  <button className="btn btn-danger btn-sm" onClick={() => handleRemoveRow(idx)}>
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
