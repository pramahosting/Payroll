import React, { createContext, useContext, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';

// ── API Config ──────────────────────────────────────────────────────────────
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// ── Auth Context ─────────────────────────────────────────────────────────────
export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function api(path, options = {}) {
  const token = localStorage.getItem('token');
  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  }).then(r => {
    if (r.status === 401) { localStorage.clear(); window.location.href = '/login'; }
    return r;
  });
}

function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
  });

  const login = async (email, password) => {
    const r = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) throw new Error('Invalid credentials');
    const data = await r.json();
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify({ email, role: data.role, user_id: data.user_id }));
    setUser({ email, role: data.role, user_id: data.user_id });
    return data;
  };

  const logout = () => {
    localStorage.clear();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

// ── Nav ───────────────────────────────────────────────────────────────────────
function Nav() {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const links = [
    { to: '/', label: '📊 Dashboard' },
    { to: '/employees', label: '👥 Employees' },
    { to: '/timesheets', label: '⏱ Timesheets' },
    { to: '/payroll', label: '💰 Run Payroll' },
    { to: '/payslips', label: '📄 Payslips' },
    { to: '/compliance', label: '🏛 Compliance' },
    { to: '/reports', label: '📈 Reports' },
  ];

  return (
    <nav style={{ background: '#1a1a2e', padding: '0 32px', display: 'flex', alignItems: 'center', gap: 0, height: 70 }}>
      <span style={{ color: '#fff', fontWeight: 800, fontSize: 24, marginRight: 40, whiteSpace: 'nowrap' }}>
        🦘 AU Payroll
      </span>
      <div style={{ display: 'flex', gap: 6, flex: 1 }}>
        {links.map(l => (
          <Link key={l.to} to={l.to} style={{
            color: loc.pathname === l.to ? '#60a5fa' : '#94a3b8',
            textDecoration: 'none',
            fontSize: 16,
            fontWeight: loc.pathname === l.to ? 600 : 400,
            padding: '8px 14px',
            borderRadius: 8,
            background: loc.pathname === l.to ? 'rgba(96,165,250,0.1)' : 'transparent',
            whiteSpace: 'nowrap',
          }}>{l.label}</Link>
        ))}
      </div>
      <span style={{ color: '#64748b', fontSize: 14, marginRight: 16 }}>
        {user?.email} ({user?.role})
      </span>
      <button onClick={logout} style={{
        background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
        borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 14
      }}>Logout</button>
    </nav>
  );
}

// ── Pages ─────────────────────────────────────────────────────────────────────
import Dashboard from './pages/Dashboard';
import Employees from './pages/Employees';
import Timesheets from './pages/Timesheets';
import PayrollRun from './pages/PayrollRun';
import Payslips from './pages/Payslips';
import Compliance from './pages/Compliance';
import Reports from './pages/Reports';
import Login from './pages/Login';

function PrivateRoute({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={
            <PrivateRoute>
              <div style={{ minHeight: '100vh', background: '#0f172a', color: '#e2e8f0', fontSize: '48px' }}>
                <Nav />
                <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/employees" element={<Employees />} />
                    <Route path="/timesheets" element={<Timesheets />} />
                    <Route path="/payroll" element={<PayrollRun />} />
                    <Route path="/payslips" element={<Payslips />} />
                    <Route path="/compliance" element={<Compliance />} />
                    <Route path="/reports" element={<Reports />} />
                  </Routes>
                </div>
              </div>
            </PrivateRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
