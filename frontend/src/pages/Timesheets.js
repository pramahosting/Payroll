import React, { useState, useEffect } from 'react';
import { api } from '../App';

const EMPTY_TS = {
  employee_id: '', period_start: '', period_end: '',
  ordinary_hours: 0, overtime_hours_1_5x: 0, overtime_hours_2x: 0,
  public_holiday_hours: 0, annual_leave_hours: 0, sick_leave_hours: 0,
  long_service_leave_hours: 0, unpaid_leave_hours: 0, notes: '',
};

const statusColor = {
  draft: { bg: '#1e293b', color: '#94a3b8' },
  submitted: { bg: '#1e3a5f', color: '#60a5fa' },
  approved: { bg: '#064e3b', color: '#34d399' },
  rejected: { bg: '#4b1d1d', color: '#f87171' },
};

function NumberInput({ label, value, onChange }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 3 }}>{label}</label>
      <input
        type="number" min="0" step="0.5" value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        style={{
          width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #334155',
          background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
        }}
      />
    </div>
  );
}

export default function Timesheets() {
  const [timesheets, setTimesheets] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_TS);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [filterEmployee, setFilterEmployee] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([
      api('/timesheets').then(r => r.json()).catch(() => []),
      api('/employees').then(r => r.json()).catch(() => []),
    ]).then(([ts, emps]) => {
      setTimesheets(Array.isArray(ts) ? ts : []);
      setEmployees(Array.isArray(emps) ? emps : []);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async e => {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const r = await api('/timesheets', { method: 'POST', body: JSON.stringify(form) });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Failed'); }
      setShowForm(false);
      setForm(EMPTY_TS);
      load();
    } catch (err) { setError(err.message); }
    setSaving(false);
  };

  const action = async (id, endpoint) => {
    await api(`/timesheets/${id}/${endpoint}`, { method: 'POST' });
    load();
  };

  const filtered = timesheets
    .filter(t => !filterEmployee || t.employee_id === filterEmployee)
    .filter(t => !filterStatus || t.status === filterStatus);

  const empName = id => {
    const e = employees.find(e => e.id === id);
    return e ? `${e.first_name} ${e.last_name}` : id;
  };

  const sel = { padding: '8px 12px', borderRadius: 7, border: '1px solid #334155', background: '#1e293b', color: '#94a3b8', fontSize: 13 };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ color: '#f1f5f9', margin: 0 }}>Timesheets</h2>
          <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: 13 }}>{timesheets.length} records</p>
        </div>
        <button onClick={() => { setForm(EMPTY_TS); setShowForm(true); setError(''); }} style={{
          background: '#3b82f6', border: 'none', color: '#fff', borderRadius: 8,
          padding: '10px 20px', cursor: 'pointer', fontSize: 14, fontWeight: 600
        }}>+ New Timesheet</button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <select value={filterEmployee} onChange={e => setFilterEmployee(e.target.value)} style={sel}>
          <option value="">All Employees</option>
          {employees.map(e => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={sel}>
          <option value="">All Statuses</option>
          {['draft', 'submitted', 'approved', 'rejected'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading ? <p style={{ color: '#64748b' }}>Loading...</p> : (
        <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#0f172a' }}>
                {['Employee', 'Period', 'Ord Hrs', 'OT 1.5x', 'OT 2x', 'Leave', 'Total', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ color: '#64748b', fontSize: 12, padding: '12px 14px', textAlign: 'left', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(ts => {
                const sc = statusColor[ts.status] || { bg: '#1e293b', color: '#94a3b8' };
                const totalLeave = (ts.annual_leave_hours || 0) + (ts.sick_leave_hours || 0);
                return (
                  <tr key={ts.id} style={{ borderTop: '1px solid #0f172a' }}>
                    <td style={{ padding: '12px 14px', color: '#e2e8f0', fontSize: 13 }}>{empName(ts.employee_id)}</td>
                    <td style={{ padding: '12px 14px', color: '#94a3b8', fontSize: 12 }}>
                      {ts.period_start}<br />{ts.period_end}
                    </td>
                    <td style={{ padding: '12px 14px', color: '#e2e8f0', fontSize: 13 }}>{ts.ordinary_hours}</td>
                    <td style={{ padding: '12px 14px', color: '#f59e0b', fontSize: 13 }}>{ts.overtime_hours_1_5x}</td>
                    <td style={{ padding: '12px 14px', color: '#f97316', fontSize: 13 }}>{ts.overtime_hours_2x}</td>
                    <td style={{ padding: '12px 14px', color: '#a78bfa', fontSize: 13 }}>{totalLeave}</td>
                    <td style={{ padding: '12px 14px', color: '#34d399', fontWeight: 600, fontSize: 13 }}>
                      {((ts.ordinary_hours || 0) + (ts.overtime_hours_1_5x || 0) + (ts.overtime_hours_2x || 0) + totalLeave).toFixed(1)}h
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{ ...sc, fontSize: 11, padding: '3px 10px', borderRadius: 99, display: 'inline-block' }}>
                        {ts.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {ts.status === 'draft' && (
                          <button onClick={() => action(ts.id, 'submit')} style={{
                            background: 'transparent', border: '1px solid #1d4ed8', color: '#60a5fa',
                            borderRadius: 6, padding: '3px 8px', cursor: 'pointer', fontSize: 11
                          }}>Submit</button>
                        )}
                        {ts.status === 'submitted' && (
                          <>
                            <button onClick={() => action(ts.id, 'approve')} style={{
                              background: 'transparent', border: '1px solid #065f46', color: '#34d399',
                              borderRadius: 6, padding: '3px 8px', cursor: 'pointer', fontSize: 11
                            }}>Approve</button>
                            <button onClick={() => action(ts.id, 'reject')} style={{
                              background: 'transparent', border: '1px solid #7f1d1d', color: '#f87171',
                              borderRadius: 6, padding: '3px 8px', cursor: 'pointer', fontSize: 11
                            }}>Reject</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={9} style={{ padding: 32, textAlign: 'center', color: '#475569' }}>No timesheets found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex',
          alignItems: 'flex-start', justifyContent: 'center', zIndex: 1000, overflowY: 'auto', padding: '40px 0'
        }}>
          <div style={{ background: '#1e293b', borderRadius: 16, padding: 32, width: 560, border: '1px solid #334155', margin: 'auto' }}>
            <h3 style={{ color: '#f1f5f9', marginBottom: 20 }}>New Timesheet</h3>
            <form onSubmit={save}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Employee *</label>
                <select value={form.employee_id} onChange={e => setF('employee_id', e.target.value)} required style={{
                  width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
                  background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
                }}>
                  <option value="">Select employee...</option>
                  {employees.map(e => <option key={e.id} value={e.id}>{e.first_name} {e.last_name} ({e.employee_number})</option>)}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Period Start *</label>
                  <input type="date" value={form.period_start} onChange={e => setF('period_start', e.target.value)} required style={{
                    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
                    background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
                  }} />
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Period End *</label>
                  <input type="date" value={form.period_end} onChange={e => setF('period_end', e.target.value)} required style={{
                    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
                    background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
                  }} />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <NumberInput label="Ordinary Hours" value={form.ordinary_hours} onChange={v => setF('ordinary_hours', v)} />
                <NumberInput label="Overtime 1.5x Hours" value={form.overtime_hours_1_5x} onChange={v => setF('overtime_hours_1_5x', v)} />
                <NumberInput label="Overtime 2x Hours" value={form.overtime_hours_2x} onChange={v => setF('overtime_hours_2x', v)} />
                <NumberInput label="Public Holiday Hours" value={form.public_holiday_hours} onChange={v => setF('public_holiday_hours', v)} />
                <NumberInput label="Annual Leave Hours" value={form.annual_leave_hours} onChange={v => setF('annual_leave_hours', v)} />
                <NumberInput label="Sick Leave Hours" value={form.sick_leave_hours} onChange={v => setF('sick_leave_hours', v)} />
                <NumberInput label="Long Service Leave" value={form.long_service_leave_hours} onChange={v => setF('long_service_leave_hours', v)} />
                <NumberInput label="Unpaid Leave Hours" value={form.unpaid_leave_hours} onChange={v => setF('unpaid_leave_hours', v)} />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Notes</label>
                <textarea value={form.notes} onChange={e => setF('notes', e.target.value)} rows={2} style={{
                  width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
                  background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box', resize: 'vertical'
                }} />
              </div>

              {error && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 12 }}>{error}</p>}
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                  borderRadius: 8, padding: '10px 20px', cursor: 'pointer'
                }}>Cancel</button>
                <button type="submit" disabled={saving} style={{
                  background: '#3b82f6', border: 'none', color: '#fff',
                  borderRadius: 8, padding: '10px 24px', cursor: 'pointer', fontWeight: 600
                }}>{saving ? 'Saving...' : 'Create Timesheet'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
