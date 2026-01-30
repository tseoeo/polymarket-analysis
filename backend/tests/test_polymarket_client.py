"""Tests for Polymarket API client."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client."""
    mock_client = AsyncMock()
    mock_client.is_closed = False
    return mock_client


@pytest.mark.asyncio
async def test_get_markets_pagination():
    """Client should handle pagination when fetching markets."""
    from services.polymarket_client import PolymarketClient

    client = PolymarketClient()

    # Mock responses for pagination
    page1 = [{"id": f"market-{i}"} for i in range(100)]
    page2 = [{"id": f"market-{i}"} for i in range(100, 150)]
    page3 = []  # Empty = end of pagination

    with patch.object(client, "_get") as mock_get:
        mock_get.side_effect = [page1, page2, page3]

        markets = await client.get_all_markets()

    assert len(markets) == 150
    assert mock_get.call_count == 3

    await client.close()


@pytest.mark.asyncio
async def test_sync_markets_invalid_token_ids_filtered(test_session):
    """Markets with short/garbage token IDs should be filtered out.

    This verifies the fix for the isalnum() check that was too strict.
    Now we use length-only validation (>= 10 chars).
    """
    from services.polymarket_client import PolymarketClient

    client = PolymarketClient()

    # Mock market data with various token ID formats
    mock_markets = [
        {
            "id": "market-valid",
            "condition_id": "cond-1",
            "question": "Valid market?",
            "tokens": [
                {"token_id": "valid-token-id-12345", "outcome": "Yes", "price": 0.5},
                {"token_id": "another-valid-one-67890", "outcome": "No", "price": 0.5},
            ],
        },
        {
            "id": "market-garbage",
            "condition_id": "cond-2",
            "question": "Garbage tokens?",
            "tokens": [
                {"token_id": "5", "outcome": "Yes"},  # Too short
                {"token_id": "\\", "outcome": "No"},  # Garbage
            ],
        },
        {
            "id": "market-hyphenated",
            "condition_id": "cond-3",
            "question": "Hyphenated tokens?",
            "tokens": [
                {"token_id": "token-with-hyphens-123", "outcome": "Yes"},  # Valid with hyphens
            ],
        },
    ]

    with patch.object(client, "get_all_markets", return_value=mock_markets):
        # Use the fallback path since SQLite doesn't support ON CONFLICT
        count = await client.sync_markets(test_session)
        await test_session.commit()

    # market-garbage should have 0 outcomes (both filtered out)
    # market-valid and market-hyphenated should work
    from sqlalchemy import select
    from models.market import Market

    result = await test_session.execute(select(Market))
    markets = result.scalars().all()

    market_ids = {m.id for m in markets}
    assert "market-valid" in market_ids
    assert "market-hyphenated" in market_ids
    assert "market-garbage" in market_ids  # Still synced but with empty outcomes

    # Check that garbage market has no valid outcomes
    garbage = next(m for m in markets if m.id == "market-garbage")
    assert len(garbage.outcomes) == 0

    # Valid market should have 2 outcomes
    valid = next(m for m in markets if m.id == "market-valid")
    assert len(valid.outcomes) == 2

    await client.close()


@pytest.mark.asyncio
async def test_get_orderbook_returns_snapshot():
    """get_orderbook should return parsed order book data."""
    from services.polymarket_client import PolymarketClient

    client = PolymarketClient()

    mock_book = {
        "bids": [{"price": "0.60", "size": "100"}],
        "asks": [{"price": "0.62", "size": "150"}],
    }

    with patch.object(client, "_get", return_value=mock_book):
        result = await client.get_orderbook("token123")

    assert result == mock_book
    assert result["bids"][0]["price"] == "0.60"

    await client.close()


@pytest.mark.asyncio
async def test_collect_orderbooks_concurrency(test_session):
    """collect_orderbooks should respect the semaphore concurrency limit."""
    from services.polymarket_client import PolymarketClient
    from models.market import Market
    from config import settings

    # Create a test market
    market = Market(
        id="concurrent-test",
        question="Concurrency test?",
        outcomes=[
            {"name": "Yes", "token_id": "token-abc-123456789"},
            {"name": "No", "token_id": "token-def-987654321"},
        ],
        active=True,
        enable_order_book=True,
    )
    test_session.add(market)
    await test_session.commit()

    client = PolymarketClient()

    # Track concurrent calls
    concurrent_count = 0
    max_concurrent = 0

    async def mock_fetch_orderbook(token_id, market_id, semaphore):
        nonlocal concurrent_count, max_concurrent
        async with semaphore:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)  # Small delay to allow overlap
            concurrent_count -= 1

            from models.orderbook import OrderBookSnapshot

            snapshot = OrderBookSnapshot(
                token_id=token_id,
                market_id=market_id,
            )
            raw_data = {
                "token_id": token_id,
                "market_id": market_id,
                "bids": [],
                "asks": [],
            }
            return (snapshot, raw_data)

    with patch.object(client, "_fetch_single_orderbook", side_effect=mock_fetch_orderbook):
        count = await client.collect_orderbooks(test_session)

    # Should have collected 2 orderbooks (one per token)
    assert count == 2
    # Max concurrent should not exceed configured limit
    assert max_concurrent <= settings.orderbook_concurrency

    await client.close()


@pytest.mark.asyncio
async def test_client_reuses_http_connection():
    """Client should reuse the same httpx.AsyncClient for multiple requests."""
    from services.polymarket_client import PolymarketClient

    client = PolymarketClient()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.is_closed = False
        mock_client_class.return_value = mock_instance

        # First call creates client
        await client._get_client()
        # Second call should reuse
        await client._get_client()

    # Should only create one client instance
    assert mock_client_class.call_count == 1

    await client.close()
