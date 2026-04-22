"""
speech/tts.py  —  STEP 13
Google Cloud TTS primary + gTTS fallback.
Supports streaming synthesis for low-latency voice output.
"""

import io
import logging
import time
from typing import AsyncIterator, Optional

from pydantic import BaseModel

from config.settings import settings
from utils.language_utils import get_language_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class TTSResult(BaseModel):
    audio_bytes: bytes
    latency_ms: float
    service_used: str  # "google" | "gtts" | "mock"
    success: bool
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# TTS Service
# ---------------------------------------------------------------------------

class TTSService:
    """
    Primary: Google Cloud Text-to-Speech.
    Fallback: gTTS (free, no credentials needed).
    Supports streaming for reduced first-byte latency.
    """

    async def synthesize(self, text: str, language: str = "en") -> TTSResult:
        """
        Synthesise text to audio bytes.
        Tries Google Cloud TTS first; falls back to gTTS if credentials missing.
        """
        start = time.perf_counter()
        lang_cfg = get_language_config(language)

        import os
        creds_path = settings.google_credentials_json
        creds_valid = bool(creds_path and os.path.isfile(creds_path))

        if creds_valid:
            result = await self._google_tts(text, lang_cfg, start)
            if result.success:
                return result
            logger.warning("Google TTS failed, falling back to gTTS: %s", result.error)

        return await self._gtts_fallback(text, lang_cfg, start)

    async def synthesize_streaming(
        self, text: str, language: str = "en", chunk_size: int = 4096
    ) -> AsyncIterator[bytes]:
        """
        Streaming TTS — yields audio chunks as soon as synthesis completes.
        For true streaming, the full audio is synthesised then chunked.
        Google Cloud TTS streaming API can be added here for production.
        """
        result = await self.synthesize(text, language)
        if not result.success or not result.audio_bytes:
            logger.error("Streaming TTS synthesis failed: %s", result.error)
            return

        audio = result.audio_bytes
        for offset in range(0, len(audio), chunk_size):
            yield audio[offset: offset + chunk_size]

    # ── Google Cloud TTS ─────────────────────────────────────────────────

    async def _google_tts(
        self, text: str, lang_cfg: dict, start: float
    ) -> TTSResult:
        try:
            import os
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_credentials_json

            from google.cloud import texttospeech  # type: ignore

            client = texttospeech.TextToSpeechAsyncClient()

            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=lang_cfg["tts_code"],
                name=lang_cfg["tts_voice"],
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0,
            )

            response = await client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )

            latency_ms = (time.perf_counter() - start) * 1000
            return TTSResult(
                audio_bytes=response.audio_content,
                latency_ms=round(latency_ms, 2),
                service_used="google",
                success=True,
            )

        except ImportError:
            return TTSResult(
                audio_bytes=b"",
                latency_ms=0.0,
                service_used="google",
                success=False,
                error="google-cloud-texttospeech not installed",
            )
        except Exception as exc:
            logger.error("Google TTS error: %s", exc)
            return TTSResult(
                audio_bytes=b"",
                latency_ms=(time.perf_counter() - start) * 1000,
                service_used="google",
                success=False,
                error=str(exc),
            )

    # ── gTTS Fallback ─────────────────────────────────────────────────────

    async def _gtts_fallback(
        self, text: str, lang_cfg: dict, start: float
    ) -> TTSResult:
        try:
            import asyncio
            from gtts import gTTS  # type: ignore

            # Map our tts_code to gTTS lang code (first 2 chars)
            gtts_lang = lang_cfg["tts_code"].split("-")[0]

            def _synth() -> bytes:
                tts = gTTS(text=text, lang=gtts_lang, slow=False)
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                return buf.getvalue()

            # Run blocking gTTS in thread pool
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, _synth)

            latency_ms = (time.perf_counter() - start) * 1000
            return TTSResult(
                audio_bytes=audio_bytes,
                latency_ms=round(latency_ms, 2),
                service_used="gtts",
                success=True,
            )

        except ImportError:
            logger.error("gTTS not installed. Install with: pip install gtts")
            return TTSResult(
                audio_bytes=b"",
                latency_ms=(time.perf_counter() - start) * 1000,
                service_used="mock",
                success=False,
                error="No TTS service available. Install gtts or configure Google credentials.",
            )
        except Exception as exc:
            logger.error("gTTS error: %s", exc)
            return TTSResult(
                audio_bytes=b"",
                latency_ms=(time.perf_counter() - start) * 1000,
                service_used="gtts",
                success=False,
                error=str(exc),
            )


# Module-level singleton
tts_service = TTSService()
