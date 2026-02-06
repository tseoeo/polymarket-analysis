"""Cross-market arbitrage detection service.

Detects pricing anomalies across related markets:
- Type A: Mutually exclusive markets (sum > 100%)
- Type B: Conditional markets (child > parent)
- Type C: Time sequence (earlier > later)
- Type D: Subset mispricing (specific > general)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError

from config import settings
from models.market import Market
from models.relationship import MarketRelationship
from models.orderbook import OrderBookSnapshot
from models.alert import Alert

logger = logging.getLogger(__name__)


class CrossMarketArbitrageDetector:
    """Detects arbitrage opportunities across related markets.

    Uses pre-defined market relationships to identify:
    1. Mutually exclusive mispricing (probabilities sum > 100%)
    2. Conditional mispricing (child probability > parent)
    3. Time inversion (earlier deadline priced higher)
    4. Subset mispricing (specific outcome > general outcome)
    """

    def __init__(
        self,
        max_snapshot_age_minutes: int = None,
        min_liquidity: float = None,
    ):
        self.min_profit = settings.arbitrage_min_profit
        self.max_age = timedelta(minutes=max_snapshot_age_minutes or settings.orderbook_max_age_minutes)
        self.min_liquidity = min_liquidity or settings.arb_min_liquidity

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Run all cross-market arbitrage detectors.

        Returns list of alerts for detected opportunities.
        """
        alerts = []

        # Get existing active cross-market arbitrage alerts
        existing = await self._get_existing_alerts(session)

        # Run each type of detection
        alerts.extend(await self.detect_mutually_exclusive_arb(session, existing))
        alerts.extend(await self.detect_conditional_arb(session, existing))
        alerts.extend(await self.detect_time_inversion(session, existing))
        alerts.extend(await self.detect_subset_mispricing(session, existing))

        return alerts

    async def detect_mutually_exclusive_arb(
        self,
        session: AsyncSession,
        existing_alerts: Set[str],
    ) -> List[Alert]:
        """Detect arbitrage in mutually exclusive market groups.

        Two strategies:
        - Sell-all: If sum(YES prices) > 100%, sell all outcomes
        - Buy-all: If sum(YES prices) < 100%, buy all outcomes
        """
        alerts = []

        # Get all mutually exclusive relationships grouped
        result = await session.execute(
            select(MarketRelationship)
            .where(MarketRelationship.relationship_type == "mutually_exclusive")
            .where(MarketRelationship.group_id.isnot(None))
        )
        relationships = result.scalars().all()

        # Group by group_id
        groups = defaultdict(set)
        for rel in relationships:
            groups[rel.group_id].add(rel.parent_market_id)
            groups[rel.group_id].add(rel.child_market_id)

        for group_id, market_ids in groups.items():
            # Check for legacy alert key - if exists, suppress both new keys
            legacy_key = f"exclusive-{group_id}"
            if legacy_key in existing_alerts:
                continue  # Legacy alert exists, skip this group entirely

            # Get market prices with side-aware pricing
            # For sell-all, we use bid prices; for buy-all, we use ask prices
            sell_prices = await self._get_market_prices(
                session, list(market_ids), side="sell"
            )
            buy_prices = await self._get_market_prices(
                session, list(market_ids), side="buy"
            )

            if len(sell_prices) < len(market_ids) or len(buy_prices) < len(market_ids):
                continue  # Not all markets have prices

            # Check for sell-all opportunity (sum > 1)
            sell_alert_key = f"exclusive-sell-{group_id}"
            if sell_alert_key not in existing_alerts:
                sell_total = sum(
                    p["yes_price"] for p in sell_prices.values() if p.get("yes_price")
                )

                if sell_total > 1.0:
                    profit = sell_total - 1.0
                    min_liq = min(p.get("liquidity", 0) for p in sell_prices.values())

                    if profit >= self.min_profit and min_liq >= self.min_liquidity:
                        alert = Alert.create_arbitrage_alert(
                            title=f"Cross-market: {profit:.1%} profit (sell all)",
                            description=(
                                f"Sell all {len(market_ids)} mutually exclusive outcomes. "
                                f"Combined probability {sell_total:.1%} > 100%"
                            ),
                            market_ids=list(market_ids),
                            profit_estimate=profit,
                            data={
                                "type": "mutually_exclusive",
                                "group_id": group_id,
                                "markets": {
                                    mid: sell_prices[mid]
                                    for mid in market_ids
                                    if mid in sell_prices
                                },
                                "total_probability": sell_total,
                                "strategy": "sell_all_outcomes",
                            },
                        )
                        alert.expires_at = datetime.utcnow() + timedelta(minutes=30)
                        try:
                            session.add(alert)
                            await session.flush()
                            alerts.append(alert)
                            logger.info(
                                f"Mutually exclusive sell-all: {group_id} profit={profit:.2%}"
                            )
                        except IntegrityError:
                            await session.rollback()

            # Check for buy-all opportunity (sum < 1)
            buy_alert_key = f"exclusive-buy-{group_id}"
            if buy_alert_key not in existing_alerts:
                buy_total = sum(
                    p["yes_price"] for p in buy_prices.values() if p.get("yes_price")
                )

                if buy_total < 1.0:
                    profit = 1.0 - buy_total
                    min_liq = min(p.get("liquidity", 0) for p in buy_prices.values())

                    if profit >= self.min_profit and min_liq >= self.min_liquidity:
                        alert = Alert.create_arbitrage_alert(
                            title=f"Cross-market: {profit:.1%} profit (buy all)",
                            description=(
                                f"Buy all {len(market_ids)} mutually exclusive outcomes. "
                                f"Combined probability {buy_total:.1%} < 100%"
                            ),
                            market_ids=list(market_ids),
                            profit_estimate=profit,
                            data={
                                "type": "mutually_exclusive",
                                "group_id": group_id,
                                "markets": {
                                    mid: buy_prices[mid]
                                    for mid in market_ids
                                    if mid in buy_prices
                                },
                                "total_probability": buy_total,
                                "strategy": "buy_all_outcomes",
                            },
                        )
                        alert.expires_at = datetime.utcnow() + timedelta(minutes=30)
                        try:
                            session.add(alert)
                            await session.flush()
                            alerts.append(alert)
                            logger.info(
                                f"Mutually exclusive buy-all: {group_id} profit={profit:.2%}"
                            )
                        except IntegrityError:
                            await session.rollback()

        return alerts

    async def detect_conditional_arb(
        self,
        session: AsyncSession,
        existing_alerts: Set[str],
    ) -> List[Alert]:
        """Detect conditional relationship violations.

        If a child event requires a parent event, child probability
        should never exceed parent probability.

        Strategy: buy_parent_sell_child
        - Buy parent at ask price
        - Sell child at bid price
        - Profit if child_bid > parent_ask
        """
        alerts = []

        result = await session.execute(
            select(MarketRelationship)
            .where(MarketRelationship.relationship_type == "conditional")
        )
        relationships = result.scalars().all()

        for rel in relationships:
            alert_key = f"conditional-{rel.parent_market_id}-{rel.child_market_id}"
            if alert_key in existing_alerts:
                continue

            # Side-aware pricing: buy parent (ask), sell child (bid)
            parent_prices = await self._get_market_prices(
                session, [rel.parent_market_id], side="buy"
            )
            child_prices = await self._get_market_prices(
                session, [rel.child_market_id], side="sell"
            )

            parent_price = parent_prices.get(rel.parent_market_id, {}).get("yes_price")
            child_price = child_prices.get(rel.child_market_id, {}).get("yes_price")

            if parent_price is None or child_price is None:
                continue

            # Child bid should be <= parent ask for no arbitrage
            if child_price <= parent_price:
                continue

            # Calculate potential profit (sell child bid - buy parent ask)
            profit = child_price - parent_price
            if profit < self.min_profit:
                continue

            alert = Alert.create_arbitrage_alert(
                title=f"Conditional violation: {profit:.1%} profit",
                description=(
                    f"Child market priced higher than parent. "
                    f"Sell child @ {child_price:.1%}, Buy parent @ {parent_price:.1%}"
                ),
                market_ids=[rel.parent_market_id, rel.child_market_id],
                profit_estimate=profit,
                data={
                    "type": "conditional",
                    "parent_market_id": rel.parent_market_id,
                    "parent_price": parent_price,
                    "parent_side": "buy",
                    "child_market_id": rel.child_market_id,
                    "child_price": child_price,
                    "child_side": "sell",
                    "strategy": "buy_parent_sell_child",
                },
            )
            alert.expires_at = datetime.utcnow() + timedelta(minutes=30)
            try:
                session.add(alert)
                await session.flush()
                alerts.append(alert)
                logger.info(f"Conditional arb: {rel.parent_market_id} -> {rel.child_market_id}")
            except IntegrityError:
                await session.rollback()

        return alerts

    async def detect_time_inversion(
        self,
        session: AsyncSession,
        existing_alerts: Set[str],
    ) -> List[Alert]:
        """Detect time sequence inversions.

        Earlier deadline events should price <= later deadline events
        (assuming same underlying outcome).

        Strategy: sell_earlier_buy_later
        - Sell earlier at bid price
        - Buy later at ask price
        - Profit if earlier_bid > later_ask
        """
        alerts = []

        result = await session.execute(
            select(MarketRelationship)
            .where(MarketRelationship.relationship_type == "time_sequence")
        )
        relationships = result.scalars().all()

        for rel in relationships:
            earlier_id = rel.parent_market_id  # parent = earlier
            later_id = rel.child_market_id     # child = later

            alert_key = f"time-{earlier_id}-{later_id}"
            if alert_key in existing_alerts:
                continue

            # Side-aware pricing: sell earlier (bid), buy later (ask)
            earlier_prices = await self._get_market_prices(
                session, [earlier_id], side="sell"
            )
            later_prices = await self._get_market_prices(
                session, [later_id], side="buy"
            )

            earlier_price = earlier_prices.get(earlier_id, {}).get("yes_price")
            later_price = later_prices.get(later_id, {}).get("yes_price")

            if earlier_price is None or later_price is None:
                continue

            # Earlier bid should be <= later ask for no arbitrage
            if earlier_price <= later_price:
                continue

            # Profit = sell earlier bid - buy later ask
            profit = earlier_price - later_price
            if profit < self.min_profit:
                continue

            alert = Alert.create_arbitrage_alert(
                title=f"Time inversion: {profit:.1%} profit",
                description=(
                    f"Earlier deadline priced higher than later. "
                    f"Sell earlier @ {earlier_price:.1%}, Buy later @ {later_price:.1%}"
                ),
                market_ids=[earlier_id, later_id],
                profit_estimate=profit,
                data={
                    "type": "time_sequence",
                    "earlier_market_id": earlier_id,
                    "earlier_price": earlier_price,
                    "earlier_side": "sell",
                    "later_market_id": later_id,
                    "later_price": later_price,
                    "later_side": "buy",
                    "strategy": "sell_earlier_buy_later",
                },
            )
            alert.expires_at = datetime.utcnow() + timedelta(minutes=30)
            try:
                session.add(alert)
                await session.flush()
                alerts.append(alert)
                logger.info(f"Time inversion arb: {earlier_id} -> {later_id}")
            except IntegrityError:
                await session.rollback()

        return alerts

    async def detect_subset_mispricing(
        self,
        session: AsyncSession,
        existing_alerts: Set[str],
    ) -> List[Alert]:
        """Detect subset relationship violations.

        Specific outcome (subset) should price <= general outcome.
        E.g., "wins by 10+" should price <= "wins"

        Strategy: sell_specific_buy_general
        - Sell specific at bid price
        - Buy general at ask price
        - Profit if specific_bid > general_ask
        """
        alerts = []

        result = await session.execute(
            select(MarketRelationship)
            .where(MarketRelationship.relationship_type == "subset")
        )
        relationships = result.scalars().all()

        for rel in relationships:
            general_id = rel.parent_market_id   # parent = general/superset
            specific_id = rel.child_market_id   # child = specific/subset

            alert_key = f"subset-{general_id}-{specific_id}"
            if alert_key in existing_alerts:
                continue

            # Side-aware pricing: sell specific (bid), buy general (ask)
            specific_prices = await self._get_market_prices(
                session, [specific_id], side="sell"
            )
            general_prices = await self._get_market_prices(
                session, [general_id], side="buy"
            )

            general_price = general_prices.get(general_id, {}).get("yes_price")
            specific_price = specific_prices.get(specific_id, {}).get("yes_price")

            if general_price is None or specific_price is None:
                continue

            # Specific bid should be <= general ask for no arbitrage
            if specific_price <= general_price:
                continue

            # Profit = sell specific bid - buy general ask
            profit = specific_price - general_price
            if profit < self.min_profit:
                continue

            alert = Alert.create_arbitrage_alert(
                title=f"Subset mispricing: {profit:.1%} profit",
                description=(
                    f"Specific outcome priced higher than general. "
                    f"Sell specific @ {specific_price:.1%}, Buy general @ {general_price:.1%}"
                ),
                market_ids=[general_id, specific_id],
                profit_estimate=profit,
                data={
                    "type": "subset",
                    "general_market_id": general_id,
                    "general_price": general_price,
                    "general_side": "buy",
                    "specific_market_id": specific_id,
                    "specific_price": specific_price,
                    "specific_side": "sell",
                    "strategy": "sell_specific_buy_general",
                },
            )
            alert.expires_at = datetime.utcnow() + timedelta(minutes=30)
            try:
                session.add(alert)
                await session.flush()
                alerts.append(alert)
                logger.info(f"Subset mispricing: {general_id} -> {specific_id}")
            except IntegrityError:
                await session.rollback()

        return alerts

    async def get_arbitrage_opportunities(
        self,
        session: AsyncSession,
        include_inactive: bool = False,
    ) -> List[Dict]:
        """Get all cross-market arbitrage opportunities (active alerts)."""
        # Query arbitrage alerts and filter by type in Python for SQLite compatibility
        query = select(Alert).where(Alert.alert_type == "arbitrage")

        if not include_inactive:
            query = query.where(Alert.is_active == True)

        result = await session.execute(query.order_by(Alert.created_at.desc()))
        alerts = result.scalars().all()

        # Filter by cross-market types
        cross_market_types = {"mutually_exclusive", "conditional", "time_sequence", "subset"}
        filtered_alerts = [
            alert for alert in alerts
            if alert.data and alert.data.get("type") in cross_market_types
        ]

        return [
            {
                "id": alert.id,
                "type": alert.data.get("type") if alert.data else None,
                "title": alert.title,
                "description": alert.description,
                "profit_estimate": alert.data.get("profit_estimate") if alert.data else None,
                "market_ids": alert.related_market_ids,
                "strategy": alert.data.get("strategy") if alert.data else None,
                "created_at": alert.created_at.isoformat(),
                "is_active": alert.is_active,
            }
            for alert in filtered_alerts
        ]

    async def _get_market_prices(
        self,
        session: AsyncSession,
        market_ids: List[str],
        side: str = "sell",
    ) -> Dict[str, Dict]:
        """Get YES prices for markets, preferring orderbook data.

        Args:
            session: Database session
            market_ids: List of market IDs
            side: 'sell' uses best_bid (price to sell YES), 'buy' uses best_ask

        Returns:
            Dict mapping market_id to price info with yes_price, liquidity, source
        """
        now = datetime.utcnow()
        cutoff = now - self.max_age
        prices = {}

        # Get markets
        result = await session.execute(
            select(Market).where(Market.id.in_(market_ids))
        )
        markets = {m.id: m for m in result.scalars().all()}

        # Try to get orderbook prices first
        all_token_ids = []
        token_to_market = {}
        for market_id, market in markets.items():
            yes_token = self._get_yes_token(market)
            if yes_token:
                all_token_ids.append(yes_token)
                token_to_market[yes_token] = market_id

        if all_token_ids:
            # Get latest snapshots
            subq = (
                select(
                    OrderBookSnapshot.token_id,
                    func.max(OrderBookSnapshot.timestamp).label("max_ts"),
                )
                .where(OrderBookSnapshot.token_id.in_(all_token_ids))
                .where(OrderBookSnapshot.timestamp >= cutoff)
                .group_by(OrderBookSnapshot.token_id)
                .subquery()
            )

            ob_result = await session.execute(
                select(
                    OrderBookSnapshot.token_id,
                    OrderBookSnapshot.best_ask,
                    OrderBookSnapshot.best_bid,
                    OrderBookSnapshot.bid_depth_1pct,
                    OrderBookSnapshot.ask_depth_1pct,
                )
                .join(
                    subq,
                    and_(
                        OrderBookSnapshot.token_id == subq.c.token_id,
                        OrderBookSnapshot.timestamp == subq.c.max_ts,
                    ),
                )
            )

            for row in ob_result.all():
                token_id = row[0]
                market_id = token_to_market.get(token_id)
                if market_id:
                    best_ask = float(row[1]) if row[1] else None
                    best_bid = float(row[2]) if row[2] else None
                    bid_depth = float(row[3]) if row[3] else 0
                    ask_depth = float(row[4]) if row[4] else 0

                    # Side-aware pricing
                    if side == "sell":
                        # Selling YES means hitting bids
                        yes_price = best_bid
                        liquidity = bid_depth
                    else:
                        # Buying YES means hitting asks
                        yes_price = best_ask
                        liquidity = ask_depth

                    prices[market_id] = {
                        "yes_price": yes_price,
                        "bid_price": best_bid,
                        "ask_price": best_ask,
                        "liquidity": liquidity,
                        "source": "orderbook",
                    }

        # Fall back to market prices for missing
        for market_id, market in markets.items():
            if market_id not in prices:
                yes_price = market.yes_price
                price_data = {
                    "yes_price": yes_price,
                    "liquidity": float(market.liquidity) if market.liquidity else 0,
                    "source": "market",
                }
                # Only set assumed_yes_outcome if market doesn't have explicit "Yes" name
                if not self._has_explicit_yes_outcome(market):
                    price_data["assumed_yes_outcome"] = True
                prices[market_id] = price_data

        return prices

    def _has_explicit_yes_outcome(self, market: Market) -> bool:
        """Check if market has an outcome explicitly named 'Yes'.

        Args:
            market: Market object with outcomes

        Returns:
            True if any outcome is named 'Yes' (case-insensitive)
        """
        if not market.outcomes:
            return False

        for outcome in market.outcomes:
            name = outcome.get("name", "").lower()
            if name == "yes":
                return True
        return False

    def _get_yes_token(self, market: Market) -> Optional[str]:
        """Get the YES token for a market, preferring outcome named 'Yes'.

        Args:
            market: Market object with outcomes

        Returns:
            Token ID for the YES outcome, or None if not found
        """
        if not market.outcomes:
            return None

        # First, look for an outcome explicitly named "Yes"
        for outcome in market.outcomes:
            name = outcome.get("name", "").lower()
            if name == "yes":
                return outcome.get("token_id")

        # Fallback to first outcome (common convention)
        return market.outcomes[0].get("token_id") if market.outcomes else None

    async def _get_existing_alerts(
        self,
        session: AsyncSession,
    ) -> Set[str]:
        """Get set of alert keys for existing active cross-market arb alerts."""
        result = await session.execute(
            select(Alert.data)
            .where(Alert.alert_type == "arbitrage")
            .where(Alert.is_active == True)
        )

        existing = set()
        for row in result.all():
            data = row[0]
            if not data:
                continue

            arb_type = data.get("type")
            if arb_type == "mutually_exclusive":
                group_id = data.get("group_id")
                strategy = data.get("strategy", "")
                if group_id:
                    # Use strategy-specific keys for buy-all vs sell-all
                    if strategy == "buy_all_outcomes":
                        existing.add(f"exclusive-buy-{group_id}")
                    elif strategy == "sell_all_outcomes":
                        existing.add(f"exclusive-sell-{group_id}")
                    else:
                        # Legacy: support old format
                        existing.add(f"exclusive-{group_id}")
            elif arb_type == "conditional":
                existing.add(
                    f"conditional-{data.get('parent_market_id')}-{data.get('child_market_id')}"
                )
            elif arb_type == "time_sequence":
                existing.add(
                    f"time-{data.get('earlier_market_id')}-{data.get('later_market_id')}"
                )
            elif arb_type == "subset":
                existing.add(
                    f"subset-{data.get('general_market_id')}-{data.get('specific_market_id')}"
                )

        return existing
