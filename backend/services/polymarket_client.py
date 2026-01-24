"""Polymarket API client for Gamma and CLOB APIs."""

import asyncio
import logging
from typing import Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from config import settings
from models.market import Market
from models.orderbook import OrderBookSnapshot

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Client for interacting with Polymarket APIs.

    Uses a shared httpx.AsyncClient for connection pooling and efficiency.
    """

    def __init__(self):
        self.gamma_url = settings.gamma_api_url
        self.clob_url = settings.clob_api_url
        self.timeout = httpx.Timeout(30.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make GET request with error handling using shared client."""
        client = await self._get_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ========== Gamma API (Market Metadata) ==========

    async def get_markets(self, limit: int = 100, offset: int = 0) -> list:
        """Fetch markets from Gamma API."""
        url = f"{self.gamma_url}/markets"
        params = {"limit": limit, "offset": offset, "active": "true"}
        return await self._get(url, params)

    async def get_all_markets(self) -> list:
        """Fetch all active markets with pagination."""
        all_markets = []
        offset = 0
        limit = 100

        while True:
            markets = await self.get_markets(limit=limit, offset=offset)
            if not markets:
                break
            all_markets.extend(markets)
            offset += limit

            # Safety limit
            if offset > 10000:
                logger.warning("Hit safety limit on market pagination")
                break

        return all_markets

    async def sync_markets(self, session: AsyncSession) -> int:
        """Sync markets from Gamma API to database using bulk upsert."""
        logger.info("Syncing markets from Gamma API...")

        try:
            markets_data = await self.get_all_markets()
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return 0

        if not markets_data:
            logger.info("No markets returned from API")
            return 0

        # Prepare records for bulk upsert
        records = []
        for data in markets_data:
            try:
                market_id = data.get("id") or data.get("condition_id")
                if not market_id:
                    continue

                # Parse outcomes
                outcomes = []
                tokens = data.get("tokens", [])
                for token in tokens:
                    token_id = token.get("token_id")
                    # Skip invalid token_ids (must be alphanumeric, reasonable length)
                    if token_id and len(token_id) > 5 and token_id.isalnum():
                        outcomes.append({
                            "name": token.get("outcome", "Unknown"),
                            "token_id": token_id,
                            "price": token.get("price"),
                        })

                # Also check clobTokenIds if tokens is empty
                if not outcomes:
                    clob_token_ids = data.get("clobTokenIds", [])
                    for i, token_id in enumerate(clob_token_ids):
                        # Skip invalid token_ids
                        if not token_id or len(token_id) < 5 or not token_id.isalnum():
                            continue
                        outcome_name = "Yes" if i == 0 else "No" if i == 1 else f"Outcome {i+1}"
                        outcomes.append({
                            "name": outcome_name,
                            "token_id": token_id,
                            "price": None,
                        })

                records.append({
                    "id": market_id,
                    "condition_id": data.get("condition_id") or data.get("conditionId"),
                    "slug": data.get("slug"),
                    "question": data.get("question", "Unknown"),
                    "description": data.get("description"),
                    "outcomes": outcomes,
                    "volume": data.get("volume") or data.get("volumeNum"),
                    "liquidity": data.get("liquidity") or data.get("liquidityNum"),
                    "active": data.get("active", True),
                    "category": data.get("category"),
                })
            except Exception as e:
                logger.warning(f"Failed to process market {data.get('id')}: {e}")
                continue

        if not records:
            logger.info("No valid market records to sync")
            return 0

        # Bulk upsert using PostgreSQL ON CONFLICT
        try:
            stmt = insert(Market).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "question": stmt.excluded.question,
                    "description": stmt.excluded.description,
                    "outcomes": stmt.excluded.outcomes,
                    "volume": stmt.excluded.volume,
                    "liquidity": stmt.excluded.liquidity,
                    "active": stmt.excluded.active,
                    "category": stmt.excluded.category,
                },
            )
            await session.execute(stmt)
            logger.info(f"Synced {len(records)} markets")
            return len(records)
        except Exception as e:
            logger.error(f"Bulk upsert failed: {e}")
            # Rollback the failed transaction before fallback
            await session.rollback()
            # Fallback to individual inserts for non-PostgreSQL or on error
            return await self._sync_markets_fallback(session, records)

    async def _sync_markets_fallback(self, session: AsyncSession, records: list) -> int:
        """Fallback sync using individual operations."""
        # Preload all existing market IDs to avoid N+1 queries
        existing_ids_result = await session.execute(select(Market.id))
        existing_ids = set(row[0] for row in existing_ids_result)

        count = 0
        for record in records:
            try:
                if record["id"] in existing_ids:
                    # Update existing
                    await session.execute(
                        Market.__table__.update()
                        .where(Market.id == record["id"])
                        .values(**{k: v for k, v in record.items() if k != "id"})
                    )
                else:
                    # Insert new
                    session.add(Market(**record))
                count += 1
            except Exception as e:
                logger.warning(f"Failed to sync market {record.get('id')}: {e}")

        return count

    # ========== CLOB API (Order Books & Trades) ==========

    async def get_orderbook(self, token_id: str) -> dict:
        """Fetch order book for a token from CLOB API."""
        url = f"{self.clob_url}/book"
        params = {"token_id": token_id}
        return await self._get(url, params)

    async def get_price(self, token_id: str) -> dict:
        """Fetch current price for a token."""
        url = f"{self.clob_url}/price"
        params = {"token_id": token_id}
        return await self._get(url, params)

    async def get_trades(self, token_id: str, limit: int = 100) -> list:
        """Fetch recent trades for a token."""
        url = f"{self.clob_url}/trades"
        params = {"token_id": token_id, "limit": limit}
        data = await self._get(url, params)
        return data if isinstance(data, list) else data.get("trades", [])

    async def _fetch_single_orderbook(
        self,
        token_id: str,
        market_id: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[OrderBookSnapshot]:
        """Fetch a single orderbook with semaphore for rate limiting."""
        async with semaphore:
            try:
                book_data = await self.get_orderbook(token_id)
                return OrderBookSnapshot.from_api_response(
                    token_id=token_id,
                    market_id=market_id,
                    data=book_data,
                )
            except Exception as e:
                logger.warning(f"Failed to get orderbook for {token_id}: {e}")
                return None

    async def collect_orderbooks(self, session: AsyncSession) -> int:
        """Collect order book snapshots for all active markets with bounded concurrency."""
        logger.info("Collecting order book snapshots...")

        # Get active markets
        result = await session.execute(
            select(Market).where(Market.active == True, Market.enable_order_book == True)
        )
        markets = result.scalars().all()

        # Build list of (token_id, market_id) pairs to fetch
        fetch_tasks = []
        for market in markets:
            for token_id in market.token_ids:
                if token_id:
                    fetch_tasks.append((token_id, market.id))

        if not fetch_tasks:
            logger.info("No orderbooks to collect")
            return 0

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(settings.orderbook_concurrency)

        # Fetch all orderbooks concurrently (with bounded concurrency)
        tasks = [
            self._fetch_single_orderbook(token_id, market_id, semaphore)
            for token_id, market_id in fetch_tasks
        ]
        snapshots = await asyncio.gather(*tasks)

        # Add successful snapshots to session
        count = 0
        for snapshot in snapshots:
            if snapshot is not None:
                session.add(snapshot)
                count += 1

        logger.info(f"Collected {count} order book snapshots")
        return count
