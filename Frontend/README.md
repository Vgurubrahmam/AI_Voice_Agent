# Voice AI Agent — Frontend UI

> React + TypeScript + Vite dashboard for managing multilingual voice appointment bookings  
> Real-time WebSocket voice testing · Patient/Doctor management · Latency monitoring

---

## Production URLs

- **Live Frontend:** https://ai-voice-agent-puce.vercel.app/
- **Backend API:** https://ai-voice-agent-8ea2.onrender.com
- **API Docs:** https://ai-voice-agent-8ea2.onrender.com/docs

---

## Features

### 📞 Voice Test Tab
- Real-time WebSocket connection to backend
- Live audio transcription (STT) from patient phone number
- Multilingual support (English · Hindi · Tamil) with language auto-detection
- Send text messages to test LLM responses
- Monitor WebSocket connection status and latency
- Language indicators with flags 🇬🇧 🇮🇳

### 👥 Patients Tab
- Browse all registered patients
- View patient phone, name, and preferred language
- Real-time patient list from backend

### 👨‍⚕️ Doctors Tab
- Browse all available doctors
- View doctor specialties
- Search and filter by department

### 📅 Appointments Tab
- List all scheduled appointments
- Book new appointments
- Cancel existing appointments
- Reschedule appointments

### 📊 Dashboard Tab
- System health status
- Latency metrics (p50/p95/p99)
  - STT latency
  - LLM latency
  - TTS latency
  - Total pipeline latency
- Real-time monitoring charts

### 📡 Monitoring Tab
- View recent reasoning traces
- Inspect LLM decision-making
- Tool call history
- Latency logs

---

## Setup

### 1. Install dependencies
```bash
cd Frontend
npm install
```

### 2. Create `.env.local` (development)
```env
VITE_API_BASE_URL=http://localhost:8000
```

For production (on Vercel), this is set via environment variables.

### 3. Start development server
```bash
npm run dev
```

Open http://localhost:5173 in your browser.

### 4. Build for production
```bash
npm run build
npm run preview  # Preview optimized build
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `https://ai-voice-agent-8ea2.onrender.com` | Backend API base URL (HTTP/HTTPS) |

**Notes:**
- WebSocket URLs are automatically derived by replacing `http://` → `ws://` and `https://` → `wss://`
- For local development, set to `http://localhost:8000`
- For production, Vercel environment variables are used

---

## Project Structure

```
Frontend/
├── src/
│   ├── components/
│   │   ├── AppointmentsTab.tsx    # Appointment management
│   │   ├── DashboardTab.tsx       # Health & latency metrics
│   │   ├── MonitoringTab.tsx      # Reasoning traces & logs
│   │   ├── PatientsTab.tsx        # Patient list
│   │   ├── ToastContainer.tsx     # Notifications
│   │   └── VoiceTestTab.tsx       # Real-time WebSocket testing
│   ├── hooks/
│   │   └── useToast.ts            # Toast notification hook
│   ├── types/
│   │   └── index.ts               # TypeScript types
│   ├── api/
│   │   └── index.ts               # API client
│   ├── App.tsx                    # Main tab container
│   └── main.tsx                   # Entry point
├── public/                        # Static assets
├── index.html                     # HTML entry
├── vite.config.ts                 # Vite configuration
├── tsconfig.json                  # TypeScript config
└── package.json                   # Dependencies

```

---

## API Integration

The frontend communicates with the backend via:

- **REST API:** Health checks, patient/doctor lists, appointments
- **WebSocket:** Real-time voice sessions at `/ws/voice/{phone}`

All requests include `Content-Type: application/json` header.

### Example API Call
```typescript
// From src/api/index.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://ai-voice-agent-8ea2.onrender.com';

export const getHealth = () => req<HealthStatus>('/health');
export const getPatients = () => req<Patient[]>('/patients');
export const getDoctors = () => req<Doctor[]>('/doctors');
```

---

## Deployment to Vercel

### 1. Connect Repository
1. Push code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Import the repository → Select `Frontend` as root directory

### 2. Configure Environment
1. Go to Settings → Environment Variables
2. Add:
   ```
   VITE_API_BASE_URL = https://ai-voice-agent-8ea2.onrender.com
   ```

### 3. Deploy
```bash
# Auto-deploys on git push
git add .
git commit -m "Update frontend"
git push
```

Or manually redeploy:
1. Deployments → Find latest → Click ⋮ → Redeploy

---

## Development

### Scripts
```bash
npm run dev       # Start dev server with HMR
npm run build     # Production build
npm run preview   # Preview optimized build
npm run lint      # Run ESLint
```

### Technology Stack
- **React 18** — UI framework
- **TypeScript** — Type safety
- **Vite** — Build tool with HMR
- **Lucide React** — Icons
- **date-fns** — Date formatting
- **ESLint** — Code linting

### Type Safety
All API responses are strictly typed via `src/types/index.ts`:
```typescript
interface Patient {
  phone: string;
  name: string;
  preferred_language: string;
}

interface Doctor {
  id: string;
  name: string;
  specialty: string;
  available: boolean;
}
```

---

## Troubleshooting

**Issue:** `GET http://localhost:8000/health net::ERR_CONNECTION_REFUSED`

**Solution:** Update `VITE_API_BASE_URL` to point to correct backend:
- Local: `http://localhost:8000`
- Production: `https://ai-voice-agent-8ea2.onrender.com`

---

## Production Monitoring

- Monitor frontend errors: Vercel → Deployments → Function Logs
- Monitor backend: Render → Logs
- API health: https://ai-voice-agent-8ea2.onrender.com/health
- Latency metrics: https://ai-voice-agent-8ea2.onrender.com/latency/report

---

*Built for production voice AI agent. Real-time WebSocket streaming with multilingual support.*
