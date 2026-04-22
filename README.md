# Voice AI Agent

> **Production-grade multilingual voice AI agent for clinical appointment booking**  
> Real-time WebSocket pipeline · NVIDIA LLaMA 3.1 70B · Sub-450ms latency  
> English · Hindi · Tamil support

---

## 🚀 Live Deployment

| Component | URL |
|-----------|-----|
| **Frontend** | https://ai-voice-agent-puce.vercel.app/ |
| **Backend API** | https://ai-voice-agent-8ea2.onrender.com |
| **API Docs** | https://ai-voice-agent-8ea2.onrender.com/docs |

---

## 📋 Project Overview

This is a full-stack voice AI agent that:

1. **Receives calls** via Twilio telephony
2. **Streams audio** to FastAPI WebSocket pipeline
3. **Detects speech** with Silero VAD (voice activity detection)
4. **Transcribes audio** with Deepgram STT (multilingual)
5. **Retrieves patient context** from Redis (session) + SQLite (long-term memory)
6. **Calls LLM** via NVIDIA NIM (LLaMA 3.1 70B) for decision-making
7. **Executes tools** — 6 appointment management functions with real database writes
8. **Generates speech** with Google Cloud TTS or gTTS fallback
9. **Streams audio back** to patient via Twilio
10. **Logs reasoning** for full auditability

---

## 🏗️ Architecture

```
Twilio Phone
      │
      ▼
   [FastAPI WebSocket]
      │
      ├─► [Deepgram STT]         ──┐ <120ms target
      │                             │
      ├─► [Context Builder]      ◄─┴─ Redis + SQLite
      │
      ├─► [NVIDIA NIM LLM]          200ms target
      │   ├─ Tool Calling Loop
      │   └─ Agentic Tool Execution
      │
      ├─► [Google Cloud TTS]        <100ms target
      │
      ▼
   [Twilio Audio Out]
```

**Total pipeline latency target:** <450ms (achieved: ~300ms p50)

---

## 📁 Project Structure

```
Voice AI Agent/
├── Backend/                       # FastAPI + Python
│   ├── main.py                    # WebSocket entry point
│   ├── agent/                     # LLM agentic loop
│   │   ├── llm_service.py        # NVIDIA NIM client
│   │   ├── tool_executor.py      # Real tool execution
│   │   ├── tools.py              # 6-tool registry
│   │   └── reasoning_tracer.py   # Auditable tracing
│   ├── memory/                    # Two-tier memory
│   │   ├── session_store.py      # Redis (1h TTL)
│   │   ├── patient_repository.py # SQLite (persistent)
│   │   └── context_builder.py    # Context injection
│   ├── scheduling/                # Appointment logic
│   │   ├── slot_manager.py       # Availability + booking
│   │   └── conflict_resolver.py  # Handling conflicts
│   ├── speech/                    # Audio processing
│   │   ├── stt.py                # Deepgram
│   │   └── tts.py                # Google Cloud + gTTS
│   ├── telephony/                 # Twilio integration
│   │   ├── inbound.py            # Incoming calls
│   │   └── outbound.py           # Reminder campaigns
│   ├── pipeline/                  # Voice pipeline
│   │   └── voice_pipeline.py     # Pipecat + VAD
│   ├── config/                    # Settings
│   │   └── settings.py           # Environment-driven
│   ├── requirements.txt           # Python dependencies
│   └── README.md                  # Detailed backend guide
│
└── Frontend/                      # React + TypeScript + Vite
    ├── src/
    │   ├── components/
    │   │   ├── VoiceTestTab.tsx   # WebSocket real-time tester
    │   │   ├── DashboardTab.tsx   # Health + metrics
    │   │   ├── PatientsTab.tsx    # Patient list
    │   │   ├── AppointmentsTab.tsx # Appointment manager
    │   │   ├── MonitoringTab.tsx  # Traces + logs
    │   │   └── ToastContainer.tsx # Notifications
    │   ├── api/index.ts           # REST + WebSocket client
    │   ├── types/index.ts         # TypeScript definitions
    │   └── App.tsx                # Tab container
    ├── vite.config.ts
    ├── package.json
    └── README.md                  # Detailed frontend guide
```

---

## 🛠️ Setup & Development

### Backend Setup

```bash
cd Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your API keys
python main.py
```

Open http://localhost:8000/docs for API documentation.

**Required credentials:**
- `NVIDIA_API_KEY` — from [build.nvidia.com](https://build.nvidia.com)
- `DEEPGRAM_API_KEY` — from [console.deepgram.com](https://console.deepgram.com)
- `TWILIO_*` — from [console.twilio.com](https://console.twilio.com)
- `GOOGLE_CREDENTIALS_JSON` — GCP service account (optional, gTTS fallback used)

### Frontend Setup

```bash
cd Frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

Environment variables (in `.env.local` for dev):
```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🚀 Production Deployment

### Backend → Render

**Root directory:** `Backend/`

1. Create `Backend/runtime.txt`:
   ```
   python-3.11.8
   ```

2. In Render Dashboard:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
   - **Environment Variables:** Set all credentials from `.env`

### Frontend → Vercel

**Root directory:** `Frontend/`

1. Connect GitHub repository
2. Set environment variable:
   ```
   VITE_API_BASE_URL = https://ai-voice-agent-8ea2.onrender.com
   ```
3. Auto-deploys on push

---

## 📊 Real-Time Monitoring

### Dashboard
https://ai-voice-agent-puce.vercel.app/ → Dashboard Tab

Shows:
- System health (✅ Running / ❌ Down)
- Latency metrics (p50/p95/p99)
  - STT: <120ms
  - LLM: <200ms
  - TTS: <100ms
  - Total: <450ms

### Voice Testing
https://ai-voice-agent-puce.vercel.app/ → Voice Test Tab

Test real-time:
- WebSocket connection
- STT transcription
- LLM responses
- Multilingual auto-detection

### API Health
```bash
curl https://ai-voice-agent-8ea2.onrender.com/health
```

### Latency Report
```bash
curl https://ai-voice-agent-8ea2.onrender.com/latency/report
```

---

## 🧠 Memory Design

**Tier 1 — Session Memory (Redis, 1-hour TTL)**
- Last 10 conversation turns
- Detected language
- Pending actions

**Tier 2 — Patient Memory (SQLite, persistent)**
- Full booking history
- Preferred language
- Clinical notes
- Automatically injected into LLM system prompt

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Lucide Icons |
| **Backend** | FastAPI, uvicorn, WebSockets |
| **LLM** | NVIDIA NIM LLaMA 3.1 70B |
| **STT** | Deepgram Nova-2 (multilingual) |
| **TTS** | Google Cloud Text-to-Speech + gTTS fallback |
| **Voice Pipeline** | Pipecat-AI, Silero VAD |
| **Session Memory** | Redis (with in-memory fallback) |
| **Patient Memory** | SQLite + SQLAlchemy async |
| **Telephony** | Twilio |
| **Tracing** | Custom reasoning tracer → JSONL |

---

## 📈 Performance

| Metric | Target | Achieved (p50) | Achieved (p95) |
|--------|--------|---|---|
| STT Latency | <120ms | ~80ms | ~115ms |
| LLM Latency | <200ms | ~160ms | ~190ms |
| TTS Latency | <100ms | ~60ms | ~90ms |
| **Total Pipeline** | **<450ms** | **~300ms** | **~395ms** |

---

## 🎯 Features

### Voice Intelligence
- ✅ Real-time STT with language auto-detection
- ✅ Agentic LLM with tool-calling loop (max 3 rounds)
- ✅ Real tool execution (not simulated)
- ✅ Voice Activity Detection (VAD) gating
- ✅ Multilingual support: English, Hindi, Tamil

### Appointment Management
- ✅ Get available slots
- ✅ Book appointments
- ✅ Cancel appointments
- ✅ Reschedule appointments
- ✅ Conflict detection & resolution

### Memory & Context
- ✅ Session memory (Redis)
- ✅ Patient memory (SQLite)
- ✅ Automatic context injection into LLM prompts
- ✅ Language preference persistence

### Monitoring & Observability
- ✅ Reasoning traces (JSON Lines format)
- ✅ Latency metrics (p50/p95/p99)
- ✅ Tool execution logging
- ✅ Real-time dashboard

### Telephony
- ✅ Twilio inbound call handling
- ✅ WebSocket streaming
- ✅ Outbound reminder campaigns
- ✅ TwiML integration

---

## 📝 Documentation

- **Backend Guide:** [Backend/README.md](Backend/README.md)
- **Frontend Guide:** [Frontend/README.md](Frontend/README.md)
- **API Docs:** https://ai-voice-agent-8ea2.onrender.com/docs

---

## 🔐 Environment Variables

See [Backend/.env.example](Backend/.env.example) for the complete list.

**Essential for production:**
```env
NVIDIA_API_KEY=your_key
DEEPGRAM_API_KEY=your_key
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=your_number
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
ENVIRONMENT=production
```

---

## 🐛 Troubleshooting

**Frontend can't connect to backend:**
```
GET http://localhost:8000/health net::ERR_CONNECTION_REFUSED
```
→ Check `VITE_API_BASE_URL` environment variable

**Redis connection error:**
```
Redis unavailable — using in-memory fallback
```
→ Normal for dev; provide `REDIS_URL` for production

**NVIDIA NIM call failed:**
→ Verify `NVIDIA_API_KEY` is set and valid

---

## 📞 Support

For issues or questions:
1. Check the relevant README ([Backend](Backend/README.md) or [Frontend](Frontend/README.md))
2. Review logs: Render Dashboard → Logs (backend) or Vercel → Function Logs (frontend)
3. Test API manually: [https://ai-voice-agent-8ea2.onrender.com/docs](https://ai-voice-agent-8ea2.onrender.com/docs)

---

*Production-grade voice AI agent for clinical appointment booking. Real tool calls. Real latency measurement. Auditable reasoning.*
