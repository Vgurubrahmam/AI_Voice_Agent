"""
memory/patient_repository.py
Async PostgreSQL + SQLAlchemy ORM for persistent patient records and appointments.
Uses asyncpg driver (Supabase / PostgreSQL compatible).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine — PostgreSQL via asyncpg
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,          # detects stale connections automatically
    pool_recycle=300,            # recycle connections every 5 min (Supabase drops idle)
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True)           # phone number as PK
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    preferred_language = Column(String, default="en")
    last_interaction = Column(DateTime(timezone=True), nullable=True)
    booking_history = Column(Text, default="[]")    # JSON array stored as text
    total_bookings = Column(Integer, default=0)
    notes = Column(String, default="")


class AppointmentModel(Base):
    """Persistent appointment store — survives server restarts."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_phone = Column(String, nullable=False, index=True)
    patient_name = Column(String, nullable=False)
    doctor_id = Column(String, nullable=False)
    doctor_name = Column(String, nullable=False)
    specialty = Column(String, nullable=False, default="")
    date = Column(String, nullable=False)           # YYYY-MM-DD
    time = Column(String, nullable=False)           # HH:MM
    status = Column(String, default="confirmed")    # confirmed / cancelled
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class PatientRepository:
    """Async CRUD for patients and appointments tables (PostgreSQL)."""

    async def create_tables(self) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Patient tables created / verified.")

    # ── Patient CRUD ─────────────────────────────────────────────────────

    async def get_patient(self, phone: str) -> Optional[dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PatientModel).where(PatientModel.phone == phone)
            )
            patient = result.scalar_one_or_none()
            return self._to_dict(patient) if patient else None

    async def upsert_patient(
        self,
        phone: str,
        name: Optional[str] = None,
        language: Optional[str] = None,
        booking: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PatientModel).where(PatientModel.phone == phone)
            )
            patient = result.scalar_one_or_none()

            if patient is None:
                patient = PatientModel(
                    id=phone,
                    phone=phone,
                    name=name or "Unknown",
                    preferred_language=language or "en",
                    booking_history="[]",
                    total_bookings=0,
                    notes=notes or "",
                )
                session.add(patient)
            else:
                if name:
                    patient.name = name
                if language:
                    patient.preferred_language = language
                if notes:
                    patient.notes = notes

            if booking:
                history: list = json.loads(patient.booking_history or "[]")
                history.append(booking)
                patient.booking_history = json.dumps(history[-20:])  # keep last 20
                patient.total_bookings = (patient.total_bookings or 0) + 1

            patient.last_interaction = datetime.now(timezone.utc)
            await session.commit()
            logger.debug("Upserted patient %s", phone)

    async def get_all_patients(self) -> list[dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PatientModel))
            return [self._to_dict(p) for p in result.scalars().all()]

    async def count_patients(self) -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count()).select_from(PatientModel)
            )
            return result.scalar_one()

    # ── Appointment CRUD ─────────────────────────────────────────────────

    async def save_appointment(self, booking: dict) -> None:
        """Persist a confirmed booking to the appointments table."""
        async with AsyncSessionLocal() as session:
            appt = AppointmentModel(
                patient_phone=booking.get("patient_phone", ""),
                patient_name=booking.get("patient_name", "Unknown"),
                doctor_id=booking.get("doctor_id", ""),
                doctor_name=booking.get("doctor_name", ""),
                specialty=booking.get("specialty", ""),
                date=booking.get("date", ""),
                time=booking.get("time", ""),
                status=booking.get("status", "confirmed"),
            )
            session.add(appt)
            await session.commit()
            logger.info(
                "Appointment saved: %s with %s on %s at %s",
                booking.get("patient_name"),
                booking.get("doctor_name"),
                booking.get("date"),
                booking.get("time"),
            )

    async def get_appointments(self, patient_phone: Optional[str] = None) -> list[dict]:
        """Fetch all appointments, optionally filtered by patient phone."""
        async with AsyncSessionLocal() as session:
            query = select(AppointmentModel)
            if patient_phone:
                query = query.where(AppointmentModel.patient_phone == patient_phone)
            result = await session.execute(query.order_by(AppointmentModel.created_at.desc()))
            return [self._appt_to_dict(a) for a in result.scalars().all()]

    async def cancel_appointment_db(
        self, patient_phone: str, doctor_id: str, date_str: str, time_str: str
    ) -> bool:
        """Mark an appointment as cancelled in the DB."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AppointmentModel).where(
                    AppointmentModel.patient_phone == patient_phone,
                    AppointmentModel.doctor_id == doctor_id,
                    AppointmentModel.date == date_str,
                    AppointmentModel.time == time_str,
                    AppointmentModel.status == "confirmed",
                )
            )
            appt = result.scalar_one_or_none()
            if appt:
                appt.status = "cancelled"
                await session.commit()
                return True
            return False

    async def mark_booking_cancelled_in_history(
        self, patient_phone: str, doctor_id: str, date_str: str, time_str: str
    ) -> bool:
        """
        Keep patient.booking_history in sync with appointment cancellation state.
        Marks the most recent matching entry as cancelled.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PatientModel).where(PatientModel.phone == patient_phone)
            )
            patient = result.scalar_one_or_none()
            if not patient:
                return False

            history: list[dict] = json.loads(patient.booking_history or "[]")
            updated = False

            # Update the latest matching booking first.
            for booking in reversed(history):
                if (
                    booking.get("doctor_id") == doctor_id
                    and booking.get("date") == date_str
                    and booking.get("time") == time_str
                ):
                    booking["status"] = "cancelled"
                    updated = True
                    break

            if not updated:
                return False

            patient.booking_history = json.dumps(history[-20:])
            patient.last_interaction = datetime.now(timezone.utc)
            await session.commit()
            return True

    async def load_active_bookings(self) -> dict:
        """
        Load all confirmed appointments from DB into the SlotManager's
        in-memory dict format: {doctor_id: {date: {time: {patient_phone, patient_name}}}}
        Called at startup to restore state after a server restart.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AppointmentModel).where(AppointmentModel.status == "confirmed")
            )
            bookings: dict = {}
            for appt in result.scalars().all():
                bookings \
                    .setdefault(appt.doctor_id, {}) \
                    .setdefault(appt.date, {})[appt.time] = {
                        "patient_phone": appt.patient_phone,
                        "patient_name": appt.patient_name,
                    }
            return bookings

    # ── Summary ──────────────────────────────────────────────────────────

    async def get_patient_summary(self, phone: str) -> str:
        """Human-readable summary injected into the LLM system prompt."""
        patient = await self.get_patient(phone)
        if patient is None:
            return "New patient — no prior history available."

        raw_history = patient.get("booking_history", [])
        history: list = raw_history if isinstance(raw_history, list) else json.loads(raw_history or "[]")
        total = patient.get("total_bookings", 0)
        lang_map = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
        lang = lang_map.get(patient.get("preferred_language", "en"), "English")
        name = patient.get("name", "Unknown")
        notes = patient.get("notes", "")

        last_visit = ""
        if history:
            last = history[-1]
            last_visit = (
                f"Last appointment: {last.get('doctor_name', '?')} "
                f"on {last.get('date', '?')} at {last.get('time', '?')}."
            )

        morning_slots = sum(1 for b in history if b.get("time", "14:00") < "12:00")
        slot_pref = "morning slots" if morning_slots > total / 2 else "afternoon slots"

        summary_parts = [
            f"{'Returning' if total > 0 else 'New'} patient: {name}.",
            f"{total} prior visit(s)." if total > 0 else "",
            f"Preferred language: {lang}.",
            last_visit,
            f"Usually prefers {slot_pref}." if total > 0 else "",
            f"Notes: {notes}" if notes else "",
        ]
        return " ".join(p for p in summary_parts if p)

    # ── Private ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(patient: PatientModel) -> dict:
        return {
            "id": patient.id,
            "phone": patient.phone,
            "name": patient.name,
            "preferred_language": patient.preferred_language,
            "last_interaction": patient.last_interaction.isoformat() if patient.last_interaction else None,
            "booking_history": json.loads(patient.booking_history or "[]"),
            "total_bookings": patient.total_bookings,
            "notes": patient.notes,
        }

    @staticmethod
    def _appt_to_dict(appt: AppointmentModel) -> dict:
        return {
            "id": appt.id,
            "patient_phone": appt.patient_phone,
            "patient_name": appt.patient_name,
            "doctor_id": appt.doctor_id,
            "doctor_name": appt.doctor_name,
            "specialty": appt.specialty,
            "date": appt.date,
            "time": appt.time,
            "status": appt.status,
            "created_at": appt.created_at.isoformat() if appt.created_at else None,
        }
