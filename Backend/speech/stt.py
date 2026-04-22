"""
speech/stt.py  —  STEP 12
Deepgram async STT wrapper.
Returns STTResult with transcript, language, confidence, latency.
"""

import logging
import time
from typing import Optional

import httpx
from pydantic import BaseModel

from config.settings import settings
from utils.language_utils import map_deepgram_language

logger = logging.getLogger(__name__)

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class STTResult(BaseModel):
    transcript: str
    language: str
    confidence: float
    latency_ms: float
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# STT Service
# ---------------------------------------------------------------------------

class STTService:
    """
    Wraps Deepgram Nova-2 multilingual STT.
    On failure returns empty STTResult with success=False.
    """

    def __init__(self) -> None:
        self._api_key = settings.deepgram_api_key
        self._auth_header = {"Authorization": f"Token {self._api_key}"}

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "multi",
        sample_rate: int = 16000,
    ) -> STTResult:
        """
        Send audio bytes to Deepgram and return transcript with metadata.
        language='multi' enables automatic multilingual detection.
        """
        start = time.perf_counter()

        params = {
            "model": "nova-2",
            "language": language,
            "smart_format": "true",
            "punctuate": "true",
            "diarize": "false",
        }

        if not self._api_key:
            logger.warning("Deepgram API key not set — returning mock STT result.")
            return self._mock_result(start)

        try:
            content_type = self._detect_content_type(audio_bytes)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    DEEPGRAM_API_URL,
                    headers={**self._auth_header, "Content-Type": content_type},
                    params=params,
                    content=audio_bytes,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.perf_counter() - start) * 1000
            return self._parse_response(data, latency_ms)

        except httpx.HTTPStatusError as exc:
            logger.error("Deepgram HTTP error: %s %s", exc.response.status_code, exc.response.text)
            return STTResult(
                transcript="",
                language="en",
                confidence=0.0,
                latency_ms=(time.perf_counter() - start) * 1000,
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.error("Deepgram transcription failed: %s", exc)
            return STTResult(
                transcript="",
                language="en",
                confidence=0.0,
                latency_ms=(time.perf_counter() - start) * 1000,
                success=False,
                error=str(exc),
            )

    @staticmethod
    def _detect_content_type(audio_bytes: bytes) -> str:
        """
        Infer container type from magic bytes.
        Browser MediaRecorder commonly sends WebM/Opus.
        """
        if audio_bytes.startswith(b"RIFF"):
            return "audio/wav"
        if audio_bytes.startswith(b"OggS"):
            return "audio/ogg"
        if audio_bytes.startswith(b"ID3") or audio_bytes[:2] == b"\xff\xfb":
            return "audio/mpeg"
        if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            return "audio/webm"
        return "application/octet-stream"

    @staticmethod
    def _parse_response(data: dict, latency_ms: float) -> STTResult:
        try:
            channel = data["results"]["channels"][0]
            alternative = channel["alternatives"][0]
            transcript = alternative.get("transcript", "")
            confidence = alternative.get("confidence", 0.0)
            detected_lang = channel.get("detected_language", "en")
            canonical_lang = map_deepgram_language(detected_lang)
            return STTResult(
                transcript=transcript,
                language=canonical_lang,
                confidence=confidence,
                latency_ms=round(latency_ms, 2),
                success=bool(transcript),
            )
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Failed to parse Deepgram response: %s", exc)
            return STTResult(
                transcript="",
                language="en",
                confidence=0.0,
                latency_ms=round(latency_ms, 2),
                success=False,
                error=f"Parse error: {exc}",
            )

    @staticmethod
    def _mock_result(start: float) -> STTResult:
        """Returns a mock result when API key is missing (dev/test mode)."""
        return STTResult(
            transcript="[Mock STT — configure DEEPGRAM_API_KEY]",
            language="en",
            confidence=1.0,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            success=True,
        )


# Convenience function
async def transcribe_audio(audio_bytes: bytes) -> STTResult:
    return await STTService().transcribe_audio(audio_bytes)
