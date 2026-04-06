import React, { useState, useEffect, useRef } from 'react';
import { api } from '../App';

const fmt = n => `$${Number(n || 0).toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function RunCard({ run, onView }) {
  const statusColors = {
    completed: { bg: '#064e3b', color: '#34d399' },
    processing: { bg: '#1e3a5f', color: '#60a5fa' },
    pending: { bg: '#292524', color: '#d97706' },
    failed: { bg: '#4b1d1d', color: '#f87171' },
  };
  const sc = statusColors[run.status] || statusColors.pending;

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, border: '1px solid #334155', marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h4 style={{ color: '#f1f5f9', margin: '0 0 4px', fontSize: 16 }}>{run.run_name}</h4>
          <p style={{ color: '#64748b', margin: 0, fontSize: 13 }}>
            {run.period_start} → {run.period_end} | Pay date: {run.pay_date}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ ...sc, fontSize: 12, padding: '3px 12px', borderRadius: 99, display: 'inline-block' }}>
            {run.status}
          </span>
          {run.status === 'completed' && (
            <button onClick={() => onView(run.id)} style={{
              background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
              borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 12
            }}>View Payslips</button>
          )}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        {[
          ['Employees', run.employee_count],
          ['Gross', fmt(run.total_gross)],
          ['Tax', fmt(run.total_tax)],
          ['Net', fmt(run.total_net)],
          ['Super', fmt(run.total_super)],
        ].map(([label, val]) => (
          <div key={label}>
            <p style={{ color: '#475569', fontSize: 11, margin: '0 0 2px', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</p>
            <p style={{ color: '#e2e8f0', fontSize: 15, margin: 0, fontWeight: 600 }}>{val}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PayrollRun() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [viewRunId, setViewRunId] = useState(null);
  const [viewData, setViewData] = useState(null);
  const [form, setForm] = useState({
    run_name: '', period_start: '', period_end: '', pay_date: '',
    pay_frequency: 'fortnightly', use_orchestrator: false,
    employer_bsb: '062-000', employer_account: '123456789',
    employer_name: 'ACME PTY LTD', employer_abn: '12345678901',
    generate_aba: true, generate_super_batch: true,
  });
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  const load = () => {
    api('/payroll-runs').then(r => r.json()).then(d => {
      setRuns(Array.isArray(d) ? d : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); return () => clearInterval(pollRef.current); }, []);

  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const startRun = async e => {
    e.preventDefault();
    setRunning(true); setError(''); setRunResult(null);

    try {
      if (form.use_orchestrator) {
        // Full orchestrated run (payroll + ABA + super + STP)
        const r = await api('/orchestrate/full-payroll-run', {
          method: 'POST',
          body: JSON.stringify({
            run_name: form.run_name,
            period_start: form.period_start,
            period_end: form.period_end,
            pay_date: form.pay_date,
            pay_frequency: form.pay_frequency,
            employer_bsb: form.employer_bsb,
            employer_account: form.employer_account,
            employer_name: form.employer_name,
            employer_abn: form.employer_abn,
            generate_aba: form.generate_aba,
            generate_super_batch: form.generate_super_batch,
          })
        });
        const data = await r.json();
        setRunResult(data);
        setShowForm(false);
        load();
      } else {
        // Payroll calculation only
        const r = await api('/payroll-runs', {
          method: 'POST',
          body: JSON.stringify({
            run_name: form.run_name,
            period_start: form.period_start,
            period_end: form.period_end,
            pay_date: form.pay_date,
            pay_frequency: form.pay_frequency,
          })
        });
        if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Failed'); }
        setShowForm(false);
        // Poll for completion
        pollRef.current = setInterval(() => {
          load();
          api('/payroll-runs').then(r => r.json()).then(d => {
            if (Array.isArray(d) && d[0]?.status === 'completed') clearInterval(pollRef.current);
          });
        }, 3000);
        setTimeout(() => clearInterval(pollRef.current), 60000);
      }
    } catch (err) { setError(err.message); }
    setRunning(false);
  };

  const viewRun = async id => {
    setViewRunId(id);
    const r = await api(`/payroll-runs/${id}`);
    const d = await r.json();
    setViewData(d);
  };

  const inp = (label, key, type = 'text', options) => (
    <div style={{ marginBottom: 12 }}>
      <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>{label}</label>
      {options ? (
        <select value={form[key]} onChange={e => setF(key, e.target.value)} style={{
          width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
          background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
        }}>
          {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
      ) : (
        <input type={type} value={form[key]} onChange={e => setF(key, e.target.value)} style={{
          width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
          background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box'
        }} />
      )}
    </div>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ color: '#f1f5f9', margin: 0 }}>Payroll Runs</h2>
          <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: 13 }}>{runs.length} total runs</p>
        </div>
        <button onClick={() => { setShowForm(true); setError(''); setRunResult(null); }} style={{
          background: '#10b981', border: 'none', color: '#fff', borderRadius: 8,
          padding: '10px 20px', cursor: 'pointer', fontSize: 14, fontWeight: 600
        }}>▶ Run Payroll</button>
      </div>

      {runResult && (
        <div style={{ background: '#064e3b', border: '1px solid #065f46', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <h4 style={{ color: '#34d399', marginBottom: 12 }}>✓ Orchestrated Payroll Complete</h4>
          {runResult.steps?.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              <span style={{ color: '#34d399', fontSize: 13 }}>✓</span>
              <span style={{ color: '#d1fae5', fontSize: 13 }}>
                {s.step.replace(/_/g, ' ')} — {s.status}
                {s.total_amount ? ` · ${fmt(s.total_amount)}` : ''}
                {s.totals ? ` · Gross: ${fmt(s.totals.gross)} | Net: ${fmt(s.totals.net)}` : ''}
              </span>
            </div>
          ))}
          {runResult.errors?.map((e, i) => (
            <p key={i} style={{ color: '#fca5a5', fontSize: 13, margin: '4px 0' }}>⚠ {e}</p>
          ))}
        </div>
      )}

      {loading ? <p style={{ color: '#64748b' }}>Loading...</p> : (
        <>
          {runs.map(run => <RunCard key={run.id} run={run} onView={viewRun} />)}
          {runs.length === 0 && (
            <div style={{ textAlign: 'center', padding: 60, color: '#475569' }}>
              <p style={{ fontSize: 48, marginBottom: 16 }}>💰</p>
              <p>No payroll runs yet. Click "Run Payroll" to get started.</p>
            </div>
          )}
        </>
      )}

      {/* Run Form */}
      {showForm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{ background: '#1e293b', borderRadius: 16, padding: 32, width: 560, border: '1px solid #334155' }}>
            <h3 style={{ color: '#f1f5f9', marginBottom: 20 }}>Configure Payroll Run</h3>
            <form onSubmit={startRun}>
              {inp('Run Name', 'run_name')}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                {inp('Period Start', 'period_start', 'date')}
                {inp('Period End', 'period_end', 'date')}
                {inp('Pay Date', 'pay_date', 'date')}
                {inp('Pay Frequency', 'pay_frequency', 'text', [
                  { v: 'weekly', l: 'Weekly' },
                  { v: 'fortnightly', l: 'Fortnightly' },
                  { v: 'monthly', l: 'Monthly' },
                ])}
              </div>

              <div style={{
                background: '#0f172a', borderRadius: 8, padding: 16, marginBottom: 16,
                border: '1px solid #334155'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <input type="checkbox" id="orch" checked={form.use_orchestrator}
                    onChange={e => setF('use_orchestrator', e.target.checked)} />
                  <label htmlFor="orch" style={{ color: '#e2e8f0', fontSize: 14, cursor: 'pointer' }}>
                    Full Orchestration (ABA + Super + STP)
                  </label>
                </div>
                {form.use_orchestrator && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
                    {inp('Employer ABN', 'employer_abn')}
                    {inp('Employer Name', 'employer_name')}
                    {inp('Bank BSB', 'employer_bsb')}
                    {inp('Bank Account', 'employer_account')}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <input type="checkbox" checked={form.generate_aba}
                        onChange={e => setF('generate_aba', e.target.checked)} id="aba" />
                      <label htmlFor="aba" style={{ color: '#94a3b8', fontSize: 13 }}>Generate ABA File</label>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <input type="checkbox" checked={form.generate_super_batch}
                        onChange={e => setF('generate_super_batch', e.target.checked)} id="super" />
                      <label htmlFor="super" style={{ color: '#94a3b8', fontSize: 13 }}>Generate Super Batch</label>
                    </div>
                  </div>
                )}
              </div>

              {error && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 12 }}>{error}</p>}
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                  borderRadius: 8, padding: '10px 20px', cursor: 'pointer'
                }}>Cancel</button>
                <button type="submit" disabled={running} style={{
                  background: running ? '#334155' : '#10b981', border: 'none', color: '#fff',
                  borderRadius: 8, padding: '10px 24px', cursor: running ? 'default' : 'pointer', fontWeight: 600
                }}>{running ? '⏳ Processing...' : '▶ Start Payroll Run'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Payslips Modal */}
      {viewData && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex',
          alignItems: 'flex-start', justifyContent: 'center', zIndex: 1000, overflowY: 'auto', padding: '40px 0'
        }}>
          <div style={{ background: '#1e293b', borderRadius: 16, padding: 32, width: 900, border: '1px solid #334155', margin: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ color: '#f1f5f9', margin: 0 }}>Payslips — {viewData.run?.run_name}</h3>
              <button onClick={() => setViewData(null)} style={{
                background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                borderRadius: 6, padding: '4px 12px', cursor: 'pointer'
              }}>✕ Close</button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#0f172a' }}>
                    {['Name', 'Gross', 'PAYG Tax', 'Net Pay', 'Super', 'Ord Hrs', 'OT Hrs', 'Pay Date'].map(h => (
                      <th key={h} style={{ color: '#64748b', padding: '10px 12px', textAlign: 'left', fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(viewData.payslips || []).map(ps => (
                    <tr key={ps.id} style={{ borderTop: '1px solid #0f172a' }}>
                      <td style={{ padding: '10px 12px', color: '#e2e8f0' }}>{ps.full_name}</td>
                      <td style={{ padding: '10px 12px', color: '#f59e0b' }}>{fmt(ps.gross_earnings)}</td>
                      <td style={{ padding: '10px 12px', color: '#f87171' }}>{fmt(ps.payg_tax)}</td>
                      <td style={{ padding: '10px 12px', color: '#34d399', fontWeight: 700 }}>{fmt(ps.net_pay)}</td>
                      <td style={{ padding: '10px 12px', color: '#a78bfa' }}>{fmt(ps.super_guarantee)}</td>
                      <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{ps.ordinary_hours}</td>
                      <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{(ps.overtime_hours_1_5x || 0) + (ps.overtime_hours_2x || 0)}</td>
                      <td style={{ padding: '10px 12px', color: '#64748b' }}>{ps.pay_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
