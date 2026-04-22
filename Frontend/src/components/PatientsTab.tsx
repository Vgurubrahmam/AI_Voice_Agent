// Patients tab — list and view patient details
import React, { useEffect, useState } from 'react';
import { Users, Search, Phone, Clock, X, ChevronDown, ChevronRight } from 'lucide-react';
import { getPatients, getPatient } from '../api';
import type { Patient, Booking } from '../types';

interface Props {
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

function BookingRow({ b }: { b: Booking }) {
  const statusColor =
    b.status === 'confirmed'   ? 'var(--emerald)' :
    b.status === 'cancelled'   ? 'var(--rose)'    : 'var(--amber)';
  return (
    <div style={{
      background: 'var(--bg-glass)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '0.625rem 0.875rem',
      display: 'flex',
      gap: '1rem',
      alignItems: 'center',
      flexWrap: 'wrap',
      fontSize: '0.8125rem',
    }}>
      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{b.doctor_name}</span>
      <span style={{ color: 'var(--text-muted)' }}>{b.specialty}</span>
      <span style={{ color: 'var(--text-secondary)' }}>{b.date} @ {b.time}</span>
      <span style={{ marginLeft: 'auto', color: statusColor, fontWeight: 600, textTransform: 'capitalize' }}>
        {b.status}
      </span>
    </div>
  );
}

export default function PatientsTab({ onToast }: Props) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [detail, setDetail] = useState<{ patient: Patient; summary: string } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { patients: p } = await getPatients();
      setPatients(p);
    } catch {
      onToast('Failed to load patients', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function openDetail(phone: string) {
    setDetailLoading(true);
    try {
      const res = await getPatient(phone);
      setDetail(res);
    } catch {
      onToast('Could not load patient details', 'error');
    } finally {
      setDetailLoading(false);
    }
  }

  const filtered = patients.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.phone.includes(search)
  );

  const langLabel: Record<string,string> = { en: 'English', hi: 'हिन्दी', ta: 'தமிழ்' };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Patients</div>
          <div className="page-subtitle">{patients.length} registered patients</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : 'Refresh'}
        </button>
      </div>

      {/* Search */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform:'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            id="patient-search"
            className="input"
            placeholder="Search by name or phone…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: '2.25rem' }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {loading ? (
          <div className="flex-center" style={{ padding: '3rem' }}><div className="spinner" /></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <Users size={40} />
            <p>No patients found</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th><Phone size={12} style={{ marginRight: 4 }} />Phone</th>
                  <th>Language</th>
                  <th><Clock size={12} style={{ marginRight: 4 }} />Last Interaction</th>
                  <th>Bookings</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(p => (
                  <React.Fragment key={p.id}>
                    <tr style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{p.name}</td>
                      <td><code className="mono">{p.phone}</code></td>
                      <td>
                        <span className="badge badge-accent">{langLabel[p.preferred_language] ?? p.preferred_language}</span>
                      </td>
                      <td>{p.last_interaction ? new Date(p.last_interaction).toLocaleString() : '—'}</td>
                      <td>
                        <span className="badge badge-muted">{p.total_bookings}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                          {expanded === p.id ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                          <button
                            id={`view-patient-${p.id}`}
                            className="btn btn-ghost btn-sm"
                            onClick={e => { e.stopPropagation(); openDetail(p.phone); }}
                          >
                            Details
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded === p.id && p.booking_history.length > 0 && (
                      <tr>
                        <td colSpan={6} style={{ padding: '0 1rem 1rem' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                            {p.booking_history.slice(-3).reverse().map((b) => (
                              <BookingRow key={`${b.date}-${b.time}-${b.doctor_id}`} b={b} />
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {(detailLoading || detail) && (
        <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setDetail(null); }}>
          <div className="modal" style={{ maxWidth: 560 }}>
            {detailLoading ? (
              <div className="flex-center" style={{ padding: '3rem' }}><div className="spinner" /></div>
            ) : detail ? (
              <>
                <div className="modal-header">
                  <h3>{detail.patient.name}</h3>
                  <button className="btn btn-ghost btn-sm" onClick={() => setDetail(null)}>
                    <X size={15} />
                  </button>
                </div>

                {/* AI Summary */}
                {detail.summary && (
                  <div style={{
                    background: 'var(--accent-dim)',
                    border: '1px solid rgba(56,189,248,0.2)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.875rem',
                    fontSize: '0.875rem',
                    color: 'var(--text-secondary)',
                    marginBottom: '1rem',
                    lineHeight: 1.6,
                  }}>
                    {detail.summary}
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1rem' }}>
                  {[
                    ['Phone', detail.patient.phone],
                    ['Language', langLabel[detail.patient.preferred_language] ?? detail.patient.preferred_language],
                    ['Total Bookings', String(detail.patient.total_bookings)],
                    ['Notes', detail.patient.notes || '—'],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', gap: '1rem', fontSize: '0.875rem' }}>
                      <span style={{ color: 'var(--text-muted)', minWidth: '110px' }}>{k}</span>
                      <span style={{ color: 'var(--text-primary)' }}>{v}</span>
                    </div>
                  ))}
                </div>

                {detail.patient.booking_history.length > 0 && (
                  <>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Booking History
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '250px', overflowY: 'auto' }}>
                      {[...detail.patient.booking_history].reverse().map((b) => (
                        <BookingRow key={`${b.date}-${b.time}-${b.doctor_id}`} b={b} />
                      ))}
                    </div>
                  </>
                )}

                <div className="modal-footer">
                  <button className="btn btn-ghost" onClick={() => setDetail(null)}>Close</button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
