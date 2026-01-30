"""Tests for Phase 4: Dedicated API endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock

import pytest


# ============================================================================
# Arbitrage API Tests
# ============================================================================

@pytest.mark.asyncio
async def test_arbitrage_opportunities_endpoint(test_session):
    """Test /api/arbitrage/opportunities endpoint."""
    from api.arbitrage import list_arbitrage_opportunities

    # No alerts - should return empty
    result = await list_arbitrage_opportunities(
        type=None,
        is_active=True,
        limit=50,
        offset=0,
        session=test_session,
    )

    assert result.total == 0
    assert result.opportunities == []


@pytest.mark.asyncio
async def test_arbitrage_groups_endpoint(test_session):
    """Test /api/arbitrage/groups endpoint."""
    from api.arbitrage import list_relationship_groups
    from models.relationship import MarketRelationship
    from models.market import Market

    # Create markets and relationships
    market_a = Market(id="grp-a", question="A?", active=True)
    market_b = Market(id="grp-b", question="B?", active=True)
    test_session.add_all([market_a, market_b])

    rels = MarketRelationship.create_mutually_exclusive(
        market_ids=["grp-a", "grp-b"],
        group_id="test-group",
    )
    for rel in rels:
        test_session.add(rel)
    await test_session.commit()

    result = await list_relationship_groups(session=test_session)

    assert "groups" in result
    assert len(result["groups"]) == 1
    assert result["groups"][0].group_id == "test-group"
    assert set(result["groups"][0].market_ids) == {"grp-a", "grp-b"}


@pytest.mark.asyncio
async def test_create_relationship_endpoint(test_session):
    """Test POST /api/arbitrage/relationships endpoint."""
    from api.arbitrage import create_relationship, CreateRelationshipRequest
    from models.market import Market

    # Create markets
    parent = Market(id="rel-parent", question="Parent?", active=True)
    child = Market(id="rel-child", question="Child?", active=True)
    test_session.add_all([parent, child])
    await test_session.commit()

    request = CreateRelationshipRequest(
        relationship_type="conditional",
        parent_market_id="rel-parent",
        child_market_id="rel-child",
        notes="Test relationship",
        confidence=0.9,
    )

    result = await create_relationship(request=request, session=test_session)

    assert result.id is not None
    assert result.relationship_type == "conditional"
    assert result.parent_market_id == "rel-parent"


@pytest.mark.asyncio
async def test_create_relationship_missing_market(test_session):
    """Test creating relationship with nonexistent market returns 404."""
    from api.arbitrage import create_relationship, CreateRelationshipRequest
    from fastapi import HTTPException

    request = CreateRelationshipRequest(
        relationship_type="conditional",
        parent_market_id="nonexistent",
        child_market_id="also-nonexistent",
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_relationship(request=request, session=test_session)

    assert exc_info.value.status_code == 404


# ============================================================================
# Orderbook API Tests
# ============================================================================

@pytest.mark.asyncio
async def test_orderbook_endpoint(test_session):
    """Test /api/orderbook/{token_id} endpoint."""
    from api.orderbook import get_orderbook
    from models.orderbook import OrderBookSnapshot
    from fastapi import HTTPException

    # Create snapshot
    snapshot = OrderBookSnapshot(
        token_id="ob-token",
        market_id="ob-market",
        timestamp=datetime.utcnow(),
        best_bid=0.50,
        best_ask=0.52,
        spread_pct=0.038,
        imbalance=0.1,
        bid_depth_1pct=1000,
        ask_depth_1pct=1200,
        bid_depth_5pct=5000,
        ask_depth_5pct=6000,
    )
    test_session.add(snapshot)
    await test_session.commit()

    result = await get_orderbook(token_id="ob-token", session=test_session)

    assert result.token_id == "ob-token"
    assert result.best_bid == 0.50
    assert result.best_ask == 0.52


@pytest.mark.asyncio
async def test_orderbook_not_found(test_session):
    """Test orderbook endpoint with nonexistent token returns 404."""
    from api.orderbook import get_orderbook
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_orderbook(token_id="nonexistent", session=test_session)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_slippage_endpoint(test_session):
    """Test /api/orderbook/{token_id}/slippage endpoint."""
    from api.orderbook import calculate_slippage
    from models.orderbook import OrderBookSnapshot, OrderBookLatestRaw

    snapshot = OrderBookSnapshot(
        token_id="slip-token",
        market_id="slip-market",
        timestamp=datetime.utcnow(),
        best_bid=0.50,
        best_ask=0.52,
    )
    test_session.add(snapshot)

    raw = OrderBookLatestRaw(
        token_id="slip-token",
        market_id="slip-market",
        timestamp=datetime.utcnow(),
        bids=[
            {"price": "0.50", "size": "100"},
            {"price": "0.49", "size": "200"},
        ],
        asks=[
            {"price": "0.52", "size": "100"},
            {"price": "0.53", "size": "200"},
        ],
    )
    test_session.add(raw)
    await test_session.commit()

    result = await calculate_slippage(
        token_id="slip-token",
        size=50.0,
        side="buy",
        session=test_session,
    )

    assert result.token_id == "slip-token"
    assert result.side == "buy"
    assert result.best_price == 0.52


@pytest.mark.asyncio
async def test_orderbook_history_endpoint(test_session):
    """Test /api/orderbook/{token_id}/history endpoint."""
    from api.orderbook import get_orderbook_history
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()
    for i in range(5):
        snapshot = OrderBookSnapshot(
            token_id="hist-token",
            market_id="hist-market",
            timestamp=now - timedelta(hours=i),
            best_bid=0.50,
            best_ask=0.52,
            spread_pct=0.03,
        )
        test_session.add(snapshot)
    await test_session.commit()

    result = await get_orderbook_history(
        token_id="hist-token",
        hours=24,
        session=test_session,
    )

    assert len(result) == 5


# ============================================================================
# Volume API Tests
# ============================================================================

@pytest.mark.asyncio
async def test_volume_stats_endpoint(test_session):
    """Test /api/volume/{token_id}/stats endpoint."""
    from api.volume import get_volume_stats
    from models.trade import Trade
    from models.market import Market
    from fastapi import HTTPException

    market = Market(id="vol-market", question="Test?")
    test_session.add(market)

    now = datetime.utcnow()
    for day in range(3):
        for i in range(5):
            trade = Trade(
                trade_id=f"vol-trade-{day}-{i}",
                token_id="vol-token",
                market_id="vol-market",
                price=0.50,
                size=100.0,
                side="buy",
                timestamp=now - timedelta(days=day, hours=i),
            )
            test_session.add(trade)
    await test_session.commit()

    result = await get_volume_stats(token_id="vol-token", session=test_session)

    assert result.token_id == "vol-token"
    assert result.total_volume > 0


@pytest.mark.asyncio
async def test_volume_acceleration_endpoint(test_session):
    """Test /api/volume/{token_id}/acceleration endpoint."""
    from api.volume import get_volume_acceleration
    from models.trade import Trade
    from models.market import Market

    market = Market(id="accel-api-market", question="Test?")
    test_session.add(market)

    now = datetime.utcnow()
    # Create trades in recent and previous windows
    for i in range(5):
        trade = Trade(
            trade_id=f"accel-api-{i}",
            token_id="accel-api-token",
            market_id="accel-api-market",
            price=0.50,
            size=100.0,
            side="buy",
            timestamp=now - timedelta(hours=i),
        )
        test_session.add(trade)
    await test_session.commit()

    result = await get_volume_acceleration(
        token_id="accel-api-token",
        window_hours=6,
        session=test_session,
    )

    assert result.token_id == "accel-api-token"
    assert result.window_hours == 6


@pytest.mark.asyncio
async def test_volume_leaders_endpoint(test_session):
    """Test /api/volume/leaders endpoint."""
    from api.volume import get_volume_leaders
    from models.trade import Trade
    from models.market import Market

    market = Market(id="leader-market", question="Test?")
    test_session.add(market)

    now = datetime.utcnow()
    for i in range(10):
        trade = Trade(
            trade_id=f"leader-{i}",
            token_id="leader-token",
            market_id="leader-market",
            price=0.50,
            size=500.0,
            side="buy",
            timestamp=now - timedelta(hours=i),
        )
        test_session.add(trade)
    await test_session.commit()

    result = await get_volume_leaders(limit=10, session=test_session)

    assert len(result) >= 1
    assert result[0].volume_24h > 0


# ============================================================================
# Market Maker API Tests
# ============================================================================

@pytest.mark.asyncio
async def test_mm_presence_endpoint(test_session):
    """Test /api/mm/{token_id}/presence endpoint."""
    from api.mm import get_mm_presence
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()
    for i in range(10):
        snapshot = OrderBookSnapshot(
            token_id="mm-token",
            market_id="mm-market",
            timestamp=now - timedelta(hours=i),
            spread_pct=0.02,
            bid_depth_1pct=1000,
            ask_depth_1pct=1200,
        )
        test_session.add(snapshot)
    await test_session.commit()

    result = await get_mm_presence(
        token_id="mm-token",
        hours=24,
        session=test_session,
    )

    assert result.token_id == "mm-token"
    assert result.presence_score >= 0
    assert result.presence_score <= 1
    assert result.snapshot_count == 10


@pytest.mark.asyncio
async def test_mm_patterns_endpoint(test_session):
    """Test /api/mm/{token_id}/patterns endpoint."""
    from api.mm import get_mm_patterns
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()
    for hour in range(24):
        for i in range(2):
            snapshot = OrderBookSnapshot(
                token_id="pattern-mm-token",
                market_id="mm-market",
                timestamp=now.replace(hour=hour, minute=i*30) - timedelta(days=1),
                spread_pct=0.02 + hour * 0.001,  # Spread varies by hour
                bid_depth_1pct=1000,
                ask_depth_1pct=1000,
            )
            test_session.add(snapshot)
    await test_session.commit()

    result = await get_mm_patterns(
        token_id="pattern-mm-token",
        hours=48,
        session=test_session,
    )

    assert result.token_id == "pattern-mm-token"
    assert len(result.hourly_patterns) > 0


@pytest.mark.asyncio
async def test_mm_pullbacks_endpoint(test_session):
    """Test /api/mm/pullbacks endpoint."""
    from api.mm import get_mm_pullbacks
    from models.alert import Alert

    # Create MM pullback alert
    alert = Alert(
        alert_type="mm_pullback",
        severity="high",
        title="MM withdrew liquidity",
        market_id="pullback-market",
        data={
            "token_id": "pullback-token",
            "depth_drop_pct": 0.60,
            "previous_depth": 10000,
            "current_depth": 4000,
        },
        is_active=True,
    )
    test_session.add(alert)
    await test_session.commit()

    result = await get_mm_pullbacks(is_active=True, limit=20, session=test_session)

    assert len(result) == 1
    assert result[0].token_id == "pullback-token"
    assert result[0].depth_drop_pct == 0.60


@pytest.mark.asyncio
async def test_best_hours_overall_endpoint(test_session):
    """Test /api/mm/best-hours endpoint."""
    from api.mm import get_best_hours_overall
    from models.orderbook import OrderBookSnapshot

    now = datetime.utcnow()
    for hour in range(24):
        for token in ["token-1", "token-2"]:
            snapshot = OrderBookSnapshot(
                token_id=token,
                market_id=f"market-{token}",
                timestamp=now.replace(hour=hour, minute=0) - timedelta(days=1),
                spread_pct=0.02 + hour * 0.001,
                bid_depth_1pct=1000,
                ask_depth_1pct=1000,
            )
            test_session.add(snapshot)
    await test_session.commit()

    result = await get_best_hours_overall(hours=48, limit=24, session=test_session)

    assert len(result) > 0
    # Best hours should be sorted by quality score
    assert result[0].quality_score >= result[-1].quality_score
