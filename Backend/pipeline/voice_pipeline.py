"""
pipeline/voice_pipeline.py  —  STEP 16
Pipecat WebSocket voice pipeline: VAD → STT → LLM (agentic) → TTS.
Each session gets its own tracer, tool_executor, and context.
"""

import logging
import time
from uuid import uuid4

from agent.llm_service import NVIDIALLMService
from agent.reasoning_tracer import ReasoningTracer
from agent.tool_executor import ToolExecutor
from memory.context_builder import ContextBuilder
from memory.patient_repository import PatientRepository
from memory.session_store import session_store
from speech.stt import STTService
from speech.tts import TTSService
from utils.language_utils import detect_language, map_deepgram_language
from utils.latency_logger import latency_logger

logger = logging.getLogger(__name__)


class VoicePipelineSession:
    """
    Manages one WebSocket voice session end-to-end.
    Handles VAD simulation, STT, agentic LLM, TTS, and latency tracking.

    In production with Pipecat, the Pipeline([...]) construct replaces this.
    Here we expose the session manager for direct WebSocket integration.
    """

    def __init__(self, patient_phone: str, session_id: str) -> None:
        self.patient_phone = patient_phone
        self.session_id = session_id
        self.tracer = ReasoningTracer(session_id)
        self.tool_executor = ToolExecutor(self.tracer)
        self.llm_service = NVIDIALLMService()
        self.stt_service = STTService()
        self.tts_service = TTSService()
        self.context_builder = ContextBuilder()
        self.patient_repo = PatientRepository()
        self._system_prompt: str = ""
        self._language: str = "en"

    async def initialise(self) -> None:
        """Set up patient context and build system prompt."""
        patient = await self.patient_repo.get_patient(self.patient_phone)
        self._language = patient.get("preferred_language", "en") if patient else "en"

        self._system_prompt = await self.context_builder.build_system_prompt(
            patient_phone=self.patient_phone,
            language=self._language,
            tracer=self.tracer,
        )
        logger.info("Pipeline initialised for %s (lang=%s)", self.patient_phone, self._language)

    async def process_audio_turn(self, audio_bytes: bytes) -> tuple[bytes, str, str]:
        """
        Process one complete VAD-gated audio turn:
        audio → STT → LLM (agentic) → TTS → audio bytes

        Returns: (tts_audio_bytes, agent_response_text, stt_transcript)
        """
        # ── STT ──────────────────────────────────────────────────────
        t0 = time.perf_counter()
        stt_result = await self.stt_service.transcribe_audio(audio_bytes, language="multi")
        stt_ms = (time.perf_counter() - t0) * 1000

        if not stt_result.success or not stt_result.transcript:
            logger.warning(
                "STT returned empty transcript (audio_bytes=%d, error=%s)",
                len(audio_bytes),
                stt_result.error,
            )
            fallback_text = "I could not clearly hear that. Please speak a little louder and try again."
            tts_result = await self.tts_service.synthesize(fallback_text, self._language)
            audio_out = tts_result.audio_bytes if tts_result.success else b""
            return audio_out, fallback_text, ""

        stt_transcript = stt_result.transcript

        # Update language if detected
        if stt_result.language and stt_result.language != self._language:
            self._language = stt_result.language
            self.tracer.log_language_detection(
                detected=stt_result.language,
                confidence=stt_result.confidence,
                text_preview=stt_transcript,
            )
            # Persist language preference
            await self.patient_repo.upsert_patient(
                phone=self.patient_phone, language=self._language
            )
            await session_store.update_language(self.session_id, self._language)

        # Add turn to session history
        await session_store.add_turn(self.session_id, "user", stt_transcript)

        # ── LLM Agentic Loop ─────────────────────────────────────────
        session = await session_store.get_session(self.session_id, self.patient_phone)
        history = [
            {"role": h["role"], "content": h["content"]}
            for h in session.get("history", [])
        ]

        patient_context = {"phone": self.patient_phone, "language": self._language}

        t1 = time.perf_counter()
        response_text, llm_ms = await self.llm_service.run_agent_turn(
            conversation_history=history,
            patient_context=patient_context,
            language=self._language,
            tracer=self.tracer,
            tool_executor=self.tool_executor,
            system_prompt=self._system_prompt,
        )

        # ── TTS ──────────────────────────────────────────────────────
        t2 = time.perf_counter()
        tts_result = await self.tts_service.synthesize(response_text, self._language)
        tts_ms = (time.perf_counter() - t2) * 1000

        # ── Latency logging ───────────────────────────────────────────
        latency_logger.log(
            session_id=self.session_id,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
        )

        # Save agent response to session
        await session_store.add_turn(self.session_id, "assistant", response_text)

        logger.info(
            "Turn complete: STT=%.0fms LLM=%.0fms TTS=%.0fms",
            stt_ms, llm_ms, tts_ms,
        )

        audio_out = tts_result.audio_bytes if tts_result.success else b""
        return audio_out, response_text, stt_transcript

    async def process_text_turn(self, text: str) -> str:
        """
        Process a text-based turn (for WebSocket text messages / REST testing).
        Skips STT, returns text response (no TTS).
        """
        # Detect language from text if not set
        if not self._language or self._language == "en":
            detected = await detect_language(text)
            if detected != self._language:
                self._language = detected
                await self.patient_repo.upsert_patient(
                    phone=self.patient_phone, language=self._language
                )

        await session_store.add_turn(self.session_id, "user", text)

        session = await session_store.get_session(self.session_id, self.patient_phone)
        history = [
            {"role": h["role"], "content": h["content"]}
            for h in session.get("history", [])
        ]

        patient_context = {"phone": self.patient_phone, "language": self._language}

        t0 = time.perf_counter()
        response_text, llm_ms = await self.llm_service.run_agent_turn(
            conversation_history=history,
            patient_context=patient_context,
            language=self._language,
            tracer=self.tracer,
            tool_executor=self.tool_executor,
            system_prompt=self._system_prompt,
        )
        stt_ms = 0.0
        tts_ms = 0.0

        latency_logger.log(
            session_id=self.session_id,
            stt_ms=stt_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
        )

        await session_store.add_turn(self.session_id, "assistant", response_text)
        return response_text


async def create_pipeline_session(
    patient_phone: str,
    session_id: str | None = None,
) -> VoicePipelineSession:
    """Factory function — creates and initialises a VoicePipelineSession."""
    sid = session_id or uuid4().hex
    session = VoicePipelineSession(patient_phone=patient_phone, session_id=sid)
    await session.initialise()
    return session
