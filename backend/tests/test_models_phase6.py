"""Tests for Phase 6 database models: MarketRelationship and VolumeStats."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_market_relationship_creation(test_session):
    """MarketRelationship model should be creatable with all fields."""
    from models.relationship import MarketRelationship
    from models.market import Market

    # Create parent and child markets first
    market1 = Market(id="market-parent", question="Will Team A win?")
    market2 = Market(id="market-child", question="Will Team B win?")
    test_session.add_all([market1, market2])
    await test_session.commit()

    relationship = MarketRelationship(
        relationship_type="mutually_exclusive",
        parent_market_id="market-parent",
        child_market_id="market-child",
        group_id="election-2024",
        notes="Both teams cannot win the same game",
        confidence=0.95,
    )

    test_session.add(relationship)
    await test_session.commit()
    await test_session.refresh(relationship)

    assert relationship.id is not None
    assert relationship.relationship_type == "mutually_exclusive"
    assert relationship.parent_market_id == "market-parent"
    assert relationship.child_market_id == "market-child"
    assert relationship.group_id == "election-2024"
    assert relationship.confidence == 0.95


@pytest.mark.asyncio
async def test_market_relationship_repr():
    """MarketRelationship repr should be informative."""
    from models.relationship import MarketRelationship

    rel = MarketRelationship(
        relationship_type="conditional",
        parent_market_id="parent-123",
        child_market_id="child-456",
    )

    repr_str = repr(rel)
    assert "conditional" in repr_str
    assert "parent-123" in repr_str
    assert "child-456" in repr_str


@pytest.mark.asyncio
async def test_create_mutually_exclusive_factory():
    """Factory method should create correct number of relationships."""
    from models.relationship import MarketRelationship

    market_ids = ["market-a", "market-b", "market-c"]
    relationships = MarketRelationship.create_mutually_exclusive(
        market_ids=market_ids,
        group_id="test-group",
        notes="Test markets",
        confidence=0.8,
    )

    # For 3 markets: 3*(3-1)/2 = 3 relationships
    assert len(relationships) == 3

    # All should be mutually_exclusive type
    assert all(r.relationship_type == "mutually_exclusive" for r in relationships)
    assert all(r.group_id == "test-group" for r in relationships)
    assert all(r.confidence == 0.8 for r in relationships)

    # Check pairs are correct (a-b, a-c, b-c)
    pairs = [(r.parent_market_id, r.child_market_id) for r in relationships]
    assert ("market-a", "market-b") in pairs
    assert ("market-a", "market-c") in pairs
    assert ("market-b", "market-c") in pairs


@pytest.mark.asyncio
async def test_create_conditional_factory():
    """Factory method should create conditional relationship."""
    from models.relationship import MarketRelationship

    rel = MarketRelationship.create_conditional(
        parent_id="wins-primary",
        child_id="wins-election",
        notes="Must win primary to win election",
        confidence=1.0,
    )

    assert rel.relationship_type == "conditional"
    assert rel.parent_market_id == "wins-primary"
    assert rel.child_market_id == "wins-election"


@pytest.mark.asyncio
async def test_create_time_sequence_factory():
    """Factory method should create time sequence relationship."""
    from models.relationship import MarketRelationship

    rel = MarketRelationship.create_time_sequence(
        earlier_id="by-march",
        later_id="by-december",
        group_id="deadline-group",
    )

    assert rel.relationship_type == "time_sequence"
    assert rel.parent_market_id == "by-march"  # Earlier = parent
    assert rel.child_market_id == "by-december"  # Later = child


@pytest.mark.asyncio
async def test_create_subset_factory():
    """Factory method should create subset relationship."""
    from models.relationship import MarketRelationship

    rel = MarketRelationship.create_subset(
        general_id="team-wins",
        specific_id="team-wins-by-10",
    )

    assert rel.relationship_type == "subset"
    assert rel.parent_market_id == "team-wins"  # General = parent
    assert rel.child_market_id == "team-wins-by-10"  # Specific = child


@pytest.mark.asyncio
async def test_volume_stats_creation(test_session):
    """VolumeStats model should be creatable with all fields."""
    from models.volume_stats import VolumeStats
    from models.market import Market

    # Create market first
    market = Market(id="volume-test-market", question="Test?")
    test_session.add(market)
    await test_session.commit()

    now = datetime.utcnow()
    stats = VolumeStats(
        market_id="volume-test-market",
        token_id="token-123",
        period_start=now - timedelta(hours=1),
        period_end=now,
        period_type="hour",
        volume=Decimal("5000.00"),
        trade_count=42,
        avg_trade_size=Decimal("119.05"),
        price_open=Decimal("0.450000"),
        price_close=Decimal("0.520000"),
        price_high=Decimal("0.550000"),
        price_low=Decimal("0.440000"),
        buy_volume=Decimal("3000.00"),
        sell_volume=Decimal("2000.00"),
    )

    test_session.add(stats)
    await test_session.commit()
    await test_session.refresh(stats)

    assert stats.id is not None
    assert stats.market_id == "volume-test-market"
    assert stats.period_type == "hour"
    assert stats.trade_count == 42


@pytest.mark.asyncio
async def test_volume_stats_buy_sell_ratio():
    """VolumeStats should calculate buy/sell ratio correctly."""
    from models.volume_stats import VolumeStats

    stats = VolumeStats(
        market_id="m",
        token_id="t",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        period_type="hour",
        buy_volume=Decimal("3000"),
        sell_volume=Decimal("1500"),
    )

    assert stats.buy_sell_ratio == pytest.approx(2.0, rel=1e-4)


@pytest.mark.asyncio
async def test_volume_stats_buy_sell_ratio_none():
    """VolumeStats should return None when sell_volume is 0 or missing."""
    from models.volume_stats import VolumeStats

    stats = VolumeStats(
        market_id="m",
        token_id="t",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        period_type="hour",
        buy_volume=Decimal("3000"),
        sell_volume=None,
    )

    assert stats.buy_sell_ratio is None


@pytest.mark.asyncio
async def test_volume_stats_price_change():
    """VolumeStats should calculate price change correctly."""
    from models.volume_stats import VolumeStats

    stats = VolumeStats(
        market_id="m",
        token_id="t",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        period_type="hour",
        price_open=Decimal("0.50"),
        price_close=Decimal("0.55"),
    )

    # 10% increase
    assert stats.price_change == pytest.approx(0.10, rel=1e-4)


@pytest.mark.asyncio
async def test_volume_stats_price_range():
    """VolumeStats should calculate price range correctly."""
    from models.volume_stats import VolumeStats

    stats = VolumeStats(
        market_id="m",
        token_id="t",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        period_type="hour",
        price_high=Decimal("0.60"),
        price_low=Decimal("0.45"),
    )

    assert stats.price_range == pytest.approx(0.15, rel=1e-4)


@pytest.mark.asyncio
async def test_volume_stats_from_trades():
    """VolumeStats.from_trades should aggregate trades correctly."""
    from models.volume_stats import VolumeStats

    # Create mock trades
    now = datetime.utcnow()
    mock_trades = [
        MagicMock(price=0.50, size=100.0, side="buy", timestamp=now - timedelta(minutes=50)),
        MagicMock(price=0.52, size=150.0, side="buy", timestamp=now - timedelta(minutes=40)),
        MagicMock(price=0.51, size=200.0, side="sell", timestamp=now - timedelta(minutes=30)),
        MagicMock(price=0.48, size=75.0, side="sell", timestamp=now - timedelta(minutes=20)),
        MagicMock(price=0.55, size=125.0, side="buy", timestamp=now - timedelta(minutes=10)),
    ]

    stats = VolumeStats.from_trades(
        market_id="test-market",
        token_id="test-token",
        trades=mock_trades,
        period_start=now - timedelta(hours=1),
        period_end=now,
        period_type="hour",
    )

    # Total volume = 100 + 150 + 200 + 75 + 125 = 650
    assert float(stats.volume) == pytest.approx(650.0, rel=1e-4)
    assert stats.trade_count == 5

    # Buy volume = 100 + 150 + 125 = 375
    assert float(stats.buy_volume) == pytest.approx(375.0, rel=1e-4)

    # Sell volume = 200 + 75 = 275
    assert float(stats.sell_volume) == pytest.approx(275.0, rel=1e-4)

    # OHLC based on timestamps (sorted)
    assert float(stats.price_open) == pytest.approx(0.50, rel=1e-4)  # First trade
    assert float(stats.price_close) == pytest.approx(0.55, rel=1e-4)  # Last trade
    assert float(stats.price_high) == pytest.approx(0.55, rel=1e-4)
    assert float(stats.price_low) == pytest.approx(0.48, rel=1e-4)


@pytest.mark.asyncio
async def test_volume_stats_from_trades_empty():
    """VolumeStats.from_trades should handle empty trade list."""
    from models.volume_stats import VolumeStats

    now = datetime.utcnow()
    stats = VolumeStats.from_trades(
        market_id="test-market",
        token_id="test-token",
        trades=[],
        period_start=now - timedelta(hours=1),
        period_end=now,
        period_type="hour",
    )

    assert float(stats.volume) == 0
    assert stats.trade_count == 0
    assert stats.price_open is None
    assert stats.price_close is None


@pytest.mark.asyncio
async def test_volume_stats_repr():
    """VolumeStats repr should be informative."""
    from models.volume_stats import VolumeStats

    stats = VolumeStats(
        market_id="m",
        token_id="token-xyz",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        period_type="day",
        volume=Decimal("10000.00"),
        trade_count=100,
    )

    repr_str = repr(stats)
    assert "token-xyz" in repr_str
    assert "day" in repr_str
    assert "10000" in repr_str
    assert "100" in repr_str
