import React, { useState, useEffect } from 'react';
import { api } from '../App';

const fmt = n => `$${Number(n || 0).toLocaleString('en-AU', { minimumFractionDigits: 2 })}`;

export default function Compliance() {
  const [submissions, setSubmissions] = useState([]);
  const [payslips, setPayslips] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [preparing, setPreparing] = useState(false);
  const [submitting, setSubmitting] = useState(null);
  const [selectedRun, setSelectedRun] = useState('');
  const [abn, setAbn] = useState('12345678901');
  const [msg, setMsg] = useState('');

  const load = () => {
    Promise.all([
      api('/stp/submissions').then(r => r.json()).catch(() => []),
      api('/payroll-runs').then(r => r.json()).catch(() => []),
    ]).then(([subs, rs]) => {
      setSubmissions(Array.isArray(subs) ? subs : []);
      setRuns(Array.isArray(rs) ? rs.filter(r => r.status === 'completed') : []);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const prepare = async () => {
    if (!selectedRun) return alert('Select a payroll run first');
    setPreparing(true); setMsg('');
    try {
      const runResp = await api(`/payroll-runs/${selectedRun}`);
      const runData = await runResp.json();

      const r = await api('/stp/prepare', {
        method: 'POST',
        body: JSON.stringify({
          payroll_run_id: selectedRun,
          payroll_data: runData,
          abn,
          submission_type: 'PAY_EVENT',
        })
      });
      const d = await r.json();
      setMsg(`STP submission prepared: ${d.submission_id} — Status: ${d.status}${d.validation_errors?.length ? ' | Errors: ' + d.validation_errors.join(', ') : ''}`);
      load();
    } catch (err) { setMsg('Error: ' + err.message); }
    setPreparing(false);
  };

  const submit = async id => {
    setSubmitting(id);
    try {
      const r = await api(`/stp/${id}/submit`, { method: 'POST' });
      const d = await r.json();
      setMsg(`Submitted to ATO! Reference: ${d.ato_reference}`);
      load();
    } catch (err) { setMsg('Error: ' + err.message); }
    setSubmitting(null);
  };

  const statusColors = {
    draft: { bg: '#1e293b', color: '#94a3b8' },
    validated: { bg: '#1e3a5f', color: '#60a5fa' },
    validation_failed: { bg: '#4b1d1d', color: '#f87171' },
    submitted: { bg: '#064e3b', color: '#34d399' },
    accepted: { bg: '#064e3b', color: '#34d399' },
    rejected: { bg: '#4b1d1d', color: '#f87171' },
  };

  const sel = { padding: '8px 12px', borderRadius: 7, border: '1px solid #334155', background: '#1e293b', color: '#94a3b8', fontSize: 13 };

  return (
    <div>
      <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>Compliance — STP Phase 2</h2>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 13 }}>
        Single Touch Payroll Phase 2 submission management and PAYG reporting
      </p>

      {/* Prepare STP */}
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155', marginBottom: 24 }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: 16, fontSize: 16 }}>Prepare STP Submission</h3>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Payroll Run</label>
            <select value={selectedRun} onChange={e => setSelectedRun(e.target.value)} style={{ ...sel, minWidth: 280 }}>
              <option value="">Select completed run...</option>
              {runs.map(r => <option key={r.id} value={r.id}>{r.run_name} — {r.period_end}</option>)}
            </select>
          </div>
          <div>
            <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Employer ABN</label>
            <input value={abn} onChange={e => setAbn(e.target.value)} style={{
              ...sel, padding: '8px 10px', width: 160,
            }} />
          </div>
          <button onClick={prepare} disabled={preparing} style={{
            background: '#7c3aed', border: 'none', color: '#fff', borderRadius: 8,
            padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 13
          }}>{preparing ? 'Preparing...' : '🏛 Prepare STP Submission'}</button>
        </div>
        {msg && (
          <p style={{ marginTop: 12, color: msg.startsWith('Error') ? '#f87171' : '#34d399', fontSize: 13 }}>
            {msg}
          </p>
        )}
      </div>

      {/* Submissions Table */}
      <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #0f172a' }}>
          <h3 style={{ color: '#e2e8f0', margin: 0, fontSize: 16 }}>STP Submissions ({submissions.length})</h3>
        </div>
        {loading ? <p style={{ color: '#64748b', padding: 20 }}>Loading...</p> : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#0f172a' }}>
              {['Type', 'Period', 'Employees', 'Total Gross', 'Total Tax', 'Super', 'Status', 'ATO Ref', 'Action'].map(h => (
                <th key={h} style={{ color: '#64748b', fontSize: 12, padding: '12px 14px', textAlign: 'left', fontWeight: 500 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {submissions.map(s => {
                const sc = statusColors[s.status] || { bg: '#1e293b', color: '#94a3b8' };
                return (
                  <tr key={s.id} style={{ borderTop: '1px solid #0f172a' }}>
                    <td style={{ padding: '12px 14px', color: '#e2e8f0', fontSize: 13 }}>{s.submission_type}</td>
                    <td style={{ padding: '12px 14px', color: '#64748b', fontSize: 12 }}>{s.period_start}<br />{s.period_end}</td>
                    <td style={{ padding: '12px 14px', color: '#94a3b8', fontSize: 13 }}>{s.employee_count}</td>
                    <td style={{ padding: '12px 14px', color: '#f59e0b', fontSize: 13 }}>{fmt(s.total_gross)}</td>
                    <td style={{ padding: '12px 14px', color: '#f87171', fontSize: 13 }}>{fmt(s.total_tax)}</td>
                    <td style={{ padding: '12px 14px', color: '#a78bfa', fontSize: 13 }}>{fmt(s.total_super)}</td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{ ...sc, fontSize: 11, padding: '3px 10px', borderRadius: 99, display: 'inline-block' }}>
                        {s.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', color: '#64748b', fontSize: 11, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {s.ato_reference || '—'}
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      {['validated', 'draft'].includes(s.status) && (
                        <button onClick={() => submit(s.id)} disabled={submitting === s.id} style={{
                          background: 'transparent', border: '1px solid #065f46', color: '#34d399',
                          borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 11
                        }}>{submitting === s.id ? '...' : 'Submit to ATO'}</button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {submissions.length === 0 && (
                <tr><td colSpan={9} style={{ padding: 40, textAlign: 'center', color: '#475569' }}>
                  No STP submissions yet. Prepare one above after completing a payroll run.
                </td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
