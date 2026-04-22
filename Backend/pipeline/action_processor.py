"""
pipeline/action_processor.py  —  STEP 17
Intercepts Pipecat LLM frames, executes real tools, converts results to speech.
"""

import logging
from typing import Any

from agent.reasoning_tracer import ReasoningTracer
from agent.tool_executor import ToolExecutor
from memory.patient_repository import PatientRepository

logger = logging.getLogger(__name__)

# Language-aware response templates
_RESPONSE_TEMPLATES: dict[str, dict[str, str]] = {
    "book_success": {
        "en": "Confirmed! Your appointment with {doctor_name} is booked for {date} at {time}.",
        "hi": "पक्का हो गया! आपकी {doctor_name} के साथ {date} को {time} बजे अपॉइंटमेंट बुक हो गई।",
        "ta": "உறுதிப்படுத்தப்பட்டது! உங்கள் {doctor_name} உடனான சந்திப்பு {date} அன்று {time} மணிக்கு பதிவு செய்யப்பட்டது.",
    },
    "book_fail": {
        "en": "Sorry, that slot is taken. Available alternatives: {alternatives}",
        "hi": "खेद है, वह समय उपलब्ध नहीं है। उपलब्ध विकल्प: {alternatives}",
        "ta": "மன்னிக்கவும், அந்த நேரம் கிடைக்கவில்லை. கிடைக்கும் மாற்று நேரங்கள்: {alternatives}",
    },
    "slots_available": {
        "en": "Available slots with {doctor_name} on {date}: {slots}",
        "hi": "{doctor_name} के साथ {date} को उपलब्ध समय: {slots}",
        "ta": "{doctor_name} உடன் {date} அன்று கிடைக்கும் நேரங்கள்: {slots}",
    },
    "slots_none": {
        "en": "No slots available with {doctor_name} on {date}.",
        "hi": "{doctor_name} के साथ {date} को कोई स्लॉट उपलब्ध नहीं है।",
        "ta": "{doctor_name} உடன் {date} அன்று நேரம் எதுவும் கிடைக்கவில்லை.",
    },
    "cancel_success": {
        "en": "Your appointment has been cancelled successfully.",
        "hi": "आपकी अपॉइंटमेंट रद्द कर दी गई है।",
        "ta": "உங்கள் சந்திப்பு வெற்றிகரமாக ரத்து செய்யப்பட்டது.",
    },
    "cancel_fail": {
        "en": "Could not cancel the appointment: {reason}",
        "hi": "अपॉइंटमेंट रद्द नहीं हो सकी: {reason}",
        "ta": "சந்திப்பை ரத்து செய்ய முடியவில்லை: {reason}",
    },
    "reschedule_success": {
        "en": "Rescheduled! Your new appointment is on {date} at {time} with {doctor_name}.",
        "hi": "पुनर्निर्धारित! आपकी नई अपॉइंटमेंट {date} को {time} बजे {doctor_name} के साथ है।",
        "ta": "மாற்று நேரம் பதிவு செய்யப்பட்டது! உங்கள் புதிய சந்திப்பு {date} அன்று {time} மணிக்கு {doctor_name} உடன் உள்ளது.",
    },
}


class ActionProcessor:
    """
    Processes tool call results and converts them to patient-friendly speech.
    Also updates the patient database when bookings change.
    """

    def __init__(
        self,
        tool_executor: ToolExecutor,
        tracer: ReasoningTracer,
        patient_phone: str,
        language: str = "en",
    ) -> None:
        self.tool_executor = tool_executor
        self.tracer = tracer
        self.patient_phone = patient_phone
        self.language = language
        self.patient_repo = PatientRepository()

    async def process_tool_call(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> str:
        """
        Execute tool, update patient DB if needed, return natural language text.
        This is what gets sent to TTS.
        """
        result = await self.tool_executor.execute(tool_name, tool_args, self.patient_phone)

        # Update patient DB on successful booking
        if tool_name == "book_appointment" and result.get("success"):
            booking = result.get("booking", {})
            await self.patient_repo.upsert_patient(
                phone=self.patient_phone,
                name=tool_args.get("patient_name"),
                booking=booking,
            )
            logger.info("Updated patient DB after booking: %s", self.patient_phone)

        return self._result_to_speech(tool_name, result)

    def _result_to_speech(self, tool_name: str, result: dict[str, Any]) -> str:
        """Convert tool result dict to natural-language speech text."""
        lang = self.language
        templates = _RESPONSE_TEMPLATES

        if tool_name == "book_appointment":
            if result.get("success"):
                booking = result.get("booking", {})
                return templates["book_success"][lang].format(
                    doctor_name=booking.get("doctor_name", "the doctor"),
                    date=booking.get("date", ""),
                    time=booking.get("time", ""),
                )
            else:
                alts = result.get("alternatives", [])
                alt_str = ", ".join(
                    f"{a.get('date')} at {a.get('time')}" for a in alts
                ) if alts else "none available"
                return templates["book_fail"][lang].format(alternatives=alt_str)

        if tool_name == "get_available_slots":
            slots = result.get("available_slots", [])
            doctor_name = result.get("doctor_name", "the doctor")
            date_str = result.get("date", "")
            if slots:
                readable = ", ".join(slots)
                return templates["slots_available"][lang].format(
                    doctor_name=doctor_name, date=date_str, slots=readable
                )
            return templates["slots_none"][lang].format(
                doctor_name=doctor_name, date=date_str
            )

        if tool_name == "cancel_appointment":
            if result.get("success"):
                return templates["cancel_success"][lang]
            return templates["cancel_fail"][lang].format(
                reason=result.get("reason", "unknown error")
            )

        if tool_name == "reschedule_appointment":
            if result.get("success"):
                booking = result.get("booking", {})
                return templates["reschedule_success"][lang].format(
                    doctor_name=booking.get("doctor_name", "your doctor"),
                    date=booking.get("date", ""),
                    time=booking.get("time", ""),
                )
            alts = result.get("alternatives", [])
            alt_str = ", ".join(f"{a.get('date')} at {a.get('time')}" for a in alts)
            reason = result.get("reason", "")
            return (
                f"Could not reschedule: {reason}. "
                + (f"Try: {alt_str}" if alt_str else "")
            )

        if tool_name == "get_patient_history":
            if result.get("found"):
                return result.get("summary", "History retrieved.")
            return "No history found for this patient."

        if tool_name == "list_doctors":
            doctors = result.get("doctors", [])
            if not doctors:
                return "No doctors found."
            names = "; ".join(
                f"{d['name']} ({d['specialty']})" for d in doctors
            )
            return f"Available doctors: {names}."

        # Generic fallback
        return str(result)
