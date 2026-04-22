"""
memory/session_store.py  —  STEP 8
Async Redis session memory with in-memory dict fallback.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis

from config.settings import settings

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_session(session_id: str, patient_phone: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "patient_phone": patient_phone,
        "language": "en",
        "history": [],
        "pending_action": None,
        "turn_count": 0,
        "started_at": _now_iso(),
        "last_active": _now_iso(),
    }


class SessionStore:
    """
    Primary: Redis async.
    Fallback: In-process dict (loses data on restart, but keeps server alive).
    """

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None
        self._fallback: dict[str, str] = {}
        self._use_redis: bool = False

    async def connect(self) -> None:
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                max_connections=20,
            )
            await self._redis.ping()
            self._use_redis = True
            logger.info("Redis connected at %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — using in-memory fallback.", exc)
            self._use_redis = False

    async def get_session(self, session_id: str, patient_phone: str = "") -> dict[str, Any]:
        raw = await self._get_raw(session_id)
        if raw is None:
            session = _empty_session(session_id, patient_phone)
            await self.save_session(session_id, session)
            return session
        return json.loads(raw)

    async def save_session(
        self, session_id: str, data: dict[str, Any], ttl: int = _DEFAULT_TTL
    ) -> None:
        data["last_active"] = _now_iso()
        raw = json.dumps(data, ensure_ascii=False)
        await self._set_raw(session_id, raw, ttl)

    async def add_turn(self, session_id: str, role: str, content: str) -> None:
        session = await self.get_session(session_id)
        history: list = session.get("history", [])
        history.append({"role": role, "content": content, "ts": _now_iso()})
        # Keep last 10 turns to limit context size
        session["history"] = history[-10:]
        session["turn_count"] = session.get("turn_count", 0) + 1
        await self.save_session(session_id, session)

    async def set_pending_action(self, session_id: str, action: Optional[dict]) -> None:
        session = await self.get_session(session_id)
        session["pending_action"] = action
        await self.save_session(session_id, session)

    async def get_pending_action(self, session_id: str) -> Optional[dict]:
        session = await self.get_session(session_id)
        return session.get("pending_action")

    async def update_language(self, session_id: str, language: str) -> None:
        session = await self.get_session(session_id)
        session["language"] = language
        await self.save_session(session_id, session)

    async def clear_session(self, session_id: str) -> None:
        if self._use_redis and self._redis:
            await self._redis.delete(f"session:{session_id}")
        else:
            self._fallback.pop(f"session:{session_id}", None)
        logger.info("Cleared session %s", session_id)

    @property
    def is_redis_connected(self) -> bool:
        return self._use_redis

    # ── Private ─────────────────────────────────────────────────────────

    async def _get_raw(self, session_id: str) -> Optional[str]:
        key = f"session:{session_id}"
        if self._use_redis and self._redis:
            return await self._redis.get(key)
        return self._fallback.get(key)

    async def _set_raw(self, session_id: str, raw: str, ttl: int) -> None:
        key = f"session:{session_id}"
        if self._use_redis and self._redis:
            await self._redis.setex(key, ttl, raw)
        else:
            self._fallback[key] = raw


# Module-level singleton
session_store = SessionStore()
