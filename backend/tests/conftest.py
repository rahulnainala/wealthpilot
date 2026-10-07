"""Shared test fixtures.

Forces mock Kite, an in-memory SQLite database, and a throwaway Fernet key
*before* any application module reads configuration, so the suite is fully
hermetic (no Postgres, no Zerodha credentials).
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet

os.environ["USE_MOCK_KITE"] = "true"
os.environ["USE_MOCK_RISK_ENGINE"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

get_settings.cache_clear()  # ensure the forced test env is picked up


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """A shared in-memory SQLite engine (StaticPool keeps one connection)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the in-memory DB via a get_db override."""
    maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
