"""Tests for database models."""

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_market_model_creation(test_session):
    """Market model should be creatable with all fields."""
    from models.market import Market

    market = Market(
        id="test-market-123",
        condition_id="condition-456",
        slug="will-it-rain-tomorrow",
        question="Will it rain tomorrow?",
        description="Resolves YES if it rains.",
        outcomes=[
            {"name": "Yes", "token_id": "token123abc", "price": 0.65},
            {"name": "No", "token_id": "token456def", "price": 0.35},
        ],
        volume=10000.00,
        liquidity=5000.00,
        active=True,
        category="Weather",
    )

    test_session.add(market)
    await test_session.commit()
    await test_session.refresh(market)

    assert market.id == "test-market-123"
    assert market.question == "Will it rain tomorrow?"
    assert market.active is True
    assert len(market.outcomes) == 2


@pytest.mark.asyncio
async def test_market_token_ids_property(test_session):
    """Market.token_ids should extract token IDs from outcomes."""
    from models.market import Market

    market = Market(
        id="market-with-tokens",
        question="Test?",
        outcomes=[
            {"name": "Yes", "token_id": "abc123"},
            {"name": "No", "token_id": "def456"},
            {"name": "Maybe", "token_id": None},  # Should be skipped
        ],
    )

    assert market.token_ids == ["abc123", "def456"]


@pytest.mark.asyncio
async def test_market_token_ids_empty_outcomes():
    """Market.token_ids should return empty list for None outcomes."""
    from models.market import Market

    market = Market(id="empty-market", question="Test?", outcomes=None)
    assert market.token_ids == []


@pytest.mark.asyncio
async def test_market_yes_no_price_properties(test_session):
    """Market should correctly extract Yes/No prices."""
    from models.market import Market

    market = Market(
        id="price-test",
        question="Test?",
        outcomes=[
            {"name": "Yes", "token_id": "yes-token", "price": 0.72},
            {"name": "No", "token_id": "no-token", "price": 0.28},
        ],
    )

    assert market.yes_price == 0.72
    assert market.no_price == 0.28


@pytest.mark.asyncio
async def test_market_yes_no_price_fallback():
    """Market should fall back to index-based prices when names don't match."""
    from models.market import Market

    market = Market(
        id="custom-outcomes",
        question="Who will win?",
        outcomes=[
            {"name": "Team A", "token_id": "a", "price": 0.6},
            {"name": "Team B", "token_id": "b", "price": 0.4},
        ],
    )

    # Falls back to outcomes[0] for yes_price
    assert market.yes_price == 0.6
    # Falls back to outcomes[1] for no_price
    assert market.no_price == 0.4


@pytest.mark.asyncio
async def test_orderbook_snapshot_from_api_response():
    """OrderBookSnapshot should parse API response correctly."""
    from models.orderbook import OrderBookSnapshot

    api_data = {
        "bids": [
            {"price": "0.64", "size": "100.0"},
            {"price": "0.63", "size": "200.0"},
        ],
        "asks": [
            {"price": "0.66", "size": "150.0"},
            {"price": "0.67", "size": "250.0"},
        ],
    }

    snapshot = OrderBookSnapshot.from_api_response(
        token_id="token123",
        market_id="market456",
        data=api_data,
    )

    assert snapshot.token_id == "token123"
    assert snapshot.market_id == "market456"
    assert snapshot.best_bid == 0.64
    assert snapshot.best_ask == 0.66


@pytest.mark.asyncio
async def test_orderbook_metrics_calculation():
    """OrderBookSnapshot should correctly calculate spread and depth."""
    from models.orderbook import OrderBookSnapshot

    api_data = {
        "bids": [
            {"price": "0.50", "size": "100.0"},
        ],
        "asks": [
            {"price": "0.52", "size": "150.0"},
        ],
    }

    snapshot = OrderBookSnapshot.from_api_response(
        token_id="test",
        market_id="test",
        data=api_data,
    )

    assert snapshot.spread == pytest.approx(0.02, rel=1e-4)
    assert snapshot.mid_price == pytest.approx(0.51, rel=1e-4)
    # spread_pct = 0.02 / 0.51 = ~0.0392
    assert snapshot.spread_pct == pytest.approx(0.0392, rel=1e-2)


@pytest.mark.asyncio
async def test_orderbook_imbalance_calculation():
    """OrderBookSnapshot should calculate imbalance correctly.

    Note: Depth is now calculated in dollars (price * size), not shares.
    """
    from models.orderbook import OrderBookSnapshot

    # Heavy bid side = positive imbalance (buying pressure)
    api_data = {
        "bids": [{"price": "0.50", "size": "200.0"}],
        "asks": [{"price": "0.51", "size": "100.0"}],
    }

    snapshot = OrderBookSnapshot.from_api_response("t", "m", api_data)

    # Depth now in dollars:
    # bid_depth_1pct = 0.50 * 200 = $100
    # ask_depth_1pct = 0.51 * 100 = $51
    # imbalance = (100 - 51) / (100 + 51) = 49/151 = 0.3245
    assert snapshot.imbalance == pytest.approx(0.3245, rel=1e-2)


@pytest.mark.asyncio
async def test_trade_from_api_with_string_timestamp():
    """Trade should parse ISO string timestamp."""
    from models.trade import Trade

    data = {
        "id": "trade-123",
        "price": "0.65",
        "size": "500",
        "side": "buy",
        "timestamp": "2025-01-15T14:30:00Z",
    }

    trade = Trade.from_api_response("token1", "market1", data)

    assert trade.trade_id == "trade-123"
    assert trade.price == 0.65
    assert trade.size == 500.0
    assert trade.side == "buy"
    assert trade.timestamp.year == 2025
    assert trade.timestamp.month == 1
    assert trade.timestamp.day == 15


@pytest.mark.asyncio
async def test_trade_from_api_with_seconds_timestamp():
    """Trade should parse Unix timestamp in seconds."""
    from models.trade import Trade

    # 1705329000 = 2024-01-15 14:30:00 UTC
    data = {
        "id": "trade-456",
        "price": "0.42",
        "size": "1000",
        "timestamp": 1705329000,
    }

    trade = Trade.from_api_response("token2", "market2", data)

    assert trade.price == 0.42
    assert trade.timestamp.year == 2024


@pytest.mark.asyncio
async def test_trade_from_api_with_milliseconds_timestamp():
    """Trade should correctly handle millisecond timestamps.

    This verifies the fix for timestamps > 1e12 being divided by 1000.
    """
    from models.trade import Trade

    # 1705329000000 = 1705329000 seconds = 2024-01-15 14:30:00 UTC
    data = {
        "id": "trade-789",
        "price": "0.55",
        "size": "2000",
        "timestamp": 1705329000000,  # Milliseconds
    }

    trade = Trade.from_api_response("token3", "market3", data)

    # Should be same date as seconds test above
    assert trade.timestamp.year == 2024
    assert trade.timestamp.month == 1
    assert trade.timestamp.day == 15


@pytest.mark.asyncio
async def test_alert_model_creation(test_session):
    """Alert model should be creatable with all fields."""
    from models.alert import Alert

    alert = Alert(
        alert_type="arbitrage",
        severity="high",
        title="Arbitrage opportunity detected",
        description="5% profit potential",
        market_id="market-123",
        data={"profit": 0.05},
        is_active=True,
    )

    test_session.add(alert)
    await test_session.commit()
    await test_session.refresh(alert)

    assert alert.id is not None
    assert alert.alert_type == "arbitrage"
    assert alert.is_active is True


@pytest.mark.asyncio
async def test_alert_dismiss():
    """Alert.dismiss() should mark alert as inactive."""
    from models.alert import Alert

    alert = Alert(
        alert_type="volume_spike",
        title="Volume spike",
        is_active=True,
    )

    assert alert.is_active is True
    assert alert.dismissed_at is None

    alert.dismiss()

    assert alert.is_active is False
    assert alert.dismissed_at is not None


@pytest.mark.asyncio
async def test_alert_factory_methods():
    """Alert factory methods should create correctly typed alerts."""
    from models.alert import Alert

    # Arbitrage alert
    arb_alert = Alert.create_arbitrage_alert(
        title="Arb found",
        description="Cross-market opportunity",
        market_ids=["m1", "m2"],
        profit_estimate=0.06,
        data={"source": "test"},
    )
    assert arb_alert.alert_type == "arbitrage"
    assert arb_alert.severity == "high"  # > 5% profit
    assert arb_alert.related_market_ids == ["m1", "m2"]

    # Volume alert
    vol_alert = Alert.create_volume_alert(
        market_id="m3",
        title="High volume",
        volume_ratio=4.0,
        data={},
    )
    assert vol_alert.alert_type == "volume_spike"
    assert vol_alert.severity == "medium"  # 3-5x ratio

    # Spread alert
    spread_alert = Alert.create_spread_alert(
        market_id="m4",
        title="Wide spread",
        spread_pct=0.08,
        data={},
    )
    assert spread_alert.alert_type == "spread_alert"
    assert spread_alert.severity == "medium"  # > 5%
