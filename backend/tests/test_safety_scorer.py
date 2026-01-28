"""Tests for safety scorer signal counting, volume ratio, and slippage."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from models.market import Market
from models.alert import Alert
from models.orderbook import OrderBookSnapshot
from models.trade import Trade
from services.safety_scorer import SafetyScorer


@pytest.mark.asyncio
async def test_gather_metrics_counts_both_market_id_and_related(test_session):
    """Signals from both market_id and related_market_ids alerts are counted."""
    market = Market(
        id="m1",
        question="Test?",
        outcomes=[{"name": "Yes", "token_id": "tok1"}],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)

    # Single-market alert (uses market_id)
    test_session.add(Alert(
        alert_type="volume_spike",
        severity="medium",
        title="Vol spike",
        market_id="m1",
        is_active=True,
    ))
    # Cross-market alert (only related_market_ids, no market_id) —
    # tests the LIKE-based JSON containment check on SQLite
    test_session.add(Alert(
        alert_type="arbitrage",
        severity="high",
        title="Arb",
        market_id=None,
        related_market_ids=["m1", "m2"],
        is_active=True,
    ))
    await test_session.commit()

    scorer = SafetyScorer()
    metrics = await scorer._gather_metrics(test_session, market)

    assert metrics.signal_count == 2
    assert set(metrics.active_signals) == {"volume_spike", "arbitrage"}


@pytest.mark.asyncio
async def test_gather_metrics_no_duplicate_signal_types(test_session):
    """Two alerts of the same type only count as one signal."""
    market = Market(
        id="m2",
        question="Test2?",
        outcomes=[{"name": "Yes", "token_id": "tok2"}],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)
    test_session.add(Alert(
        alert_type="spread_alert",
        severity="medium",
        title="Spread1",
        market_id="m2",
        is_active=True,
    ))
    test_session.add(Alert(
        alert_type="spread_alert",
        severity="medium",
        title="Spread2",
        related_market_ids=["m2"],
        is_active=True,
    ))
    await test_session.commit()

    scorer = SafetyScorer()
    metrics = await scorer._gather_metrics(test_session, market)

    assert metrics.signal_count == 1
    assert metrics.active_signals == ["spread_alert"]


@pytest.mark.asyncio
async def test_gather_metrics_volume_ratio(test_session):
    """Volume ratio is computed as recent 1h / baseline hourly average."""
    now = datetime.utcnow()
    market = Market(
        id="m3",
        question="Test3?",
        outcomes=[{"name": "Yes", "token_id": "tok3"}],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)

    # Baseline: 23 hours of trading, need >= 10 trades for the guard
    # 23 trades x 10.0 size = 230 total, 230/23 = 10/hr average
    for i in range(23):
        test_session.add(Trade(
            trade_id=f"base-{i}",
            token_id="tok3",
            market_id="m3",
            price=0.5,
            size=10.0,
            side="buy",
            timestamp=now - timedelta(hours=23 - i),
        ))

    # Recent 1hr: 5 trades x 10 = 50 total size => ratio = 50/10 = 5.0
    for i in range(5):
        test_session.add(Trade(
            trade_id=f"recent-{i}",
            token_id="tok3",
            market_id="m3",
            price=0.5,
            size=10.0,
            side="buy",
            timestamp=now - timedelta(minutes=i * 10),
        ))

    await test_session.commit()

    scorer = SafetyScorer()
    metrics = await scorer._gather_metrics(test_session, market)

    assert metrics.volume_ratio is not None
    assert metrics.volume_ratio == 5.0


@pytest.mark.asyncio
async def test_volume_ratio_skipped_on_thin_baseline(test_session):
    """Volume ratio is None when baseline has fewer than 10 trades."""
    now = datetime.utcnow()
    market = Market(
        id="m-thin",
        question="Thin?",
        outcomes=[{"name": "Yes", "token_id": "tok-thin"}],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)

    # Only 3 baseline trades (below the 10-trade guard)
    for i in range(3):
        test_session.add(Trade(
            trade_id=f"thin-base-{i}",
            token_id="tok-thin",
            market_id="m-thin",
            price=0.5,
            size=10.0,
            side="buy",
            timestamp=now - timedelta(hours=12 - i),
        ))
    # Lots of recent volume
    for i in range(5):
        test_session.add(Trade(
            trade_id=f"thin-recent-{i}",
            token_id="tok-thin",
            market_id="m-thin",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=now - timedelta(minutes=i * 5),
        ))
    await test_session.commit()

    scorer = SafetyScorer()
    metrics = await scorer._gather_metrics(test_session, market)

    # Should be None — not enough baseline data to compute a reliable ratio
    assert metrics.volume_ratio is None


@pytest.mark.asyncio
async def test_gather_metrics_slippage(test_session):
    """Slippage is computed for 100 EUR buy when orderbook data exists."""
    now = datetime.utcnow()
    market = Market(
        id="m4",
        question="Test4?",
        outcomes=[{"name": "Yes", "token_id": "tok4"}],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)

    # Create orderbook snapshot with asks
    snapshot = OrderBookSnapshot(
        token_id="tok4",
        market_id="m4",
        timestamp=now - timedelta(minutes=5),
        best_bid=Decimal("0.50"),
        best_ask=Decimal("0.52"),
        spread=Decimal("0.02"),
        spread_pct=Decimal("0.04"),
        mid_price=Decimal("0.51"),
        bid_depth_1pct=Decimal("500"),
        ask_depth_1pct=Decimal("500"),
        bid_depth_5pct=Decimal("2000"),
        ask_depth_5pct=Decimal("2000"),
        bids=[{"price": "0.50", "size": "1000"}],
        asks=[{"price": "0.52", "size": "500"}, {"price": "0.55", "size": "500"}],
    )
    test_session.add(snapshot)
    await test_session.commit()

    scorer = SafetyScorer()
    metrics = await scorer._gather_metrics(test_session, market)

    # Should have computed slippage (exact value depends on orderbook walk logic)
    assert metrics.slippage_100_eur is not None
    assert metrics.slippage_100_eur >= 0


@pytest.mark.asyncio
async def test_briefing_teach_me_spread_alert(test_session):
    """Teach-me content handles spread_alert signal type."""
    from api.briefing import generate_teach_me_content

    opp = {
        "metrics": {
            "spread_pct": 0.06,
            "total_depth": 1000,
            "active_signals": ["spread_alert"],
        }
    }
    content = generate_teach_me_content(opp)
    assert "bid-ask spread" in content["what_signal_means"]


@pytest.mark.asyncio
async def test_briefing_teach_me_mm_pullback(test_session):
    """Teach-me content handles mm_pullback signal type."""
    from api.briefing import generate_teach_me_content

    opp = {
        "metrics": {
            "spread_pct": 0.03,
            "total_depth": 2000,
            "active_signals": ["mm_pullback"],
        }
    }
    content = generate_teach_me_content(opp)
    assert "Market makers" in content["what_signal_means"]
