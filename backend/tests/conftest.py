"""Pytest fixtures for test suite."""

import sys
from datetime import datetime, timedelta
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
    from models import market, orderbook, trade, alert, job_run, relationship, volume_stats, watchlist  # noqa: F401

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


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "id": "test-market-1",
        "question": "Will it rain tomorrow?",
        "outcomes": [
            {"name": "Yes", "token_id": "token123456789", "price": 0.65},
            {"name": "No", "token_id": "token987654321", "price": 0.35},
        ],
        "active": True,
        "volume": 10000.0,
        "liquidity": 5000.0,
    }


@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing."""
    return {
        "id": "trade-001",
        "price": 0.65,
        "size": 100.0,
        "side": "buy",
        "timestamp": datetime.utcnow().isoformat(),
        "maker": "0x1234567890abcdef",
        "taker": "0xfedcba0987654321",
    }


@pytest.fixture
def sample_orderbook_data():
    """Sample orderbook data for testing."""
    return {
        "bids": [
            {"price": "0.64", "size": "100"},
            {"price": "0.63", "size": "200"},
        ],
        "asks": [
            {"price": "0.66", "size": "150"},
            {"price": "0.67", "size": "250"},
        ],
    }


@pytest.fixture
async def seeded_job_runs(test_session):
    """Seed job runs for system status testing."""
    from models.job_run import JobRun

    now = datetime.utcnow()

    # Create successful job runs
    jobs = [
        JobRun(
            job_id="collect_markets",
            run_id="run-markets-001",
            started_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=29),
            status="success",
            records_processed=100,
        ),
        JobRun(
            job_id="collect_trades",
            run_id="run-trades-001",
            started_at=now - timedelta(minutes=10),
            completed_at=now - timedelta(minutes=9),
            status="success",
            records_processed=50,
        ),
        JobRun(
            job_id="run_analysis",
            run_id="run-analysis-001",
            started_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=59),
            status="success",
            records_processed=5,
        ),
    ]

    for job in jobs:
        test_session.add(job)
    await test_session.commit()

    return jobs


@pytest.fixture
async def seeded_trades(test_session, sample_market_data):
    """Seed trades for testing."""
    from models.market import Market
    from models.trade import Trade

    # Create market first
    market = Market(
        id=sample_market_data["id"],
        question=sample_market_data["question"],
        outcomes=sample_market_data["outcomes"],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)

    # Create trades
    now = datetime.utcnow()
    trades = []
    for i in range(10):
        trade = Trade(
            trade_id=f"trade-{i:03d}",
            token_id="token123456789",
            market_id=sample_market_data["id"],
            price=0.65,
            size=100.0 + i * 10,
            side="buy" if i % 2 == 0 else "sell",
            timestamp=now - timedelta(minutes=i * 5),
        )
        trades.append(trade)
        test_session.add(trade)

    await test_session.commit()
    return trades
