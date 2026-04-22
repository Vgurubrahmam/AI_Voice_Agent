// Monitoring tab — latency charts + reasoning traces
import { useEffect, useState } from 'react';
import { Activity, Brain, RefreshCw, TrendingUp, Clock } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine, Legend,
} from 'recharts';
import { getLatencyLog, getLatencyReport, getRecentTraces } from '../api';
import type { LatencyEntry, LatencyReport, TraceStep } from '../types';
import { format } from 'date-fns';

interface Props {
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const STEP_COLORS: Record<string, string> = {
  memory_retrieval:    'var(--accent)',
  tool_decision:       'var(--violet)',
  tool_execution:      'var(--emerald)',
  conflict_resolution: 'var(--amber)',
  language_detection:  'var(--rose)',
  response_generation: 'var(--text-secondary)',
};

const STEP_LABELS: Record<string, string> = {
  memory_retrieval:    'Memory Retrieval',
  tool_decision:       'Tool Decision',
  tool_execution:      'Tool Execution',
  conflict_resolution: 'Conflict Resolution',
  language_detection:  'Language Detection',
  response_generation: 'Response Generation',
};

const TooltipStyle = {
  backgroundColor: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  color: 'var(--text-primary)',
  fontSize: '0.8rem',
};

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { color: string; name: string; value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ ...TooltipStyle, padding: '0.625rem 0.875rem' }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontSize: '0.75rem' }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color }}>{p.name}: <strong>{Math.round(p.value)}ms</strong></div>
      ))}
    </div>
  );
}

export default function MonitoringTab({ onToast }: Props) {
  const [report, setReport] = useState<LatencyReport | null>(null);
  const [entries, setEntries] = useState<LatencyEntry[]>([]);
  const [traces, setTraces] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTrace, setActiveTrace] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [r, e, t] = await Promise.allSettled([
        getLatencyReport(),
        getLatencyLog(),
        getRecentTraces(),
      ]);
      if (r.status === 'fulfilled' && 'mean_ms' in r.value) setReport(r.value as LatencyReport);
      if (e.status === 'fulfilled') setEntries(e.value.entries.slice(-40));
      if (t.status === 'fulfilled') setTraces(t.value.traces);
    } catch {
      onToast('Failed to load monitoring data', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); const i = setInterval(load, 15_000); return () => clearInterval(i); }, []);

  // Prepare chart data
  const chartData = entries.map((e, idx) => ({
    name: `#${entries.length - 40 + idx + 1}`,
    STT: Math.round(e.stt_ms),
    LLM: Math.round(e.llm_ms),
    TTS: Math.round(e.tts_ms),
    Total: Math.round(e.total_ms),
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Monitoring</div>
          <div className="page-subtitle">Real-time latency metrics &amp; reasoning traces</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Summary stats */}
      {report ? (
        <div className="latency-stats-row" style={{ marginBottom: '1rem', gridTemplateColumns: 'repeat(auto-fill,minmax(120px,1fr))' }}>
          {[
            { label: 'Mean', val: report.mean_ms, color: 'var(--accent)' },
            { label: 'P50', val: report.p50_ms, color: 'var(--accent)' },
            { label: 'P95', val: report.p95_ms, color: report.p95_ms < 800 ? 'var(--emerald)' : 'var(--amber)' },
            { label: 'P99', val: report.p99_ms, color: report.p99_ms < 1000 ? 'var(--amber)' : 'var(--rose)' },
            { label: 'Avg STT', val: report.avg_stt_ms, color: 'var(--violet)' },
            { label: 'Avg LLM', val: report.avg_llm_ms, color: 'var(--violet)' },
            { label: 'Avg TTS', val: report.avg_tts_ms, color: 'var(--violet)' },
            { label: '< 450ms', val: parseFloat(report.under_450_pct.toFixed(1)), color: report.under_450_pct >= 90 ? 'var(--emerald)' : 'var(--amber)', suffix: '%' },
          ].map(({ label, val, color, suffix = '' }) => (
            <div key={label} className="latency-stat">
              <div className="ls-val" style={{ color }}>{Math.round(val as number)}{suffix}</div>
              <div className="ls-lbl">{label}</div>
            </div>
          ))}
        </div>
      ) : (
        !loading && (
          <div className="card" style={{ marginBottom: '1rem' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              No latency data yet. Connect via Voice Test and send a message.
            </p>
          </div>
        )
      )}

      {/* Charts */}
      <div className="grid-2" style={{ marginBottom: '1rem' }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="card-title-icon" style={{ background: 'var(--accent-dim)' }}>
                <TrendingUp size={14} color="var(--accent)" />
              </div>
              Component Latency (last 40 turns)
            </div>
          </div>
          {entries.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              {loading ? <div className="spinner" /> : <p>No data</p>}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barSize={6} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} />
                <Bar dataKey="STT" stackId="a" fill="#38bdf8" radius={[0,0,0,0]} />
                <Bar dataKey="LLM" stackId="a" fill="#a78bfa" radius={[0,0,0,0]} />
                <Bar dataKey="TTS" stackId="a" fill="#34d399" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <div className="card-title-icon" style={{ background: 'var(--emerald-dim)' }}>
                <Activity size={14} color="var(--emerald)" />
              </div>
              Total Latency per Turn
            </div>
            <span className="badge badge-accent">450ms target</span>
          </div>
          {entries.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              {loading ? <div className="spinner" /> : <p>No data</p>}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barSize={8} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={450} stroke="var(--rose)" strokeDasharray="4 2" label={{ value: '450ms', fill: 'var(--rose)', fontSize: 10, position: 'right' }} />
                <Bar
                  dataKey="Total"
                  fill="var(--accent)"
                  radius={[4,4,0,0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Reasoning Traces */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <div className="card-title-icon" style={{ background: 'var(--violet-dim)' }}>
              <Brain size={14} color="var(--violet)" />
            </div>
            Recent Reasoning Traces
          </div>
          <span className="badge badge-muted">{traces.length} entries</span>
        </div>

        {loading && traces.length === 0 ? (
          <div className="flex-center" style={{ padding: '2rem' }}><div className="spinner" /></div>
        ) : traces.length === 0 ? (
          <div className="empty-state">
            <Brain size={36} />
            <p>No traces yet. Start a voice session.</p>
          </div>
        ) : (
          <div className="section-gap" style={{ maxHeight: '520px', overflowY: 'auto' }}>
            {traces.map((t, i) => (
              <div
                key={i}
                className="trace-entry"
                style={{ cursor: 'pointer' }}
                onClick={() => setActiveTrace(activeTrace === `${i}` ? null : `${i}`)}
              >
                <div className="trace-meta">
                  <span
                    className="trace-type"
                    style={{ color: STEP_COLORS[t.step_type] ?? 'var(--text-secondary)' }}
                  >
                    {STEP_LABELS[t.step_type] ?? t.step_type}
                  </span>
                  <span className="badge badge-muted">
                    <Clock size={10} />&nbsp;{Math.round(t.latency_ms)}ms
                  </span>
                  <span className="badge badge-muted mono" style={{ fontSize: '0.7rem' }}>
                    {t.session_id.slice(0, 10)}…
                  </span>
                  <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    {format(new Date(t.timestamp), 'HH:mm:ss')}
                  </span>
                </div>
                {t.reasoning && (
                  <div className="trace-reasoning">{t.reasoning}</div>
                )}
                {activeTrace === `${i}` && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.5rem' }}>
                    {['input', 'output'].map(k => (
                      <div key={k}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</div>
                        <pre style={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.5rem',
                          fontSize: '0.75rem',
                          color: 'var(--text-secondary)',
                          overflow: 'auto',
                          maxHeight: '120px',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                        }}>
                          {JSON.stringify(k === 'input' ? t.input : t.output, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
