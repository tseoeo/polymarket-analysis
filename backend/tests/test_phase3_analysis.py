"""Tests for Phase 3 Analysis Engine.

Tests the four analyzer modules:
- VolumeAnalyzer: Volume spike detection
- SpreadAnalyzer: Wide spread detection
- MarketMakerAnalyzer: MM pullback detection
- ArbitrageDetector: Intra-market arbitrage detection
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from models.market import Market
from models.trade import Trade
from models.orderbook import OrderBookSnapshot
from models.alert import Alert
from services.volume_analyzer import VolumeAnalyzer
from services.spread_analyzer import SpreadAnalyzer
from services.mm_analyzer import MarketMakerAnalyzer
from services.arbitrage_detector import ArbitrageDetector


# =============================================================================
# Test Data Factories
# =============================================================================


def create_test_market(
    market_id: str = "test-market-1",
    yes_token: str = "yes-token-123",
    no_token: str = "no-token-456",
    yes_price: float = 0.60,
    no_price: float = 0.40,
    active: bool = True,
    enable_order_book: bool = True,
) -> Market:
    """Create a test market with binary outcomes."""
    return Market(
        id=market_id,
        question="Will test pass?",
        outcomes=[
            {"name": "Yes", "token_id": yes_token, "price": yes_price},
            {"name": "No", "token_id": no_token, "price": no_price},
        ],
        active=active,
        enable_order_book=enable_order_book,
    )


def create_test_trade(
    token_id: str,
    market_id: str,
    size: float,
    timestamp: datetime,
    price: float = 0.50,
) -> Trade:
    """Create a test trade."""
    return Trade(
        trade_id=f"trade-{timestamp.timestamp()}-{size}",
        token_id=token_id,
        market_id=market_id,
        price=price,
        size=size,
        side="buy",
        timestamp=timestamp,
    )


def create_test_snapshot(
    token_id: str,
    market_id: str,
    timestamp: datetime,
    best_bid: float = 0.50,
    best_ask: float = 0.52,
    bid_depth_1pct: float = 1000.0,
    ask_depth_1pct: float = 1000.0,
) -> OrderBookSnapshot:
    """Create a test orderbook snapshot."""
    spread = best_ask - best_bid
    mid_price = (best_ask + best_bid) / 2
    spread_pct = spread / mid_price if mid_price > 0 else None

    return OrderBookSnapshot(
        token_id=token_id,
        market_id=market_id,
        timestamp=timestamp,
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        spread_pct=spread_pct,
        mid_price=mid_price,
        bid_depth_1pct=bid_depth_1pct,
        ask_depth_1pct=ask_depth_1pct,
    )


# =============================================================================
# VolumeAnalyzer Tests
# =============================================================================


class TestVolumeAnalyzer:
    """Tests for volume spike detection."""

    @pytest.mark.asyncio
    async def test_detects_volume_spike(self, test_session):
        """5x volume spike should trigger alert."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Create baseline trades (24 trades over 23 hours = ~1 trade/hour)
        for i in range(23):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,  # $100 per hour baseline
                timestamp=now - timedelta(hours=24) + timedelta(hours=i),
            )
            test_session.add(trade)

        # Create spike in last hour (5x = $500)
        for i in range(5):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,
                timestamp=now - timedelta(minutes=30 - i * 5),
            )
            test_session.add(trade)

        await test_session.commit()

        analyzer = VolumeAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "volume_spike"
        assert alerts[0].market_id == market.id
        assert alerts[0].data["token_id"] == token_id

    @pytest.mark.asyncio
    async def test_ignores_normal_volume(self, test_session):
        """1.5x volume should not trigger alert (below 3x threshold)."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Create baseline trades
        for i in range(23):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,
                timestamp=now - timedelta(hours=24) + timedelta(hours=i),
            )
            test_session.add(trade)

        # Only 1.5x in last hour
        trade = create_test_trade(
            token_id=token_id,
            market_id=market.id,
            size=150.0,
            timestamp=now - timedelta(minutes=30),
        )
        test_session.add(trade)

        await test_session.commit()

        analyzer = VolumeAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_needs_baseline_trades(self, test_session):
        """Should not alert without enough historical trades for baseline."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Only 5 baseline trades (below min of 10)
        for i in range(5):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,
                timestamp=now - timedelta(hours=20) + timedelta(hours=i),
            )
            test_session.add(trade)

        # Big spike
        trade = create_test_trade(
            token_id=token_id,
            market_id=market.id,
            size=10000.0,
            timestamp=now - timedelta(minutes=30),
        )
        test_session.add(trade)

        await test_session.commit()

        analyzer = VolumeAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0  # Not enough baseline

    @pytest.mark.asyncio
    async def test_deduplicates_alerts(self, test_session):
        """Should not create duplicate alerts for same market+token."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Create existing active alert
        existing_alert = Alert.create_volume_alert(
            market_id=market.id,
            title="Existing spike",
            volume_ratio=5.0,
            data={"token_id": token_id},
        )
        test_session.add(existing_alert)

        # Create data that would trigger alert
        for i in range(15):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,
                timestamp=now - timedelta(hours=20) + timedelta(hours=i),
            )
            test_session.add(trade)

        for i in range(10):
            trade = create_test_trade(
                token_id=token_id,
                market_id=market.id,
                size=100.0,
                timestamp=now - timedelta(minutes=50 - i * 5),
            )
            test_session.add(trade)

        await test_session.commit()

        analyzer = VolumeAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0  # Deduped


# =============================================================================
# SpreadAnalyzer Tests
# =============================================================================


class TestSpreadAnalyzer:
    """Tests for wide spread detection."""

    @pytest.mark.asyncio
    async def test_detects_wide_spread(self, test_session):
        """10% spread should trigger alert (above 5% threshold)."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Wide spread snapshot (10% spread)
        snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.45,
            best_ask=0.55,  # 10% spread
        )
        test_session.add(snapshot)

        await test_session.commit()

        analyzer = SpreadAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "spread_alert"
        assert alerts[0].data["token_id"] == token_id

    @pytest.mark.asyncio
    async def test_ignores_tight_spread(self, test_session):
        """2% spread should not trigger alert."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Tight spread snapshot
        snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.49,
            best_ask=0.51,  # 2% spread
        )
        test_session.add(snapshot)

        await test_session.commit()

        analyzer = SpreadAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_ignores_stale_snapshot(self, test_session):
        """Stale snapshot (>30 min) should not trigger alert."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Old snapshot with wide spread
        snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(hours=1),  # Stale
            best_bid=0.40,
            best_ask=0.60,  # Very wide
        )
        test_session.add(snapshot)

        await test_session.commit()

        analyzer = SpreadAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0  # Ignored due to staleness


# =============================================================================
# MarketMakerAnalyzer Tests
# =============================================================================


class TestMarketMakerAnalyzer:
    """Tests for MM pullback detection."""

    @pytest.mark.asyncio
    async def test_detects_depth_drop(self, test_session):
        """60% depth drop should trigger alert."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Old snapshot with high depth
        old_snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(hours=3),
            bid_depth_1pct=10000.0,
            ask_depth_1pct=10000.0,
        )
        test_session.add(old_snapshot)

        # New snapshot with low depth (60% drop)
        new_snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            bid_depth_1pct=4000.0,
            ask_depth_1pct=4000.0,
        )
        test_session.add(new_snapshot)

        await test_session.commit()

        analyzer = MarketMakerAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "mm_pullback"
        assert alerts[0].data["depth_drop_pct"] >= 0.5

    @pytest.mark.asyncio
    async def test_ignores_small_drop(self, test_session):
        """20% depth drop should not trigger alert."""
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Old snapshot
        old_snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(hours=3),
            bid_depth_1pct=10000.0,
            ask_depth_1pct=10000.0,
        )
        test_session.add(old_snapshot)

        # New snapshot with small drop (20%)
        new_snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            bid_depth_1pct=8000.0,
            ask_depth_1pct=8000.0,
        )
        test_session.add(new_snapshot)

        await test_session.commit()

        analyzer = MarketMakerAnalyzer()
        alerts = await analyzer.analyze(test_session)

        assert len(alerts) == 0


# =============================================================================
# ArbitrageDetector Tests
# =============================================================================


class TestArbitrageDetector:
    """Tests for intra-market arbitrage detection."""

    @pytest.mark.asyncio
    async def test_detects_underpriced_market(self, test_session):
        """YES=0.40 + NO=0.50 = 0.90 should trigger 10% arb alert."""
        now = datetime.utcnow()
        market = create_test_market(
            yes_token="yes-arb-token",
            no_token="no-arb-token",
        )
        test_session.add(market)

        # Create orderbook with underpriced asks
        yes_snapshot = create_test_snapshot(
            token_id="yes-arb-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.38,
            best_ask=0.40,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-arb-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.48,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "arbitrage"
        assert alerts[0].data["profit_estimate"] >= 0.09  # ~10%

    @pytest.mark.asyncio
    async def test_ignores_fair_market(self, test_session):
        """YES=0.50 + NO=0.50 = 1.0 should not trigger alert."""
        now = datetime.utcnow()
        market = create_test_market(
            yes_token="yes-fair-token",
            no_token="no-fair-token",
        )
        test_session.add(market)

        # Fair market orderbook
        yes_snapshot = create_test_snapshot(
            token_id="yes-fair-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.49,
            best_ask=0.50,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-fair-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.49,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_respects_min_profit_threshold(self, test_session):
        """1% profit (below 2% threshold) should not trigger alert."""
        now = datetime.utcnow()
        market = create_test_market(
            yes_token="yes-small-token",
            no_token="no-small-token",
        )
        test_session.add(market)

        # Small profit opportunity (1%)
        yes_snapshot = create_test_snapshot(
            token_id="yes-small-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.48,
            best_ask=0.495,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-small-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.48,
            best_ask=0.495,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 0  # Below threshold

    @pytest.mark.asyncio
    async def test_deduplicates_arbitrage_alerts(self, test_session):
        """Should not create duplicate arbitrage alerts for same market."""
        now = datetime.utcnow()
        market = create_test_market(
            market_id="arb-dedup-market",
            yes_token="yes-dedup-token",
            no_token="no-dedup-token",
        )
        test_session.add(market)

        # Create existing active arbitrage alert
        existing_alert = Alert.create_arbitrage_alert(
            title="Existing arb",
            description="Already detected",
            market_ids=[market.id],  # This is what dedup checks
            profit_estimate=0.10,
            data={},
        )
        test_session.add(existing_alert)

        # Create orderbook with opportunity
        yes_snapshot = create_test_snapshot(
            token_id="yes-dedup-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.38,
            best_ask=0.40,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-dedup-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.48,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 0  # Deduped

    @pytest.mark.asyncio
    async def test_fallback_to_market_prices(self, test_session):
        """Should use market cache prices when orderbook_prices=False."""
        market = create_test_market(
            yes_price=0.40,  # These are in the market outcomes
            no_price=0.50,
        )
        test_session.add(market)

        await test_session.commit()

        # Use fallback mode (no orderbook)
        detector = ArbitrageDetector(use_orderbook_prices=False)
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].data["price_source"] == "market_cache"

    @pytest.mark.asyncio
    async def test_falls_back_when_orderbook_stale(self, test_session):
        """Should fall back to market prices when orderbook data is stale."""
        now = datetime.utcnow()
        market = create_test_market(
            market_id="stale-test-market",
            yes_token="yes-stale-token",
            no_token="no-stale-token",
            yes_price=0.40,  # Market prices that would trigger arb
            no_price=0.50,
        )
        test_session.add(market)

        # Create stale orderbook snapshots (older than 15 min default)
        yes_snapshot = create_test_snapshot(
            token_id="yes-stale-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=30),  # Stale
            best_bid=0.38,
            best_ask=0.40,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-stale-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=30),  # Stale
            best_bid=0.48,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        # With fallback enabled (default), should use market prices
        detector = ArbitrageDetector(fallback_to_market_prices=True)
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].data["price_source"] == "market_cache"

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self, test_session):
        """Should not fall back when fallback_to_market_prices=False."""
        now = datetime.utcnow()
        market = create_test_market(
            market_id="no-fallback-market",
            yes_token="yes-nofallback-token",
            no_token="no-nofallback-token",
            yes_price=0.40,  # Market prices that would trigger arb
            no_price=0.50,
        )
        test_session.add(market)

        # Create stale orderbook snapshots
        yes_snapshot = create_test_snapshot(
            token_id="yes-nofallback-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=30),  # Stale
            best_bid=0.38,
            best_ask=0.40,
        )
        no_snapshot = create_test_snapshot(
            token_id="no-nofallback-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=30),  # Stale
            best_bid=0.48,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        # With fallback disabled, should not generate alert
        detector = ArbitrageDetector(fallback_to_market_prices=False)
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_falls_back_when_orderbook_missing(self, test_session):
        """Should fall back to market prices when no orderbook data exists."""
        market = create_test_market(
            market_id="missing-ob-market",
            yes_token="yes-missing-token",
            no_token="no-missing-token",
            yes_price=0.40,
            no_price=0.50,
        )
        test_session.add(market)

        # No orderbook snapshots at all
        await test_session.commit()

        detector = ArbitrageDetector(fallback_to_market_prices=True)
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 1
        assert alerts[0].data["price_source"] == "market_cache"

    @pytest.mark.asyncio
    async def test_no_fallback_when_fresh_data_shows_no_opportunity(self, test_session):
        """Fresh orderbook showing no opportunity should NOT fall back to market prices."""
        now = datetime.utcnow()
        # Market prices would show arb opportunity
        market = create_test_market(
            market_id="fresh-no-arb-market",
            yes_token="yes-fresh-token",
            no_token="no-fresh-token",
            yes_price=0.40,  # Market cache: 0.40 + 0.50 = 0.90 (10% arb)
            no_price=0.50,
        )
        test_session.add(market)

        # Fresh orderbook shows NO opportunity (fair prices)
        yes_snapshot = create_test_snapshot(
            token_id="yes-fresh-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),  # Fresh
            best_bid=0.49,
            best_ask=0.50,  # 0.50 + 0.50 = 1.0 (no arb)
        )
        no_snapshot = create_test_snapshot(
            token_id="no-fresh-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),  # Fresh
            best_bid=0.49,
            best_ask=0.50,
        )
        test_session.add(yes_snapshot)
        test_session.add(no_snapshot)

        await test_session.commit()

        # Even with fallback enabled, should NOT use stale market prices
        detector = ArbitrageDetector(fallback_to_market_prices=True)
        alerts = await detector.analyze(test_session)

        # No alert because fresh orderbook showed no opportunity
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_uses_actual_outcome_names(self, test_session):
        """Should use actual outcome names from market, not assume YES/NO."""
        now = datetime.utcnow()
        # Create market with non-standard outcome names
        market = Market(
            id="custom-outcome-market",
            question="Who will win the election?",
            outcomes=[
                {"name": "Biden", "token_id": "biden-token", "price": 0.40},
                {"name": "Trump", "token_id": "trump-token", "price": 0.50},
            ],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)

        # Create orderbook with underpriced asks
        biden_snapshot = create_test_snapshot(
            token_id="biden-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.38,
            best_ask=0.40,
        )
        trump_snapshot = create_test_snapshot(
            token_id="trump-token",
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.48,
            best_ask=0.50,
        )
        test_session.add(biden_snapshot)
        test_session.add(trump_snapshot)

        await test_session.commit()

        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)

        assert len(alerts) == 1
        # Verify actual outcome names are used
        assert alerts[0].data["outcome1_name"] == "Biden"
        assert alerts[0].data["outcome2_name"] == "Trump"
        assert "Biden" in alerts[0].description
        assert "Trump" in alerts[0].description


# =============================================================================
# Integration Tests
# =============================================================================


class TestAnalysisJobIntegration:
    """Integration tests for the full analysis job."""

    @pytest.mark.asyncio
    async def test_run_analysis_job_calls_all_analyzers(self, test_session):
        """Verify all analyzers are called when job runs."""
        # Create test data
        now = datetime.utcnow()
        market = create_test_market()
        test_session.add(market)

        token_id = market.token_ids[0]

        # Add snapshot for spread analysis
        snapshot = create_test_snapshot(
            token_id=token_id,
            market_id=market.id,
            timestamp=now - timedelta(minutes=5),
            best_bid=0.40,
            best_ask=0.60,  # Wide spread
        )
        test_session.add(snapshot)

        await test_session.commit()

        # Run each analyzer and collect results
        volume_analyzer = VolumeAnalyzer()
        spread_analyzer = SpreadAnalyzer()
        mm_analyzer = MarketMakerAnalyzer()
        arb_detector = ArbitrageDetector()

        all_alerts = []
        all_alerts.extend(await volume_analyzer.analyze(test_session))
        all_alerts.extend(await spread_analyzer.analyze(test_session))
        all_alerts.extend(await mm_analyzer.analyze(test_session))
        all_alerts.extend(await arb_detector.analyze(test_session))

        # At minimum, spread alert should trigger
        spread_alerts = [a for a in all_alerts if a.alert_type == "spread_alert"]
        assert len(spread_alerts) >= 1
