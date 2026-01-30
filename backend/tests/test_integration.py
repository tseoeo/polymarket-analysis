"""Integration tests for full pipeline with mocked external APIs.

All external API calls are mocked to avoid flaky tests and rate limits.
Uses unittest.mock for mocking.
"""

from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import pytest


@pytest.mark.asyncio
class TestFullPipeline:
    """Test full pipeline from market sync to alert generation."""

    async def test_full_pipeline_market_to_alert(self, test_session):
        """Test complete flow: sync market -> collect trades -> analyze -> alert."""
        from models.market import Market
        from models.trade import Trade
        from services.volume_analyzer import VolumeAnalyzer

        # Step 1: Create a market directly (simulating sync)
        market = Market(
            id="test-market-1",
            question="Will test pass?",
            outcomes=[
                {"name": "Yes", "token_id": "token_yes_123456789", "price": 0.7},
                {"name": "No", "token_id": "token_no_1234567890", "price": 0.3},
            ],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)
        await test_session.commit()

        # Step 2: Create baseline trades (last 24h)
        now = datetime.utcnow()
        baseline_trades = []
        for i in range(20):  # Create baseline with moderate volume
            trade = Trade(
                trade_id=f"baseline-{i:03d}",
                token_id="token_yes_123456789",
                market_id="test-market-1",
                price=0.7,
                size=10.0,  # $10 each = $200 total over 23 hours
                side="buy",
                timestamp=now - timedelta(hours=23) + timedelta(hours=i),
            )
            baseline_trades.append(trade)
            test_session.add(trade)

        # Step 3: Create spike trades (last 1h) - 10x the hourly average
        spike_trades = []
        for i in range(30):  # Create spike with high volume
            trade = Trade(
                trade_id=f"spike-{i:03d}",
                token_id="token_yes_123456789",
                market_id="test-market-1",
                price=0.7,
                size=50.0,  # $50 each = $1500 in 1 hour
                side="buy",
                timestamp=now - timedelta(minutes=i * 2),
            )
            spike_trades.append(trade)
            test_session.add(trade)

        await test_session.commit()

        # Step 4: Run volume analyzer
        analyzer = VolumeAnalyzer()
        alerts = await analyzer.analyze(test_session)
        await test_session.commit()

        # Should detect volume spike
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "volume_spike"
        assert "token_yes_123456789" in str(alerts[0].data)

    async def test_trade_collection_dedup_across_runs(self, test_session):
        """Test that duplicate trades are properly deduplicated."""
        from models.market import Market
        from models.trade import Trade
        from sqlalchemy import select

        # Create market
        market = Market(
            id="dedup-market",
            question="Dedup test?",
            outcomes=[{"name": "Yes", "token_id": "dedup_token_12345", "price": 0.5}],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)

        # First run: insert trades
        trade1 = Trade(
            trade_id="unique-trade-001",
            token_id="dedup_token_12345",
            market_id="dedup-market",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        test_session.add(trade1)
        await test_session.commit()

        # Check trade exists
        result = await test_session.execute(
            select(Trade).where(Trade.trade_id == "unique-trade-001")
        )
        assert result.scalar_one() is not None

        # Second run: try to insert same trade (should be caught by unique constraint)
        try:
            trade2 = Trade(
                trade_id="unique-trade-001",  # Same ID
                token_id="dedup_token_12345",
                market_id="dedup-market",
                price=0.5,
                size=100.0,
                side="buy",
                timestamp=datetime.utcnow(),
            )
            test_session.add(trade2)
            await test_session.commit()
            # If we get here, the constraint didn't work as expected
            # (SQLite may silently ignore in some cases)
        except Exception:
            await test_session.rollback()
            # Expected - constraint violation

        # Verify only one trade exists
        result = await test_session.execute(
            select(Trade).where(Trade.trade_id == "unique-trade-001")
        )
        trades = result.scalars().all()
        assert len(trades) == 1


@pytest.mark.asyncio
class TestAnalyzerIntegration:
    """Test analyzer integration with real database queries."""

    async def test_spread_analyzer_with_fresh_data(self, test_session):
        """Test spread analyzer correctly identifies wide spreads."""
        from models.market import Market
        from models.orderbook import OrderBookSnapshot
        from services.spread_analyzer import SpreadAnalyzer

        # Create market
        market = Market(
            id="spread-test-market",
            question="Spread test?",
            outcomes=[{"name": "Yes", "token_id": "spread_token_1234", "price": 0.5}],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)

        # Create orderbook with wide spread (10%)
        snapshot = OrderBookSnapshot(
            token_id="spread_token_1234",
            market_id="spread-test-market",
            timestamp=datetime.utcnow(),
            best_bid=0.45,
            best_ask=0.55,
            spread=0.10,
            spread_pct=0.10,  # 10% spread > 5% threshold
            mid_price=0.50,
            bid_depth_1pct=100,
            ask_depth_1pct=100,
            bid_depth_5pct=100,
            ask_depth_5pct=100,
            imbalance=0.0,
        )
        test_session.add(snapshot)
        await test_session.commit()

        # Run analyzer
        analyzer = SpreadAnalyzer()
        alerts = await analyzer.analyze(test_session)
        await test_session.commit()

        # Should detect wide spread
        assert len(alerts) == 1
        assert alerts[0].alert_type == "spread_alert"
        assert "10.0%" in alerts[0].title

    async def test_mm_analyzer_with_depth_drop(self, test_session):
        """Test MM analyzer detects liquidity withdrawal."""
        from models.market import Market
        from models.orderbook import OrderBookSnapshot
        from services.mm_analyzer import MarketMakerAnalyzer

        # Create market
        market = Market(
            id="mm-test-market",
            question="MM test?",
            outcomes=[{"name": "Yes", "token_id": "mm_token_12345678", "price": 0.5}],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)

        now = datetime.utcnow()

        # Create old snapshot with high depth
        old_snapshot = OrderBookSnapshot(
            token_id="mm_token_12345678",
            market_id="mm-test-market",
            timestamp=now - timedelta(hours=3),
            best_bid=0.49,
            best_ask=0.51,
            spread=0.02,
            spread_pct=0.04,
            mid_price=0.50,
            bid_depth_1pct=1000,  # High depth
            ask_depth_1pct=1000,
            bid_depth_5pct=2000,
            ask_depth_5pct=2000,
            imbalance=0.0,
        )
        test_session.add(old_snapshot)

        # Create new snapshot with low depth (60% drop)
        new_snapshot = OrderBookSnapshot(
            token_id="mm_token_12345678",
            market_id="mm-test-market",
            timestamp=now,
            best_bid=0.49,
            best_ask=0.51,
            spread=0.02,
            spread_pct=0.04,
            mid_price=0.50,
            bid_depth_1pct=200,  # Low depth (80% drop from 1000)
            ask_depth_1pct=200,
            bid_depth_5pct=400,
            ask_depth_5pct=400,
            imbalance=0.0,
        )
        test_session.add(new_snapshot)
        await test_session.commit()

        # Run analyzer
        analyzer = MarketMakerAnalyzer()
        alerts = await analyzer.analyze(test_session)
        await test_session.commit()

        # Should detect MM pullback
        assert len(alerts) == 1
        assert alerts[0].alert_type == "mm_pullback"

    async def test_arbitrage_detector_with_mispricing(self, test_session):
        """Test arbitrage detector finds mispricing opportunities."""
        from models.market import Market
        from models.orderbook import OrderBookSnapshot
        from services.arbitrage_detector import ArbitrageDetector

        # Create binary market
        market = Market(
            id="arb-test-market",
            question="Arb test?",
            outcomes=[
                {"name": "Yes", "token_id": "arb_yes_token_123", "price": 0.40},
                {"name": "No", "token_id": "arb_no_token_1234", "price": 0.50},
            ],
            active=True,
            enable_order_book=True,
        )
        test_session.add(market)

        now = datetime.utcnow()

        # Create orderbook snapshots with mispricing (0.40 + 0.50 = 0.90 < 1.0)
        yes_snapshot = OrderBookSnapshot(
            token_id="arb_yes_token_123",
            market_id="arb-test-market",
            timestamp=now,
            best_bid=0.38,
            best_ask=0.40,  # Buy Yes at 0.40
            spread=0.02,
            spread_pct=0.05,
            mid_price=0.39,
            bid_depth_1pct=100,
            ask_depth_1pct=100,
            bid_depth_5pct=200,
            ask_depth_5pct=200,
            imbalance=0.0,
        )
        test_session.add(yes_snapshot)

        no_snapshot = OrderBookSnapshot(
            token_id="arb_no_token_1234",
            market_id="arb-test-market",
            timestamp=now,
            best_bid=0.48,
            best_ask=0.50,  # Buy No at 0.50
            spread=0.02,
            spread_pct=0.04,
            mid_price=0.49,
            bid_depth_1pct=100,
            ask_depth_1pct=100,
            bid_depth_5pct=200,
            ask_depth_5pct=200,
            imbalance=0.0,
        )
        test_session.add(no_snapshot)
        await test_session.commit()

        # Run analyzer
        detector = ArbitrageDetector()
        alerts = await detector.analyze(test_session)
        await test_session.commit()

        # Should detect arbitrage (0.40 + 0.50 = 0.90, profit = 0.10 = 10%)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "arbitrage"
        assert "10" in alerts[0].title  # 10% profit


@pytest.mark.asyncio
class TestAlertDeduplication:
    """Test that analyzers properly deduplicate alerts."""

    async def test_volume_analyzer_no_duplicate_alerts(self, test_session):
        """Running analyzer twice should not create duplicate alerts."""
        from models.market import Market
        from models.trade import Trade
        from models.alert import Alert
        from services.volume_analyzer import VolumeAnalyzer
        from sqlalchemy import select

        # Setup market and trades that trigger alert
        market = Market(
            id="dedup-vol-market",
            question="Dedup volume test?",
            outcomes=[{"name": "Yes", "token_id": "dedup_vol_token", "price": 0.5}],
            active=True,
        )
        test_session.add(market)

        now = datetime.utcnow()
        # Baseline trades
        for i in range(15):
            trade = Trade(
                trade_id=f"baseline-vol-{i:03d}",
                token_id="dedup_vol_token",
                market_id="dedup-vol-market",
                price=0.5,
                size=10.0,
                side="buy",
                timestamp=now - timedelta(hours=20) + timedelta(hours=i),
            )
            test_session.add(trade)

        # Spike trades
        for i in range(20):
            trade = Trade(
                trade_id=f"spike-vol-{i:03d}",
                token_id="dedup_vol_token",
                market_id="dedup-vol-market",
                price=0.5,
                size=100.0,
                side="buy",
                timestamp=now - timedelta(minutes=i * 2),
            )
            test_session.add(trade)

        await test_session.commit()

        # First run
        analyzer = VolumeAnalyzer()
        alerts1 = await analyzer.analyze(test_session)
        await test_session.commit()

        # Second run
        alerts2 = await analyzer.analyze(test_session)
        await test_session.commit()

        # First run should create alert
        assert len(alerts1) >= 1

        # Second run should NOT create duplicate
        assert len(alerts2) == 0

        # Total alerts in DB should be 1
        result = await test_session.execute(
            select(Alert)
            .where(Alert.alert_type == "volume_spike")
            .where(Alert.market_id == "dedup-vol-market")
        )
        all_alerts = result.scalars().all()
        assert len(all_alerts) == 1
