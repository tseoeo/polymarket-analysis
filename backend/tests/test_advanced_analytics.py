"""Tests for Phase 2 advanced analytics: orderbook and volume analytics."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Orderbook Analyzer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_orderbook_slippage_calculation(test_session):
    """OrderbookAnalyzer should calculate slippage correctly."""
    from services.orderbook_analyzer import OrderbookAnalyzer
    from models.orderbook import OrderBookSnapshot

    # Create a snapshot with orderbook data
    snapshot = OrderBookSnapshot(
        token_id="test-token",
        market_id="test-market",
        timestamp=datetime.utcnow(),
        bids=[
            {"price": "0.50", "size": "100"},
            {"price": "0.49", "size": "200"},
            {"price": "0.48", "size": "300"},
        ],
        asks=[
            {"price": "0.52", "size": "100"},
            {"price": "0.53", "size": "200"},
            {"price": "0.54", "size": "300"},
        ],
        best_bid=0.50,
        best_ask=0.52,
        spread=0.02,
        spread_pct=0.0385,
        mid_price=0.51,
    )
    test_session.add(snapshot)
    await test_session.commit()

    analyzer = OrderbookAnalyzer(snapshot_max_age_minutes=60)

    # Test buy slippage for small order (fits in first level)
    # $50 trade at ask price 0.52, level has 100 shares = $52 capacity
    result = await analyzer.calculate_slippage(test_session, "test-token", 50, "buy")
    assert "error" not in result
    assert result["side"] == "buy"
    assert result["best_price"] == 0.52
    assert result["expected_price"] == 0.52  # All at best price
    assert result["slippage_pct"] == pytest.approx(0.0, rel=1e-4)
    assert result["filled_dollars"] == 50  # Filled full amount

    # Test buy slippage for larger order (spans multiple levels)
    # $250 trade across multiple levels:
    # - Level 1: 100 shares @ 0.52 = $52 capacity
    # - Level 2: 200 shares @ 0.53 = $106 capacity
    # - Level 3: Need ($250 - $52 - $106) = $92 more @ 0.54
    # Total shares: 100 + 200 + (92/0.54) = 100 + 200 + 170.37 = 470.37
    # Expected price = $250 / 470.37 = 0.5315
    result = await analyzer.calculate_slippage(test_session, "test-token", 250, "buy")
    assert "error" not in result
    assert result["expected_price"] == pytest.approx(0.5315, rel=1e-2)
    assert result["slippage_pct"] > 0
    assert result["filled_dollars"] == 250


@pytest.mark.asyncio
async def test_orderbook_slippage_no_data(test_session):
    """OrderbookAnalyzer should handle missing data gracefully."""
    from services.orderbook_analyzer import OrderbookAnalyzer

    analyzer = OrderbookAnalyzer()
    result = await analyzer.calculate_slippage(test_session, "nonexistent-token", 100, "buy")

    assert "error" in result
    assert "No recent orderbook" in result["error"]


@pytest.mark.asyncio
async def test_orderbook_spread_patterns(test_session):
    """OrderbookAnalyzer should identify spread patterns by hour."""
    from services.orderbook_analyzer import OrderbookAnalyzer
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()

    # Create snapshots at different hours with varying spreads
    for i in range(24):
        for j in range(2):  # 2 snapshots per hour
            # Wider spreads during night hours (0-6), tighter during day
            spread_pct = 0.08 if i < 6 else 0.02

            snapshot = OrderBookSnapshot(
                token_id="pattern-token",
                market_id="test-market",
                timestamp=now.replace(hour=i, minute=j*30) - timedelta(days=1),
                spread_pct=spread_pct,
            )
            test_session.add(snapshot)

    await test_session.commit()

    analyzer = OrderbookAnalyzer()
    result = await analyzer.analyze_spread_patterns(test_session, "pattern-token", hours=48)

    assert "error" not in result
    assert "hourly_spreads" in result
    assert result["best_hour"] >= 6  # Day hours should be best
    assert result["worst_hour"] < 6  # Night hours should be worst


@pytest.mark.asyncio
async def test_orderbook_best_trading_hours(test_session):
    """OrderbookAnalyzer should return best hours sorted by spread."""
    from services.orderbook_analyzer import OrderbookAnalyzer
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()

    # Create snapshots with known spread patterns
    spreads_by_hour = {10: 0.01, 14: 0.015, 16: 0.02, 3: 0.10, 4: 0.12}

    for hour, spread in spreads_by_hour.items():
        for j in range(3):
            snapshot = OrderBookSnapshot(
                token_id="best-hours-token",
                market_id="test-market",
                timestamp=now.replace(hour=hour, minute=j*20) - timedelta(days=1),
                spread_pct=spread,
            )
            test_session.add(snapshot)

    await test_session.commit()

    analyzer = OrderbookAnalyzer()
    result = await analyzer.get_best_trading_hours(test_session, "best-hours-token", hours=48, top_n=3)

    assert len(result) == 3
    # Best hour should be hour 10 with 1% spread
    assert result[0]["hour"] == 10
    assert result[0]["avg_spread_pct"] == pytest.approx(0.01, rel=1e-4)
    assert result[0]["recommendation"] == "excellent"


@pytest.mark.asyncio
async def test_orderbook_history(test_session):
    """OrderbookAnalyzer should return historical snapshots."""
    from services.orderbook_analyzer import OrderbookAnalyzer
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()

    # Create several snapshots
    for i in range(5):
        snapshot = OrderBookSnapshot(
            token_id="history-token",
            market_id="test-market",
            timestamp=now - timedelta(hours=i),
            best_bid=0.50 + i * 0.01,
            best_ask=0.52 + i * 0.01,
            spread_pct=0.03 + i * 0.001,
            mid_price=0.51 + i * 0.01,
            imbalance=0.1,
        )
        test_session.add(snapshot)

    await test_session.commit()

    analyzer = OrderbookAnalyzer()
    result = await analyzer.get_orderbook_history(test_session, "history-token", hours=10)

    assert len(result) == 5
    # Most recent should be first
    assert result[0]["best_bid"] == pytest.approx(0.50, rel=1e-4)


# ============================================================================
# Volume Analyzer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_volume_7day_baseline(test_session):
    """VolumeAnalyzer should calculate 7-day baseline from trades."""
    from services.volume_analyzer import VolumeAnalyzer
    from models.trade import Trade
    from models.market import Market

    # Create market
    market = Market(id="baseline-market", question="Test?")
    test_session.add(market)

    # Create trades over 7 days
    now = datetime.utcnow()
    for day in range(7):
        for i in range(10):
            trade = Trade(
                trade_id=f"trade-{day}-{i}",
                token_id="baseline-token",
                market_id="baseline-market",
                price=0.50,
                size=100.0 + day * 10,  # Increasing volume over days
                side="buy",
                timestamp=now - timedelta(days=day, hours=i),
            )
            test_session.add(trade)

    await test_session.commit()

    analyzer = VolumeAnalyzer()
    result = await analyzer.calculate_7day_baseline(test_session, "baseline-token")

    assert "error" not in result
    assert result["period_days"] == 7
    assert result["total_volume"] > 0
    assert result["daily_avg"] > 0
    assert result["source"] == "trades"


@pytest.mark.asyncio
async def test_volume_7day_baseline_from_stats(test_session):
    """VolumeAnalyzer should prefer VolumeStats over raw trades."""
    from services.volume_analyzer import VolumeAnalyzer
    from models.volume_stats import VolumeStats
    from models.market import Market

    # Create market
    market = Market(id="stats-market", question="Test?")
    test_session.add(market)

    # Create daily VolumeStats
    now = datetime.utcnow()
    for day in range(5):
        period_start = (now - timedelta(days=day+1)).replace(hour=0, minute=0, second=0, microsecond=0)
        stats = VolumeStats(
            market_id="stats-market",
            token_id="stats-token",
            period_start=period_start,
            period_end=period_start + timedelta(days=1),
            period_type="day",
            volume=Decimal("1000") + Decimal(str(day * 100)),
            trade_count=50,
        )
        test_session.add(stats)

    await test_session.commit()

    analyzer = VolumeAnalyzer()
    result = await analyzer.calculate_7day_baseline(test_session, "stats-token")

    assert "error" not in result
    assert result["source"] == "volume_stats"
    assert result["period_days"] == 5


@pytest.mark.asyncio
async def test_volume_acceleration(test_session):
    """VolumeAnalyzer should calculate acceleration correctly."""
    from services.volume_analyzer import VolumeAnalyzer
    from models.trade import Trade
    from models.market import Market

    market = Market(id="accel-market", question="Test?")
    test_session.add(market)

    now = datetime.utcnow()

    # Previous period: low volume (6 hours ago)
    for i in range(5):
        trade = Trade(
            trade_id=f"old-trade-{i}",
            token_id="accel-token",
            market_id="accel-market",
            price=0.50,
            size=50.0,
            side="buy",
            timestamp=now - timedelta(hours=9) + timedelta(hours=i * 0.5),
        )
        test_session.add(trade)

    # Recent period: high volume (last 6 hours)
    for i in range(10):
        trade = Trade(
            trade_id=f"new-trade-{i}",
            token_id="accel-token",
            market_id="accel-market",
            price=0.50,
            size=100.0,
            side="buy",
            timestamp=now - timedelta(hours=5) + timedelta(hours=i * 0.5),
        )
        test_session.add(trade)

    await test_session.commit()

    analyzer = VolumeAnalyzer()
    result = await analyzer.calculate_acceleration(test_session, "accel-token", window_hours=6)

    assert result["token_id"] == "accel-token"
    assert result["recent_volume"] > result["previous_volume"]
    assert result["volume_acceleration"] > 0
    assert result["signal"] == "accelerating"


@pytest.mark.asyncio
async def test_volume_price_correlation(test_session):
    """VolumeAnalyzer should analyze volume-price relationship."""
    from services.volume_analyzer import VolumeAnalyzer
    from models.trade import Trade
    from models.market import Market

    market = Market(id="corr-market", question="Test?")
    test_session.add(market)

    now = datetime.utcnow()

    # Create trades with correlated volume and price (both increasing)
    for hour in range(12):
        for i in range(5):
            trade = Trade(
                trade_id=f"corr-trade-{hour}-{i}",
                token_id="corr-token",
                market_id="corr-market",
                price=0.40 + hour * 0.02,  # Price increasing
                size=100.0 + hour * 20,    # Volume also increasing
                side="buy",
                timestamp=now - timedelta(hours=12-hour) + timedelta(minutes=i*10),
            )
            test_session.add(trade)

    await test_session.commit()

    analyzer = VolumeAnalyzer()
    result = await analyzer.analyze_volume_price_relationship(test_session, "corr-token", hours=24)

    assert "error" not in result
    assert result["correlation"] > 0.5  # Should be positively correlated
    assert result["price_change_pct"] > 0
    assert result["interpretation"] == "bullish_confirmation"


@pytest.mark.asyncio
async def test_volume_price_correlation_insufficient_data(test_session):
    """VolumeAnalyzer should handle insufficient data gracefully."""
    from services.volume_analyzer import VolumeAnalyzer

    analyzer = VolumeAnalyzer()
    result = await analyzer.analyze_volume_price_relationship(test_session, "no-data-token", hours=24)

    assert "error" in result


# ============================================================================
# Volume Aggregation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_aggregate_volume_stats(test_session):
    """aggregate_volume_stats should create VolumeStats from trades."""
    from services.volume_analyzer import aggregate_volume_stats
    from models.trade import Trade
    from models.market import Market
    from models.volume_stats import VolumeStats
    from sqlalchemy import select

    market = Market(id="agg-market", question="Test?")
    test_session.add(market)

    # Create trades in the previous hour
    now = datetime.utcnow()
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    for i in range(10):
        trade = Trade(
            trade_id=f"agg-trade-{i}",
            token_id="agg-token",
            market_id="agg-market",
            price=0.50 + i * 0.01,
            size=100.0,
            side="buy" if i % 2 == 0 else "sell",
            timestamp=hour_start + timedelta(minutes=i * 5),
        )
        test_session.add(trade)

    await test_session.commit()

    # Run aggregation
    count = await aggregate_volume_stats(test_session, "hour")

    assert count >= 1

    # Verify stats were created
    result = await test_session.execute(
        select(VolumeStats)
        .where(VolumeStats.token_id == "agg-token")
        .where(VolumeStats.period_type == "hour")
    )
    stats = result.scalar_one_or_none()

    assert stats is not None
    assert stats.trade_count == 10
    assert float(stats.volume) == 1000.0  # 10 trades * 100 each
