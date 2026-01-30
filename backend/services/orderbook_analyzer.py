"""Advanced orderbook analytics service.

Provides:
- Slippage calculation for trade sizing
- Spread pattern analysis by hour
- Best trading hours identification
- Depth analysis at multiple levels
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.orderbook import OrderBookSnapshot, OrderBookLatestRaw

logger = logging.getLogger(__name__)


class OrderbookAnalyzer:
    """Advanced orderbook analysis for trading insights.

    Analyzes historical orderbook snapshots to provide:
    - Slippage estimates for different trade sizes
    - Spread patterns by hour of day
    - Best trading hours with tightest spreads
    - Depth metrics at configurable price levels
    """

    def __init__(
        self,
        snapshot_max_age_minutes: int = 30,
        depth_levels: List[float] = None,
    ):
        """Initialize analyzer.

        Args:
            snapshot_max_age_minutes: Max age for snapshots to be considered "current"
            depth_levels: Price levels for depth calculation (e.g., [0.01, 0.05, 0.10])
        """
        self.snapshot_max_age = timedelta(minutes=snapshot_max_age_minutes)
        self.depth_levels = depth_levels or [0.01, 0.05, 0.10]

    async def calculate_slippage(
        self,
        session: AsyncSession,
        token_id: str,
        trade_size: float,
        side: str,
    ) -> Dict:
        """Calculate expected slippage for a given trade size.

        Walks through the order book to simulate filling an order of the specified size.

        Note: trade_size is in dollars (USD). Orderbook sizes are in shares, so we
        convert each level to dollar capacity (price * size) when consuming.

        Args:
            session: Database session
            token_id: Token to analyze
            trade_size: Dollar amount to trade (USD)
            side: 'buy' or 'sell'

        Returns:
            Dict with slippage metrics:
            - expected_price: Volume-weighted average price
            - best_price: Best available price
            - slippage_pct: Percentage slippage from best price
            - levels_consumed: Number of price levels needed
            - unfilled_dollars: Dollar amount that couldn't be filled
            - filled_dollars: Dollar amount successfully filled
        """
        # Get latest raw orderbook (from latest-only table)
        raw = await session.get(OrderBookLatestRaw, token_id)
        if not raw or not raw.bids or not raw.asks:
            return {
                "error": "No recent orderbook data",
                "token_id": token_id,
            }

        # Select the appropriate side of the book
        levels = raw.asks if side == "buy" else raw.bids
        # Determine best price from the raw data
        best_price = None
        if levels:
            try:
                best_price = float(levels[0].get("price", 0))
                if best_price <= 0:
                    best_price = None
            except (TypeError, ValueError, KeyError):
                pass

        if not levels or not best_price:
            return {
                "error": f"No {side} liquidity available",
                "token_id": token_id,
            }

        # Walk through levels
        # trade_size is in dollars; orderbook "size" is in shares
        remaining_dollars = trade_size
        total_cost = 0.0  # Total dollars spent/received
        total_shares = 0.0  # Total shares filled
        levels_consumed = 0

        for level in levels:
            try:
                price = float(level.get("price", 0))
                size_shares = float(level.get("size", 0))

                if price <= 0 or size_shares <= 0:
                    continue

                levels_consumed += 1

                # Convert this level's share capacity to dollars
                level_capacity_dollars = price * size_shares

                if level_capacity_dollars >= remaining_dollars:
                    # This level can fill the rest
                    # Calculate how many shares we need for remaining_dollars
                    shares_to_fill = remaining_dollars / price
                    total_cost += remaining_dollars
                    total_shares += shares_to_fill
                    remaining_dollars = 0
                    break
                else:
                    # Consume entire level
                    total_cost += level_capacity_dollars
                    total_shares += size_shares
                    remaining_dollars -= level_capacity_dollars

            except (TypeError, ValueError):
                continue

        if total_shares == 0:
            return {
                "error": "Could not fill any of the order",
                "token_id": token_id,
                "trade_size": trade_size,
            }

        # Volume-weighted average price
        expected_price = total_cost / total_shares
        slippage_pct = (expected_price - float(best_price)) / float(best_price) if side == "buy" else (float(best_price) - expected_price) / float(best_price)

        return {
            "token_id": token_id,
            "side": side,
            "trade_size": trade_size,
            "filled_dollars": total_cost,
            "unfilled_dollars": remaining_dollars,
            "filled_shares": total_shares,
            "best_price": float(best_price),
            "expected_price": expected_price,
            "slippage_pct": abs(slippage_pct),
            "levels_consumed": levels_consumed,
            "snapshot_age_seconds": (datetime.utcnow() - raw.timestamp).total_seconds(),
        }

    async def analyze_spread_patterns(
        self,
        session: AsyncSession,
        token_id: str,
        hours: int = 24,
    ) -> Dict:
        """Analyze spread patterns by hour of day.

        Groups historical snapshots by hour and calculates average spreads
        to identify when liquidity is best/worst.

        Args:
            session: Database session
            token_id: Token to analyze
            hours: Number of hours of history to analyze

        Returns:
            Dict with hourly spread data:
            - hourly_spreads: Dict[hour] -> {avg_spread_pct, snapshot_count}
            - best_hour: Hour with tightest average spread
            - worst_hour: Hour with widest average spread
            - overall_avg: Average spread across all hours
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        result = await session.execute(
            select(OrderBookSnapshot)
            .where(OrderBookSnapshot.token_id == token_id)
            .where(OrderBookSnapshot.timestamp >= cutoff)
            .where(OrderBookSnapshot.spread_pct.isnot(None))
        )
        snapshots = result.scalars().all()

        if not snapshots:
            return {
                "error": "No snapshot data available",
                "token_id": token_id,
            }

        # Group by hour of day
        hourly_data = defaultdict(list)
        for snap in snapshots:
            hour = snap.timestamp.hour
            hourly_data[hour].append(float(snap.spread_pct))

        # Calculate averages
        hourly_spreads = {}
        for hour, spreads in hourly_data.items():
            hourly_spreads[hour] = {
                "avg_spread_pct": sum(spreads) / len(spreads),
                "min_spread_pct": min(spreads),
                "max_spread_pct": max(spreads),
                "snapshot_count": len(spreads),
            }

        if not hourly_spreads:
            return {
                "error": "Insufficient data for pattern analysis",
                "token_id": token_id,
            }

        # Find best and worst hours
        best_hour = min(hourly_spreads.keys(), key=lambda h: hourly_spreads[h]["avg_spread_pct"])
        worst_hour = max(hourly_spreads.keys(), key=lambda h: hourly_spreads[h]["avg_spread_pct"])

        all_spreads = [float(s.spread_pct) for s in snapshots]
        overall_avg = sum(all_spreads) / len(all_spreads)

        return {
            "token_id": token_id,
            "analysis_period_hours": hours,
            "snapshot_count": len(snapshots),
            "hourly_spreads": hourly_spreads,
            "best_hour": best_hour,
            "best_hour_spread": hourly_spreads[best_hour]["avg_spread_pct"],
            "worst_hour": worst_hour,
            "worst_hour_spread": hourly_spreads[worst_hour]["avg_spread_pct"],
            "overall_avg_spread": overall_avg,
        }

    async def get_best_trading_hours(
        self,
        session: AsyncSession,
        token_id: str,
        hours: int = 168,  # 7 days
        top_n: int = 5,
    ) -> List[Dict]:
        """Get the best hours to trade based on historical spread data.

        Args:
            session: Database session
            token_id: Token to analyze
            hours: Hours of history to analyze (default 7 days)
            top_n: Number of best hours to return

        Returns:
            List of dicts with hour and spread metrics, sorted by best spread
        """
        patterns = await self.analyze_spread_patterns(session, token_id, hours)

        if "error" in patterns:
            return [patterns]

        hourly = patterns.get("hourly_spreads", {})
        if not hourly:
            return []

        # Sort by average spread (ascending = best first)
        sorted_hours = sorted(
            hourly.items(),
            key=lambda x: x[1]["avg_spread_pct"],
        )

        return [
            {
                "hour": hour,
                "avg_spread_pct": data["avg_spread_pct"],
                "min_spread_pct": data["min_spread_pct"],
                "snapshot_count": data["snapshot_count"],
                "recommendation": "excellent" if data["avg_spread_pct"] < 0.02 else
                                  "good" if data["avg_spread_pct"] < 0.05 else
                                  "fair" if data["avg_spread_pct"] < 0.10 else "poor",
            }
            for hour, data in sorted_hours[:top_n]
        ]

    async def get_depth_at_levels(
        self,
        session: AsyncSession,
        token_id: str,
    ) -> Dict:
        """Get current order book depth at multiple price levels.

        Args:
            session: Database session
            token_id: Token to analyze

        Returns:
            Dict with depth metrics at configured levels
        """
        snapshot = await self._get_latest_snapshot(session, token_id)
        if not snapshot:
            return {
                "error": "No recent orderbook data",
                "token_id": token_id,
            }

        result = {
            "token_id": token_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "best_bid": float(snapshot.best_bid) if snapshot.best_bid else None,
            "best_ask": float(snapshot.best_ask) if snapshot.best_ask else None,
            "spread_pct": float(snapshot.spread_pct) if snapshot.spread_pct else None,
            "imbalance": float(snapshot.imbalance) if snapshot.imbalance else None,
            "depth": {},
        }

        # Use stored depth values if available
        if snapshot.bid_depth_1pct is not None:
            result["depth"]["1%"] = {
                "bid_depth": float(snapshot.bid_depth_1pct),
                "ask_depth": float(snapshot.ask_depth_1pct) if snapshot.ask_depth_1pct else 0,
            }
        if snapshot.bid_depth_5pct is not None:
            result["depth"]["5%"] = {
                "bid_depth": float(snapshot.bid_depth_5pct),
                "ask_depth": float(snapshot.ask_depth_5pct) if snapshot.ask_depth_5pct else 0,
            }

        # Calculate depth at 10% level from latest raw orderbook
        raw = await session.get(OrderBookLatestRaw, token_id)
        if raw and raw.bids and snapshot.best_bid:
            bid_depth_10pct = self._calculate_depth(
                raw.bids, float(snapshot.best_bid), 0.10, is_bid=True
            )
            ask_depth_10pct = self._calculate_depth(
                raw.asks, float(snapshot.best_ask), 0.10, is_bid=False
            ) if raw.asks and snapshot.best_ask else 0

            result["depth"]["10%"] = {
                "bid_depth": bid_depth_10pct,
                "ask_depth": ask_depth_10pct,
            }

        return result

    async def get_orderbook_history(
        self,
        session: AsyncSession,
        token_id: str,
        hours: int = 24,
    ) -> List[Dict]:
        """Get historical orderbook metrics.

        Args:
            session: Database session
            token_id: Token to analyze
            hours: Hours of history to retrieve

        Returns:
            List of snapshot summaries with key metrics
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        result = await session.execute(
            select(OrderBookSnapshot)
            .where(OrderBookSnapshot.token_id == token_id)
            .where(OrderBookSnapshot.timestamp >= cutoff)
            .order_by(OrderBookSnapshot.timestamp.desc())
        )
        snapshots = result.scalars().all()

        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "best_bid": float(s.best_bid) if s.best_bid else None,
                "best_ask": float(s.best_ask) if s.best_ask else None,
                "spread_pct": float(s.spread_pct) if s.spread_pct else None,
                "mid_price": float(s.mid_price) if s.mid_price else None,
                "imbalance": float(s.imbalance) if s.imbalance else None,
                "bid_depth_1pct": float(s.bid_depth_1pct) if s.bid_depth_1pct else None,
                "ask_depth_1pct": float(s.ask_depth_1pct) if s.ask_depth_1pct else None,
            }
            for s in snapshots
        ]

    async def _get_latest_snapshot(
        self,
        session: AsyncSession,
        token_id: str,
    ) -> Optional[OrderBookSnapshot]:
        """Get the most recent snapshot for a token within max age."""
        cutoff = datetime.utcnow() - self.snapshot_max_age

        result = await session.execute(
            select(OrderBookSnapshot)
            .where(OrderBookSnapshot.token_id == token_id)
            .where(OrderBookSnapshot.timestamp >= cutoff)
            .order_by(OrderBookSnapshot.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _calculate_depth(
        self,
        levels: List[Dict],
        best_price: float,
        pct: float,
        is_bid: bool,
    ) -> float:
        """Calculate total dollar depth within percentage of best price.

        Note: Orderbook "size" is in shares, not dollars. We convert to dollars
        by multiplying price * size for each level.
        """
        if not levels or best_price <= 0:
            return 0.0

        total = 0.0
        threshold = best_price * (1 - pct) if is_bid else best_price * (1 + pct)

        for level in levels:
            try:
                price = float(level.get("price", 0))
                size = float(level.get("size", 0))

                if price <= 0 or size <= 0:
                    continue

                if is_bid and price >= threshold:
                    # Convert shares to dollars: price * size
                    total += price * size
                elif not is_bid and price <= threshold:
                    # Convert shares to dollars: price * size
                    total += price * size
            except (TypeError, ValueError):
                continue

        return total
