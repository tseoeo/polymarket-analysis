"""Volume spike detection service.

Detects unusual trading volume by comparing recent volume to historical baseline.
Uses a sliding window approach with configurable parameters.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.trade import Trade
from models.market import Market
from models.alert import Alert

logger = logging.getLogger(__name__)


class VolumeAnalyzer:
    """Detects volume spikes by comparing recent to historical volume.

    Algorithm:
    1. Calculate recent volume (last 1 hour by default)
    2. Calculate baseline hourly average from historical data (last 24h minus recent)
    3. If recent / baseline >= threshold, generate alert

    Deduplication:
    - Only one active alert per (market_id, token_id) combination
    - Stores token_id in alert data for token-level tracking
    """

    def __init__(
        self,
        recent_window_minutes: int = 60,
        baseline_window_hours: int = 24,
        min_trades_for_baseline: int = 10,
    ):
        self.recent_window = timedelta(minutes=recent_window_minutes)
        self.baseline_window = timedelta(hours=baseline_window_hours)
        self.min_trades = min_trades_for_baseline
        self.threshold = settings.volume_spike_threshold

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Analyze all active markets for volume spikes.

        Uses batch queries to reduce database round-trips:
        1. Single query to get all token_ids from active markets
        2. Batch query for recent volumes
        3. Batch query for baseline volumes
        4. Single query for existing active alerts
        """
        now = datetime.utcnow()
        alerts = []

        # Get active markets
        result = await session.execute(
            select(Market).where(Market.active == True)
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

        # Batch fetch recent volumes (last hour)
        recent_start = now - self.recent_window
        recent_volumes = await self._batch_get_volumes(
            session, list(token_to_market.keys()), recent_start, now
        )

        # Batch fetch baseline volumes (last 24h excluding recent hour)
        baseline_start = now - self.baseline_window
        baseline_data = await self._batch_get_baseline(
            session, list(token_to_market.keys()), baseline_start, recent_start
        )

        # Get existing active volume alerts to avoid duplicates
        existing_alerts = await self._get_existing_alerts(session)

        # Analyze each token
        for token_id, market_id in token_to_market.items():
            recent_volume = recent_volumes.get(token_id, 0.0)
            baseline_volume, baseline_count = baseline_data.get(token_id, (0.0, 0))

            # Need minimum trades for reliable baseline
            if baseline_count < self.min_trades:
                continue

            # Calculate hourly average from baseline
            baseline_hours = (self.baseline_window - self.recent_window).total_seconds() / 3600
            hourly_avg = baseline_volume / baseline_hours if baseline_hours > 0 else 0

            if hourly_avg <= 0:
                continue

            # Check for spike
            ratio = recent_volume / hourly_avg
            if ratio < self.threshold:
                continue

            # Check for existing alert (dedup by market_id + token_id)
            alert_key = (market_id, token_id)
            if alert_key in existing_alerts:
                continue

            # Create alert
            alert = Alert.create_volume_alert(
                market_id=market_id,
                title=f"Volume spike: {ratio:.1f}x normal",
                volume_ratio=ratio,
                data={
                    "current_volume": float(recent_volume),
                    "average_volume": float(hourly_avg),
                    "token_id": token_id,
                },
            )
            session.add(alert)
            alerts.append(alert)
            logger.info(f"Volume spike detected: {market_id}/{token_id} at {ratio:.1f}x normal")

        return alerts

    async def _batch_get_volumes(
        self,
        session: AsyncSession,
        token_ids: List[str],
        start: datetime,
        end: datetime,
    ) -> Dict[str, float]:
        """Get total volume for each token in time window (single query)."""
        result = await session.execute(
            select(Trade.token_id, func.sum(Trade.size))
            .where(Trade.token_id.in_(token_ids))
            .where(Trade.timestamp >= start)
            .where(Trade.timestamp < end)
            .group_by(Trade.token_id)
        )
        return {row[0]: float(row[1] or 0) for row in result.all()}

    async def _batch_get_baseline(
        self,
        session: AsyncSession,
        token_ids: List[str],
        start: datetime,
        end: datetime,
    ) -> Dict[str, Tuple[float, int]]:
        """Get baseline volume and trade count for each token (single query).

        Uses func.count() instead of func.count(Trade.trade_id) to include
        all trades, including any pre-Phase-2 trades that may have NULL trade_id.
        """
        result = await session.execute(
            select(Trade.token_id, func.sum(Trade.size), func.count())
            .where(Trade.token_id.in_(token_ids))
            .where(Trade.timestamp >= start)
            .where(Trade.timestamp < end)
            .group_by(Trade.token_id)
        )
        return {row[0]: (float(row[1] or 0), row[2] or 0) for row in result.all()}

    async def _get_existing_alerts(
        self, session: AsyncSession
    ) -> set:
        """Get set of (market_id, token_id) for existing active volume alerts."""
        result = await session.execute(
            select(Alert.market_id, Alert.data)
            .where(Alert.alert_type == "volume_spike")
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
