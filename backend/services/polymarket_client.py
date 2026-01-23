"""Polymarket API client for Gamma and CLOB APIs."""

import logging
from typing import Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.market import Market
from models.orderbook import OrderBookSnapshot

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Client for interacting with Polymarket APIs."""

    def __init__(self):
        self.gamma_url = settings.gamma_api_url
        self.clob_url = settings.clob_api_url
        self.timeout = httpx.Timeout(30.0)

    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make GET request with error handling."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
        """Sync markets from Gamma API to database."""
        logger.info("Syncing markets from Gamma API...")

        try:
            markets_data = await self.get_all_markets()
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return 0

        count = 0
        for data in markets_data:
            try:
                market_id = data.get("id") or data.get("condition_id")
                if not market_id:
                    continue

                # Check if market exists
                existing = await session.get(Market, market_id)

                # Parse outcomes
                outcomes = []
                tokens = data.get("tokens", [])
                for token in tokens:
                    outcomes.append({
                        "name": token.get("outcome", "Unknown"),
                        "token_id": token.get("token_id"),
                        "price": token.get("price"),
                    })

                # Also check clobTokenIds if tokens is empty
                if not outcomes:
                    clob_token_ids = data.get("clobTokenIds", [])
                    for i, token_id in enumerate(clob_token_ids):
                        outcome_name = "Yes" if i == 0 else "No" if i == 1 else f"Outcome {i+1}"
                        outcomes.append({
                            "name": outcome_name,
                            "token_id": token_id,
                            "price": None,
                        })

                if existing:
                    # Update existing market
                    existing.question = data.get("question", existing.question)
                    existing.description = data.get("description")
                    existing.outcomes = outcomes
                    existing.volume = data.get("volume") or data.get("volumeNum")
                    existing.liquidity = data.get("liquidity") or data.get("liquidityNum")
                    existing.active = data.get("active", True)
                    existing.category = data.get("category")
                else:
                    # Create new market
                    market = Market(
                        id=market_id,
                        condition_id=data.get("condition_id") or data.get("conditionId"),
                        slug=data.get("slug"),
                        question=data.get("question", "Unknown"),
                        description=data.get("description"),
                        outcomes=outcomes,
                        end_date=None,  # Parse from data if available
                        volume=data.get("volume") or data.get("volumeNum"),
                        liquidity=data.get("liquidity") or data.get("liquidityNum"),
                        active=data.get("active", True),
                        category=data.get("category"),
                    )
                    session.add(market)

                count += 1
            except Exception as e:
                logger.warning(f"Failed to process market {data.get('id')}: {e}")
                continue

        logger.info(f"Synced {count} markets")
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

    async def collect_orderbooks(self, session: AsyncSession) -> int:
        """Collect order book snapshots for all active markets."""
        logger.info("Collecting order book snapshots...")

        # Get active markets
        result = await session.execute(
            select(Market).where(Market.active == True, Market.enable_order_book == True)
        )
        markets = result.scalars().all()

        count = 0
        for market in markets:
            for token_id in market.token_ids:
                if not token_id:
                    continue

                try:
                    book_data = await self.get_orderbook(token_id)
                    snapshot = OrderBookSnapshot.from_api_response(
                        token_id=token_id,
                        market_id=market.id,
                        data=book_data,
                    )
                    session.add(snapshot)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to get orderbook for {token_id}: {e}")
                    continue

        logger.info(f"Collected {count} order book snapshots")
        return count
