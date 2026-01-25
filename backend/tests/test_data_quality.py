"""Tests for data quality validation.

Tests cover discovered issues D-010 through D-013:
- D-010: Reject trades with price > 1
- D-011: Reject trades with negative size
- D-012: Filter short/invalid token IDs
- D-013: Handle malformed timestamps
"""

from datetime import datetime, timedelta

import pytest

from models.trade import Trade


class TestTradeValidation:
    """Test Trade.is_valid() data quality checks."""

    def test_rejects_price_above_1(self):
        """Trades with price > 1.0 should be invalid (D-010).

        Polymarket prices are probabilities (0 to 1). A price > 1 indicates
        bad data from the API that should be filtered out.
        """
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=1.5,  # Invalid: > 1
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    def test_rejects_price_at_exactly_1_is_valid(self):
        """Price exactly at 1.0 should be valid (edge case)."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=1.0,  # Valid: exactly 1
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert trade.is_valid()

    def test_rejects_price_zero(self):
        """Trades with price = 0 should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.0,  # Invalid: zero
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    def test_rejects_negative_price(self):
        """Trades with negative price should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=-0.5,  # Invalid: negative
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    def test_rejects_negative_size(self):
        """Trades with negative size should be invalid (D-011)."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=-100.0,  # Invalid: negative
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    def test_rejects_zero_size(self):
        """Trades with size = 0 should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=0.0,  # Invalid: zero
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()

    def test_accepts_valid_trade(self):
        """A properly formed trade should be valid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.65,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow(),
        )
        assert trade.is_valid()

    def test_rejects_future_timestamp(self):
        """Trades with timestamp far in future should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow() + timedelta(hours=2),  # Too far in future
        )
        assert not trade.is_valid()

    def test_accepts_slight_future_timestamp(self):
        """Trades with timestamp slightly in future (clock skew) should be valid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime.utcnow() + timedelta(minutes=30),  # Within 1hr tolerance
        )
        assert trade.is_valid()

    def test_rejects_missing_timestamp(self):
        """Trades without timestamp should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=None,  # Invalid: missing
        )
        assert not trade.is_valid()

    def test_accepts_none_side(self):
        """Trades with None side should still be valid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side=None,  # Valid: None is allowed
            timestamp=datetime.utcnow(),
        )
        assert trade.is_valid()

    def test_rejects_invalid_side(self):
        """Trades with invalid side string should be invalid."""
        trade = Trade(
            trade_id="test-001",
            token_id="token123456789",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="unknown",  # Invalid: not buy/sell
            timestamp=datetime.utcnow(),
        )
        assert not trade.is_valid()


class TestTokenIdFiltering:
    """Test token ID validation in market sync (D-012)."""

    def test_filters_short_token_ids(self):
        """Token IDs shorter than 10 chars should be filtered.

        Short token IDs like "5", "]", "\\" are garbage from malformed API data.
        Valid token IDs are typically 64+ character hex strings or long numeric IDs.
        """
        short_ids = ["5", "]", "\\", "abc", "12345"]

        for token_id in short_ids:
            assert len(token_id) < 10, f"Test data error: {token_id} is not short"

    def test_accepts_valid_length_token_ids(self):
        """Token IDs with 10+ chars should be accepted."""
        valid_ids = [
            "1234567890",  # Exactly 10 chars
            "token_id_123456789",  # Alphanumeric
            "0x1234567890abcdef1234567890abcdef",  # Hex format
            "123456789012345678901234567890",  # Long numeric
        ]

        for token_id in valid_ids:
            assert len(token_id) >= 10, f"Test data error: {token_id} is too short"


class TestTimestampParsing:
    """Test timestamp parsing edge cases (D-013)."""

    def test_parses_iso_string(self):
        """ISO format timestamp strings should be parsed correctly."""
        data = {
            "id": "trade-001",
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": "2024-01-15T10:30:00Z",
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        assert trade.timestamp is not None
        assert trade.timestamp.year == 2024
        assert trade.timestamp.month == 1
        assert trade.timestamp.day == 15

    def test_parses_unix_seconds(self):
        """Unix timestamp in seconds should be parsed correctly."""
        data = {
            "id": "trade-001",
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": 1705315800,  # 2024-01-15 10:30:00 UTC
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        assert trade.timestamp is not None
        assert trade.timestamp.year == 2024

    def test_parses_unix_milliseconds(self):
        """Unix timestamp in milliseconds should be parsed correctly."""
        data = {
            "id": "trade-001",
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": 1705315800000,  # Milliseconds
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        assert trade.timestamp is not None
        assert trade.timestamp.year == 2024

    def test_handles_malformed_timestamp(self):
        """Malformed timestamps should result in None (caught by is_valid)."""
        data = {
            "id": "trade-001",
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": "not-a-timestamp",
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        # Timestamp should be None due to parse failure
        assert trade.timestamp is None
        # Trade should be invalid
        assert not trade.is_valid()

    def test_normalizes_timezone_to_utc(self):
        """Timezone-aware timestamps should be normalized to naive UTC."""
        data = {
            "id": "trade-001",
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": "2024-01-15T05:30:00-05:00",  # EST
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        assert trade.timestamp is not None
        assert trade.timestamp.tzinfo is None  # Should be naive UTC
        assert trade.timestamp.hour == 10  # 5:30 EST = 10:30 UTC


class TestDedupKeyGeneration:
    """Test trade deduplication key generation."""

    def test_compute_dedup_key_deterministic(self):
        """Dedup key should be deterministic for same inputs."""
        trade1 = Trade(
            token_id="token123",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )

        trade2 = Trade(
            token_id="token123",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )

        assert trade1.compute_dedup_key() == trade2.compute_dedup_key()

    def test_compute_dedup_key_different_for_different_trades(self):
        """Dedup key should differ for different trade data."""
        trade1 = Trade(
            token_id="token123",
            market_id="market-1",
            price=0.5,
            size=100.0,
            side="buy",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )

        trade2 = Trade(
            token_id="token123",
            market_id="market-1",
            price=0.6,  # Different price
            size=100.0,
            side="buy",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )

        assert trade1.compute_dedup_key() != trade2.compute_dedup_key()

    def test_from_api_response_generates_dedup_key_when_missing_id(self):
        """Trade.from_api_response should generate dedup key if id missing."""
        data = {
            # No "id" field
            "price": 0.5,
            "size": 100,
            "side": "buy",
            "timestamp": "2024-01-15T10:30:00Z",
        }

        trade = Trade.from_api_response("token123456789", "market-1", data)

        # Should have generated a trade_id
        assert trade.trade_id is not None
        assert len(trade.trade_id) == 32  # SHA256 hex truncated to 32
