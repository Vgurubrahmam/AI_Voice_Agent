// src/types/index.ts
// Central type definitions for the Voice AI Agent frontend

export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  language_support: string[];
  slots: Record<string, string[]>;
}

export interface BookingRequest {
  patient_phone: string;
  doctor_id: string;
  date: string;
  time: string;
  patient_name: string;
}

export interface BookingResult {
  success: boolean;
  booking?: Booking;
  reason?: string;
  alternatives?: AlternativeSlot[];
}

export interface Booking {
  doctor_id: string;
  doctor_name: string;
  specialty: string;
  date: string;
  time: string;
  patient_phone: string;
  patient_name: string;
  status: string;
}

export interface AlternativeSlot {
  date: string;
  time: string;
  doctor_id: string;
}

export interface Patient {
  id: string;
  phone: string;
  name: string;
  preferred_language: string;
  last_interaction: string | null;
  booking_history: Booking[];
  total_bookings: number;
  notes: string;
}

export interface HealthStatus {
  status: string;
  redis: string;
  db: string;
  env: string;
  nvidia_nim: string;
  deepgram: string;
  active_sessions: number;
  today: string;
}

export interface LatencyEntry {
  timestamp: string;
  session_id: string;
  stt_ms: number;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
  under_450ms: boolean;
}

export interface LatencyReport {
  total_entries: number;
  mean_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
  under_450_pct: number;
  avg_stt_ms: number;
  avg_llm_ms: number;
  avg_tts_ms: number;
}

export interface TraceStep {
  timestamp: string;
  session_id: string;
  trace_id: string;
  step_type: 'memory_retrieval' | 'tool_decision' | 'tool_execution' | 'conflict_resolution' | 'language_detection' | 'response_generation';
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  latency_ms: number;
  reasoning: string;
}

export interface WsMessage {
  type: 'session_start' | 'response' | 'turn_complete' | 'error' | 'pong';
  session_id?: string;
  text?: string;
  user_text?: string;   // STT transcript of what the user said (voice turns)
  has_audio?: boolean;  // whether audio bytes were sent before this JSON
  language?: string;
  message?: string;
}

export type Language = 'en' | 'hi' | 'ta';

export interface TranscriptEntry {
  role: 'user' | 'assistant' | 'system';
  content: string;
  language?: string;
  timestamp: string;
}
