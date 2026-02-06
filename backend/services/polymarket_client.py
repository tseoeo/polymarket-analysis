"""Polymarket API client for Gamma and CLOB APIs."""

import asyncio
import base64
import hashlib
import hmac
import logging
import random
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Tuple
from urllib.parse import urlencode
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from config import settings
from models.market import Market
from models.orderbook import OrderBookSnapshot

logger = logging.getLogger(__name__)


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an exception should trigger a retry.

    Only retry on:
    - Network errors (timeout, connection)
    - Rate limiting (429)
    - Server errors (5xx)

    Do NOT retry on client errors (4xx except 429) - those are bad requests.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def with_retry(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Decorator for retrying async functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if not _is_retryable_error(e):
                        raise  # Don't retry non-retryable errors (400, 401, 404, etc.)

                    last_exc = e
                    if attempt == max_attempts - 1:
                        break

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    delay += random.uniform(0, delay * 0.25)  # jitter
                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                        f"after {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


class PolymarketClient:
    """Client for interacting with Polymarket APIs.

    Uses a shared httpx.AsyncClient for connection pooling and efficiency.
    """

    def __init__(self):
        self.gamma_url = settings.gamma_api_url
        self.clob_url = settings.clob_api_url
        self.timeout = httpx.Timeout(30.0)
        self._client: Optional[httpx.AsyncClient] = None

        # API credentials for authenticated endpoints
        self.api_key = settings.polymarket_api_key
        self.api_secret = settings.polymarket_api_secret
        self.api_passphrase = settings.polymarket_api_passphrase
        self.wallet_address = settings.polymarket_wallet_address

        # Rate limit monitoring
        self.rate_limit_hits = 0
        self._request_count = 0

    def _has_api_credentials(self) -> bool:
        """Check if API credentials are configured."""
        return all([self.api_key, self.api_secret, self.api_passphrase, self.wallet_address])

    def _create_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Create HMAC-SHA256 signature for CLOB API authentication.

        Per Polymarket's py-clob-client:
        - Secret: urlsafe_b64decode
        - Output: urlsafe_b64encode
        """
        message = f"{timestamp}{method}{path}"
        if body:
            message += body
        secret_bytes = base64.urlsafe_b64decode(self.api_secret)
        signature = hmac.new(secret_bytes, message.encode('utf-8'), hashlib.sha256)
        return base64.urlsafe_b64encode(signature.digest()).decode()

    def _get_auth_headers(self, method: str, path: str, body: str = "") -> dict:
        """Get Level 2 authentication headers for CLOB API request."""
        timestamp = str(int(time.time()))
        signature = self._create_signature(timestamp, method, path, body)
        return {
            "POLY_ADDRESS": self.wallet_address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_API_KEY": self.api_key,
            "POLY_PASSPHRASE": self.api_passphrase,
        }

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

    @with_retry(
        max_attempts=settings.api_max_retries,
        base_delay=settings.api_retry_base_delay,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make GET request with error handling and retry."""
        client = await self._get_client()
        self._request_count += 1
        response = await client.get(url, params=params)
        if response.status_code == 429:
            self.rate_limit_hits += 1
        response.raise_for_status()
        return response.json()

    @with_retry(
        max_attempts=settings.api_max_retries,
        base_delay=settings.api_retry_base_delay,
    )
    async def _get_authenticated(self, url: str, path: str, params: Optional[dict] = None) -> dict:
        """Make authenticated GET request to CLOB API.

        Note: Per py-clob-client, only the base path is signed (no query params).
        Query params are added to the URL after signing.
        """
        if not self._has_api_credentials():
            raise ValueError("API credentials not configured for authenticated request")

        client = await self._get_client()

        # Sign only the base path (no query params) per py-clob-client
        headers = self._get_auth_headers("GET", path)
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    # ========== Gamma API (Market Metadata) ==========

    async def get_markets(self, limit: int = 100, offset: int = 0) -> list:
        """Fetch markets from Gamma API (only active, non-closed markets)."""
        url = f"{self.gamma_url}/markets"
        params = {"limit": limit, "offset": offset, "active": "true", "closed": "false"}
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

        # Disable orderbook collection for all existing markets first
        # The upsert will re-enable only for markets that are currently tradeable
        from sqlalchemy import update
        await session.execute(
            update(Market).values(enable_order_book=False)
        )
        logger.info("Reset enable_order_book for all existing markets")

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
                    # Skip invalid token_ids (must have reasonable length)
                    # Length check filters garbage like "\\", "]", "5" while allowing
                    # valid formats (numeric, hex, or alphanumeric with separators)
                    if token_id and len(token_id) >= 10:
                        outcomes.append({
                            "name": token.get("outcome", "Unknown"),
                            "token_id": token_id,
                            "price": token.get("price"),
                        })

                # Also check clobTokenIds if tokens is empty
                # Note: Gamma API returns these as JSON strings, not arrays
                if not outcomes:
                    import json
                    clob_token_ids_raw = data.get("clobTokenIds", [])
                    outcome_names_raw = data.get("outcomes", [])

                    # Parse JSON strings if needed
                    if isinstance(clob_token_ids_raw, str):
                        try:
                            clob_token_ids = json.loads(clob_token_ids_raw)
                        except json.JSONDecodeError:
                            clob_token_ids = []
                    else:
                        clob_token_ids = clob_token_ids_raw or []

                    if isinstance(outcome_names_raw, str):
                        try:
                            outcome_names = json.loads(outcome_names_raw)
                        except json.JSONDecodeError:
                            outcome_names = []
                    else:
                        outcome_names = outcome_names_raw or []

                    for i, token_id in enumerate(clob_token_ids):
                        # Skip invalid token_ids (length check only)
                        if not token_id or len(str(token_id)) < 10:
                            continue
                        # Use actual outcome name if available
                        if i < len(outcome_names):
                            outcome_name = outcome_names[i]
                        else:
                            outcome_name = "Yes" if i == 0 else "No" if i == 1 else f"Outcome {i+1}"
                        outcomes.append({
                            "name": outcome_name,
                            "token_id": str(token_id),
                            "price": None,
                        })

                # Parse end_date from various API field names
                end_date_raw = (
                    data.get("end_date") or
                    data.get("endDate") or
                    data.get("resolutionDate")
                )
                end_date = None
                if end_date_raw:
                    try:
                        if isinstance(end_date_raw, str):
                            from dateutil.parser import parse as parse_date
                            parsed = parse_date(end_date_raw)
                            # Convert to naive UTC if timezone-aware
                            if parsed.tzinfo is not None:
                                from datetime import timezone
                                end_date = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                            else:
                                end_date = parsed
                        elif isinstance(end_date_raw, (int, float)):
                            # Use utcfromtimestamp to get naive UTC datetime
                            if end_date_raw > 1e12:
                                end_date = datetime.utcfromtimestamp(end_date_raw / 1000)
                            else:
                                end_date = datetime.utcfromtimestamp(end_date_raw)
                    except Exception:
                        pass  # Ignore invalid dates

                # Use Gamma API's enableOrderBook and acceptingOrders fields
                # Only collect orderbooks for markets that are actually tradeable
                api_enable_orderbook = data.get("enableOrderBook", False)
                accepting_orders = data.get("acceptingOrders", False)
                is_closed = data.get("closed", False)
                has_valid_tokens = len(outcomes) > 0

                # Enable orderbook only if API says so AND market is accepting orders
                should_enable = (
                    has_valid_tokens
                    and api_enable_orderbook
                    and accepting_orders
                    and not is_closed
                )

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
                    "end_date": end_date,
                    "enable_order_book": should_enable,
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
                    "end_date": stmt.excluded.end_date,
                    "enable_order_book": stmt.excluded.enable_order_book,
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

    async def get_trades_for_token(self, token_id: str, limit: int = 100) -> list:
        """Fetch recent trades for a specific token from public Data API."""
        data_api_url = "https://data-api.polymarket.com"
        url = f"{data_api_url}/trades"
        params = {"asset_id": token_id, "limit": limit}

        try:
            data = await self._get(url, params)
            trades = data if isinstance(data, list) else data.get("data", data.get("trades", []))
            return trades
        except Exception as e:
            logger.debug(f"Failed to fetch trades for {token_id}: {e}")
            return []

    async def get_all_recent_trades(self, limit: int = 500) -> list:
        """Fetch recent trades from public Data API (no auth required).

        If the API returns exactly `limit` results, paginates with offset
        to ensure no trades are missed during busy periods.
        """
        data_api_url = "https://data-api.polymarket.com"
        url = f"{data_api_url}/trades"
        all_trades = []
        max_pages = 5  # Safety limit on pagination

        try:
            for page in range(max_pages):
                params = {"limit": limit}
                if all_trades:
                    params["offset"] = len(all_trades)

                data = await self._get(url, params)
                trades = data if isinstance(data, list) else data.get("data", data.get("trades", []))

                if not trades:
                    break

                all_trades.extend(trades)

                # If we got fewer than limit, we have all trades
                if len(trades) < limit:
                    break

                logger.info(
                    f"Trade pagination: page {page + 1}, got {len(trades)} trades "
                    f"(total so far: {len(all_trades)}), fetching more..."
                )

            logger.info(f"All recent trades from Data API: {len(all_trades)} found")
            return all_trades
        except Exception as e:
            logger.warning(f"Failed to fetch from Data API: {e}")
            return all_trades if all_trades else []

    async def get_trades(self, token_id: str, limit: int = 100) -> list:
        """Fetch recent trades for a token (requires API authentication)."""
        return await self.get_trades_for_token(token_id, limit)

    async def _fetch_single_orderbook(
        self,
        token_id: str,
        market_id: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[tuple]:
        """Fetch a single orderbook with semaphore for rate limiting.

        Returns a tuple of (snapshot, raw_data_dict) where raw_data_dict
        contains the bids/asks JSON for the latest-only table.
        """
        async with semaphore:
            try:
                book_data = await self.get_orderbook(token_id)
                snapshot = OrderBookSnapshot.from_api_response(
                    token_id=token_id,
                    market_id=market_id,
                    data=book_data,
                )
                raw_data = {
                    "token_id": token_id,
                    "market_id": market_id,
                    "bids": book_data.get("bids", []),
                    "asks": book_data.get("asks", []),
                }
                return (snapshot, raw_data)
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

        # Add successful snapshots to session and UPSERT latest raw orderbooks
        from models.orderbook import OrderBookLatestRaw
        from datetime import datetime

        count = 0
        for result in snapshots:
            if result is not None:
                snapshot, raw_data = result
                session.add(snapshot)
                count += 1

                # UPSERT latest raw orderbook (one row per token_id)
                existing = await session.get(OrderBookLatestRaw, raw_data["token_id"])
                if existing:
                    existing.market_id = raw_data["market_id"]
                    existing.timestamp = datetime.utcnow()
                    existing.bids = raw_data["bids"]
                    existing.asks = raw_data["asks"]
                else:
                    session.add(OrderBookLatestRaw(
                        token_id=raw_data["token_id"],
                        market_id=raw_data["market_id"],
                        bids=raw_data["bids"],
                        asks=raw_data["asks"],
                    ))

        if self.rate_limit_hits > 0:
            logger.warning(
                f"Hit rate limits {self.rate_limit_hits} times during orderbook collection "
                f"({self.rate_limit_hits}/{self._request_count} requests = "
                f"{self.rate_limit_hits / max(self._request_count, 1) * 100:.0f}%)"
            )

        logger.info(f"Collected {count} order book snapshots")
        return count

    # ========== Trade Collection ==========

    async def _fetch_trades_for_token(
        self,
        token_id: str,
        market_id: str,
        semaphore: asyncio.Semaphore,
        since_timestamp: Optional[datetime] = None,
    ) -> list:
        """Fetch trades for a single token with rate limiting.

        Note: API returns max 100 trades. For busy markets, we rely on
        frequent collection (5min default) to avoid gaps. If gaps occur,
        consider reducing trade_collection_interval_minutes.
        """
        from models.trade import Trade

        async with semaphore:
            try:
                trades_data = await self.get_trades(token_id, limit=100)

                # Check if we might be missing trades (got exactly 100)
                if len(trades_data) >= 100:
                    logger.warning(
                        f"Token {token_id} returned 100 trades - may be missing older trades. "
                        "Consider reducing TRADE_COLLECTION_INTERVAL_MINUTES."
                    )

                trades = []
                for data in trades_data:
                    try:
                        trade = Trade.from_api_response(token_id, market_id, data)
                        # Skip trades older than since_timestamp
                        if since_timestamp and trade.timestamp and trade.timestamp < since_timestamp:
                            continue
                        if trade.is_valid():
                            trades.append(trade)
                    except Exception as e:
                        logger.debug(f"Failed to parse trade for {token_id}: {e}")
                return trades

            except Exception as e:
                logger.warning(f"Failed to fetch trades for {token_id}: {e}")
                return []

    async def collect_trades(self, session: AsyncSession) -> Tuple[int, int]:
        """Collect trades by fetching all recent trades and filtering locally.

        Instead of making hundreds of per-token requests, we fetch all recent
        trades from the Data API in one call and filter by our tracked tokens.

        Returns:
            Tuple of (new_trades_count, duplicate_trades_skipped)
        """
        from models.trade import Trade

        logger.info("Collecting trades...")

        # Get active markets with orderbook collection enabled
        result = await session.execute(
            select(Market).where(Market.active == True, Market.enable_order_book == True)
        )
        markets = result.scalars().all()

        # Build set of token_ids we care about and token->market mapping
        token_to_market = {}
        for market in markets:
            for token_id in market.token_ids:
                if token_id:
                    token_to_market[token_id] = market.id

        if not token_to_market:
            logger.info("No tokens to collect trades for")
            return (0, 0)

        logger.info(f"Tracking {len(token_to_market)} tokens across {len(markets)} markets")

        # Fetch ALL recent trades in one request (much more efficient than per-token)
        all_trades_data = await self.get_all_recent_trades(limit=1000)
        logger.info(f"Fetched {len(all_trades_data)} recent trades from Data API")

        # Filter to only trades for tokens we're tracking
        since_timestamp = datetime.utcnow() - timedelta(minutes=settings.trade_lookback_minutes)
        all_trades = []
        seen_ids = set()

        for data in all_trades_data:
            try:
                # Data API uses 'asset' for token_id
                token_id = data.get("asset") or data.get("asset_id") or data.get("token_id")
                if not token_id or token_id not in token_to_market:
                    continue  # Skip trades for tokens we don't track

                market_id = token_to_market[token_id]
                trade = Trade.from_api_response(token_id, market_id, data)

                # Skip old trades and duplicates
                if since_timestamp and trade.timestamp and trade.timestamp < since_timestamp:
                    continue
                if trade.trade_id in seen_ids:
                    continue
                if not trade.is_valid():
                    continue

                seen_ids.add(trade.trade_id)
                all_trades.append(trade)
            except Exception as e:
                logger.debug(f"Failed to parse trade: {e}")

        if not all_trades:
            logger.info("No new trades collected")
            return (0, 0)

        # Pre-filter: check which trade_ids already exist in DB
        existing_ids_result = await session.execute(
            select(Trade.trade_id).where(
                Trade.trade_id.in_([t.trade_id for t in all_trades])
            )
        )
        existing_ids = set(row[0] for row in existing_ids_result)
        new_trades = [t for t in all_trades if t.trade_id not in existing_ids]

        if not new_trades:
            logger.info(f"No new trades (all {len(all_trades)} already exist)")
            return (0, len(all_trades))

        # Bulk insert (no conflict expected after pre-filter)
        try:
            records = [{
                "trade_id": t.trade_id,
                "token_id": t.token_id,
                "market_id": t.market_id,
                "price": t.price,
                "size": t.size,
                "side": t.side,
                "timestamp": t.timestamp,
                "maker_address": t.maker_address,
                "taker_address": t.taker_address,
            } for t in new_trades]

            stmt = insert(Trade).values(records)
            stmt = stmt.on_conflict_do_nothing(index_elements=["trade_id"])
            await session.execute(stmt)

            logger.info(f"Collected {len(new_trades)} new trades")
            return (len(new_trades), len(all_trades) - len(new_trades))

        except Exception as e:
            logger.error(f"Bulk trade insert failed: {e}")
            await session.rollback()

            # Fallback: batch insert with savepoints to isolate failures
            new_count = 0
            dup_count = 0
            for trade in new_trades:
                try:
                    async with session.begin_nested():  # Savepoint
                        session.add(trade)
                    new_count += 1
                except Exception:
                    dup_count += 1

            logger.info(f"Fallback insert: {new_count} new trades, {dup_count} duplicates")
            return (new_count, dup_count)
