"""Tests for Phase 2 data collection features."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestTradeValidation:
    """Tests for trade data validation."""

    @pytest.mark.asyncio
    async def test_trade_rejects_zero_price(self):
        """Trade with price=0 should be invalid."""
        from models.trade import Trade

        trade = Trade(
            trade_id="zero-price",
            token_id="token1",
            market_id="market1",
            price=0.0,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_rejects_price_over_1(self):
        """Trade with price > 1 should be invalid (not a probability)."""
        from models.trade import Trade

        trade = Trade(
            trade_id="high-price",
            token_id="token1",
            market_id="market1",
            price=1.5,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_rejects_negative_size(self):
        """Trade with negative size should be invalid."""
        from models.trade import Trade

        trade = Trade(
            trade_id="neg-size",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=-100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_rejects_invalid_side(self):
        """Trade with invalid side should be invalid."""
        from models.trade import Trade

        trade = Trade(
            trade_id="bad-side",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="hodl",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_allows_none_side(self):
        """Trade with None side should be valid (optional field)."""
        from models.trade import Trade

        trade = Trade(
            trade_id="no-side",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side=None,
            timestamp=datetime.utcnow(),
        )
        assert trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_rejects_missing_timestamp(self):
        """Trade without timestamp should be invalid."""
        from models.trade import Trade

        trade = Trade(
            trade_id="no-ts",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=None,
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_rejects_future_timestamp(self):
        """Trade with future timestamp should be invalid."""
        from models.trade import Trade

        trade = Trade(
            trade_id="future",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow() + timedelta(hours=2),
        )
        assert not trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_handles_tz_aware_timestamp(self):
        """Trade with timezone-aware timestamp should work."""
        from models.trade import Trade

        # Create a trade with tz-aware timestamp
        tz_aware_ts = datetime.now(timezone.utc)
        trade = Trade(
            trade_id="tz-aware",
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=tz_aware_ts,
        )
        # Should not raise during is_valid()
        assert trade.is_valid()

    @pytest.mark.asyncio
    async def test_trade_generates_dedup_key_when_no_id(self):
        """Trade without trade_id should generate dedup key."""
        from models.trade import Trade

        data = {
            "price": "0.5",
            "size": "100",
            "side": "buy",
            "timestamp": datetime.utcnow().isoformat(),
            # No "id" field
        }

        trade = Trade.from_api_response("token1", "market1", data)

        # Should have generated a dedup key
        assert trade.trade_id is not None
        assert len(trade.trade_id) == 32  # SHA256 truncated to 32 chars

    @pytest.mark.asyncio
    async def test_trade_dedup_key_is_deterministic(self):
        """Same trade data should produce same dedup key."""
        from models.trade import Trade

        ts = datetime.utcnow()
        trade1 = Trade(
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=ts,
        )
        trade2 = Trade(
            token_id="token1",
            market_id="market1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=ts,
        )

        assert trade1.compute_dedup_key() == trade2.compute_dedup_key()


class TestTradeCollection:
    """Tests for trade collection functionality."""

    @pytest.mark.asyncio
    async def test_collect_trades_job_exists(self):
        """collect_trades_job should be importable and callable."""
        from jobs.scheduler import collect_trades_job
        assert asyncio.iscoroutinefunction(collect_trades_job)

    @pytest.mark.asyncio
    async def test_scheduler_includes_trades_job(self):
        """Scheduler should register the trades collection job."""
        from jobs.scheduler import start_scheduler, stop_scheduler

        with patch("jobs.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await start_scheduler()

            job_ids = [call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list]
            assert "collect_trades" in job_ids

            await stop_scheduler()

    @pytest.mark.asyncio
    async def test_scheduler_uses_config_interval(self):
        """Scheduler should use trade_collection_interval_minutes from config."""
        from jobs.scheduler import start_scheduler, stop_scheduler
        from config import settings

        with patch("jobs.scheduler.AsyncIOScheduler") as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            await start_scheduler()

            # Find the collect_trades job call
            trades_job_call = None
            for call in mock_scheduler.add_job.call_args_list:
                if call.kwargs.get("id") == "collect_trades":
                    trades_job_call = call
                    break

            assert trades_job_call is not None
            # Check interval matches config
            trigger = trades_job_call.args[1]
            assert trigger.interval.total_seconds() == settings.trade_collection_interval_minutes * 60

            await stop_scheduler()

    @pytest.mark.asyncio
    async def test_collect_trades_respects_concurrency(self, test_session):
        """Trade collection should respect semaphore concurrency limits."""
        from services.polymarket_client import PolymarketClient
        from models.market import Market
        from config import settings

        # Create test market
        market = Market(
            id="trade-test-market",
            question="Trade test?",
            outcomes=[
                {"name": "Yes", "token_id": "token-trade-abc123456"},
                {"name": "No", "token_id": "token-trade-def789012"},
            ],
            active=True,
        )
        test_session.add(market)
        await test_session.commit()

        client = PolymarketClient()

        concurrent_count = 0
        max_concurrent = 0

        async def mock_fetch_trades(token_id, market_id, semaphore, since_ts):
            nonlocal concurrent_count, max_concurrent
            async with semaphore:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.01)
                concurrent_count -= 1
                return []

        with patch.object(client, "_fetch_trades_for_token", side_effect=mock_fetch_trades):
            await client.collect_trades(test_session)

        assert max_concurrent <= settings.orderbook_concurrency

        await client.close()


class TestRetryLogic:
    """Tests for API retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Should retry on timeout errors."""
        from services.polymarket_client import _is_retryable_error
        import httpx

        exc = httpx.TimeoutException("Connection timed out")
        assert _is_retryable_error(exc) is True

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """Should retry on rate limit (429)."""
        from services.polymarket_client import _is_retryable_error
        import httpx

        response = MagicMock()
        response.status_code = 429
        exc = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is True

    @pytest.mark.asyncio
    async def test_retry_on_500(self):
        """Should retry on server error (500)."""
        from services.polymarket_client import _is_retryable_error
        import httpx

        response = MagicMock()
        response.status_code = 500
        exc = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is True

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self):
        """Should NOT retry on bad request (400)."""
        from services.polymarket_client import _is_retryable_error
        import httpx

        response = MagicMock()
        response.status_code = 400
        exc = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is False

    @pytest.mark.asyncio
    async def test_no_retry_on_404(self):
        """Should NOT retry on not found (404)."""
        from services.polymarket_client import _is_retryable_error
        import httpx

        response = MagicMock()
        response.status_code = 404
        exc = httpx.HTTPStatusError("Not found", request=MagicMock(), response=response)
        assert _is_retryable_error(exc) is False


class TestOrderBookEdgeCases:
    """Tests for orderbook edge case handling."""

    @pytest.mark.asyncio
    async def test_orderbook_handles_zero_best_price(self):
        """OrderBook should handle zero best prices."""
        from models.orderbook import OrderBookSnapshot

        api_data = {
            "bids": [{"price": "0", "size": "100"}],
            "asks": [{"price": "0.5", "size": "100"}],
        }

        snapshot = OrderBookSnapshot.from_api_response("token", "market", api_data)

        # best_bid should be None for zero price
        assert snapshot.best_bid is None
        # Depth should be 0 when best_price is invalid
        assert snapshot.bid_depth_1pct == 0.0 or snapshot.bid_depth_1pct is None

    @pytest.mark.asyncio
    async def test_orderbook_handles_empty_levels(self):
        """OrderBook should handle empty bid/ask arrays."""
        from models.orderbook import OrderBookSnapshot

        api_data = {
            "bids": [],
            "asks": [],
        }

        snapshot = OrderBookSnapshot.from_api_response("token", "market", api_data)

        assert snapshot.best_bid is None
        assert snapshot.best_ask is None
        assert snapshot.spread is None
        assert snapshot.mid_price is None

    @pytest.mark.asyncio
    async def test_orderbook_handles_malformed_levels(self):
        """OrderBook should handle malformed price levels gracefully."""
        from models.orderbook import OrderBookSnapshot

        api_data = {
            "bids": [
                {"price": "0.5", "size": "100"},
                {"price": "invalid", "size": "50"},  # Should be skipped
                {"price": "0.4", "size": "abc"},  # Should be skipped
            ],
            "asks": [{"price": "0.6", "size": "200"}],
        }

        snapshot = OrderBookSnapshot.from_api_response("token", "market", api_data)

        # Should not raise, should calculate with valid levels only
        assert snapshot.best_bid == 0.5
        assert snapshot.best_ask == 0.6


class TestMarketEndDate:
    """Tests for market end_date capture."""

    @pytest.mark.asyncio
    async def test_sync_markets_captures_end_date(self, test_session):
        """sync_markets should populate end_date from API response."""
        from services.polymarket_client import PolymarketClient
        from models.market import Market
        from sqlalchemy import select

        client = PolymarketClient()

        mock_markets = [
            {
                "id": "end-date-test",
                "condition_id": "cond-end",
                "question": "End date test?",
                "end_date": "2025-06-01T00:00:00Z",
                "tokens": [{"token_id": "token-end-12345678", "outcome": "Yes"}],
            }
        ]

        with patch.object(client, "get_all_markets", return_value=mock_markets):
            await client.sync_markets(test_session)
            await test_session.commit()

        result = await test_session.execute(
            select(Market).where(Market.id == "end-date-test")
        )
        market = result.scalar_one()

        assert market.end_date is not None
        assert market.end_date.year == 2025
        assert market.end_date.month == 6

        await client.close()

    @pytest.mark.asyncio
    async def test_sync_markets_handles_unix_end_date(self, test_session):
        """sync_markets should handle Unix timestamp end_date."""
        from services.polymarket_client import PolymarketClient
        from models.market import Market
        from sqlalchemy import select

        client = PolymarketClient()

        # 1717200000 = 2024-06-01 00:00:00 UTC
        mock_markets = [
            {
                "id": "unix-end-date",
                "condition_id": "cond-unix",
                "question": "Unix end date?",
                "endDate": 1717200000,
                "tokens": [{"token_id": "token-unix-12345678", "outcome": "Yes"}],
            }
        ]

        with patch.object(client, "get_all_markets", return_value=mock_markets):
            await client.sync_markets(test_session)
            await test_session.commit()

        result = await test_session.execute(
            select(Market).where(Market.id == "unix-end-date")
        )
        market = result.scalar_one()

        assert market.end_date is not None
        assert market.end_date.year == 2024

        await client.close()
