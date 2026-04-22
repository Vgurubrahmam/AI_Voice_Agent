// Appointments tab — book, view doctors & slots
import { useEffect, useState } from 'react';
import { CalendarDays, ChevronRight, Search, Stethoscope, X } from 'lucide-react';
import { getDoctors, getSlots, bookAppointment } from '../api';
import type { Doctor, BookingRequest } from '../types';

interface Props {
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const SPECIALTIES = ['Any', 'Cardiology', 'Neurology', 'Orthopedics', 'Dermatology', 'Pediatrics', 'General Practice'];

function todayStr() {
  return new Date().toISOString().split('T')[0];
}

export default function AppointmentsTab({ onToast }: Props) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [specialty, setSpecialty] = useState('Any');
  const [search, setSearch] = useState('');

  // Booking modal
  const [selected, setSelected] = useState<Doctor | null>(null);
  const [bookDate, setBookDate] = useState(todayStr());
  const [slots, setSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState('');
  const [patientPhone, setPatientPhone] = useState('');
  const [patientName, setPatientName] = useState('');
  const [booking, setBooking] = useState(false);

  async function loadDoctors() {
    setLoading(true);
    try {
      const { doctors: d } = await getDoctors(specialty === 'Any' ? undefined : specialty);
      setDoctors(d);
    } catch {
      onToast('Failed to load doctors', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadDoctors(); }, [specialty]);

  async function loadSlots() {
    if (!selected || !bookDate) return;
    setSlotsLoading(true);
    setSelectedSlot('');
    try {
      const res = await getSlots(selected.id, bookDate);
      setSlots(res.available_slots);
    } catch {
      setSlots([]);
      onToast('Could not load slots', 'error');
    } finally {
      setSlotsLoading(false);
    }
  }

  useEffect(() => { if (selected) loadSlots(); }, [selected, bookDate]);

  async function handleBook() {
    if (!selected || !selectedSlot || !patientPhone || !patientName) {
      onToast('Please fill all fields', 'error');
      return;
    }
    setBooking(true);
    try {
      const req: BookingRequest = {
        patient_phone: patientPhone,
        doctor_id: selected.id,
        date: bookDate,
        time: selectedSlot,
        patient_name: patientName,
      };
      const res = await bookAppointment(req);
      if (res.success) {
        onToast('Appointment booked successfully! 🎉', 'success');
        setSelected(null);
        setSelectedSlot('');
        setPatientPhone('');
        setPatientName('');
      } else {
        onToast(res.reason ?? 'Slot unavailable', 'error');
      }
    } catch (e: unknown) {
      onToast((e as Error).message || 'Booking failed', 'error');
    } finally {
      setBooking(false);
    }
  }

  const filtered = doctors.filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.specialty.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Appointments</div>
          <div className="page-subtitle">Browse doctors and book clinical appointments</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: '1', minWidth: '200px' }}>
            <Search size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform:'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              id="doctor-search"
              className="input"
              placeholder="Search doctors…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: '2.25rem' }}
            />
          </div>
          <select
            id="specialty-filter"
            className="select"
            value={specialty}
            onChange={e => setSpecialty(e.target.value)}
            style={{ width: 'auto', minWidth: '160px' }}
          >
            {SPECIALTIES.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Doctor grid */}
      {loading ? (
        <div className="flex-center" style={{ padding: '3rem' }}><div className="spinner" /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <Stethoscope size={40} />
          <p>No doctors found</p>
        </div>
      ) : (
        <div className="grid-auto">
          {filtered.map(doc => (
            <div key={doc.id} className="doctor-card">
              <div style={{ display: 'flex', gap: '0.875rem', alignItems: 'flex-start', marginBottom: '0.875rem' }}>
                <div className="doctor-avatar">🩺</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {doc.name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{doc.specialty}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                {doc.language_support.map(lang => (
                  <span key={lang} className="badge badge-accent">{lang.toUpperCase()}</span>
                ))}
              </div>
              <button
                id={`book-${doc.id}`}
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={() => { setSelected(doc); setBookDate(todayStr()); }}
              >
                Book Appointment <ChevronRight size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Booking Modal */}
      {selected && (
        <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setSelected(null); }}>
          <div className="modal">
            <div className="modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CalendarDays size={18} color="var(--accent)" />
                Book with {selected.name}
              </h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelected(null)}>
                <X size={15} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label" htmlFor="book-name">Patient Name</label>
                <input id="book-name" className="input" placeholder="Full name" value={patientName} onChange={e => setPatientName(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="book-phone">Phone Number</label>
                <input id="book-phone" className="input" placeholder="+91XXXXXXXXXX" value={patientPhone} onChange={e => setPatientPhone(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="book-date">Date</label>
                <input id="book-date" className="input" type="date" value={bookDate} min={todayStr()} onChange={e => setBookDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Available Slots</label>
                {slotsLoading ? (
                  <div className="flex-center" style={{ padding: '1rem' }}><div className="spinner" /></div>
                ) : slots.length === 0 ? (
                  <p style={{ fontSize: '0.875rem', color: 'var(--rose)' }}>No available slots for this date.</p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {slots.map(slot => (
                      <button
                        key={slot}
                        id={`slot-${slot}`}
                        className={`btn btn-sm ${selectedSlot === slot ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => setSelectedSlot(slot)}
                      >
                        {slot}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setSelected(null)}>Cancel</button>
              <button
                id="confirm-booking"
                className="btn btn-primary"
                disabled={!selectedSlot || !patientPhone || !patientName || booking}
                onClick={handleBook}
              >
                {booking ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Booking…</> : 'Confirm Booking'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
