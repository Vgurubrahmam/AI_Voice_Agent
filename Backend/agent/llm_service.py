"""
agent/llm_service.py  —  STEP 6  (CRITICAL)
NVIDIA NIM agentic loop: LLM decides tools → tools run → results fed back.
Real while-loop, real tool_calls from response, max 3 rounds.
"""

import json
import logging
import re
import time
from typing import Optional

from openai import AsyncOpenAI

from agent.reasoning_tracer import ReasoningTracer
from agent.tool_executor import ToolExecutor
from agent.tools import TOOLS_REGISTRY
from config.settings import settings

logger = logging.getLogger(__name__)

_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
_MODEL = "meta/llama-3.1-70b-instruct"
_MAX_ROUNDS = 3


class NVIDIALLMService:
    """
    Agentic LLM service backed by NVIDIA NIM (LLaMA 3.1 70B).
    Implements a real tool-calling loop — not simulated.
    """

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url=_NVIDIA_BASE_URL,
            api_key=settings.nvidia_api_key or "no-key-set",
        )
        self.model = _MODEL

    async def run_agent_turn(
        self,
        conversation_history: list[dict],
        patient_context: dict,
        language: str,
        tracer: ReasoningTracer,
        tool_executor: ToolExecutor,
        system_prompt: str,
    ) -> tuple[str, float]:
        """
        Run one full agent turn with the agentic tool-calling loop.

        Returns:
          (final_text_response, total_llm_latency_ms)
        """
        patient_phone = patient_context.get("phone", "unknown")
        messages = [{"role": "system", "content": system_prompt}] + conversation_history

        total_llm_ms = 0.0
        round_num = 0

        # ── Real agentic loop ────────────────────────────────────────────
        while round_num < _MAX_ROUNDS:
            round_num += 1
            logger.debug("LLM round %d for session %s", round_num, tracer.session_id)

            start = time.perf_counter()
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_REGISTRY,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=512,
                )
            except Exception as exc:
                logger.error("NVIDIA NIM call failed (round %d): %s", round_num, exc)
                return self._error_response(language), total_llm_ms

            round_ms = (time.perf_counter() - start) * 1000
            total_llm_ms += round_ms

            choice = response.choices[0]
            assistant_message = choice.message

            # -- Direct text response (no tool calls) ---------------------
            if not assistant_message.tool_calls:
                final_text = self._sanitize_user_facing_response(
                    assistant_message.content or ""
                )
                tracer.log_step(
                    step_type="response_generation",
                    input_data={"round": round_num, "history_len": len(messages)},
                    output_data={"response_length": len(final_text), "preview": final_text[:100]},
                    latency_ms=round_ms,
                    reasoning=(
                        f"LLM finished reasoning in round {round_num}. "
                        "No further tool calls needed. Generating final response."
                    ),
                )
                return final_text, total_llm_ms

            # -- Tool calls requested -------------------------------------
            tool_calls = assistant_message.tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            # Execute each tool
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                # Log the DECISION to call this tool
                tracer.log_tool_decision(
                    tool_name=tool_name,
                    args=tool_args,
                    reasoning=self._reasoning_for_tool(tool_name, tool_args, patient_phone),
                )

                # Execute the REAL tool function
                tool_result = await tool_executor.execute(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    patient_phone=patient_phone,
                )

                # Append tool result to messages for next LLM round
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        # Max rounds exhausted — return whatever the last message was
        logger.warning("Max LLM rounds (%d) reached for session %s", _MAX_ROUNDS, tracer.session_id)
        return (
            "I'm sorry, I wasn't able to complete that action. Please try again.",
            total_llm_ms,
        )

    async def simple_completion(self, messages: list[dict]) -> str:
        """
        Single-shot completion without tools.
        Used for outbound reminder text generation.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=150,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("Simple completion failed: %s", exc)
            return ""

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _reasoning_for_tool(
        tool_name: str, args: dict, patient_phone: str
    ) -> str:
        """Generate a human-readable reasoning string for each tool decision."""
        if tool_name == "get_available_slots":
            return (
                f"Patient requested an appointment with doctor {args.get('doctor_id')} on "
                f"{args.get('date')}. Calling get_available_slots to check real availability "
                "before attempting any booking."
            )
        if tool_name == "book_appointment":
            return (
                f"Available slots confirmed. Proceeding to book appointment for "
                f"{args.get('patient_name', patient_phone)} with {args.get('doctor_id')} "
                f"on {args.get('date')} at {args.get('time')}."
            )
        if tool_name == "cancel_appointment":
            return (
                f"Patient {patient_phone} requested cancellation of appointment with "
                f"{args.get('doctor_id')} on {args.get('date')} at {args.get('time')}."
            )
        if tool_name == "reschedule_appointment":
            return (
                f"Patient {patient_phone} wants to reschedule from "
                f"{args.get('old_date')} {args.get('old_time')} to "
                f"{args.get('new_date')} {args.get('new_time')}. "
                "Will atomically cancel old slot and book new one."
            )
        if tool_name == "get_patient_history":
            return (
                f"Retrieving patient history for {args.get('patient_phone', patient_phone)} "
                "to personalise the response based on prior interactions."
            )
        if tool_name == "list_doctors":
            specialty = args.get("specialty", "any specialty")
            return f"Patient asked about doctors. Listing all doctors for {specialty}."
        if tool_name == "get_current_time":
            return "Patient asked about the current date or time. Fetching server time."
        return f"Calling {tool_name} with args {args}."

    @staticmethod
    def _error_response(language: str) -> str:
        messages = {
            "hi": "मुझे खेद है, एक त्रुटि हुई। कृपया पुनः प्रयास करें।",
            "ta": "மன்னிக்கவும், ஒரு பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.",
            "en": "I'm sorry, there was an error processing your request. Please try again.",
        }
        return messages.get(language, messages["en"])

    @staticmethod
    def _sanitize_user_facing_response(text: str) -> str:
        """
        Remove agent/tool-planning meta text from user-facing replies.
        """
        cleaned = text.strip()
        if not cleaned:
            return "Hello! How can I help you today?"

        meta_patterns = [
            r"\bi don't have (?:a|any) (?:specific )?(?:function|tool) to call\b.*",
            r"\bno function call is required\b.*",
            r"\bno tool call is required\b.*",
            r"\bi (?:will|can) (?:not )?call (?:any )?(?:function|tool)\b.*",
        ]
        for pattern in meta_patterns:
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                return "Nice to meet you! How can I help you today?"

        return NVIDIALLMService._convert_24h_to_12h(cleaned)

    @staticmethod
    def _convert_24h_to_12h(text: str) -> str:
        """Convert plain HH:MM times in responses to 12-hour voice-friendly format."""
        def _replace(match: re.Match[str]) -> str:
            raw = match.group(0)
            try:
                parsed = time.strptime(raw, "%H:%M")
                formatted = time.strftime("%I:%M %p", parsed).lstrip("0")
                return formatted
            except ValueError:
                return raw

        # Do not touch times that already have AM/PM suffix.
        return re.sub(
            r"\b(?:[01]\d|2[0-3]):[0-5]\d\b(?!\s*(?:AM|PM)\b)",
            _replace,
            text,
            flags=re.IGNORECASE,
        )
