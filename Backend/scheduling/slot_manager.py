"""
scheduling/slot_manager.py
Core booking logic: doctors.json for slot schedules + PostgreSQL for persistent bookings.
All functions async. Pydantic models for all I/O.

SlotManager is a module-level singleton so ALL components share the same _bookings dict.
On startup it reloads active bookings from PostgreSQL so state survives restarts.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DOCTORS_FILE = Path(__file__).parent.parent / "data" / "doctors.json"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BookingRequest(BaseModel):
    patient_phone: str
    doctor_id: str
    date: str
    time: str
    patient_name: str


class BookingResult(BaseModel):
    success: bool
    booking: Optional[dict] = None
    reason: Optional[str] = None
    alternatives: list[dict] = []


# ---------------------------------------------------------------------------
# SlotManager
# ---------------------------------------------------------------------------

class SlotManager:
    """
    Manages appointment slots loaded from doctors.json.

    Bookings are stored in PostgreSQL via PatientRepository and cached in
    an in-memory dict for fast lookup. Call `restore_from_db()` at startup
    to reload persisted bookings so state survives server restarts.

    Always import `slot_manager` from this module — never call SlotManager()
    directly, or each instance will have isolated booking state.
    """

    def __init__(self) -> None:
        self._doctors: list[dict] = []
        self._bookings: dict[str, dict[str, dict[str, dict]]] = {}
        self._repo = None   # set lazily to avoid circular imports at module load
        self._load_doctors()

    # ── Initialisation ────────────────────────────────────────────────

    def _load_doctors(self) -> None:
        try:
            raw = DOCTORS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._doctors = data["doctors"]
            for doc in self._doctors:
                self._bookings[doc["id"]] = {}
            logger.info("Loaded %d doctors from %s", len(self._doctors), DOCTORS_FILE)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to load doctors.json: %s", exc)
            self._doctors = []

    def _get_repo(self):
        """Lazy import to avoid circular dependency at module load time."""
        if self._repo is None:
            from memory.patient_repository import PatientRepository
            self._repo = PatientRepository()
        return self._repo

    async def restore_from_db(self) -> None:
        """
        Load all confirmed appointments from PostgreSQL into in-memory cache.
        Call this once at startup (after create_tables) so bookings survive restarts.
        """
        try:
            repo = self._get_repo()
            bookings = await repo.load_active_bookings()
            # Merge into existing in-memory structure (doctors already initialised)
            for doctor_id, dates in bookings.items():
                self._bookings.setdefault(doctor_id, {}).update(dates)
            total = sum(
                len(slots)
                for dates in bookings.values()
                for slots in dates.values()
            )
            logger.info("Restored %d confirmed appointments from database.", total)
        except Exception as exc:
            logger.error("Failed to restore bookings from DB: %s", exc)

    # ── Query helpers ─────────────────────────────────────────────────

    def _get_doctor(self, doctor_id: str) -> Optional[dict]:
        for doc in self._doctors:
            if doc["id"] == doctor_id:
                return doc
        return None

    def _is_booked(self, doctor_id: str, date_str: str, time_str: str) -> bool:
        return bool(
            self._bookings.get(doctor_id, {}).get(date_str, {}).get(time_str)
        )

    def _original_slots(self, doctor_id: str, date_str: str) -> list[str]:
        doc = self._get_doctor(doctor_id)
        if not doc:
            return []
        return doc.get("slots", {}).get(date_str, [])

    # ── Public API (all async) ─────────────────────────────────────────

    async def get_available_slots(self, doctor_id: str, date_str: str) -> list[str]:
        """Return slots not yet booked for a doctor on a date."""
        all_slots = self._original_slots(doctor_id, date_str)
        booked = set(self._bookings.get(doctor_id, {}).get(date_str, {}).keys())
        available = [s for s in all_slots if s not in booked]
        logger.debug("Available slots for %s on %s: %s", doctor_id, date_str, available)
        return available

    async def get_all_doctors(self, specialty: Optional[str] = None) -> list[dict]:
        """Return all doctors, optionally filtered by specialty."""
        if specialty:
            return [
                d for d in self._doctors
                if d["specialty"].lower() == specialty.lower()
            ]
        return list(self._doctors)

    async def book_slot(self, request: BookingRequest) -> BookingResult:
        """
        Book a slot. Returns failure with alternatives if already booked.
        Also persists to PostgreSQL and updates patient history.
        """
        doc = self._get_doctor(request.doctor_id)
        if not doc:
            return BookingResult(success=False, reason=f"Doctor {request.doctor_id} not found.")

        # Past date check
        try:
            req_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            return BookingResult(success=False, reason="Invalid date format. Use YYYY-MM-DD.")

        if req_date < date.today():
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            return BookingResult(
                success=False,
                reason=f"Cannot book in the past. Please choose a date from {tomorrow} onwards.",
            )

        # Slot existence check
        original = self._original_slots(request.doctor_id, request.date)
        if request.time not in original:
            return BookingResult(
                success=False,
                reason=f"Slot {request.time} does not exist for {doc['name']} on {request.date}.",
            )

        # Double-booking check
        if self._is_booked(request.doctor_id, request.date, request.time):
            alternatives = await self.find_alternatives(request.doctor_id, request.date)
            return BookingResult(
                success=False,
                reason=f"Slot {request.time} on {request.date} is already booked.",
                alternatives=alternatives,
            )

        # Commit to in-memory cache
        self._bookings.setdefault(request.doctor_id, {}).setdefault(request.date, {})[
            request.time
        ] = {"patient_phone": request.patient_phone, "patient_name": request.patient_name}

        booking = {
            "doctor_id": request.doctor_id,
            "doctor_name": doc["name"],
            "specialty": doc["specialty"],
            "date": request.date,
            "time": request.time,
            "patient_phone": request.patient_phone,
            "patient_name": request.patient_name,
            "status": "confirmed",
        }
        logger.info("Booked: %s", booking)

        # ── Persist to PostgreSQL ───────────────────────────────────────
        try:
            repo = self._get_repo()
            # Save to appointments table
            await repo.save_appointment(booking)
            # Update patient's booking history & profile
            await repo.upsert_patient(
                phone=request.patient_phone,
                name=request.patient_name,
                booking=booking,
            )
        except Exception as exc:
            logger.error("Failed to persist booking to DB: %s", exc)
            # Don't fail the booking — in-memory succeeded

        return BookingResult(success=True, booking=booking)

    async def cancel_slot(
        self, patient_phone: str, doctor_id: str, date_str: str, time_str: str
    ) -> BookingResult:
        """Cancel a booking. Frees the slot and updates DB status."""
        slot = self._bookings.get(doctor_id, {}).get(date_str, {}).get(time_str)
        if not slot:
            return BookingResult(success=False, reason="No booking found for the given slot.")

        if slot["patient_phone"] != patient_phone:
            return BookingResult(success=False, reason="This booking belongs to a different patient.")

        # Remove from in-memory cache
        del self._bookings[doctor_id][date_str][time_str]
        logger.info(
            "Cancelled booking: doctor=%s date=%s time=%s patient=%s",
            doctor_id, date_str, time_str, patient_phone,
        )

        # ── Update DB ──────────────────────────────────────────────────
        try:
            repo = self._get_repo()
            updated = await repo.cancel_appointment_db(patient_phone, doctor_id, date_str, time_str)
            if updated:
                await repo.mark_booking_cancelled_in_history(
                    patient_phone=patient_phone,
                    doctor_id=doctor_id,
                    date_str=date_str,
                    time_str=time_str,
                )
        except Exception as exc:
            logger.error("Failed to update cancellation in DB: %s", exc)

        return BookingResult(success=True, reason="Appointment cancelled successfully.")

    async def reschedule_slot(
        self,
        patient_phone: str,
        doctor_id: str,
        old_date: str,
        old_time: str,
        new_date: str,
        new_time: str,
    ) -> BookingResult:
        """Atomically cancel old slot and book new slot. Rolls back if new slot fails."""
        old_slot = self._bookings.get(doctor_id, {}).get(old_date, {}).get(old_time)
        if not old_slot:
            return BookingResult(success=False, reason="No existing booking found to reschedule.")
        if old_slot["patient_phone"] != patient_phone:
            return BookingResult(success=False, reason="This booking belongs to a different patient.")

        patient_name = old_slot["patient_name"]

        cancel_result = await self.cancel_slot(patient_phone, doctor_id, old_date, old_time)
        if not cancel_result.success:
            return cancel_result

        book_req = BookingRequest(
            patient_phone=patient_phone,
            doctor_id=doctor_id,
            date=new_date,
            time=new_time,
            patient_name=patient_name,
        )
        book_result = await self.book_slot(book_req)

        if not book_result.success:
            # Rollback: restore old slot in-memory
            self._bookings.setdefault(doctor_id, {}).setdefault(old_date, {})[old_time] = old_slot
            logger.warning("Reschedule failed, rolled back to old slot: %s %s", old_date, old_time)
            return BookingResult(
                success=False,
                reason=f"Could not secure new slot: {book_result.reason}",
                alternatives=book_result.alternatives,
            )

        logger.info(
            "Rescheduled: %s → %s for %s",
            f"{old_date} {old_time}", f"{new_date} {new_time}", patient_phone,
        )
        return book_result

    async def find_alternatives(
        self, doctor_id: str, date_str: str, count: int = 3
    ) -> list[dict]:
        """Find up to `count` alternative slots starting from date_str."""
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = date.today()

        alternatives: list[dict] = []
        search_date = start_date

        for _ in range(7):
            date_key = search_date.isoformat()
            available = await self.get_available_slots(doctor_id, date_key)
            for slot in available:
                if len(alternatives) >= count:
                    break
                alternatives.append({"date": date_key, "time": slot, "doctor_id": doctor_id})
            if len(alternatives) >= count:
                break
            search_date += timedelta(days=1)

        return alternatives


# ---------------------------------------------------------------------------
# Module-level singleton — import and use this everywhere so all components
# share the same _bookings in-memory state.
# ---------------------------------------------------------------------------

slot_manager = SlotManager()
