"""Volume spike detection and advanced volume analytics service.

Provides:
- Volume spike detection by comparing recent volume to historical baseline
- 7-day baseline calculation for more robust comparisons
- Volume acceleration metric (rate of change)
- Volume vs price correlation analysis
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError

from config import settings
from models.trade import Trade
from models.market import Market
from models.alert import Alert
from models.volume_stats import VolumeStats

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

        # Also batch fetch 15-minute volumes for flash spike detection
        flash_start = now - timedelta(minutes=15)
        flash_volumes = await self._batch_get_volumes(
            session, list(token_to_market.keys()), flash_start, now
        )

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

            # Check for spike (60-min window)
            ratio = recent_volume / hourly_avg

            # Also check 15-minute flash spike (scale baseline to 15-min equivalent)
            flash_volume = flash_volumes.get(token_id, 0.0)
            quarter_hour_avg = hourly_avg / 4  # 15-min portion of hourly avg
            flash_ratio = flash_volume / quarter_hour_avg if quarter_hour_avg > 0 else 0

            is_standard_spike = ratio >= self.threshold
            is_flash_spike = flash_ratio >= 5 and ratio < self.threshold

            if not is_standard_spike and not is_flash_spike:
                continue

            # Check for existing alert (dedup by market_id + token_id)
            alert_key = (market_id, token_id)
            if alert_key in existing_alerts:
                continue

            # Use the higher ratio for the alert
            effective_ratio = max(ratio, flash_ratio)
            spike_type = "flash_spike" if is_flash_spike else "volume_spike"

            # Create alert
            alert = Alert.create_volume_alert(
                market_id=market_id,
                title=f"Volume spike: {effective_ratio:.1f}x normal"
                      + (" (flash)" if is_flash_spike else ""),
                volume_ratio=effective_ratio,
                data={
                    "current_volume": float(recent_volume),
                    "average_volume": float(hourly_avg),
                    "token_id": token_id,
                    "spike_type": spike_type,
                    "flash_volume_15m": float(flash_volume),
                    "flash_ratio": float(flash_ratio),
                },
            )
            try:
                session.add(alert)
                await session.flush()
                alerts.append(alert)
                logger.info(
                    f"Volume {spike_type} detected: {market_id}/{token_id} "
                    f"at {effective_ratio:.1f}x normal"
                )
            except IntegrityError:
                await session.rollback()
                # Duplicate — another analyzer already created this alert

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

    async def calculate_7day_baseline(
        self,
        session: AsyncSession,
        token_id: str,
    ) -> Dict:
        """Calculate 7-day volume baseline for a token.

        Provides a more robust baseline than 24-hour by using:
        - Daily average volume
        - Day-of-week patterns
        - Overall trend direction

        Args:
            session: Database session
            token_id: Token to analyze

        Returns:
            Dict with baseline metrics
        """
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        # Get daily volumes from VolumeStats if available
        result = await session.execute(
            select(VolumeStats)
            .where(VolumeStats.token_id == token_id)
            .where(VolumeStats.period_type == "day")
            .where(VolumeStats.period_start >= week_ago)
            .order_by(VolumeStats.period_start)
        )
        daily_stats = result.scalars().all()

        if daily_stats:
            # Use pre-aggregated stats
            daily_volumes = [float(s.volume) for s in daily_stats]
            total_volume = sum(daily_volumes)
            daily_avg = total_volume / len(daily_volumes)

            # Calculate trend (positive = increasing)
            if len(daily_volumes) >= 2:
                first_half = sum(daily_volumes[:len(daily_volumes)//2])
                second_half = sum(daily_volumes[len(daily_volumes)//2:])
                trend = (second_half - first_half) / first_half if first_half > 0 else 0
            else:
                trend = 0

            return {
                "token_id": token_id,
                "period_days": len(daily_stats),
                "total_volume": total_volume,
                "daily_avg": daily_avg,
                "min_daily": min(daily_volumes) if daily_volumes else 0,
                "max_daily": max(daily_volumes) if daily_volumes else 0,
                "trend_pct": trend,
                "source": "volume_stats",
            }

        # Fall back to raw trade data
        result = await session.execute(
            select(
                func.date(Trade.timestamp).label("date"),
                func.sum(Trade.size).label("daily_volume"),
            )
            .where(Trade.token_id == token_id)
            .where(Trade.timestamp >= week_ago)
            .group_by(func.date(Trade.timestamp))
            .order_by(func.date(Trade.timestamp))
        )
        rows = result.all()

        if not rows:
            return {
                "token_id": token_id,
                "error": "No trade data available",
            }

        daily_volumes = [float(r[1] or 0) for r in rows]
        total_volume = sum(daily_volumes)
        daily_avg = total_volume / len(daily_volumes)

        # Calculate trend
        if len(daily_volumes) >= 2:
            first_half = sum(daily_volumes[:len(daily_volumes)//2])
            second_half = sum(daily_volumes[len(daily_volumes)//2:])
            trend = (second_half - first_half) / first_half if first_half > 0 else 0
        else:
            trend = 0

        return {
            "token_id": token_id,
            "period_days": len(rows),
            "total_volume": total_volume,
            "daily_avg": daily_avg,
            "min_daily": min(daily_volumes) if daily_volumes else 0,
            "max_daily": max(daily_volumes) if daily_volumes else 0,
            "trend_pct": trend,
            "source": "trades",
        }

    async def calculate_acceleration(
        self,
        session: AsyncSession,
        token_id: str,
        window_hours: int = 6,
    ) -> Dict:
        """Calculate volume acceleration (rate of change).

        Compares recent volume velocity to previous period to detect
        rapidly increasing or decreasing activity.

        Args:
            session: Database session
            token_id: Token to analyze
            window_hours: Size of comparison windows

        Returns:
            Dict with acceleration metrics
        """
        now = datetime.utcnow()
        window = timedelta(hours=window_hours)

        # Recent period
        recent_start = now - window
        recent_end = now

        # Previous period (before recent)
        prev_start = recent_start - window
        prev_end = recent_start

        # Get recent volume
        recent_result = await session.execute(
            select(func.sum(Trade.size), func.count())
            .where(Trade.token_id == token_id)
            .where(Trade.timestamp >= recent_start)
            .where(Trade.timestamp < recent_end)
        )
        recent_row = recent_result.one()
        recent_volume = float(recent_row[0] or 0)
        recent_count = recent_row[1] or 0

        # Get previous volume
        prev_result = await session.execute(
            select(func.sum(Trade.size), func.count())
            .where(Trade.token_id == token_id)
            .where(Trade.timestamp >= prev_start)
            .where(Trade.timestamp < prev_end)
        )
        prev_row = prev_result.one()
        prev_volume = float(prev_row[0] or 0)
        prev_count = prev_row[1] or 0

        # Calculate acceleration
        if prev_volume > 0:
            volume_acceleration = (recent_volume - prev_volume) / prev_volume
        else:
            volume_acceleration = 1.0 if recent_volume > 0 else 0.0

        if prev_count > 0:
            trade_acceleration = (recent_count - prev_count) / prev_count
        else:
            trade_acceleration = 1.0 if recent_count > 0 else 0.0

        return {
            "token_id": token_id,
            "window_hours": window_hours,
            "recent_volume": recent_volume,
            "recent_trade_count": recent_count,
            "previous_volume": prev_volume,
            "previous_trade_count": prev_count,
            "volume_acceleration": volume_acceleration,
            "trade_acceleration": trade_acceleration,
            "signal": "accelerating" if volume_acceleration > 0.5 else
                      "decelerating" if volume_acceleration < -0.3 else "stable",
        }

    async def analyze_volume_price_relationship(
        self,
        session: AsyncSession,
        token_id: str,
        hours: int = 24,
    ) -> Dict:
        """Analyze correlation between volume and price movement.

        Helps identify whether volume is confirming or diverging from price action.

        Args:
            session: Database session
            token_id: Token to analyze
            hours: Hours of history to analyze

        Returns:
            Dict with volume-price analysis
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)

        # Get all trades in the period
        result = await session.execute(
            select(Trade)
            .where(Trade.token_id == token_id)
            .where(Trade.timestamp >= cutoff)
            .order_by(Trade.timestamp)
        )
        trades = result.scalars().all()

        if len(trades) < 5:
            return {
                "token_id": token_id,
                "error": "Insufficient data for correlation analysis",
            }

        # Group trades by hour manually (database-agnostic)
        from collections import defaultdict
        hourly_groups = defaultdict(list)
        for trade in trades:
            hour_key = trade.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_groups[hour_key].append(trade)

        if len(hourly_groups) < 3:
            return {
                "token_id": token_id,
                "error": "Insufficient data for correlation analysis",
            }

        # Calculate hourly aggregates
        hourly_data = []
        for hour_key in sorted(hourly_groups.keys()):
            hour_trades = hourly_groups[hour_key]
            volume = sum(float(t.size) for t in hour_trades)
            avg_price = sum(float(t.price) for t in hour_trades) / len(hour_trades)
            hourly_data.append((hour_key, volume, avg_price))

        # Extract series
        volumes = [r[1] for r in hourly_data]
        prices = [r[2] for r in hourly_data]

        # Calculate simple correlation coefficient
        n = len(volumes)
        mean_vol = sum(volumes) / n
        mean_price = sum(prices) / n

        # Covariance and standard deviations
        cov = sum((v - mean_vol) * (p - mean_price) for v, p in zip(volumes, prices)) / n
        std_vol = (sum((v - mean_vol) ** 2 for v in volumes) / n) ** 0.5
        std_price = (sum((p - mean_price) ** 2 for p in prices) / n) ** 0.5

        if std_vol > 0 and std_price > 0:
            correlation = cov / (std_vol * std_price)
        else:
            correlation = 0.0

        # Price change over period
        if prices[0] > 0:
            price_change = (prices[-1] - prices[0]) / prices[0]
        else:
            price_change = 0.0

        # Volume trend
        vol_first_half = sum(volumes[:n//2])
        vol_second_half = sum(volumes[n//2:])
        volume_trend = (vol_second_half - vol_first_half) / vol_first_half if vol_first_half > 0 else 0

        # Interpretation
        if correlation > 0.5 and price_change > 0 and volume_trend > 0:
            interpretation = "bullish_confirmation"
        elif correlation > 0.5 and price_change < 0 and volume_trend > 0:
            interpretation = "bearish_confirmation"
        elif correlation < -0.3 and price_change > 0:
            interpretation = "bullish_divergence"
        elif correlation < -0.3 and price_change < 0:
            interpretation = "bearish_divergence"
        else:
            interpretation = "neutral"

        return {
            "token_id": token_id,
            "analysis_hours": hours,
            "data_points": n,
            "correlation": correlation,
            "price_change_pct": price_change,
            "volume_trend_pct": volume_trend,
            "total_volume": sum(volumes),
            "avg_hourly_volume": mean_vol,
            "price_start": prices[0],
            "price_end": prices[-1],
            "interpretation": interpretation,
        }


async def aggregate_volume_stats(
    session: AsyncSession,
    period_type: str = "hour",
) -> int:
    """Aggregate trade data into VolumeStats records.

    Called by the scheduler to pre-compute volume statistics
    for faster queries and historical analysis.

    Args:
        session: Database session
        period_type: 'hour', 'day', or 'week'

    Returns:
        Number of stats records created/updated
    """
    now = datetime.utcnow()
    count = 0

    # Determine period boundaries
    if period_type == "hour":
        # Aggregate the previous complete hour
        period_end = now.replace(minute=0, second=0, microsecond=0)
        period_start = period_end - timedelta(hours=1)
    elif period_type == "day":
        # Aggregate the previous complete day
        period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = period_end - timedelta(days=1)
    elif period_type == "week":
        # Aggregate the previous complete week (Monday-Sunday)
        days_since_monday = now.weekday()
        period_end = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        period_start = period_end - timedelta(weeks=1)
    else:
        raise ValueError(f"Invalid period_type: {period_type}")

    # Get all token_ids with trades in this period
    token_result = await session.execute(
        select(Trade.token_id, Trade.market_id)
        .where(Trade.timestamp >= period_start)
        .where(Trade.timestamp < period_end)
        .group_by(Trade.token_id, Trade.market_id)
    )
    tokens = token_result.all()

    for token_id, market_id in tokens:
        # Check if stats already exist for this period
        existing = await session.execute(
            select(VolumeStats)
            .where(VolumeStats.token_id == token_id)
            .where(VolumeStats.period_type == period_type)
            .where(VolumeStats.period_start == period_start)
        )
        if existing.scalar_one_or_none():
            continue  # Skip if already aggregated

        # Get trades for this token in this period
        trades_result = await session.execute(
            select(Trade)
            .where(Trade.token_id == token_id)
            .where(Trade.timestamp >= period_start)
            .where(Trade.timestamp < period_end)
        )
        trades = trades_result.scalars().all()

        if trades:
            stats = VolumeStats.from_trades(
                market_id=market_id,
                token_id=token_id,
                trades=trades,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
            )
            session.add(stats)
            count += 1

    await session.commit()
    logger.info(f"Aggregated {count} {period_type}ly volume stats")
    return count
