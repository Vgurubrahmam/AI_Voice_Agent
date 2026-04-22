"""
config/settings.py
Centralised configuration using pydantic-settings.
All secrets must live in .env — never hardcoded here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────
    nvidia_api_key: str = ""

    # ── STT ──────────────────────────────────────────────────────
    deepgram_api_key: str = ""

    # ── TTS ──────────────────────────────────────────────────────
    google_credentials_json: str = ""   # path to service-account JSON

    # ── Twilio ────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ── Infrastructure ────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    database_url: str = "sqlite+aiosqlite:///./voice_agent.db"

    # ── App ───────────────────────────────────────────────────────
    base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    environment: str = "development"

    # ── Latency targets (ms) ──────────────────────────────────────
    stt_target_ms: float = 120.0
    llm_target_ms: float = 200.0
    tts_target_ms: float = 100.0
    total_target_ms: float = 450.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton — import this everywhere
settings = Settings()
