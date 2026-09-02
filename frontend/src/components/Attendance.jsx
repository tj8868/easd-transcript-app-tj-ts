import React, { useState } from 'react';
import { Users, CheckCheck, X, UserPlus, Search } from 'lucide-react';

export default function Attendance({ attendance, setAttendance }) {
  const [filterText, setFilterText] = useState('');

  const handleToggle = (idx, value) => {
    const next = [...attendance];
    next[idx].participation = value;
    setAttendance(next);
  };

  const handleSelectAll = (value) => {
    setAttendance(attendance.map((m) => ({ ...m, participation: value })));
  };

  const handleAddMember = () => {
    const name = prompt('Enter new team member full name:');
    if (name && name.trim()) {
      setAttendance([
        ...attendance,
        {
          serial: (attendance.length + 1).toString(),
          name: name.trim(),
          participation: 'Yes'
        }
      ]);
    }
  };

  const filteredMembers = attendance.filter((m) =>
    m.name.toLowerCase().includes(filterText.toLowerCase().trim())
  );

  return (
    <div className="card" id="section-attendance">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Users size={20} color="var(--accent-color)" /> 6. Attendance Sheet Checklist (21 Members)
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Toggle Yes/No participation for template Table 1.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm" onClick={() => handleSelectAll('Yes')}>
            <CheckCheck size={14} color="var(--success-color)" /> All Yes
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => handleSelectAll('No')}>
            <X size={14} color="var(--danger-color)" /> All No
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleAddMember}>
            <UserPlus size={14} /> Add Member
          </button>
        </div>
      </div>

      <div style={{ position: 'relative', marginBottom: '16px' }}>
        <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
        <input
          type="text"
          className="form-control"
          style={{ paddingLeft: '36px' }}
          placeholder="Filter attendees by name..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
        />
      </div>

      <div className="attendance-grid">
        {filteredMembers.map((member, idx) => {
          const originalIdx = attendance.findIndex((m) => m === member);
          const isYes = member.participation === 'Yes';
          return (
            <div key={idx} className="attendance-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {member.serial || originalIdx + 1}
                </div>
                <div style={{ fontSize: '0.88rem', fontWeight: 600 }}>{member.name}</div>
              </div>
              <div className="toggle-switch">
                <button
                  className={`toggle-opt ${isYes ? 'active-yes' : ''}`}
                  onClick={() => handleToggle(originalIdx, 'Yes')}
                >
                  Yes
                </button>
                <button
                  className={`toggle-opt ${!isYes ? 'active-no' : ''}`}
                  onClick={() => handleToggle(originalIdx, 'No')}
                >
                  No
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
