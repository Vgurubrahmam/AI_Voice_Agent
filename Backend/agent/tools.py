"""
agent/tools.py  —  STEP 3
All tool definitions in OpenAI function-calling format.
The LLM decides which tool to call; nothing is hardcoded here.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Individual tool definitions
# ---------------------------------------------------------------------------

_get_available_slots: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_available_slots",
        "description": (
            "Get available appointment slots for a specific doctor on a given date. "
            "Always call this before booking to confirm slot availability."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {
                    "type": "string",
                    "description": "Unique doctor identifier, e.g. D001, D002, D003",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format",
                },
            },
            "required": ["doctor_id", "date"],
        },
    },
}

_book_appointment: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": (
            "Book a clinical appointment for a patient with a specific doctor. "
            "Only call after confirming the slot is available via get_available_slots."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {
                    "type": "string",
                    "description": "Patient's phone number (E.164 format)",
                },
                "doctor_id": {
                    "type": "string",
                    "description": "Unique doctor identifier",
                },
                "date": {
                    "type": "string",
                    "description": "Appointment date in YYYY-MM-DD format",
                },
                "time": {
                    "type": "string",
                    "description": "Appointment time in HH:MM 24-hour format",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Full name of the patient",
                },
            },
            "required": ["patient_phone", "doctor_id", "date", "time", "patient_name"],
        },
    },
}

_cancel_appointment: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cancel_appointment",
        "description": (
            "Cancel an existing appointment for a patient. "
            "Frees the slot for other patients."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {
                    "type": "string",
                    "description": "Patient's phone number",
                },
                "doctor_id": {
                    "type": "string",
                    "description": "Unique doctor identifier",
                },
                "date": {
                    "type": "string",
                    "description": "Appointment date in YYYY-MM-DD format",
                },
                "time": {
                    "type": "string",
                    "description": "Appointment time in HH:MM 24-hour format",
                },
            },
            "required": ["patient_phone", "doctor_id", "date", "time"],
        },
    },
}

_reschedule_appointment: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "reschedule_appointment",
        "description": (
            "Reschedule an existing appointment to a new date and time slot. "
            "Atomically cancels the old appointment and books the new one."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {
                    "type": "string",
                    "description": "Patient's phone number",
                },
                "doctor_id": {
                    "type": "string",
                    "description": "Unique doctor identifier",
                },
                "old_date": {
                    "type": "string",
                    "description": "Current appointment date in YYYY-MM-DD format",
                },
                "old_time": {
                    "type": "string",
                    "description": "Current appointment time in HH:MM format",
                },
                "new_date": {
                    "type": "string",
                    "description": "New appointment date in YYYY-MM-DD format",
                },
                "new_time": {
                    "type": "string",
                    "description": "New appointment time in HH:MM format",
                },
            },
            "required": [
                "patient_phone",
                "doctor_id",
                "old_date",
                "old_time",
                "new_date",
                "new_time",
            ],
        },
    },
}

_get_patient_history: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_patient_history",
        "description": (
            "Retrieve a patient's booking history, preferred language, and notes. "
            "Use to personalise the conversation and understand patient preferences."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_phone": {
                    "type": "string",
                    "description": "Patient's phone number",
                },
            },
            "required": ["patient_phone"],
        },
    },
}

_list_doctors: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_doctors",
        "description": (
            "List all available doctors. Optionally filter by medical specialty. "
            "Use to help patients find the right doctor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": (
                        "Medical specialty to filter by, e.g. 'Cardiology', "
                        "'Pediatrics', 'General Medicine'. Leave empty for all doctors."
                    ),
                },
            },
            "required": [],
        },
    },
}

_get_current_time: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": (
            "Get the current date and time in the server's local timezone. "
            "Use this when the patient or context requires knowing today's date or the current time, "
            "for example when booking an appointment for 'today' or 'tomorrow'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

# ---------------------------------------------------------------------------
# Exported registry  — imported by llm_service and pipeline
# ---------------------------------------------------------------------------

TOOLS_REGISTRY: list[dict[str, Any]] = [
    _get_available_slots,
    _book_appointment,
    _cancel_appointment,
    _reschedule_appointment,
    _get_patient_history,
    _list_doctors,
    _get_current_time,
]
