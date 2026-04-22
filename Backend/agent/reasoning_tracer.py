"""
agent/reasoning_tracer.py  —  STEP 4
Makes every reasoning step VISIBLE and AUDITABLE.
Writes to reasoning_trace.jsonl + coloured console output.
"""

import json
import logging

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# ANSI colour codes
_COLOURS = {
    "memory_retrieval":   "\033[94m",   # blue
    "tool_decision":      "\033[93m",   # yellow
    "tool_execution":     "\033[92m",   # green
    "conflict_resolution": "\033[91m",  # red
    "language_detection": "\033[95m",   # magenta
    "response_generation": "\033[96m",  # cyan
}
_RESET = "\033[0m"
_BOLD = "\033[1m"

TRACE_FILE = Path("reasoning_trace.jsonl")


class ReasoningTracer:
    """
    Logs every reasoning step taken by the agent during a session turn.
    Each step is written immediately to reasoning_trace.jsonl so judges
    can see the agent's decision-making in real time.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.trace_id = uuid4().hex[:8]
        self.steps: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core logging method
    # ------------------------------------------------------------------

    def log_step(
        self,
        step_type: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        latency_ms: float,
        reasoning: str,
    ) -> None:
        """Record one reasoning step, persist to file, and print to console."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "step_type": step_type,
            "input": input_data,
            "output": output_data,
            "latency_ms": round(latency_ms, 2),
            "reasoning": reasoning,
        }
        self.steps.append(entry)
        self._persist(entry)
        self._print(entry)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def log_memory_retrieval(
        self, phone: str, retrieved_context: str, latency_ms: float = 0.0
    ) -> None:
        """
        Log a memory retrieval step.
        Pass latency_ms measured around the actual DB query in the caller.
        """
        self.log_step(
            step_type="memory_retrieval",
            input_data={"patient_phone": phone},
            output_data={"context_length": len(retrieved_context), "preview": retrieved_context[:200]},
            latency_ms=latency_ms,
            reasoning=(
                f"Retrieving patient history for {phone} to personalise the system prompt. "
                "This context is injected into LLM system message to influence behaviour."
            ),
        )

    def log_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        latency_ms: float,
    ) -> None:
        self.log_step(
            step_type="tool_execution",
            input_data={"tool": tool_name, "args": args},
            output_data=result,
            latency_ms=latency_ms,
            reasoning=(
                f"Executing {tool_name} with args {args}. "
                "Real function call — result will be fed back to LLM context."
            ),
        )

    def log_tool_decision(
        self,
        tool_name: str,
        args: dict[str, Any],
        reasoning: str,
    ) -> None:
        self.log_step(
            step_type="tool_decision",
            input_data={"requested_tool": tool_name, "args": args},
            output_data={"decision": "execute"},
            latency_ms=0.0,
            reasoning=reasoning,
        )

    def log_conflict(
        self,
        requested_slot: dict[str, Any],
        alternatives_offered: list[dict[str, Any]],
    ) -> None:
        self.log_step(
            step_type="conflict_resolution",
            input_data={"requested_slot": requested_slot},
            output_data={"alternatives_count": len(alternatives_offered), "alternatives": alternatives_offered},
            latency_ms=0.0,
            reasoning=(
                f"Slot {requested_slot} is already booked. "
                f"Offering {len(alternatives_offered)} alternative slots to patient."
            ),
        )

    def log_language_detection(
        self, detected: str, confidence: float, text_preview: str
    ) -> None:
        self.log_step(
            step_type="language_detection",
            input_data={"text_preview": text_preview[:100]},
            output_data={"detected_language": detected, "confidence": confidence},
            latency_ms=0.0,
            reasoning=(
                f"Detected language '{detected}' with confidence {confidence:.2f}. "
                "TTS voice and LLM response language will be set accordingly."
            ),
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_full_trace(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "total_steps": len(self.steps),
            "steps": self.steps,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _persist(self, entry: dict[str, Any]) -> None:
        try:
            with TRACE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                fh.flush()
        except OSError as exc:
            logger.error("Failed to write reasoning trace: %s", exc)

    def _print(self, entry: dict[str, Any]) -> None:
        colour = _COLOURS.get(entry["step_type"], "\033[0m")
        step_label = entry["step_type"].upper().replace("_", " ")
        print(
            f"{colour}{_BOLD}[TRACE {entry['trace_id']}] {step_label}{_RESET} "
            f"| session={entry['session_id']} "
            f"| latency={entry['latency_ms']:.1f}ms\n"
            f"  {colour}↳ {entry['reasoning'][:120]}{_RESET}"
        )
