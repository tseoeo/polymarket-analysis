"""Market maker pullback detection service.

Detects when market makers withdraw liquidity by comparing orderbook depth
over time. A significant drop in depth suggests MMs are reducing exposure,
which often precedes volatility.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.orderbook import OrderBookSnapshot
from models.market import Market
from models.alert import Alert

logger = logging.getLogger(__name__)


class MarketMakerAnalyzer:
    """Detects market maker liquidity withdrawals.

    Algorithm:
    1. Get oldest and newest snapshots within lookback window
    2. Compare total depth (bid + ask at 1% level)
    3. If depth dropped by >= threshold, generate alert

    Uses depth at 1% level as it represents the most liquid, actively
    managed portion of the order book.
    """

    def __init__(
        self,
        lookback_hours: int = 4,
        depth_drop_threshold: float = 0.5,  # 50% drop triggers alert
        max_snapshot_age_minutes: int = 30,  # Newest snapshot must be fresh
    ):
        self.lookback = timedelta(hours=lookback_hours)
        self.drop_threshold = depth_drop_threshold
        self.max_age = timedelta(minutes=max_snapshot_age_minutes)

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Analyze depth changes for MM pullback patterns.

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

        lookback_start = now - self.lookback
        token_ids = list(token_to_market.keys())

        # Batch fetch oldest snapshots in window
        oldest_snapshots = await self._batch_get_oldest_snapshots(
            session, token_ids, lookback_start
        )

        # Batch fetch newest snapshots
        newest_snapshots = await self._batch_get_newest_snapshots(session, token_ids)

        # Get existing active MM alerts
        existing_alerts = await self._get_existing_alerts(session)

        cutoff = now - self.max_age

        for token_id, market_id in token_to_market.items():
            oldest = oldest_snapshots.get(token_id)
            newest = newest_snapshots.get(token_id)

            if not oldest or not newest:
                continue

            # Skip if newest snapshot is stale
            if newest.timestamp < cutoff:
                logger.debug(
                    f"Skipping stale snapshot for MM analysis {token_id}: "
                    f"age={now - newest.timestamp}"
                )
                continue

            # Calculate total depth at 1% level
            old_depth = (oldest.bid_depth_1pct or 0) + (oldest.ask_depth_1pct or 0)
            new_depth = (newest.bid_depth_1pct or 0) + (newest.ask_depth_1pct or 0)

            if old_depth <= 0:
                continue

            drop_ratio = 1 - (new_depth / old_depth)
            if drop_ratio < self.drop_threshold:
                continue

            # Check for existing alert (dedup by market_id + token_id)
            alert_key = (market_id, token_id)
            if alert_key in existing_alerts:
                continue

            # Create alert
            alert = Alert.create_mm_pullback_alert(
                market_id=market_id,
                title=f"MM pullback: {drop_ratio:.0%} depth reduction",
                data={
                    "old_depth": float(old_depth),
                    "new_depth": float(new_depth),
                    "drop_pct": float(drop_ratio),
                    "token_id": token_id,
                    "lookback_hours": self.lookback.total_seconds() / 3600,
                    "oldest_snapshot_time": oldest.timestamp.isoformat(),
                    "newest_snapshot_time": newest.timestamp.isoformat(),
                },
            )
            session.add(alert)
            alerts.append(alert)
            logger.info(
                f"MM pullback detected: {market_id}/{token_id} "
                f"depth dropped {drop_ratio:.0%}"
            )

        return alerts

    async def _batch_get_oldest_snapshots(
        self,
        session: AsyncSession,
        token_ids: List[str],
        after: datetime,
    ) -> Dict[str, OrderBookSnapshot]:
        """Get oldest snapshot for each token after the given time."""
        subq = (
            select(
                OrderBookSnapshot.token_id,
                func.min(OrderBookSnapshot.timestamp).label("min_ts"),
            )
            .where(OrderBookSnapshot.token_id.in_(token_ids))
            .where(OrderBookSnapshot.timestamp >= after)
            .group_by(OrderBookSnapshot.token_id)
            .subquery()
        )

        result = await session.execute(
            select(OrderBookSnapshot).join(
                subq,
                and_(
                    OrderBookSnapshot.token_id == subq.c.token_id,
                    OrderBookSnapshot.timestamp == subq.c.min_ts,
                ),
            )
        )

        return {s.token_id: s for s in result.scalars().all()}

    async def _batch_get_newest_snapshots(
        self,
        session: AsyncSession,
        token_ids: List[str],
    ) -> Dict[str, OrderBookSnapshot]:
        """Get newest snapshot for each token."""
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
            select(OrderBookSnapshot).join(
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
        """Get set of (market_id, token_id) for existing active MM alerts."""
        result = await session.execute(
            select(Alert.market_id, Alert.data)
            .where(Alert.alert_type == "mm_pullback")
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
