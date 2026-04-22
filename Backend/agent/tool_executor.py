"""
agent/tool_executor.py  —  STEP 5
Executes tool calls from the LLM — all REAL function calls, nothing hardcoded.
Routes each tool_name to the correct domain function and logs to tracer.
"""

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any

from agent.reasoning_tracer import ReasoningTracer
from memory.patient_repository import PatientRepository
from scheduling.slot_manager import BookingRequest, slot_manager as _shared_slot_manager

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Dispatches LLM tool calls to real Python functions.
    Every execution is timed and logged to the ReasoningTracer.
    """

    def __init__(self, tracer: ReasoningTracer) -> None:
        self.tracer = tracer
        self.slot_manager = _shared_slot_manager  # singleton — shared bookings state
        self.patient_repo = PatientRepository()

    async def execute(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        patient_phone: str,
    ) -> dict[str, Any]:
        """
        Central dispatch point. Times the execution and logs to tracer.
        Returns a dict that gets serialised back into the LLM context.
        """
        start = time.perf_counter()

        try:
            result = await self._dispatch(tool_name, tool_args, patient_phone)
        except Exception as exc:
            logger.error("Tool %s failed with args %s: %s", tool_name, tool_args, exc)
            result = {"error": str(exc), "tool": tool_name}

        latency_ms = (time.perf_counter() - start) * 1000
        self.tracer.log_tool_call(tool_name, tool_args, result, latency_ms)
        return result

    async def _dispatch(
        self,
        tool_name: str,
        args: dict[str, Any],
        phone: str,
    ) -> dict[str, Any]:
        """Route to the correct handler function."""

        if tool_name == "get_available_slots":
            return await self._get_available_slots(args)

        if tool_name == "book_appointment":
            return await self._book_appointment(args, phone)

        if tool_name == "cancel_appointment":
            return await self._cancel_appointment(args, phone)

        if tool_name == "reschedule_appointment":
            return await self._reschedule_appointment(args, phone)

        if tool_name == "get_patient_history":
            return await self._get_patient_history(args)

        if tool_name == "list_doctors":
            return await self._list_doctors(args)

        if tool_name == "get_current_time":
            return self._get_current_time()

        logger.error("Unknown tool requested: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name}"}

    # ── Real tool implementations ─────────────────────────────────────────

    async def _get_available_slots(self, args: dict[str, Any]) -> dict[str, Any]:
        doctor_id: str = args["doctor_id"]
        date_str: str = args["date"]
        slots = await self.slot_manager.get_available_slots(doctor_id, date_str)
        doctors = await self.slot_manager.get_all_doctors()
        doctor_name = next((d["name"] for d in doctors if d["id"] == doctor_id), doctor_id)
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor_name,
            "date": date_str,
            "available_slots": slots,
            "slot_count": len(slots),
        }

    async def _book_appointment(
        self, args: dict[str, Any], phone: str
    ) -> dict[str, Any]:
        request = BookingRequest(
            patient_phone=args.get("patient_phone", phone),
            doctor_id=args["doctor_id"],
            date=args["date"],
            time=args["time"],
            patient_name=args.get("patient_name", "Patient"),
        )
        result = await self.slot_manager.book_slot(request)
        return result.model_dump()

    async def _cancel_appointment(
        self, args: dict[str, Any], phone: str
    ) -> dict[str, Any]:
        result = await self.slot_manager.cancel_slot(
            patient_phone=args.get("patient_phone", phone),
            doctor_id=args["doctor_id"],
            date_str=args["date"],
            time_str=args["time"],
        )
        return result.model_dump()

    async def _reschedule_appointment(
        self, args: dict[str, Any], phone: str
    ) -> dict[str, Any]:
        result = await self.slot_manager.reschedule_slot(
            patient_phone=args.get("patient_phone", phone),
            doctor_id=args["doctor_id"],
            old_date=args["old_date"],
            old_time=args["old_time"],
            new_date=args["new_date"],
            new_time=args["new_time"],
        )
        return result.model_dump()

    async def _get_patient_history(self, args: dict[str, Any]) -> dict[str, Any]:
        phone: str = args["patient_phone"]
        patient = await self.patient_repo.get_patient(phone)
        if patient is None:
            return {"found": False, "patient_phone": phone, "message": "No history found."}
        summary = await self.patient_repo.get_patient_summary(phone)
        return {
            "found": True,
            "patient": patient,
            "summary": summary,
        }

    async def _list_doctors(self, args: dict[str, Any]) -> dict[str, Any]:
        specialty: str | None = args.get("specialty")
        doctors = await self.slot_manager.get_all_doctors(specialty=specialty)
        today = date.today()
        allowed_dates = {
            today.isoformat(),
            (today + timedelta(days=1)).isoformat(),
        }

        compact_doctors: list[dict[str, Any]] = []
        for d in doctors:
            raw_slots = d.get("slots", {}) or {}
            filtered_slots = {
                dt: times for dt, times in raw_slots.items() if dt in allowed_dates
            }
            compact_doctors.append(
                {
                    **d,
                    "slots": filtered_slots,
                    "spoken_slots": {
                        dt: [self._format_time_for_speech(t) for t in times]
                        for dt, times in filtered_slots.items()
                    },
                }
            )
        return {
            "doctors": compact_doctors,
            "count": len(compact_doctors),
            "filter_applied": specialty or "none",
            "slot_window": "today_tomorrow",
        }

    @staticmethod
    def _get_current_time() -> dict[str, Any]:
        """Returns the current server date and time."""
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "readable": now.strftime("%B %d, %Y, %I:%M %p"),
        }

    @staticmethod
    def _format_time_for_speech(time_24h: str) -> str:
        """Convert HH:MM to 12-hour format for natural speech."""
        try:
            parsed = datetime.strptime(time_24h, "%H:%M")
            return parsed.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            return time_24h
