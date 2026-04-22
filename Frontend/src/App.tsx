import { useState } from 'react';
import { LayoutDashboard, CalendarDays, Users, Mic, Activity } from 'lucide-react';
import DashboardTab from './components/DashboardTab';
import AppointmentsTab from './components/AppointmentsTab';
import PatientsTab from './components/PatientsTab';
import VoiceTestTab from './components/VoiceTestTab';
import MonitoringTab from './components/MonitoringTab';
import ToastContainer from './components/ToastContainer';
import { useToast } from './hooks/useToast';
import './App.css';

type Tab = 'dashboard' | 'appointments' | 'patients' | 'voice' | 'monitoring';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard',    label: 'Dashboard',    icon: <LayoutDashboard size={15} /> },
  { id: 'appointments', label: 'Appointments', icon: <CalendarDays size={15} /> },
  { id: 'patients',     label: 'Patients',     icon: <Users size={15} /> },
  { id: 'voice',        label: 'Voice Test',   icon: <Mic size={15} /> },
  { id: 'monitoring',   label: 'Monitoring',   icon: <Activity size={15} /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const { toasts, addToast, removeToast } = useToast();

  return (
    <div className="app-shell">
      {/* Top Navigation */}
      <nav className="topnav" role="navigation" aria-label="Main navigation">
        {/* Brand */}
        <div className="topnav-brand">
          <div className="brand-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" x2="12" y1="19" y2="22" />
            </svg>
          </div>
          ClinicalVoice AI
        </div>

        {/* Tabs */}
        <div className="topnav-tabs" role="tablist">
          {TABS.map(t => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              role="tab"
              aria-selected={tab === t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <span className="tab-icon">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Status */}
        <div className="topnav-status">
          <div className="status-dot ok" title="System online" />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>v1.0</span>
        </div>
      </nav>

      {/* Main content */}
      <main className="main-content" role="main">
        {tab === 'dashboard'    && <DashboardTab />}
        {tab === 'appointments' && <AppointmentsTab onToast={addToast} />}
        {tab === 'patients'     && <PatientsTab onToast={addToast} />}
        {tab === 'voice'        && <VoiceTestTab onToast={addToast} />}
        {tab === 'monitoring'   && <MonitoringTab onToast={addToast} />}
      </main>

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}
