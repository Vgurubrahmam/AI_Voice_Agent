"""
utils/language_utils.py  —  STEP 15
Language detection and TTS/STT configuration mapping.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

LANGUAGE_CONFIG: dict[str, dict[str, str]] = {
    "en": {
        "name": "English",
        "tts_code": "en-IN",
        "tts_voice": "en-IN-Standard-D",
        "deepgram_code": "en",
    },
    "hi": {
        "name": "Hindi",
        "tts_code": "hi-IN",
        "tts_voice": "hi-IN-Standard-A",
        "deepgram_code": "hi",
    },
    "ta": {
        "name": "Tamil",
        "tts_code": "ta-IN",
        "tts_voice": "ta-IN-Standard-A",
        "deepgram_code": "ta",
    },
}

# Deepgram language code → our canonical code
_DEEPGRAM_MAP: dict[str, str] = {
    "en": "en",
    "en-IN": "en",
    "en-US": "en",
    "en-GB": "en",
    "hi": "hi",
    "hi-IN": "hi",
    "ta": "ta",
    "ta-IN": "ta",
}


async def detect_language(text: str) -> str:
    """
    Detect language from text using langdetect.
    Maps result to canonical en/hi/ta codes.
    Defaults to 'en' on failure.
    """
    if not text or not text.strip():
        return "en"

    try:
        from langdetect import detect, LangDetectException  # type: ignore
        detected = detect(text)
        mapped = _map_language(detected)
        logger.debug("Language detected: %s → mapped: %s (text: %s)", detected, mapped, text[:50])
        return mapped
    except Exception as exc:
        logger.warning("Language detection failed (%s), defaulting to 'en'.", exc)
        return "en"


def map_deepgram_language(deepgram_lang: str) -> str:
    """Map Deepgram language code to our canonical code."""
    return _DEEPGRAM_MAP.get(deepgram_lang, "en")


def get_language_config(lang: str) -> dict[str, str]:
    """Return TTS/STT config for a language. Falls back to English."""
    return LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG["en"])


def get_language_name(lang: str) -> str:
    return LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG["en"])["name"]


def _map_language(raw: str) -> str:
    """Map langdetect output to supported canonical codes."""
    raw = raw.lower().strip()
    if raw.startswith("hi"):
        return "hi"
    if raw.startswith("ta"):
        return "ta"
    if raw.startswith("en"):
        return "en"
    # Fallback: if unknown, return English
    return "en"
