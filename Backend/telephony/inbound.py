"""
telephony/inbound.py  —  STEP 18a
Handles incoming Twilio calls via TwiML and webhook processing.
"""

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


def generate_twiml(phone: str, base_url: str) -> str:
    """
    Generate TwiML that streams inbound call audio to our WebSocket endpoint.
    The <Stream> verb connects Twilio's media stream to our FastAPI WebSocket.
    """
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = ws_url.rstrip("/")
    stream_url = f"{ws_url}/ws/voice/{phone}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="phone" value="{phone}" />
        </Stream>
    </Connect>
</Response>"""
    logger.info("Generated TwiML for %s → %s", phone, stream_url)
    return twiml


async def handle_inbound_webhook(form_data: dict[str, Any]) -> str:
    """
    Parse Twilio inbound webhook POST data and return TwiML response.
    Extracts caller's phone number and routes to our voice pipeline.
    """
    caller_phone = form_data.get("From", "unknown")
    called_number = form_data.get("To", settings.twilio_phone_number)
    call_sid = form_data.get("CallSid", "")

    logger.info(
        "Inbound call: from=%s to=%s sid=%s",
        caller_phone, called_number, call_sid,
    )

    twiml = generate_twiml(phone=caller_phone, base_url=settings.base_url)
    return twiml


async def handle_status_callback(form_data: dict[str, Any]) -> dict[str, Any]:
    """
    Handle Twilio call status callbacks.
    Returns a summary dict for logging/monitoring.
    """
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "unknown")
    duration = form_data.get("CallDuration", "0")
    caller = form_data.get("From", "unknown")

    logger.info(
        "Call status update: sid=%s status=%s duration=%ss from=%s",
        call_sid, call_status, duration, caller,
    )

    return {
        "call_sid": call_sid,
        "status": call_status,
        "duration_seconds": int(duration),
        "caller": caller,
    }
