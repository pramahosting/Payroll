import React, { useState, useEffect } from 'react';
import { api } from '../App';

const EMPTY = {
  employee_number: '', first_name: '', last_name: '', email: '', phone: '',
  employment_type: 'full_time', pay_frequency: 'fortnightly', annual_salary: '',
  hourly_rate: '', tfn: '', super_fund_name: 'AustralianSuper', super_member_number: '',
  bank_bsb: '', bank_account_number: '', bank_account_name: '',
  start_date: '', tax_free_threshold: true, residency_status: 'resident',
  address_line1: '', address_suburb: '', address_state: '', address_postcode: '',
};

function Badge({ status }) {
  const colors = {
    true: { bg: '#064e3b', color: '#34d399' },
    false: { bg: '#4b1d1d', color: '#f87171' },
  };
  const c = colors[String(status)] || { bg: '#1e3a5f', color: '#60a5fa' };
  return (
    <span style={{ ...c, fontSize: 11, padding: '2px 8px', borderRadius: 99, display: 'inline-block' }}>
      {status ? 'Active' : 'Inactive'}
    </span>
  );
}

function Input({ label, value, onChange, type = 'text', options, required }) {
  const style = {
    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #334155',
    background: '#0f172a', color: '#f1f5f9', fontSize: 13, boxSizing: 'border-box',
  };
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ color: '#94a3b8', fontSize: 12, display: 'block', marginBottom: 4 }}>
        {label}{required && ' *'}
      </label>
      {options ? (
        <select value={value} onChange={e => onChange(e.target.value)} style={style}>
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : type === 'checkbox' ? (
        <input type="checkbox" checked={value} onChange={e => onChange(e.target.checked)} />
      ) : (
        <input type={type} value={value} onChange={e => onChange(e.target.value)} style={style} required={required} />
      )}
    </div>
  );
}

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  const load = () => {
    setLoading(true);
    api('/employees?active_only=false').then(r => r.json()).then(d => {
      setEmployees(Array.isArray(d) ? d : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(load, []);

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const openNew = () => { setForm(EMPTY); setEditId(null); setShowForm(true); setError(''); };
  const openEdit = emp => {
    setForm({ ...EMPTY, ...emp });
    setEditId(emp.id);
    setShowForm(true);
    setError('');
  };

  const save = async e => {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const payload = { ...form, annual_salary: parseFloat(form.annual_salary) || 0 };
      if (form.hourly_rate) payload.hourly_rate = parseFloat(form.hourly_rate);
      const r = editId
        ? await api(`/employees/${editId}`, { method: 'PATCH', body: JSON.stringify(payload) })
        : await api('/employees', { method: 'POST', body: JSON.stringify(payload) });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Save failed'); }
      setShowForm(false);
      load();
    } catch (err) { setError(err.message); }
    setSaving(false);
  };

  const deactivate = async id => {
    if (!window.confirm('Deactivate this employee?')) return;
    await api(`/employees/${id}`, { method: 'DELETE' });
    load();
  };

  const filtered = employees.filter(e =>
    `${e.first_name} ${e.last_name} ${e.employee_number} ${e.email}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ color: '#f1f5f9', margin: 0 }}>Employees</h2>
          <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: 13 }}>{employees.length} total employees</p>
        </div>
        <button onClick={openNew} style={{
          background: '#3b82f6', border: 'none', color: '#fff', borderRadius: 8,
          padding: '10px 20px', cursor: 'pointer', fontSize: 14, fontWeight: 600
        }}>+ New Employee</button>
      </div>

      <input
        placeholder="Search by name, number or email..."
        value={search} onChange={e => setSearch(e.target.value)}
        style={{
          width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #334155',
          background: '#1e293b', color: '#f1f5f9', fontSize: 14, marginBottom: 20, boxSizing: 'border-box'
        }}
      />

      {loading ? <p style={{ color: '#64748b' }}>Loading employees...</p> : (
        <div style={{ background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#0f172a' }}>
                {['#', 'Name', 'Email', 'Type', 'Salary', 'Pay Freq', 'Start Date', 'Status', 'Actions'].map(h => (
                  <th key={h} style={{ color: '#64748b', fontSize: 12, padding: '12px 16px', textAlign: 'left', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(emp => (
                <tr key={emp.id} style={{ borderTop: '1px solid #0f172a' }}>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>{emp.employee_number}</td>
                  <td style={{ padding: '12px 16px', color: '#f1f5f9', fontSize: 14 }}>{emp.first_name} {emp.last_name}</td>
                  <td style={{ padding: '12px 16px', color: '#64748b', fontSize: 13 }}>{emp.email}</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>{emp.employment_type.replace('_', ' ')}</td>
                  <td style={{ padding: '12px 16px', color: '#34d399', fontSize: 13 }}>
                    ${Number(emp.annual_salary).toLocaleString('en-AU')}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>{emp.pay_frequency}</td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: 13 }}>{emp.start_date}</td>
                  <td style={{ padding: '12px 16px' }}><Badge status={emp.is_active} /></td>
                  <td style={{ padding: '12px 16px' }}>
                    <button onClick={() => openEdit(emp)} style={{
                      background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                      borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12, marginRight: 6
                    }}>Edit</button>
                    {emp.is_active && (
                      <button onClick={() => deactivate(emp.id)} style={{
                        background: 'transparent', border: '1px solid #7f1d1d', color: '#f87171',
                        borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12
                      }}>Deactivate</button>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={9} style={{ padding: 32, textAlign: 'center', color: '#475569' }}>
                  No employees found
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Employee Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex',
          alignItems: 'flex-start', justifyContent: 'center', zIndex: 1000, overflowY: 'auto', padding: '40px 0'
        }}>
          <div style={{
            background: '#1e293b', borderRadius: 16, padding: 32, width: 700, maxWidth: '95vw',
            border: '1px solid #334155', margin: 'auto'
          }}>
            <h3 style={{ color: '#f1f5f9', marginBottom: 24 }}>{editId ? 'Edit Employee' : 'New Employee'}</h3>
            <form onSubmit={save}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <Input label="Employee Number" value={form.employee_number} onChange={v => setField('employee_number', v)} required />
                <Input label="Start Date" value={form.start_date} onChange={v => setField('start_date', v)} type="date" required />
                <Input label="First Name" value={form.first_name} onChange={v => setField('first_name', v)} required />
                <Input label="Last Name" value={form.last_name} onChange={v => setField('last_name', v)} required />
                <Input label="Email" value={form.email} onChange={v => setField('email', v)} type="email" required />
                <Input label="Phone" value={form.phone} onChange={v => setField('phone', v)} />
                <Input label="Employment Type" value={form.employment_type} onChange={v => setField('employment_type', v)} options={[
                  { value: 'full_time', label: 'Full Time' },
                  { value: 'part_time', label: 'Part Time' },
                  { value: 'casual', label: 'Casual' },
                  { value: 'contract', label: 'Contract' },
                ]} />
                <Input label="Pay Frequency" value={form.pay_frequency} onChange={v => setField('pay_frequency', v)} options={[
                  { value: 'weekly', label: 'Weekly' },
                  { value: 'fortnightly', label: 'Fortnightly' },
                  { value: 'monthly', label: 'Monthly' },
                ]} />
                <Input label="Annual Salary ($)" value={form.annual_salary} onChange={v => setField('annual_salary', v)} type="number" required />
                <Input label="Hourly Rate (optional)" value={form.hourly_rate} onChange={v => setField('hourly_rate', v)} type="number" />
                <Input label="TFN" value={form.tfn} onChange={v => setField('tfn', v)} />
                <Input label="Residency Status" value={form.residency_status} onChange={v => setField('residency_status', v)} options={[
                  { value: 'resident', label: 'Australian Resident' },
                  { value: 'non_resident', label: 'Non-Resident' },
                  { value: 'working_holiday', label: 'Working Holiday' },
                ]} />
              </div>

              <h4 style={{ color: '#94a3b8', marginTop: 8, marginBottom: 12, fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 }}>Superannuation</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <Input label="Super Fund Name" value={form.super_fund_name} onChange={v => setField('super_fund_name', v)} />
                <Input label="Member Number" value={form.super_member_number} onChange={v => setField('super_member_number', v)} />
              </div>

              <h4 style={{ color: '#94a3b8', marginTop: 8, marginBottom: 12, fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 }}>Bank Details</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '0 16px' }}>
                <Input label="BSB" value={form.bank_bsb} onChange={v => setField('bank_bsb', v)} />
                <Input label="Account Number" value={form.bank_account_number} onChange={v => setField('bank_account_number', v)} />
                <Input label="Account Name" value={form.bank_account_name} onChange={v => setField('bank_account_name', v)} />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <input type="checkbox" checked={form.tax_free_threshold}
                  onChange={e => setField('tax_free_threshold', e.target.checked)} id="tft" />
                <label htmlFor="tft" style={{ color: '#94a3b8', fontSize: 13 }}>Claims Tax-Free Threshold</label>
              </div>

              {error && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 12 }}>{error}</p>}

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  background: 'transparent', border: '1px solid #334155', color: '#94a3b8',
                  borderRadius: 8, padding: '10px 20px', cursor: 'pointer'
                }}>Cancel</button>
                <button type="submit" disabled={saving} style={{
                  background: '#3b82f6', border: 'none', color: '#fff',
                  borderRadius: 8, padding: '10px 24px', cursor: 'pointer', fontWeight: 600
                }}>{saving ? 'Saving...' : (editId ? 'Update Employee' : 'Create Employee')}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
