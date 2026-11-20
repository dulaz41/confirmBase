from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# In-memory Async SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Set test environment
os.environ["APP_ENV"] = "testing"
os.environ["ADMIN_API_KEY"] = "test_admin_secret_key_1234567890"
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.database import Base, get_db
from app.main import app

# In-memory Async SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def prepare_database():
    """Creates database schema before each test and drops it afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    limiter.reset()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP async client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct database session fixture for test data setup and inspection."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}
