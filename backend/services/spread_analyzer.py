"""Spread and liquidity analysis service.

Detects wide spreads that indicate poor liquidity or market stress.
Only analyzes fresh orderbook data to avoid stale alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.orderbook import OrderBookSnapshot
from models.market import Market
from models.alert import Alert

logger = logging.getLogger(__name__)


class SpreadAnalyzer:
    """Detects wide spreads indicating poor liquidity.

    Algorithm:
    1. Get latest orderbook snapshot for each token
    2. Check if snapshot is fresh (within max_age)
    3. If spread_pct >= threshold, generate alert

    Freshness check prevents stale snapshots from generating false alerts
    when markets are inactive or data collection is delayed.
    """

    def __init__(
        self,
        max_snapshot_age_minutes: int = 30,
    ):
        self.spread_threshold = settings.spread_alert_threshold  # 0.05 = 5%
        self.max_age = timedelta(minutes=max_snapshot_age_minutes)

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Analyze latest orderbook snapshots for spread issues.

        Uses batch queries to reduce database round-trips.
        """
        now = datetime.utcnow()
        alerts = []

        # Get active markets with orderbook enabled
        result = await session.execute(
            select(Market).where(
                and_(Market.active == True, Market.enable_order_book == True)
            )
        )
        markets = result.scalars().all()

        # Build token_id -> market_id mapping
        token_to_market: Dict[str, str] = {}
        for market in markets:
            for token_id in market.token_ids:
                if token_id:
                    token_to_market[token_id] = market.id

        if not token_to_market:
            return alerts

        # Batch fetch latest snapshots for all tokens
        latest_snapshots = await self._batch_get_latest_snapshots(
            session, list(token_to_market.keys())
        )

        # Get existing active spread alerts
        existing_alerts = await self._get_existing_alerts(session)

        cutoff = now - self.max_age

        for token_id, market_id in token_to_market.items():
            snapshot = latest_snapshots.get(token_id)

            if not snapshot:
                continue

            # Skip stale snapshots
            if snapshot.timestamp < cutoff:
                logger.debug(
                    f"Skipping stale snapshot for {token_id}: "
                    f"age={now - snapshot.timestamp}"
                )
                continue

            if snapshot.spread_pct is None:
                continue

            if snapshot.spread_pct < self.spread_threshold:
                continue

            # Check for existing alert (dedup by market_id + token_id)
            alert_key = (market_id, token_id)
            if alert_key in existing_alerts:
                continue

            # Create alert (convert Decimals to floats for JSON serialization)
            spread_pct_float = float(snapshot.spread_pct)
            alert = Alert.create_spread_alert(
                market_id=market_id,
                title=f"Wide spread: {spread_pct_float:.1%}",
                spread_pct=spread_pct_float,
                data={
                    "spread": float(snapshot.spread) if snapshot.spread else None,
                    "best_bid": float(snapshot.best_bid) if snapshot.best_bid else None,
                    "best_ask": float(snapshot.best_ask) if snapshot.best_ask else None,
                    "token_id": token_id,
                    "snapshot_age_seconds": (now - snapshot.timestamp).total_seconds(),
                },
            )
            session.add(alert)
            alerts.append(alert)
            logger.info(
                f"Wide spread detected: {market_id}/{token_id} at {snapshot.spread_pct:.1%}"
            )

        return alerts

    async def _batch_get_latest_snapshots(
        self,
        session: AsyncSession,
        token_ids: List[str],
    ) -> Dict[str, OrderBookSnapshot]:
        """Get latest snapshot for each token using a window function.

        Uses DISTINCT ON (PostgreSQL) pattern for efficient latest-per-group query.
        Falls back to subquery approach for SQLite compatibility in tests.
        """
        # Use subquery approach for cross-database compatibility
        # For each token, get the max timestamp, then fetch those snapshots
        subq = (
            select(
                OrderBookSnapshot.token_id,
                func.max(OrderBookSnapshot.timestamp).label("max_ts"),
            )
            .where(OrderBookSnapshot.token_id.in_(token_ids))
            .group_by(OrderBookSnapshot.token_id)
            .subquery()
        )

        result = await session.execute(
            select(OrderBookSnapshot)
            .join(
                subq,
                and_(
                    OrderBookSnapshot.token_id == subq.c.token_id,
                    OrderBookSnapshot.timestamp == subq.c.max_ts,
                ),
            )
        )

        return {s.token_id: s for s in result.scalars().all()}

    async def _get_existing_alerts(
        self, session: AsyncSession
    ) -> set:
        """Get set of (market_id, token_id) for existing active spread alerts."""
        result = await session.execute(
            select(Alert.market_id, Alert.data)
            .where(Alert.alert_type == "spread_alert")
            .where(Alert.is_active == True)
        )
        existing = set()
        for row in result.all():
            market_id = row[0]
            data = row[1] or {}
            token_id = data.get("token_id")
            if market_id and token_id:
                existing.add((market_id, token_id))
        return existing
