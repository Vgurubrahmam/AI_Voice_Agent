"""
scheduling/conflict_resolver.py  —  STEP 11
Validates booking requests and resolves conflicts with alternatives.
"""

import logging
from datetime import date, datetime

from agent.reasoning_tracer import ReasoningTracer
from scheduling.slot_manager import slot_manager as _shared_slot_manager

logger = logging.getLogger(__name__)


class ConflictResolver:
    """
    Validates booking requests and finds alternative slots when conflicts occur.
    All conflict decisions are logged to the ReasoningTracer for visibility.
    """

    def __init__(self) -> None:
        self._slot_manager = _shared_slot_manager  # singleton — shared bookings state

    async def resolve(
        self,
        doctor_id: str,
        date_str: str,
        time_str: str,
        tracer: ReasoningTracer,
    ) -> dict:
        """
        Check whether the requested slot is available.
        If taken: find 3 alternatives.
        Returns:
          {"conflict": False}
          or
          {"conflict": True, "alternatives": [...]}
        """
        available = await self._slot_manager.get_available_slots(doctor_id, date_str)

        if time_str in available:
            return {"conflict": False}

        # Slot is taken — find alternatives
        alternatives = await self._slot_manager.find_alternatives(doctor_id, date_str, count=3)

        tracer.log_conflict(
            requested_slot={"doctor_id": doctor_id, "date": date_str, "time": time_str},
            alternatives_offered=alternatives,
        )

        return {"conflict": True, "alternatives": alternatives}

    async def validate_booking_request(
        self,
        doctor_id: str,
        date_str: str,
        time_str: str,
    ) -> tuple[bool, str]:
        """
        Validates a booking request before execution.
        Returns (is_valid, error_reason) tuple.
        Checks:
          - Date is not in the past
          - Doctor exists
          - Slot exists in doctor schedule
          - Slot is not already booked
        """
        # Past date check
        try:
            req_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return False, f"Invalid date format '{date_str}'. Use YYYY-MM-DD."

        if req_date < date.today():
            return False, f"Date {date_str} is in the past. Please choose a future date."

        # Doctor existence check
        doctors = await self._slot_manager.get_all_doctors()
        doctor_ids = {d["id"] for d in doctors}
        if doctor_id not in doctor_ids:
            return False, f"Doctor '{doctor_id}' not found."

        # Slot existence + availability check
        available = await self._slot_manager.get_available_slots(doctor_id, date_str)
        all_slots_for_date: list[str] = []
        for doc in doctors:
            if doc["id"] == doctor_id:
                all_slots_for_date = doc.get("slots", {}).get(date_str, [])
                break

        if not all_slots_for_date:
            return False, f"No scheduled slots for doctor {doctor_id} on {date_str}."

        if time_str not in all_slots_for_date:
            return False, (
                f"Time {time_str} is not a valid slot for {doctor_id} on {date_str}. "
                f"Valid slots: {', '.join(all_slots_for_date)}"
            )

        if time_str not in available:
            return False, f"Slot {time_str} on {date_str} is already booked."

        return True, ""
