import React, { useState, useEffect } from 'react';
import { api } from '../App';

function StatCard({ label, value, sub, color = '#3b82f6' }) {
  return (
    <div style={{
      background: '#1e293b', borderRadius: 12, padding: '20px 24px',
      border: '1px solid #334155', flex: 1, minWidth: 160
    }}>
      <p style={{ color: '#64748b', fontSize: 13, margin: '0 0 8px' }}>{label}</p>
      <p style={{ color, fontSize: 28, fontWeight: 700, margin: '0 0 4px' }}>{value}</p>
      {sub && <p style={{ color: '#475569', fontSize: 12, margin: 0 }}>{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [runs, setRuns] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [services, setServices] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api('/payroll-runs').then(r => r.json()).catch(() => []),
      api('/employees').then(r => r.json()).catch(() => []),
      api('/services/health').then(r => r.json()).catch(() => ({ services: {} })),
    ]).then(([r, e, s]) => {
      setRuns(Array.isArray(r) ? r : []);
      setEmployees(Array.isArray(e) ? e : []);
      setServices(s.services || {});
      setLoading(false);
    });
  }, []);

  const latestRun = runs[0];
  const fmt = n => n ? `$${Number(n).toLocaleString('en-AU', { minimumFractionDigits: 2 })}` : '$0.00';

  return (
    <div>
      <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>Dashboard</h2>
      <p style={{ color: '#64748b', marginBottom: 28, fontSize: 14 }}>
        Australian Payroll Platform — {new Date().toLocaleDateString('en-AU', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
      </p>

      {loading ? <p style={{ color: '#64748b' }}>Loading...</p> : (
        <>
          <div style={{ display: 'flex', gap: 16, marginBottom: 32, flexWrap: 'wrap' }}>
            <StatCard label="Active Employees" value={employees.length} color="#34d399" />
            <StatCard label="Payroll Runs" value={runs.length} color="#60a5fa" />
            <StatCard label="Latest Gross" value={latestRun ? fmt(latestRun.total_gross) : 'N/A'} color="#f59e0b" sub={latestRun?.period_end} />
            <StatCard label="Latest Net" value={latestRun ? fmt(latestRun.total_net) : 'N/A'} color="#a78bfa" />
            <StatCard label="Latest Super" value={latestRun ? fmt(latestRun.total_super) : 'N/A'} color="#f472b6" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Recent Payroll Runs */}
            <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, border: '1px solid #334155' }}>
              <h3 style={{ color: '#e2e8f0', marginBottom: 16, fontSize: 16 }}>Recent Payroll Runs</h3>
              {runs.slice(0, 5).map(r => (
                <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
                  <div>
                    <p style={{ color: '#e2e8f0', margin: 0, fontSize: 14 }}>{r.run_name}</p>
                    <p style={{ color: '#64748b', margin: 0, fontSize: 12 }}>{r.period_start} → {r.period_end}</p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <p style={{ color: '#34d399', margin: 0, fontSize: 14, fontWeight: 600 }}>{fmt(r.total_net)}</p>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 99,
                      background: r.status === 'completed' ? '#064e3b' : r.status === 'processing' ? '#1e3a5f' : '#4b1d1d',
                      color: r.status === 'completed' ? '#34d399' : r.status === 'processing' ? '#60a5fa' : '#f87171',
                    }}>{r.status}</span>
                  </div>
                </div>
              ))}
              {runs.length === 0 && <p style={{ color: '#475569', fontSize: 13 }}>No payroll runs yet</p>}
            </div>

            {/* Service Health */}
            <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, border: '1px solid #334155' }}>
              <h3 style={{ color: '#e2e8f0', marginBottom: 16, fontSize: 16 }}>Service Health</h3>
              {Object.entries(services).map(([name, status]) => (
                <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #0f172a' }}>
                  <span style={{ color: '#94a3b8', fontSize: 13 }}>{name}</span>
                  <span style={{
                    fontSize: 12, padding: '2px 10px', borderRadius: 99,
                    background: status === 'ok' ? '#064e3b' : '#4b1d1d',
                    color: status === 'ok' ? '#34d399' : '#f87171',
                  }}>{status}</span>
                </div>
              ))}
              {Object.keys(services).length === 0 && (
                <p style={{ color: '#475569', fontSize: 13 }}>
                  Services loading or integration-service unreachable
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
