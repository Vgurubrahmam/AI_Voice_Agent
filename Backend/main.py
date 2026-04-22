"""
main.py  —  STEP 19
FastAPI entry point: WebSocket voice pipeline + REST API + monitoring endpoints.
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config.settings import settings
from memory.patient_repository import PatientRepository
from memory.session_store import session_store
from pipeline.voice_pipeline import create_pipeline_session
from scheduling.slot_manager import BookingRequest, slot_manager
from telephony.inbound import handle_inbound_webhook, handle_status_callback
from telephony.outbound import make_reminder_call, run_campaign
from utils.latency_logger import latency_logger

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────
patient_repo = PatientRepository()
# Use the module-level singleton so this shares _bookings with the WebSocket/LLM pipeline

# ── Active WebSocket sessions ─────────────────────────────────────────────
_active_sessions: dict[str, Any] = {}


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── STARTUP ──────────────────────────────────────────────────────
    logger.info("=== Voice AI Agent starting up ===")

    # Create DB tables
    await patient_repo.create_tables()
    logger.info("Database tables ready.")

    # Restore persisted bookings into slot_manager's in-memory cache
    await slot_manager.restore_from_db()

    # Seed patients if DB is empty
    count = await patient_repo.count_patients()
    if count == 0:
        await _seed_patients()

    # Redis connection (warn if unavailable — fallback will be used)
    await session_store.connect()
    redis_status = "connected" if session_store.is_redis_connected else "fallback (in-memory)"
    logger.info("Redis: %s", redis_status)

    # Log sanitised settings
    logger.info(
        "Config: base_url=%s log_level=%s environment=%s "
        "nvidia_key=%s deepgram_key=%s",
        settings.base_url,
        settings.log_level,
        settings.environment,
        "SET" if settings.nvidia_api_key else "NOT SET",
        "SET" if settings.deepgram_api_key else "NOT SET",
    )

    logger.info("=== Backend ready ===")
    yield

    # ── SHUTDOWN ─────────────────────────────────────────────────────
    logger.info("Shutting down Voice AI Agent.")


# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Real-Time Multilingual Voice AI Agent",
    description="Clinical Appointment Booking — Powered by NVIDIA NIM + Deepgram + Google TTS",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# WEBSOCKET — Real-time voice pipeline
# =============================================================================

@app.websocket("/ws/voice/{phone}")
async def websocket_voice(websocket: WebSocket, phone: str) -> None:
    """
    Primary WebSocket endpoint.
    Accepts audio bytes or text messages.
    Audio → STT → LLM (agentic) → TTS → audio out.
    Text → LLM (agentic) → text out (for testing).
    """
    from urllib.parse import unquote
    # Sanitize: URL-decode and strip any stray whitespace
    phone = unquote(phone).strip().replace(" ", "")

    await websocket.accept()
    session_id = uuid4().hex
    logger.info("WebSocket connected: phone=%s session=%s", phone, session_id)

    try:
        pipeline = await create_pipeline_session(
            patient_phone=phone, session_id=session_id
        )
        _active_sessions[session_id] = pipeline

        await websocket.send_json({
            "type": "session_start",
            "session_id": session_id,
            "language": pipeline._language,
            "message": "Voice pipeline ready. Send audio bytes or text messages.",
        })

        audio_stream_chunks: list[bytes] = []
        stream_active = False
        stream_mode_enabled = False

        while True:
            data = await websocket.receive()

            # Starlette sends a raw disconnect ASGI message — handle it cleanly
            if data.get("type") == "websocket.disconnect":
                logger.info("WebSocket client disconnected: session=%s code=%s", session_id, data.get("code", 1000))
                break

            if "bytes" in data and data["bytes"]:
                if stream_active:
                    # Streaming mode: buffer chunks until audio_end control arrives
                    audio_stream_chunks.append(data["bytes"])
                    continue

                if stream_mode_enabled:
                    # Ignore trailing chunks that can arrive just after audio_end
                    # from MediaRecorder flush timing.
                    logger.debug("Ignoring stray audio chunk outside stream window: session=%s", session_id)
                    continue

                # Legacy one-shot mode: process full payload directly
                audio_out, response_text, user_transcript = await pipeline.process_audio_turn(data["bytes"])
                if audio_out:
                    await websocket.send_bytes(audio_out)
                await websocket.send_json({
                    "type": "turn_complete",
                    "session_id": session_id,
                    "text": response_text,          # agent's reply (for transcript UI)
                    "user_text": user_transcript,   # what STT heard (for transcript UI)
                    "language": pipeline._language,
                    "has_audio": bool(audio_out),
                })

            elif "text" in data and data["text"]:
                # Text turn — LLM only (for testing without audio)
                msg = data["text"]
                if msg.strip().lower() == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                # Control channel for streamed audio framing
                try:
                    control = json.loads(msg)
                    if isinstance(control, dict) and control.get("type") == "audio_start":
                        stream_mode_enabled = True
                        stream_active = True
                        audio_stream_chunks.clear()
                        continue
                    if isinstance(control, dict) and control.get("type") == "audio_end":
                        stream_active = False
                        audio_payload = b"".join(audio_stream_chunks)
                        audio_stream_chunks.clear()
                        if not audio_payload:
                            await websocket.send_json({
                                "type": "turn_complete",
                                "session_id": session_id,
                                "text": "",
                                "user_text": "",
                                "language": pipeline._language,
                                "has_audio": False,
                            })
                            continue

                        audio_out, response_text, user_transcript = await pipeline.process_audio_turn(audio_payload)
                        if audio_out:
                            await websocket.send_bytes(audio_out)
                        await websocket.send_json({
                            "type": "turn_complete",
                            "session_id": session_id,
                            "text": response_text,
                            "user_text": user_transcript,
                            "language": pipeline._language,
                            "has_audio": bool(audio_out),
                        })
                        continue
                except json.JSONDecodeError:
                    pass

                response = await pipeline.process_text_turn(msg)
                await websocket.send_json({
                    "type": "response",
                    "session_id": session_id,
                    "text": response,
                    "language": pipeline._language,
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except RuntimeError as exc:
        # Guards against "Cannot call receive once a disconnect message has been received"
        # which can fire if the client drops mid-processing
        if "disconnect" in str(exc).lower():
            logger.info("WebSocket closed mid-receive: session=%s", session_id)
        else:
            logger.error("WebSocket runtime error: session=%s error=%s", session_id, exc, exc_info=True)
    except Exception as exc:
        logger.error("WebSocket error: session=%s error=%s", session_id, exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        _active_sessions.pop(session_id, None)
        logger.info("Session cleaned up: %s", session_id)


# =============================================================================
# TWILIO ENDPOINTS
# =============================================================================

@app.post("/twilio/inbound")
async def twilio_inbound(request: Request) -> PlainTextResponse:
    """Receive inbound Twilio call and return TwiML to stream audio."""
    form = dict(await request.form())
    twiml = await handle_inbound_webhook(form)
    return PlainTextResponse(content=twiml, media_type="application/xml")


@app.post("/twilio/status")
async def twilio_status(request: Request) -> JSONResponse:
    """Handle Twilio call status callbacks."""
    form = dict(await request.form())
    result = await handle_status_callback(form)
    return JSONResponse(result)


# =============================================================================
# OUTBOUND ENDPOINTS
# =============================================================================

class OutboundCallRequest(BaseModel):
    booking: Optional[dict] = None


@app.post("/outbound/call/{phone}")
async def outbound_call(phone: str, body: OutboundCallRequest = OutboundCallRequest()) -> JSONResponse:
    """Initiate an outbound reminder call to a patient."""
    result = await make_reminder_call(phone, body.booking or {})
    return JSONResponse(result)


class CampaignRequest(BaseModel):
    phones: list[str]
    campaign_type: str = "reminder"
    booking_data: Optional[dict] = None


@app.post("/outbound/campaign")
async def outbound_campaign(body: CampaignRequest) -> JSONResponse:
    """Run a bulk outbound calling campaign."""
    result = await run_campaign(body.phones, body.campaign_type, body.booking_data)
    return JSONResponse(result)


@app.get("/outbound/remind/{phone}")
async def outbound_remind(phone: str) -> JSONResponse:
    """Send a reminder to a specific patient based on their most recent booking."""
    patient = await patient_repo.get_patient(phone)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    history = patient.get("booking_history", [])
    booking = history[-1] if history else {}
    result = await make_reminder_call(phone, booking)
    return JSONResponse(result)


# =============================================================================
# SCHEDULING ENDPOINTS
# =============================================================================

@app.get("/doctors")
async def list_doctors(specialty: Optional[str] = None) -> JSONResponse:
    """List all available doctors, optionally filtered by specialty."""
    doctors = await slot_manager.get_all_doctors(specialty=specialty)
    return JSONResponse({"doctors": doctors, "count": len(doctors)})


@app.get("/doctors/{doctor_id}/slots/{date_str}")
async def get_slots(doctor_id: str, date_str: str) -> JSONResponse:
    """Get available slots for a doctor on a specific date."""
    slots = await slot_manager.get_available_slots(doctor_id, date_str)
    doctors = await slot_manager.get_all_doctors()
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if not doctor:
        raise HTTPException(status_code=404, detail=f"Doctor {doctor_id} not found")
    return JSONResponse({
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"],
        "date": date_str,
        "available_slots": slots,
        "count": len(slots),
    })


class BookingRequestBody(BaseModel):
    patient_phone: str
    doctor_id: str
    date: str
    time: str
    patient_name: str


@app.post("/appointments/book")
async def book_appointment(body: BookingRequestBody) -> JSONResponse:
    """Book an appointment. Returns conflict info with 3 alternatives if slot taken."""
    request = BookingRequest(**body.model_dump())
    result = await slot_manager.book_slot(request)
    # slot_manager.book_slot now persists to DB and updates patient history automatically
    return JSONResponse(result.model_dump(), status_code=200 if result.success else 409)


class CancelBody(BaseModel):
    patient_phone: str
    doctor_id: str
    date: str
    time: str


@app.post("/appointments/cancel")
async def cancel_appointment(body: CancelBody) -> JSONResponse:
    """Cancel an existing appointment."""
    result = await slot_manager.cancel_slot(
        patient_phone=body.patient_phone,
        doctor_id=body.doctor_id,
        date_str=body.date,
        time_str=body.time,
    )
    return JSONResponse(result.model_dump(), status_code=200 if result.success else 400)


class RescheduleBody(BaseModel):
    patient_phone: str
    doctor_id: str
    old_date: str
    old_time: str
    new_date: str
    new_time: str


@app.post("/appointments/reschedule")
async def reschedule_appointment(body: RescheduleBody) -> JSONResponse:
    """Atomically cancel old appointment and book new one."""
    result = await slot_manager.reschedule_slot(
        patient_phone=body.patient_phone,
        doctor_id=body.doctor_id,
        old_date=body.old_date,
        old_time=body.old_time,
        new_date=body.new_date,
        new_time=body.new_time,
    )
    return JSONResponse(result.model_dump(), status_code=200 if result.success else 409)


# =============================================================================
# PATIENT ENDPOINTS
# =============================================================================

@app.get("/patients")
async def list_patients() -> JSONResponse:
    """List all patients in the database."""
    patients = await patient_repo.get_all_patients()
    return JSONResponse({"patients": patients, "count": len(patients)})


@app.get("/patients/{phone}")
async def get_patient(phone: str) -> JSONResponse:
    """Get a specific patient by phone number."""
    patient = await patient_repo.get_patient(phone)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    summary = await patient_repo.get_patient_summary(phone)
    return JSONResponse({"patient": patient, "summary": summary})


# =============================================================================
# APPOINTMENTS ENDPOINTS
# =============================================================================

@app.get("/appointments")
async def list_appointments(phone: Optional[str] = None) -> JSONResponse:
    """List all appointments from the database, optionally filtered by patient phone."""
    appointments = await patient_repo.get_appointments(patient_phone=phone)
    return JSONResponse({"appointments": appointments, "count": len(appointments)})


# =============================================================================
# MONITORING ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check — verifies DB and Redis connectivity."""
    redis_status = "connected" if session_store.is_redis_connected else "fallback"
    db_ok = True
    try:
        await patient_repo.count_patients()
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_ok = False

    return JSONResponse({
        "status": "ok",
        "redis": redis_status,
        "db": "ok" if db_ok else "error",
        "env": settings.environment,
        "nvidia_nim": "configured" if settings.nvidia_api_key else "not configured",
        "deepgram": "configured" if settings.deepgram_api_key else "not configured",
        "active_sessions": len(_active_sessions),
        "today": date.today().isoformat(),
    })


@app.get("/latency/report")
async def latency_report() -> JSONResponse:
    """Get p50/p95/p99 latency percentile report."""
    report = latency_logger.get_report()
    if report is None:
        return JSONResponse({"message": "No latency data yet. Make some calls first."})
    return JSONResponse(report.model_dump())


@app.get("/latency/log")
async def latency_log() -> JSONResponse:
    """Get all raw latency log entries."""
    entries = latency_logger.get_all_entries()
    return JSONResponse({
        "entries": [e.model_dump() for e in entries],
        "count": len(entries),
    })


@app.get("/traces/recent")
async def recent_traces() -> JSONResponse:
    """Get the last 20 reasoning trace entries from reasoning_trace.jsonl."""
    from pathlib import Path
    trace_file = Path("reasoning_trace.jsonl")
    if not trace_file.exists():
        return JSONResponse({"message": "No traces yet. Make a WebSocket call first.", "traces": []})

    traces: list[dict] = []
    try:
        with trace_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    traces.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read traces: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)

    # Return last 20 in reverse order (most recent first)
    recent = list(reversed(traces[-20:]))
    return JSONResponse({"traces": recent, "count": len(recent), "total_in_file": len(traces)})


@app.get("/traces/{session_id}")
async def get_session_trace(session_id: str) -> JSONResponse:
    """Get full reasoning trace for a specific session."""
    from pathlib import Path
    trace_file = Path("reasoning_trace.jsonl")
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="No trace file found")

    session_traces: list[dict] = []
    try:
        with trace_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    if entry.get("session_id") == session_id:
                        session_traces.append(entry)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read traces for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if not session_traces:
        raise HTTPException(status_code=404, detail=f"No traces found for session {session_id}")

    return JSONResponse({
        "session_id": session_id,
        "step_count": len(session_traces),
        "steps": session_traces,
    })


# =============================================================================
# Seeding helper
# =============================================================================

async def _seed_patients() -> None:
    """Seed the database with patients from patients_seed.json."""
    from pathlib import Path
    seed_file = Path(__file__).parent / "data" / "patients_seed.json"
    if not seed_file.exists():
        logger.warning("Seed file not found: %s", seed_file)
        return

    try:
        seed_data = json.loads(seed_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read seed file: %s", exc)
        return

    for p in seed_data:
        history = p.get("booking_history", [])
        await patient_repo.upsert_patient(
            phone=p["phone"],
            name=p["name"],
            language=p.get("preferred_language", "en"),
            notes=p.get("notes", ""),
        )
        # Add each booking individually so total_bookings increments correctly
        for booking in history:
            await patient_repo.upsert_patient(phone=p["phone"], booking=booking)

    logger.info("Seeded %d patients from %s", len(seed_data), seed_file)


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
