"""
telephony/outbound.py  —  STEP 18b
Outbound Twilio calls: appointment reminders + campaign management.
"""

import logging
from typing import Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


async def make_reminder_call(phone: str, booking: dict) -> dict[str, Any]:
    """
    Initiate an outbound reminder call via Twilio REST API.
    Generates a personalised message using NVIDIA NIM.
    Returns call SID and status.
    """
    if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_phone_number]):
        logger.warning("Twilio credentials not configured — skipping outbound call to %s", phone)
        return {
            "success": False,
            "error": "Twilio credentials not configured.",
            "phone": phone,
        }

    try:
        import asyncio
        from twilio.rest import Client  # type: ignore

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        # Generate personalised reminder message via LLM
        reminder_text = await _generate_reminder_text(booking)

        # TwiML for the outbound call
        twiml = _build_reminder_twiml(reminder_text)

        # Run the synchronous Twilio SDK call in a thread-pool executor
        # to avoid blocking the asyncio event loop.
        loop = asyncio.get_event_loop()
        call = await loop.run_in_executor(
            None,
            lambda: client.calls.create(
                to=phone,
                from_=settings.twilio_phone_number,
                twiml=twiml,
            ),
        )

        logger.info("Outbound reminder call initiated: sid=%s to=%s", call.sid, phone)
        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "phone": phone,
            "booking": booking,
        }

    except ImportError:
        logger.error("twilio package not installed.")
        return {"success": False, "error": "twilio not installed", "phone": phone}
    except Exception as exc:
        logger.error("Outbound call failed for %s: %s", phone, exc)
        return {"success": False, "error": str(exc), "phone": phone}


async def run_campaign(
    phones: list[str],
    campaign_type: str,
    booking_data: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Run an outbound calling campaign for a list of phone numbers.
    Returns aggregate stats: total, success, failed.
    """
    logger.info("Starting %s campaign for %d patients", campaign_type, len(phones))

    results: list[dict] = []
    success_count = 0
    failed_count = 0

    for phone in phones:
        booking = booking_data or {"type": campaign_type}
        result = await make_reminder_call(phone, booking)
        results.append(result)
        if result.get("success"):
            success_count += 1
        else:
            failed_count += 1

    logger.info(
        "Campaign complete: total=%d success=%d failed=%d",
        len(phones), success_count, failed_count,
    )

    return {
        "campaign_type": campaign_type,
        "total": len(phones),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }


# ── Private helpers ───────────────────────────────────────────────────────

async def _generate_reminder_text(booking: dict) -> str:
    """Generate a personalised reminder message using NVIDIA NIM."""
    try:
        from agent.llm_service import NVIDIALLMService
        llm = NVIDIALLMService()
        prompt = (
            f"Generate a brief, friendly appointment reminder message (under 30 words) for: "
            f"Doctor: {booking.get('doctor_name', 'your doctor')}, "
            f"Date: {booking.get('date', 'your appointment date')}, "
            f"Time: {booking.get('time', 'your appointment time')}."
        )
        text = await llm.simple_completion([{"role": "user", "content": prompt}])
        return text or _default_reminder_text(booking)
    except Exception as exc:
        logger.warning("LLM reminder generation failed: %s", exc)
        return _default_reminder_text(booking)


def _default_reminder_text(booking: dict) -> str:
    return (
        f"Hello, this is a reminder for your appointment with "
        f"{booking.get('doctor_name', 'your doctor')} "
        f"on {booking.get('date', '')} at {booking.get('time', '')}. "
        "Please call us if you need to reschedule."
    )


def _build_reminder_twiml(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{escaped}</Say>
    <Pause length="1"/>
    <Say voice="Polly.Aditi">Press 1 to confirm, or 2 to reschedule.</Say>
</Response>"""
