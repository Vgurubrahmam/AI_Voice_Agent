// Dashboard overview tab
import { useEffect, useState } from 'react';
import { Activity, Users, Calendar, Clock, Wifi, WifiOff, Cpu, Database } from 'lucide-react';
import { getHealth, getPatients, getLatencyReport, getDoctors } from '../api';
import type { HealthStatus, LatencyReport } from '../types';

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon: React.ReactNode;
}

function StatCard({ label, value, sub, color = 'var(--accent)', icon }: StatCardProps) {
  return (
    <div className="stat-card" style={{ '--stat-color': color } as React.CSSProperties}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="stat-label">{label}</span>
        <span style={{ color, opacity: 0.6 }}>{icon}</span>
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function HealthIndicator({ label, value }: { label: string; value: string }) {
  const isOk = value === 'ok' || value === 'connected' || value === 'configured';
  const isWarn = value === 'fallback';
  return (
    <div className="health-item">
      <div className="health-item-label">{label}</div>
      <div
        className="health-item-value"
        style={{ color: isOk ? 'var(--emerald)' : isWarn ? 'var(--amber)' : 'var(--rose)' }}
      >
        {value}
      </div>
    </div>
  );
}

export default function DashboardTab() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [latency, setLatency] = useState<LatencyReport | null>(null);
  const [patientCount, setPatientCount] = useState<number>(0);
  const [doctorCount, setDoctorCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [h, p, lr, d] = await Promise.allSettled([
        getHealth(),
        getPatients(),
        getLatencyReport(),
        getDoctors(),
      ]);
      if (h.status === 'fulfilled') setHealth(h.value);
      else setError('Backend unreachable');
      if (p.status === 'fulfilled') setPatientCount(p.value.count);
      if (lr.status === 'fulfilled' && 'mean_ms' in lr.value) setLatency(lr.value as LatencyReport);
      if (d.status === 'fulfilled') setDoctorCount(d.value.count);
    } catch {
      setError('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); const i = setInterval(load, 30_000); return () => clearInterval(i); }, []);

  const isOnline = !!health && !error;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Overview</div>
          <div className="page-subtitle">Real-time system health &amp; metrics</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {loading && <div className="spinner" />}
          <div className={`conn-badge ${isOnline ? 'connected' : 'disconnected'}`}>
            {isOnline ? <Wifi size={13} /> : <WifiOff size={13} />}
            {isOnline ? 'Backend Online' : error ?? 'Connecting…'}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'rgba(248,113,113,0.3)', background: 'rgba(248,113,113,0.05)', marginBottom: '1rem' }}>
          <p style={{ color: 'var(--rose)', fontSize: '0.875rem' }}>
            ⚠️ {error} — make sure the FastAPI backend is running on port 8000.
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        <StatCard
          label="Active Sessions"
          value={health?.active_sessions ?? '—'}
          sub="WebSocket connections"
          color="var(--accent)"
          icon={<Activity size={16} />}
        />
        <StatCard
          label="Total Patients"
          value={patientCount || '—'}
          sub="Registered in DB"
          color="var(--emerald)"
          icon={<Users size={16} />}
        />
        <StatCard
          label="Doctors Available"
          value={doctorCount || '—'}
          sub="Across all specialties"
          color="var(--violet)"
          icon={<Calendar size={16} />}
        />
        <StatCard
          label="Avg Latency"
          value={latency ? `${Math.round(latency.mean_ms)}ms` : '—'}
          sub={latency ? `P95: ${Math.round(latency.p95_ms)}ms` : 'No data yet'}
          color={latency && latency.mean_ms < 450 ? 'var(--emerald)' : 'var(--amber)'}
          icon={<Clock size={16} />}
        />
      </div>

      <div className="grid-2" style={{ gap: '1rem' }}>
        {/* System Health */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="card-title-icon" style={{ background: 'var(--accent-dim)' }}>
                <Cpu size={14} color="var(--accent)" />
              </div>
              System Services
            </div>
            <div>
              <div
                className="status-dot"
                style={{ display: 'inline-block' }}
                data-status={health?.status}
              />
            </div>
          </div>
          {health ? (
            <div className="health-grid">
              <HealthIndicator label="API Status" value={health.status} />
              <HealthIndicator label="Redis" value={health.redis} />
              <HealthIndicator label="Database" value={health.db} />
              <HealthIndicator label="Environment" value={health.env} />
              <HealthIndicator label="NVIDIA NIM" value={health.nvidia_nim} />
              <HealthIndicator label="Deepgram" value={health.deepgram} />
            </div>
          ) : (
            <div className="empty-state" style={{ padding: '1.5rem' }}>
              {loading ? <div className="spinner" /> : <p>No data</p>}
            </div>
          )}
        </div>

        {/* Latency Summary */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="card-title-icon" style={{ background: 'var(--violet-dim)' }}>
                <Database size={14} color="var(--violet)" />
              </div>
              Latency Summary
            </div>
            {latency && (
              <span className={`badge ${latency.under_450_pct >= 90 ? 'badge-emerald' : 'badge-amber'}`}>
                {latency.under_450_pct.toFixed(1)}% under 450ms
              </span>
            )}
          </div>
          {latency ? (
            <div className="latency-stats-row">
              {[
                { label: 'P50', val: latency.p50_ms },
                { label: 'P95', val: latency.p95_ms },
                { label: 'P99', val: latency.p99_ms },
                { label: 'STT avg', val: latency.avg_stt_ms },
                { label: 'LLM avg', val: latency.avg_llm_ms },
                { label: 'TTS avg', val: latency.avg_tts_ms },
              ].map(({ label, val }) => (
                <div key={label} className="latency-stat">
                  <div className="ls-val">{Math.round(val)}</div>
                  <div className="ls-lbl">{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state" style={{ padding: '1.5rem' }}>
              {loading ? <div className="spinner" /> : (
                <p style={{ fontSize: '0.85rem' }}>No latency data. Start a voice session first.</p>
              )}
            </div>
          )}
          {health && (
            <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Today: <strong style={{ color: 'var(--text-secondary)' }}>{health.today}</strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
