// src/api/index.ts
// Typed API client for the Voice AI Agent backend

import type {
  BookingRequest,
  BookingResult,
  Doctor,
  HealthStatus,
  LatencyEntry,
  LatencyReport,
  Patient,
  TraceStep,
} from '../types';

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Request failed');
  }
  return res.json();
}

// ── Health ────────────────────────────────────────────────────────────────
export const getHealth = () => req<HealthStatus>('/health');

// ── Doctors ───────────────────────────────────────────────────────────────
export const getDoctors = (specialty?: string) =>
  req<{ doctors: Doctor[]; count: number }>(
    specialty ? `/doctors?specialty=${encodeURIComponent(specialty)}` : '/doctors',
  );

export const getSlots = (doctorId: string, date: string) =>
  req<{ doctor_id: string; doctor_name: string; date: string; available_slots: string[]; count: number }>(
    `/doctors/${doctorId}/slots/${date}`,
  );

// ── Appointments ──────────────────────────────────────────────────────────
export const bookAppointment = (body: BookingRequest) =>
  req<BookingResult>('/appointments/book', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const cancelAppointment = (body: {
  patient_phone: string;
  doctor_id: string;
  date: string;
  time: string;
}) => req<BookingResult>('/appointments/cancel', { method: 'POST', body: JSON.stringify(body) });

export const rescheduleAppointment = (body: {
  patient_phone: string;
  doctor_id: string;
  old_date: string;
  old_time: string;
  new_date: string;
  new_time: string;
}) => req<BookingResult>('/appointments/reschedule', { method: 'POST', body: JSON.stringify(body) });

// ── Patients ──────────────────────────────────────────────────────────────
export const getPatients = () => req<{ patients: Patient[]; count: number }>('/patients');

export const getPatient = (phone: string) =>
  req<{ patient: Patient; summary: string }>(`/patients/${encodeURIComponent(phone)}`);

// ── Monitoring ────────────────────────────────────────────────────────────
export const getLatencyReport = () => req<LatencyReport | { message: string }>('/latency/report');
export const getLatencyLog = () => req<{ entries: LatencyEntry[]; count: number }>('/latency/log');

export const getRecentTraces = () =>
  req<{ traces: TraceStep[]; count: number; total_in_file: number }>('/traces/recent');

export const getSessionTrace = (sessionId: string) =>
  req<{ session_id: string; step_count: number; steps: TraceStep[] }>(`/traces/${sessionId}`);
