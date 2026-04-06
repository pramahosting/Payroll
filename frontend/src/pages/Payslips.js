// Payslips.js
import React, { useState, useEffect } from 'react';
import { api } from '../App';

const fmt = n => `$${Number(n || 0).toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function Payslips() {
  const [payslips, setPayslips] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [filterEmp, setFilterEmp] = useState('');

  useEffect(() => {
    Promise.all([
      api('/payslips').then(r => r.json()).catch(() => []),
      api('/employees').then(r => r.json()).catch(() => []),
    ]).then(([ps, emps]) => {
      setPayslips(Array.isArray(ps) ? ps : []);
      setEmployees(Array.isArray(emps) ? emps : []);
      setLoading(false);
    });
  }, []);

  const filtered = payslips.filter(p => !filterEmp || p.employee_id === filterEmp);

  const Row = ({ label, value, highlight }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid #1e293b' }}>
      <span style={{ color: '#94a3b8', fontSize: 13 }}>{label}</span>
      <span style={{ color: highlight || '#e2e8f0', fontSize: 13, fontWeight: highlight ? 700 : 400 }}>{value}</span>
    </div>
  );

  return (
    <div>
      <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>Payslips</h2>
      <p style={{ color: '#64748b', marginBottom: 20, fontSize: 13 }}>{payslips.length} payslips generated</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <select value={filterEmp} onChange={e => setFilterEmp(e.target.value)} style={{
          padding: '8px 12px', borderRadius: 7, border: '1px solid #334155', background: '#1e293b', color: '#94a3b8', fontSize: 13
        }}>
          <option value="">All Employees</option>
          {employees.map(e => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
        </select>
      </div>

      {loading ? <p style={{ color: '#64748b' }}>Loading...</p> : (
        <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: '#0f172a' }}>
              {['Employee', 'Period', 'Gross', 'PAYG', 'Net Pay', 'Super', 'Pay Date', ''].map(h => (
                <th key={h} style={{ color: '#64748b', fontSize: 12, padding: '12px 14px', textAlign: 'left', fontWeight: 500 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {filtered.map(ps => (
                <tr key={ps.id} style={{ borderTop: '1px solid #0f172a', cursor: 'pointer' }} onClick={() => setSelected(ps)}>
                  <td style={{ padding: '12px 14px', color: '#e2e8f0', fontSize: 13 }}>{ps.full_name}</td>
                  <td style={{ padding: '12px 14px', color: '#64748b', fontSize: 12 }}>{ps.period_start}<br />{ps.period_end}</td>
                  <td style={{ padding: '12px 14px', color: '#f59e0b', fontSize: 13 }}>{fmt(ps.gross_earnings)}</td>
                  <td style={{ padding: '12px 14px', color: '#f87171', fontSize: 13 }}>{fmt(ps.payg_tax)}</td>
                  <td style={{ padding: '12px 14px', color: '#34d399', fontWeight: 700, fontSize: 13 }}>{fmt(ps.net_pay)}</td>
                  <td style={{ padding: '12px 14px', color: '#a78bfa', fontSize: 13 }}>{fmt(ps.super_guarantee)}</td>
                  <td style={{ padding: '12px 14px', color: '#64748b', fontSize: 12 }}>{ps.pay_date}</td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ color: '#60a5fa', fontSize: 12 }}>View →</span>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={8} style={{ padding: 32, textAlign: 'center', color: '#475569' }}>No payslips found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Payslip Detail Modal */}
      {selected && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{ background: '#1e293b', borderRadius: 16, padding: 32, width: 480, border: '1px solid #334155' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <h3 style={{ color: '#f1f5f9', margin: 0 }}>Payslip</h3>
                <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: 13 }}>{selected.period_start} → {selected.period_end}</p>
              </div>
              <button onClick={() => setSelected(null)} style={{
                background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                borderRadius: 6, padding: '4px 12px', cursor: 'pointer'
              }}>✕</button>
            </div>

            <div style={{ background: '#0f172a', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <h4 style={{ color: '#e2e8f0', margin: '0 0 4px', fontSize: 16 }}>{selected.full_name}</h4>
              <p style={{ color: '#64748b', margin: 0, fontSize: 12 }}>
                {selected.employee_number} | Pay Date: {selected.pay_date}
              </p>
            </div>

            <h5 style={{ color: '#64748b', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Earnings</h5>
            <Row label="Ordinary Pay" value={fmt(selected.ordinary_pay)} />
            {selected.overtime_pay_1_5x > 0 && <Row label="Overtime (1.5x)" value={fmt(selected.overtime_pay_1_5x)} />}
            {selected.overtime_pay_2x > 0 && <Row label="Overtime (2x)" value={fmt(selected.overtime_pay_2x)} />}
            {selected.annual_leave_pay > 0 && <Row label="Annual Leave" value={fmt(selected.annual_leave_pay)} />}
            {selected.sick_leave_pay > 0 && <Row label="Sick Leave" value={fmt(selected.sick_leave_pay)} />}
            <Row label="Gross Earnings" value={fmt(selected.gross_earnings)} highlight="#f59e0b" />

            <h5 style={{ color: '#64748b', margin: '12px 0 8px', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Deductions</h5>
            <Row label="PAYG Tax Withheld" value={`−${fmt(selected.payg_tax)}`} highlight="#f87171" />

            <div style={{ marginTop: 12, padding: '12px 0', borderTop: '2px solid #334155' }}>
              <Row label="Net Pay" value={fmt(selected.net_pay)} highlight="#34d399" />
            </div>

            <h5 style={{ color: '#64748b', margin: '12px 0 8px', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Superannuation</h5>
            <Row label="Employer Super (11%)" value={fmt(selected.super_guarantee)} />
            <Row label="Fund" value={selected.super_fund_name || '—'} />

            <h5 style={{ color: '#64748b', margin: '12px 0 8px', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>Year to Date</h5>
            <Row label="YTD Gross" value={fmt(selected.ytd_gross)} />
            <Row label="YTD Tax" value={fmt(selected.ytd_tax)} />
            <Row label="YTD Super" value={fmt(selected.ytd_super)} />
          </div>
        </div>
      )}
    </div>
  );
}
