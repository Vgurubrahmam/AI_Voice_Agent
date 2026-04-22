"""
utils/latency_logger.py  —  STEP 14
Records per-turn latency to latency_log.jsonl.
Computes p50/p95/p99 percentile reports.
Colour-codes output: GREEN<450ms, YELLOW<600ms, RED>600ms.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)

LOG_FILE = Path("latency_log.jsonl")

# ANSI colours
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LatencyEntry(BaseModel):
    timestamp: str
    session_id: str
    stt_ms: float
    llm_ms: float
    tts_ms: float
    total_ms: float
    under_450ms: bool


class LatencyReport(BaseModel):
    total_entries: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    under_450_pct: float
    avg_stt_ms: float
    avg_llm_ms: float
    avg_tts_ms: float


# ---------------------------------------------------------------------------
# Logger class
# ---------------------------------------------------------------------------

class LatencyLogger:
    """
    Logs per-turn latency breakdown and persists to latency_log.jsonl.
    Provides percentile reports on demand.
    """

    def log(
        self,
        session_id: str,
        stt_ms: float,
        llm_ms: float,
        tts_ms: float,
    ) -> LatencyEntry:
        total = stt_ms + llm_ms + tts_ms
        entry = LatencyEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            stt_ms=round(stt_ms, 2),
            llm_ms=round(llm_ms, 2),
            tts_ms=round(tts_ms, 2),
            total_ms=round(total, 2),
            under_450ms=total < 450.0,
        )

        self._persist(entry)
        self._print(entry)
        return entry

    def get_report(self) -> Optional[LatencyReport]:
        entries = self._load_all()
        if not entries:
            return None

        totals = [e.total_ms for e in entries]
        stts = [e.stt_ms for e in entries]
        llms = [e.llm_ms for e in entries]
        ttss = [e.tts_ms for e in entries]
        under = sum(1 for e in entries if e.under_450ms)

        arr = np.array(totals)
        return LatencyReport(
            total_entries=len(entries),
            mean_ms=round(float(np.mean(arr)), 2),
            p50_ms=round(float(np.percentile(arr, 50)), 2),
            p95_ms=round(float(np.percentile(arr, 95)), 2),
            p99_ms=round(float(np.percentile(arr, 99)), 2),
            min_ms=round(float(np.min(arr)), 2),
            max_ms=round(float(np.max(arr)), 2),
            under_450_pct=round(under / len(entries) * 100, 1),
            avg_stt_ms=round(float(np.mean(stts)), 2),
            avg_llm_ms=round(float(np.mean(llms)), 2),
            avg_tts_ms=round(float(np.mean(ttss)), 2),
        )

    def get_all_entries(self) -> list[LatencyEntry]:
        return self._load_all()

    # ── Private ──────────────────────────────────────────────────────────

    def _persist(self, entry: LatencyEntry) -> None:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(entry.model_dump_json() + "\n")
                fh.flush()
        except OSError as exc:
            logger.error("Failed to write latency log: %s", exc)

    def _print(self, entry: LatencyEntry) -> None:
        if entry.total_ms < 450:
            colour = _GREEN
            label = "✓ FAST"
        elif entry.total_ms < 600:
            colour = _YELLOW
            label = "⚠ SLOW"
        else:
            colour = _RED
            label = "✗ OVER"

        print(
            f"{colour}{_BOLD}[LATENCY {label}]{_RESET} "
            f"STT={entry.stt_ms:.0f}ms | "
            f"LLM={entry.llm_ms:.0f}ms | "
            f"TTS={entry.tts_ms:.0f}ms | "
            f"{colour}TOTAL={entry.total_ms:.0f}ms{_RESET}"
        )

    def _load_all(self) -> list[LatencyEntry]:
        if not LOG_FILE.exists():
            return []
        entries: list[LatencyEntry] = []
        try:
            with LOG_FILE.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        entries.append(LatencyEntry(**json.loads(line)))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to read latency log: %s", exc)
        return entries


# Module-level singleton
latency_logger = LatencyLogger()
