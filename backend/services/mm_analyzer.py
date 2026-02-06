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

from sqlalchemy.exc import IntegrityError

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

            # Skip if oldest and newest are the same snapshot or too close together
            # (need at least 1 hour of history for meaningful comparison)
            if oldest.id == newest.id or (newest.timestamp - oldest.timestamp).total_seconds() < 3600:
                continue

            # Skip if newest snapshot is stale
            if newest.timestamp < cutoff:
                logger.debug(
                    f"Skipping stale snapshot for MM analysis {token_id}: "
                    f"age={now - newest.timestamp}"
                )
                continue

            # Check for existing alert (dedup by market_id + token_id)
            alert_key = (market_id, token_id)
            if alert_key in existing_alerts:
                continue

            # Check depth at 1%, 5%, and 10% levels
            # Alert if ANY level shows a >= threshold drop
            depth_levels = [
                ("1%", "bid_depth_1pct", "ask_depth_1pct"),
                ("5%", "bid_depth_5pct", "ask_depth_5pct"),
                ("10%", "bid_depth_10pct", "ask_depth_10pct"),
            ]

            worst_drop = 0.0
            worst_level = None
            worst_old_depth = 0.0
            worst_new_depth = 0.0

            for level_name, bid_field, ask_field in depth_levels:
                old_bid = getattr(oldest, bid_field, 0) or 0
                old_ask = getattr(oldest, ask_field, 0) or 0
                new_bid = getattr(newest, bid_field, 0) or 0
                new_ask = getattr(newest, ask_field, 0) or 0

                old_depth = old_bid + old_ask
                new_depth = new_bid + new_ask

                if old_depth <= 0:
                    continue

                drop_ratio = 1 - (new_depth / old_depth)
                if drop_ratio > worst_drop:
                    worst_drop = drop_ratio
                    worst_level = level_name
                    worst_old_depth = old_depth
                    worst_new_depth = new_depth

            if worst_drop < self.drop_threshold:
                continue

            # Create alert with the worst affected level
            alert = Alert.create_mm_pullback_alert(
                market_id=market_id,
                title=f"MM pullback: {worst_drop:.0%} depth reduction at {worst_level}",
                data={
                    "previous_depth": float(worst_old_depth),
                    "current_depth": float(worst_new_depth),
                    "depth_drop_pct": float(worst_drop),
                    "depth_level": worst_level,
                    "token_id": token_id,
                    "lookback_hours": self.lookback.total_seconds() / 3600,
                    "oldest_snapshot_time": oldest.timestamp.isoformat(),
                    "newest_snapshot_time": newest.timestamp.isoformat(),
                },
            )
            try:
                session.add(alert)
                await session.flush()
                alerts.append(alert)
                logger.info(
                    f"MM pullback detected: {market_id}/{token_id} "
                    f"depth dropped {worst_drop:.0%} at {worst_level} level"
                )
            except IntegrityError:
                await session.rollback()
                # Duplicate — another analyzer already created this alert

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
