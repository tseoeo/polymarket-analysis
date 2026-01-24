"""Arbitrage detection service (intra-market).

Phase 3: Intra-market arbitrage (YES + NO pricing anomalies)
Phase 4: Cross-market arbitrage (related market mispricings)

For binary markets, YES + NO should sum to ~1.0 (minus fees).
If the sum is significantly less than 1.0, buying both sides guarantees profit.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy import select, desc, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.market import Market
from models.orderbook import OrderBookSnapshot
from models.alert import Alert

logger = logging.getLogger(__name__)

# Sentinel to distinguish "no opportunity found" from "couldn't check"
_NO_OPPORTUNITY = object()


class ArbitrageDetector:
    """Detects arbitrage opportunities within markets.

    Phase 3: Intra-market (YES + NO pricing anomalies)
    - For binary markets: if YES + NO < 1.0, buying both guarantees profit
    - Uses orderbook best_ask prices for more accurate/actionable signals

    Phase 4 (future): Cross-market arbitrage detection
    """

    def __init__(
        self,
        max_snapshot_age_minutes: int = 15,  # Tight freshness for arb
        use_orderbook_prices: bool = True,   # Use live orderbook vs cached market prices
        fallback_to_market_prices: bool = True,  # Fall back when orderbook unavailable
    ):
        self.min_profit = settings.arbitrage_min_profit  # 0.02 = 2%
        self.max_age = timedelta(minutes=max_snapshot_age_minutes)
        self.use_orderbook_prices = use_orderbook_prices
        self.fallback_to_market_prices = fallback_to_market_prices

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Detect intra-market arbitrage opportunities.

        For each binary market:
        1. Get outcome prices (from orderbook or market cache)
        2. Check if outcome1 + outcome2 < 1.0 - min_profit
        3. Generate alert if opportunity exists

        When use_orderbook_prices=True and orderbook data is missing/stale,
        falls back to cached market prices if fallback_to_market_prices=True.

        Deduplication:
        - Arbitrage alerts use `related_market_ids` not `market_id`
        - Check if market.id is in any active arbitrage alert's related_market_ids
        """
        now = datetime.utcnow()
        alerts = []

        # Get active binary markets (exactly 2 outcomes)
        result = await session.execute(
            select(Market).where(Market.active == True)
        )
        markets = result.scalars().all()

        # Filter to binary markets with valid tokens
        binary_markets = []
        for market in markets:
            if market.outcomes and len(market.outcomes) == 2:
                tokens = market.token_ids
                if len(tokens) == 2 and all(tokens):
                    binary_markets.append(market)

        if not binary_markets:
            return alerts

        # Get existing active arbitrage alerts
        existing_market_ids = await self._get_existing_alert_market_ids(session)

        # Batch fetch orderbook prices if enabled
        orderbook_prices = {}
        if self.use_orderbook_prices:
            all_token_ids = []
            for market in binary_markets:
                all_token_ids.extend(market.token_ids)

            orderbook_prices = await self._batch_get_orderbook_prices(
                session, all_token_ids, now
            )

        for market in binary_markets:
            if market.id in existing_market_ids:
                continue

            alert = None

            if self.use_orderbook_prices:
                result = self._check_orderbook_arbitrage(market, orderbook_prices, now)
                if result is _NO_OPPORTUNITY:
                    # Fresh data showed no opportunity - don't fall back
                    continue
                elif result is not None:
                    # Found an opportunity
                    alert = result
                # result is None means missing/stale data - fall back below

            # Only fall back to market prices if orderbook data was unavailable
            if alert is None and self.fallback_to_market_prices:
                alert = self._check_market_price_arbitrage(market)

            if alert:
                session.add(alert)
                alerts.append(alert)

        return alerts

    def _check_orderbook_arbitrage(
        self,
        market: Market,
        orderbook_prices: Dict[str, dict],
        now: datetime,
    ):
        """Check for arbitrage using orderbook best_ask prices.

        To buy both sides:
        - Buy outcome1 at best_ask for token1
        - Buy outcome2 at best_ask for token2
        Total cost = outcome1_ask + outcome2_ask
        If < 1.0, guaranteed profit on settlement.

        Returns:
            Alert: opportunity found
            _NO_OPPORTUNITY: fresh data showed no opportunity (don't fall back)
            None: data missing or stale (caller can fall back to market prices)
        """
        token_ids = market.token_ids
        if len(token_ids) != 2:
            return None

        # Get outcome names from market (not assuming YES/NO)
        outcome1_name = market.outcomes[0].get("name", "Outcome 1")
        outcome2_name = market.outcomes[1].get("name", "Outcome 2")
        token1, token2 = token_ids[0], token_ids[1]

        data1 = orderbook_prices.get(token1, {})
        data2 = orderbook_prices.get(token2, {})

        ask1 = data1.get("best_ask")
        ask2 = data2.get("best_ask")

        # Missing price data - allow fallback
        if ask1 is None or ask2 is None:
            logger.debug(f"Missing orderbook data for {market.id}, allowing fallback")
            return None

        # Check freshness - stale data allows fallback
        ts1 = data1.get("timestamp")
        ts2 = data2.get("timestamp")
        cutoff = now - self.max_age

        if ts1 and ts1 < cutoff:
            logger.debug(f"Stale orderbook for {market.id} token1, allowing fallback")
            return None
        if ts2 and ts2 < cutoff:
            logger.debug(f"Stale orderbook for {market.id} token2, allowing fallback")
            return None

        # At this point we have fresh data - check for opportunity
        total = ask1 + ask2

        # If total >= 1.0, no opportunity (fresh data, don't fall back)
        if total >= 1.0:
            return _NO_OPPORTUNITY

        profit = 1.0 - total
        if profit < self.min_profit:
            # Below threshold (fresh data, don't fall back)
            return _NO_OPPORTUNITY

        # Create alert with actual outcome names
        alert = Alert.create_arbitrage_alert(
            title=f"Arbitrage: {profit:.1%} profit",
            description=(
                f"Buy both {outcome1_name} (${ask1:.3f}) and {outcome2_name} (${ask2:.3f}) "
                f"for guaranteed ${profit:.3f} profit per share"
            ),
            market_ids=[market.id],
            profit_estimate=profit,
            data={
                "outcome1_name": outcome1_name,
                "outcome1_price": float(ask1),
                "outcome1_token_id": token1,
                "outcome2_name": outcome2_name,
                "outcome2_price": float(ask2),
                "outcome2_token_id": token2,
                "total": float(total),
                "strategy": "buy_both_sides",
                "price_source": "orderbook_best_ask",
            },
        )
        logger.info(f"Arbitrage opportunity: {market.id} profit={profit:.2%}")
        return alert

    def _check_market_price_arbitrage(self, market: Market) -> Optional[Alert]:
        """Check for arbitrage using cached market prices.

        Less accurate than orderbook prices but works when orderbook
        data is unavailable. Uses prices from market.outcomes (Gamma API).
        """
        if not market.outcomes or len(market.outcomes) != 2:
            return None

        # Get prices and names from outcomes directly
        outcome1 = market.outcomes[0]
        outcome2 = market.outcomes[1]

        outcome1_name = outcome1.get("name", "Outcome 1")
        outcome2_name = outcome2.get("name", "Outcome 2")
        price1 = outcome1.get("price")
        price2 = outcome2.get("price")

        if price1 is None or price2 is None:
            return None

        total = price1 + price2

        if total >= 1.0:
            return None

        profit = 1.0 - total
        if profit < self.min_profit:
            return None

        alert = Alert.create_arbitrage_alert(
            title=f"Arbitrage: {profit:.1%} profit",
            description=(
                f"Buy both {outcome1_name} (${price1:.3f}) and {outcome2_name} (${price2:.3f}) "
                f"for guaranteed ${profit:.3f} profit per share"
            ),
            market_ids=[market.id],
            profit_estimate=profit,
            data={
                "outcome1_name": outcome1_name,
                "outcome1_price": float(price1),
                "outcome2_name": outcome2_name,
                "outcome2_price": float(price2),
                "total": float(total),
                "strategy": "buy_both_sides",
                "price_source": "market_cache",
            },
        )
        logger.info(f"Arbitrage opportunity: {market.id} profit={profit:.2%}")
        return alert

    async def _batch_get_orderbook_prices(
        self,
        session: AsyncSession,
        token_ids: List[str],
        now: datetime,
    ) -> Dict[str, dict]:
        """Get latest orderbook best_ask for each token.

        Returns dict of token_id -> {best_ask, best_bid, timestamp}
        """
        # Get latest snapshot for each token
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
            select(
                OrderBookSnapshot.token_id,
                OrderBookSnapshot.best_ask,
                OrderBookSnapshot.best_bid,
                OrderBookSnapshot.timestamp,
            ).join(
                subq,
                and_(
                    OrderBookSnapshot.token_id == subq.c.token_id,
                    OrderBookSnapshot.timestamp == subq.c.max_ts,
                ),
            )
        )

        return {
            row[0]: {
                "best_ask": float(row[1]) if row[1] else None,
                "best_bid": float(row[2]) if row[2] else None,
                "timestamp": row[3],
            }
            for row in result.all()
        }

    async def _get_existing_alert_market_ids(
        self, session: AsyncSession
    ) -> set:
        """Get set of market_ids that have active arbitrage alerts.

        Since arbitrage alerts use related_market_ids (list) not market_id,
        we need to extract market IDs from the JSON field.
        """
        result = await session.execute(
            select(Alert.related_market_ids)
            .where(Alert.alert_type == "arbitrage")
            .where(Alert.is_active == True)
        )
        existing = set()
        for row in result.all():
            market_ids = row[0]  # This is a list
            if market_ids:
                existing.update(market_ids)
        return existing
