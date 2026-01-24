"""Pytest fixtures for test suite."""

import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import Base

# Use SQLite for tests with StaticPool to share connection across async operations.
# StaticPool ensures the same connection is reused, so tables created in create_all()
# are visible to all sessions. Without this, each connection gets its own empty DB.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create a test database engine with in-memory SQLite.

    Uses StaticPool to ensure single connection is reused across all operations,
    which is required for in-memory SQLite to share tables between create_all()
    and subsequent session operations.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Import models to register with Base.metadata
    from models import market, orderbook, trade, alert  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_client():
    """Create a test HTTP client for API testing.

    Mocks init_db and close_db to prevent the app from trying to connect
    to the real PostgreSQL database during tests.
    """
    with patch("main.init_db", new_callable=AsyncMock) as mock_init, \
         patch("main.close_db", new_callable=AsyncMock) as mock_close:

        from main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
