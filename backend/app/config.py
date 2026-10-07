"""Application configuration sourced from environment variables.

All development and tests default to the mock Kite service, so the app boots
cleanly without real Zerodha credentials or a Fernet key.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Zerodha Kite Connect -------------------------------------------------
    kite_api_key: str = "mock-api-key"
    kite_api_secret: str = "mock-api-secret"
    # Where Kite redirects the browser after login. The frontend hosts the
    # callback page which forwards the request_token to the backend.
    kite_redirect_url: str = "http://localhost:3001/auth/kite/callback"
    use_mock_kite: bool = True

    # --- Security -------------------------------------------------------------
    # Fernet key for encrypting the Kite access token at rest. Optional so that
    # mock-mode development runs without a real key; a clear error is raised only
    # if encryption is actually attempted without one. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str | None = None
    # App login password (Phase 40). Empty = auth disabled (local/mock); set it to
    # gate the app before execution / public deploy.
    app_password: str | None = None

    # --- Database -------------------------------------------------------------
    database_url: str = (
        "postgresql+asyncpg://wealthpilot:wealthpilot@localhost:5432/wealthpilot"
    )

    # --- Risk engine (gRPC) ---------------------------------------------------
    risk_engine_host: str = "localhost"
    risk_engine_port: int = 50051
    simulation_paths: int = 10_000
    # When true, goal simulations use a lightweight in-process approximation
    # instead of the C++ gRPC engine — lets the backend run/test without it.
    use_mock_risk_engine: bool = True

    # --- HTTP / CORS ----------------------------------------------------------
    frontend_origin: str = "http://localhost:3001"

    # --- Caching --------------------------------------------------------------
    kite_cache_ttl_seconds: int = 60
    # Redis-backed Kite cache when set (e.g. redis://redis:6379/0); in-process otherwise.
    redis_url: str | None = None
    # "memory" (default, tests/bare-local) | "postgres" (compose default) | "redis"
    cache_backend: str = "memory"

    # --- AI (docs/AI_ROADMAP.md) ---------------------------------------------
    anthropic_api_key: str | None = None
    ai_model: str = "claude-haiku-4-5-20251001"
    ai_chat_model: str = "claude-sonnet-5"
    ollama_url: str | None = None          # e.g. http://<3070-pc>:11434
    ollama_model: str = "llama3.1:8b"
    # Phase 45: optional bigger model for complex questions (empty = no routing).
    ollama_heavy_model: str | None = None
    ai_brief_ttl_seconds: int = 86400
    knowledge_dir: str = "/app/knowledge"
    embed_model: str = "nomic-embed-text"  # 768-dim, runs on the 3070
    vision_model: str = "llava"  # Phase 48: local vision model (ollama pull llava)

    # --- Web Push (Phase 15; empty = push disabled) ---------------------------
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:admin@example.com"

    # --- Market data (decoupled from Kite) ------------------------------------
    # "mock" = fixtures; "indianapi" = free Indian-Stock-Market-API (stocks only).
    market_data_provider: str = "mock"
    market_data_base_url: str = "http://65.0.104.9"
    market_data_timeout_seconds: float = 6.0
    # Poll interval for the free-API-backed live ticker (no WebSocket upstream).
    market_poll_seconds: float = 20.0

    # --- Scheduling & schema --------------------------------------------------
    # Weekday auto-snapshot at 09:45 IST (market opens 09:15; "fresh by 10:00").
    enable_scheduler: bool = True
    snapshot_cron_hour: int = 9
    snapshot_cron_minute: int = 45
    # Convenience for local/dev: create tables on startup. In Docker/production
    # this is false and Alembic migrations own the schema.
    auto_create_tables: bool = True

    # --- Public demo ------------------------------------------------------------
    # Read-only public instance on the fictional fixture portfolio. Forces every
    # data source to its mock and drops every key, so a stray real value in the
    # env can't reach the public. Writes are refused in app.main.
    demo_mode: bool = False

    @model_validator(mode="after")
    def _lock_demo(self) -> Settings:
        if self.demo_mode:
            self.use_mock_kite = True
            self.market_data_provider = "mock"
            self.app_password = None
            self.anthropic_api_key = None
            self.ollama_url = None
            self.vapid_public_key = None
            self.vapid_private_key = None
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one read of the environment)."""
    return Settings()
