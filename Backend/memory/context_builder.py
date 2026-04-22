"""
memory/context_builder.py  —  STEP 9
Builds the LLM system prompt by injecting memory — this is what makes
memory VISIBLY AFFECT LLM behavior.
"""

import logging
from datetime import date

from agent.reasoning_tracer import ReasoningTracer
from memory.patient_repository import PatientRepository
from scheduling.slot_manager import slot_manager as _shared_slot_manager
from utils.language_utils import get_language_config

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}


class ContextBuilder:
    """
    Assembles the LLM system prompt from:
      1. Patient history (long-term SQLite memory)
      2. Current language preference
      3. Available doctors
      4. Today's date
    The tracer logs exactly what memory was retrieved.
    """

    def __init__(self) -> None:
        self._patient_repo = PatientRepository()
        self._slot_manager = _shared_slot_manager  # singleton — shared bookings state

    async def build_system_prompt(
        self,
        patient_phone: str,
        language: str,
        tracer: ReasoningTracer,
    ) -> str:
        # 1. Patient memory retrieval — time the actual DB query
        import time as _time
        _t0 = _time.perf_counter()
        patient_summary = await self._patient_repo.get_patient_summary(patient_phone)
        _mem_ms = (_time.perf_counter() - _t0) * 1000
        tracer.log_memory_retrieval(patient_phone, patient_summary, latency_ms=_mem_ms)

        # 2. Current date
        today = date.today().isoformat()

        # 3. Doctor list
        doctors = await self._slot_manager.get_all_doctors()
        doctor_lines = "\n".join(
            f"  • {d['id']}: {d['name']} ({d['specialty']}) — "
            f"Languages: {', '.join(d['language_support'])}"
            for d in doctors
        )

        # 4. Language config
        lang_name = _LANGUAGE_NAMES.get(language, "English")
        lang_cfg = get_language_config(language)

        return f"""You are a clinical appointment booking assistant for a multilingual healthcare centre.
Your primary role is to help patients book, cancel, or reschedule medical appointments.

═══════════════════════════════════════════
LANGUAGE DIRECTIVE
═══════════════════════════════════════════
ALWAYS respond in {lang_name} ({lang_cfg['tts_code']}).
Never switch languages during a conversation.
If the patient writes in a different language, still respond in {lang_name}.

═══════════════════════════════════════════
PATIENT MEMORY (retrieved from database)
═══════════════════════════════════════════
Patient phone: {patient_phone}
{patient_summary}

This context was retrieved from persistent memory and MUST influence your responses.
If the patient is returning, acknowledge their history. If they have a preferred doctor,
suggest that doctor first. If they prefer morning slots, note that.

IMPORTANT: Do NOT call get_patient_history at the start of the conversation.
The patient history above is already loaded. Only call get_patient_history if asked
about a DIFFERENT patient by name or phone number.

═══════════════════════════════════════════
AVAILABLE DOCTORS
═══════════════════════════════════════════
{doctor_lines}

═══════════════════════════════════════════
TODAY: {today}
═══════════════════════════════════════════

═══════════════════════════════════════════
TOOL USE POLICY
═══════════════════════════════════════════
You have access to booking tools. Follow these rules strictly:

1. ALWAYS call get_available_slots before booking any appointment.
2. NEVER invent or assume slot availability — always check via tools.
3. If a booking fails, offer the alternatives returned by the tool.
4. ALWAYS call list_doctors when the patient asks about doctors or specialties.
5. Use get_patient_history ONLY to look up a different patient — NOT the current one.
6. Use get_current_time if the patient asks about today's date or time.
7. Before each tool call, state in your reasoning WHY you are calling it.
8. For initial availability suggestions, offer only today/tomorrow slots unless patient asks for another date range.
9. Always present times in 12-hour format (e.g., 2:00 PM), never 24-hour format like 14:00.
10. Keep slot suggestions concise: maximum 3-5 options per response.

═══════════════════════════════════════════
CONFLICT RULES
═══════════════════════════════════════════
- If a slot is already booked → offer exactly 3 alternatives from tool results.
- If the patient requests a past date → reject and suggest tomorrow's date.
- Rescheduling is atomic — cancel old slot first, then book new one.

Be warm, professional, and empathetic. Keep responses concise for voice output.
"""

    async def build_minimal_prompt(self, language: str) -> str:
        """Lightweight prompt for when patient phone is unknown."""
        lang_name = _LANGUAGE_NAMES.get(language, "English")
        return (
            f"You are a clinical appointment booking assistant. "
            f"Always respond in {lang_name}. "
            "Use your tools to check availability before booking."
        )
