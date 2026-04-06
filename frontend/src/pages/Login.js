import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('admin@payroll.com.au');
  const [password, setPassword] = useState('Admin1234!');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const handleLogin = async e => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      await login(email, password);
      nav('/');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const seedAdmin = async () => {
    setSeeding(true);
    try {
      const r = await fetch(`${API_URL}/auth/seed-admin`, { method: 'POST' });
      const d = await r.json();
      alert(d.message + (d.password ? `\nPassword: ${d.password}` : ''));
    } catch { alert('Seed failed - is the server running?'); }
    setSeeding(false);
  };

  return (
    <div style={{
      minHeight: '100vh', background: '#0f172a', display: 'flex',
      alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{
        background: '#1e293b', borderRadius: 16, padding: 48, width: 400,
        border: '1px solid #334155'
      }}>
        <h1 style={{ color: '#f1f5f9', fontSize: 28, marginBottom: 8, textAlign: 'center' }}>
          🦘 AU Payroll
        </h1>
        <p style={{ color: '#64748b', textAlign: 'center', marginBottom: 32, fontSize: 14 }}>
          Australian Payroll Platform
        </p>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ color: '#94a3b8', fontSize: 13, display: 'block', marginBottom: 6 }}>Email</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8,
                border: '1px solid #334155', background: '#0f172a', color: '#f1f5f9',
                fontSize: 14, boxSizing: 'border-box'
              }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label style={{ color: '#94a3b8', fontSize: 13, display: 'block', marginBottom: 6 }}>Password</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8,
                border: '1px solid #334155', background: '#0f172a', color: '#f1f5f9',
                fontSize: 14, boxSizing: 'border-box'
              }}
            />
          </div>
          {error && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 16 }}>{error}</p>}
          <button type="submit" disabled={loading} style={{
            width: '100%', padding: '12px', borderRadius: 8, border: 'none',
            background: loading ? '#334155' : '#3b82f6', color: '#fff',
            fontSize: 15, fontWeight: 600, cursor: loading ? 'default' : 'pointer'
          }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: 24, borderTop: '1px solid #334155', paddingTop: 20, textAlign: 'center' }}>
          <p style={{ color: '#64748b', fontSize: 12, marginBottom: 12 }}>First time? Seed the admin account:</p>
          <button onClick={seedAdmin} disabled={seeding} style={{
            background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
            borderRadius: 8, padding: '8px 20px', cursor: 'pointer', fontSize: 13
          }}>
            {seeding ? 'Seeding...' : 'Seed Admin Account'}
          </button>
        </div>
      </div>
    </div>
  );
}
