import React, { useState, useEffect } from 'react';
import { api } from '../App';

export default function Reports() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [reportType, setReportType] = useState('payroll-summary');
  const [financialYear, setFinancialYear] = useState('2023-24');
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api('/payroll-runs').then(r => r.json()).then(d => {
      const completed = Array.isArray(d) ? d.filter(r => r.status === 'completed') : [];
      setRuns(completed);
      if (completed[0]) setSelectedRun(completed[0].id);
    }).catch(() => {});
  }, []);

  const generateReport = async () => {
    if (!selectedRun) return alert('Select a payroll run first');
    setLoading(true); setReport(null); setMsg('');

    try {
      const runResp = await api(`/payroll-runs/${selectedRun}`);
      const runData = await runResp.json();
      const payslips = runData.payslips || [];
      const run = runData.run || {};

      let endpoint, body;
      if (reportType === 'payroll-summary') {
        endpoint = '/reports/payroll-summary';
        body = { payroll_run_id: selectedRun, run_data: run, payslips };
      } else if (reportType === 'tax-report') {
        endpoint = '/reports/tax-report';
        body = { financial_year: financialYear, payslips };
      } else {
        endpoint = '/reports/super-report';
        body = { period_start: run.period_start, period_end: run.period_end, payslips };
      }

      const r = await api(endpoint, { method: 'POST', body: JSON.stringify(body) });
      const d = await r.json();
      setReport(d);
    } catch (err) { setMsg('Error generating report: ' + err.message); }
    setLoading(false);
  };

  const downloadCSV = async () => {
    if (!selectedRun) return;
    setLoading(true);
    try {
      const runResp = await api(`/payroll-runs/${selectedRun}`);
      const runData = await runResp.json();
      const payslips = runData.payslips || [];
      const run = runData.run || {};

      let endpoint, body;
      if (reportType === 'payroll-summary') {
        endpoint = '/reports/payroll-summary?format=csv';
        body = { payroll_run_id: selectedRun, run_data: run, payslips };
      } else if (reportType === 'tax-report') {
        endpoint = '/reports/tax-report?format=csv';
        body = { financial_year: financialYear, payslips };
      } else {
        endpoint = '/reports/super-report?format=csv';
        body = { period_start: run.period_start, period_end: run.period_end, payslips };
      }

      const r = await api(endpoint, { method: 'POST', body: JSON.stringify(body) });
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportType}-${selectedRun.slice(0, 8)}.csv`;
      a.click();
    } catch (err) { setMsg('Download failed: ' + err.message); }
    setLoading(false);
  };

  const fmt = n => {
    const num = parseFloat(String(n).replace(/[$,]/g, ''));
    return isNaN(num) ? n : `$${num.toLocaleString('en-AU', { minimumFractionDigits: 2 })}`;
  };

  const sel = { padding: '8px 12px', borderRadius: 7, border: '1px solid #334155', background: '#1e293b', color: '#94a3b8', fontSize: 13 };

  const ReportTypeCard = ({ id, label, desc, icon }) => (
    <div onClick={() => setReportType(id)} style={{
      background: reportType === id ? '#1e3a5f' : '#1e293b',
      border: `1px solid ${reportType === id ? '#3b82f6' : '#334155'}`,
      borderRadius: 10, padding: '16px 20px', cursor: 'pointer', flex: 1,
    }}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>{icon}</div>
      <p style={{ color: '#e2e8f0', fontWeight: 600, margin: '0 0 4px', fontSize: 14 }}>{label}</p>
      <p style={{ color: '#64748b', fontSize: 12, margin: 0 }}>{desc}</p>
    </div>
  );

  return (
    <div>
      <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>Reports</h2>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 13 }}>Generate payroll summaries, tax and superannuation reports</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <ReportTypeCard id="payroll-summary" icon="📊" label="Payroll Summary" desc="Full payroll run breakdown per employee" />
        <ReportTypeCard id="tax-report" icon="🧾" label="Tax Report" desc="PAYG withholding by financial year" />
        <ReportTypeCard id="super-report" icon="🏦" label="Super Report" desc="Superannuation contributions breakdown" />
      </div>

      <div style={{ background: '#1e293b', borderRadius: 12, padding: 24, border: '1px solid #334155', marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Payroll Run</label>
            <select value={selectedRun} onChange={e => setSelectedRun(e.target.value)} style={{ ...sel, minWidth: 280 }}>
              <option value="">Select run...</option>
              {runs.map(r => <option key={r.id} value={r.id}>{r.run_name} ({r.period_end})</option>)}
            </select>
          </div>
          {reportType === 'tax-report' && (
            <div>
              <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>Financial Year</label>
              <select value={financialYear} onChange={e => setFinancialYear(e.target.value)} style={sel}>
                {['2023-24', '2022-23', '2021-22'].map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          )}
          <button onClick={generateReport} disabled={loading} style={{
            background: '#3b82f6', border: 'none', color: '#fff', borderRadius: 8,
            padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 13
          }}>{loading ? 'Generating...' : '📊 Generate Report'}</button>
          <button onClick={downloadCSV} disabled={loading} style={{
            background: 'transparent', border: '1px solid #334155', color: '#94a3b8', borderRadius: 8,
            padding: '10px 20px', cursor: 'pointer', fontSize: 13
          }}>⬇ Download CSV</button>
        </div>
        {msg && <p style={{ marginTop: 12, color: '#f87171', fontSize: 13 }}>{msg}</p>}
      </div>

      {/* Report Output */}
      {report && (
        <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflow: 'hidden' }}>
          {/* Totals */}
          {report.totals && (
            <div style={{ padding: 20, borderBottom: '1px solid #0f172a', display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              {Object.entries(report.totals).map(([k, v]) => (
                <div key={k}>
                  <p style={{ color: '#475569', fontSize: 11, margin: '0 0 2px', textTransform: 'uppercase', letterSpacing: 0.5 }}>{k.replace(/_/g, ' ')}</p>
                  <p style={{ color: '#e2e8f0', fontSize: 18, margin: 0, fontWeight: 700 }}>
                    {typeof v === 'number' && k !== 'employee_count' ? fmt(v) : v}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Rows Table */}
          {report.rows && report.rows.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#0f172a' }}>
                    {Object.keys(report.rows[0]).map(h => (
                      <th key={h} style={{ color: '#64748b', padding: '10px 12px', textAlign: 'left', fontWeight: 500, whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row, i) => (
                    <tr key={i} style={{ borderTop: '1px solid #0f172a' }}>
                      {Object.values(row).map((val, j) => (
                        <td key={j} style={{ padding: '10px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{val}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {report.rows?.length === 0 && (
            <p style={{ padding: 32, textAlign: 'center', color: '#475569' }}>No data in this report</p>
          )}
        </div>
      )}
    </div>
  );
}
