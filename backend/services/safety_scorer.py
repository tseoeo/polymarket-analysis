"""Safety score calculation service.

Computes a 0-100 safety score for trading opportunities based on:
- Freshness: How recent is the data?
- Liquidity: Is there enough depth to trade?
- Spread: How tight is the bid-ask spread?
- Signal alignment: Do multiple indicators agree?

Higher scores indicate safer opportunities for beginners.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from models.market import Market
from models.orderbook import OrderBookSnapshot, OrderBookLatestRaw
from models.trade import Trade
from models.alert import Alert
from models.trade import Trade

logger = logging.getLogger(__name__)


def _json_array_contains(column, value: str):
    """Build a cross-dialect JSON array containment check.

    PostgreSQL supports column.contains([value]) via the @> operator.
    SQLite does not, so we fall back to a LIKE on the text representation.
    The or_() with both approaches lets SQLAlchemy pick the one that works.
    Since we always wrap this in or_() with a market_id == check, we use
    cast-to-string + LIKE which works on both dialects.
    """
    return cast(column, String).like(f'%"{value}"%')


@dataclass
class SafetyMetrics:
    """Raw metrics used to calculate safety score."""

    # Freshness
    last_trade_time: Optional[datetime] = None
    last_orderbook_time: Optional[datetime] = None
    freshness_minutes: Optional[float] = None

    # Liquidity
    bid_depth_1pct: float = 0.0
    ask_depth_1pct: float = 0.0
    total_depth: float = 0.0

    # Spread
    spread_pct: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None

    # Volume
    volume_ratio: Optional[float] = None  # vs baseline

    # Slippage
    slippage_100_eur: Optional[float] = None  # slippage pct for 100 EUR trade

    # Signals
    active_signals: List[str] = None
    signal_count: int = 0

    def __post_init__(self):
        if self.active_signals is None:
            self.active_signals = []


@dataclass
class SafetyScore:
    """Calculated safety score with component breakdown."""

    total: int  # 0-100
    freshness_score: int  # 0-30
    liquidity_score: int  # 0-30
    spread_score: int  # 0-20
    alignment_score: int  # 0-20

    metrics: SafetyMetrics

    # Explanations
    why_safe: str
    what_could_go_wrong: str

    # Thresholds met
    passes_freshness: bool
    passes_liquidity: bool
    passes_spread: bool
    passes_alignment: bool

    @property
    def is_safe(self) -> bool:
        """Returns True if all safety thresholds are met."""
        return (
            self.passes_freshness and
            self.passes_liquidity and
            self.passes_spread and
            self.passes_alignment
        )


class SafetyScorer:
    """Calculates safety scores for trading opportunities.

    Safety score formula (0-100):
    - Freshness (0-30): Based on time since last update
    - Liquidity (0-30): Based on orderbook depth
    - Spread (0-20): Based on bid-ask spread percentage
    - Signal alignment (0-20): Based on number of confirming signals
    """

    # Freshness thresholds (minutes)
    FRESHNESS_EXCELLENT = 15  # < 15 min = 30 points
    FRESHNESS_GOOD = 30       # 15-30 min = 20 points

    # Liquidity thresholds (EUR/USD at 1% depth)
    LIQUIDITY_EXCELLENT = 2000  # > 2000 = 30 points
    LIQUIDITY_GOOD = 500        # 500-2000 = 20 points

    # Spread thresholds
    SPREAD_EXCELLENT = 0.03  # < 3% = 20 points
    SPREAD_GOOD = 0.05       # 3-5% = 10 points

    # Safe filter defaults (strict)
    DEFAULT_MAX_FRESHNESS = 30  # minutes
    DEFAULT_MIN_DEPTH = 500     # EUR
    DEFAULT_MAX_SPREAD = 0.05   # 5%
    DEFAULT_MIN_SIGNALS = 2

    # Learning pick defaults (relaxed)
    LEARNING_MAX_FRESHNESS = 60  # minutes
    LEARNING_MIN_DEPTH = 300     # EUR
    LEARNING_MAX_SPREAD = 0.07   # 7%
    LEARNING_MIN_SIGNALS = 1

    def __init__(
        self,
        max_freshness_minutes: int = None,
        min_depth: float = None,
        max_spread: float = None,
        min_signals: int = None,
    ):
        self.max_freshness = max_freshness_minutes or self.DEFAULT_MAX_FRESHNESS
        self.min_depth = min_depth or self.DEFAULT_MIN_DEPTH
        self.max_spread = max_spread or self.DEFAULT_MAX_SPREAD
        self.min_signals = min_signals or self.DEFAULT_MIN_SIGNALS

    async def calculate_score(
        self,
        session: AsyncSession,
        market: Market,
    ) -> SafetyScore:
        """Calculate safety score for a market.

        Args:
            session: Database session
            market: Market to score

        Returns:
            SafetyScore with total score, component scores, and explanations
        """
        metrics = await self._gather_metrics(session, market)

        # Calculate component scores
        freshness_score = self._score_freshness(metrics.freshness_minutes)
        liquidity_score = self._score_liquidity(metrics.total_depth)
        spread_score = self._score_spread(metrics.spread_pct)
        alignment_score = self._score_alignment(metrics.signal_count)

        total = freshness_score + liquidity_score + spread_score + alignment_score

        # Check thresholds
        passes_freshness = (
            metrics.freshness_minutes is not None and
            metrics.freshness_minutes <= self.max_freshness
        )
        passes_liquidity = metrics.total_depth >= self.min_depth
        passes_spread = (
            metrics.spread_pct is not None and
            metrics.spread_pct <= self.max_spread
        )
        passes_alignment = metrics.signal_count >= self.min_signals

        # Generate explanations
        why_safe = self._explain_why_safe(metrics, total)
        what_could_go_wrong = self._explain_risks(metrics)

        return SafetyScore(
            total=total,
            freshness_score=freshness_score,
            liquidity_score=liquidity_score,
            spread_score=spread_score,
            alignment_score=alignment_score,
            metrics=metrics,
            why_safe=why_safe,
            what_could_go_wrong=what_could_go_wrong,
            passes_freshness=passes_freshness,
            passes_liquidity=passes_liquidity,
            passes_spread=passes_spread,
            passes_alignment=passes_alignment,
        )

    async def _get_opportunities_batch(
        self,
        session: AsyncSession,
        max_freshness: int,
        min_depth: float,
        max_spread: float,
        min_signals: int,
        limit: int,
        exclude_ids: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """Get scored opportunities using bulk SQL queries (no N+1).

        Runs ~4 batch queries to gather all metrics at once, then scores
        and filters in Python. This handles thousands of markets in
        constant time regardless of scale.
        """
        now = datetime.utcnow()
        freshness_cutoff = now - timedelta(minutes=max_freshness)

        # ── Query 1: Candidate market IDs with signal counts ──
        # Markets with at least min_signals distinct active alert types.
        # We fetch (market_id, alert_type) pairs and aggregate in Python
        # to avoid dialect-specific string_agg/group_concat differences.
        signal_query = (
            select(Alert.market_id, Alert.alert_type)
            .where(Alert.is_active == True)
            .where(Alert.market_id.isnot(None))
            .distinct()
        )
        signal_result = await session.execute(signal_query)
        signal_rows = signal_result.all()

        if not signal_rows:
            return []

        # Build signal lookup: market_id -> set of alert types
        from collections import defaultdict
        raw_signals: Dict[str, set] = defaultdict(set)
        for mid, atype in signal_rows:
            raw_signals[mid].add(atype)

        signal_map = {}
        candidate_ids = set()
        for mid, types in raw_signals.items():
            if len(types) < min_signals:
                continue
            if exclude_ids and mid in exclude_ids:
                continue
            signal_map[mid] = {
                "count": len(types),
                "types": list(types),
            }
            candidate_ids.add(mid)

        if not candidate_ids:
            return []

        # ── Query 2: Latest orderbook snapshot per market (with metrics) ──
        ob_sub = (
            select(
                OrderBookSnapshot.market_id,
                OrderBookSnapshot.token_id,
                OrderBookSnapshot.timestamp,
                OrderBookSnapshot.best_bid,
                OrderBookSnapshot.best_ask,
                OrderBookSnapshot.spread_pct,
                OrderBookSnapshot.bid_depth_1pct,
                OrderBookSnapshot.ask_depth_1pct,
                func.row_number().over(
                    partition_by=OrderBookSnapshot.market_id,
                    order_by=OrderBookSnapshot.timestamp.desc(),
                ).label("rn"),
            )
            .where(OrderBookSnapshot.market_id.in_(candidate_ids))
            .where(OrderBookSnapshot.timestamp >= freshness_cutoff)
        ).subquery()

        ob_result = await session.execute(
            select(
                ob_sub.c.market_id,
                ob_sub.c.token_id,
                ob_sub.c.timestamp,
                ob_sub.c.best_bid,
                ob_sub.c.best_ask,
                ob_sub.c.spread_pct,
                ob_sub.c.bid_depth_1pct,
                ob_sub.c.ask_depth_1pct,
            ).where(ob_sub.c.rn == 1)
        )
        ob_rows = ob_result.all()

        # Build orderbook lookup
        ob_map = {}
        for row in ob_rows:
            mid, token_id, ts, best_bid, best_ask, sp_pct, bd_1, ad_1 = row
            bid_depth = float(bd_1 or 0)
            ask_depth = float(ad_1 or 0)
            total_depth = bid_depth + ask_depth
            spread_pct = float(sp_pct) if sp_pct else None

            # Apply depth + spread filters early
            if total_depth < min_depth:
                continue
            if spread_pct is not None and spread_pct > max_spread:
                continue

            freshness_minutes = (now - ts).total_seconds() / 60

            ob_map[mid] = {
                "token_id": token_id,
                "timestamp": ts,
                "best_bid": float(best_bid) if best_bid else None,
                "best_ask": float(best_ask) if best_ask else None,
                "spread_pct": spread_pct,
                "bid_depth_1pct": bid_depth,
                "ask_depth_1pct": ask_depth,
                "total_depth": total_depth,
                "freshness_minutes": freshness_minutes,
            }

        # Only keep markets that pass orderbook filters
        valid_ids = candidate_ids & set(ob_map.keys())
        if not valid_ids:
            return []

        # ── Query 3: Markets data ──
        market_result = await session.execute(
            select(Market).where(Market.id.in_(valid_ids)).where(Market.active == True)
        )
        markets = {m.id: m for m in market_result.scalars().all()}

        # ── Query 4: Recent price moves for valid markets ──
        # Get first and last trade price in last hour per token for price move calc
        token_to_market = {}
        for mid in valid_ids:
            market = markets.get(mid)
            if market and market.outcomes:
                for outcome in market.outcomes:
                    if outcome.get("name", "").lower() == "yes":
                        token_to_market[outcome.get("token_id")] = mid
                        break
                else:
                    tid = market.outcomes[0].get("token_id")
                    if tid:
                        token_to_market[tid] = mid

        price_move_map: Dict[str, Optional[float]] = {}
        if token_to_market:
            one_hour_ago = now - timedelta(hours=1)
            price_result = await session.execute(
                select(
                    Trade.token_id,
                    func.min(Trade.price).label("low"),
                    func.max(Trade.price).label("high"),
                )
                .where(Trade.token_id.in_(list(token_to_market.keys())))
                .where(Trade.timestamp >= one_hour_ago)
                .group_by(Trade.token_id)
            )
            for tid, low, high in price_result.all():
                mid = token_to_market.get(tid)
                if mid and low and high and float(low) > 0:
                    price_move_map[mid] = round((float(high) - float(low)) / float(low), 4)

        # ── Score in Python (no more DB queries) ──
        from services.opportunity_explainer import build_explanation

        opportunities = []
        for mid in valid_ids:
            market = markets.get(mid)
            if not market:
                continue

            ob = ob_map[mid]
            sig = signal_map[mid]

            metrics = SafetyMetrics(
                last_orderbook_time=ob["timestamp"],
                freshness_minutes=ob["freshness_minutes"],
                bid_depth_1pct=ob["bid_depth_1pct"],
                ask_depth_1pct=ob["ask_depth_1pct"],
                total_depth=ob["total_depth"],
                spread_pct=ob["spread_pct"],
                best_bid=ob["best_bid"],
                best_ask=ob["best_ask"],
                active_signals=sig["types"],
                signal_count=sig["count"],
            )

            freshness_score = self._score_freshness(metrics.freshness_minutes)
            liquidity_score = self._score_liquidity(metrics.total_depth)
            spread_score = self._score_spread(metrics.spread_pct)
            alignment_score = self._score_alignment(metrics.signal_count)
            total = freshness_score + liquidity_score + spread_score + alignment_score

            why_safe = self._explain_why_safe(metrics, total)
            what_could_go_wrong = self._explain_risks(metrics)

            # Build explanation with profit estimates
            explanation_metrics = {
                "freshness_minutes": metrics.freshness_minutes,
                "spread_pct": metrics.spread_pct,
                "total_depth": metrics.total_depth,
                "best_bid": metrics.best_bid,
                "best_ask": metrics.best_ask,
                "signal_count": metrics.signal_count,
                "slippage_100_eur": None,
                "recent_price_move_pct": price_move_map.get(mid),
                "typical_move_pct_24h": None,
            }
            explanation = build_explanation(sig["types"], explanation_metrics)

            opportunities.append({
                "market_id": mid,
                "market_question": market.question,
                "category": market.category,
                "outcomes": market.outcomes,
                "safety_score": total,
                "scores": {
                    "freshness": freshness_score,
                    "liquidity": liquidity_score,
                    "spread": spread_score,
                    "alignment": alignment_score,
                },
                "metrics": {
                    "freshness_minutes": metrics.freshness_minutes,
                    "spread_pct": metrics.spread_pct,
                    "total_depth": metrics.total_depth,
                    "bid_depth_1pct": metrics.bid_depth_1pct,
                    "ask_depth_1pct": metrics.ask_depth_1pct,
                    "best_bid": metrics.best_bid,
                    "best_ask": metrics.best_ask,
                    "signal_count": metrics.signal_count,
                    "active_signals": metrics.active_signals,
                    "volume_ratio": None,
                    "slippage_100_eur": None,
                },
                "explanation": explanation,
                "why_safe": why_safe,
                "what_could_go_wrong": what_could_go_wrong,
                "last_updated": ob["timestamp"].isoformat(),
            })

        opportunities.sort(key=lambda x: x["safety_score"], reverse=True)
        return opportunities[:limit]

    async def get_safe_opportunities(
        self,
        session: AsyncSession,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get top safe opportunities using batch queries."""
        return await self._get_opportunities_batch(
            session,
            max_freshness=self.max_freshness,
            min_depth=self.min_depth,
            max_spread=self.max_spread,
            min_signals=self.min_signals,
            limit=limit,
        )

    async def get_learning_opportunities(
        self,
        session: AsyncSession,
        limit: int = 5,
        exclude_ids: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """Get learning picks with relaxed thresholds using batch queries."""
        return await self._get_opportunities_batch(
            session,
            max_freshness=self.LEARNING_MAX_FRESHNESS,
            min_depth=self.LEARNING_MIN_DEPTH,
            max_spread=self.LEARNING_MAX_SPREAD,
            min_signals=self.LEARNING_MIN_SIGNALS,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    async def _gather_metrics(
        self,
        session: AsyncSession,
        market: Market,
    ) -> SafetyMetrics:
        """Gather all metrics needed for safety score calculation."""
        metrics = SafetyMetrics()
        now = datetime.utcnow()

        # Get YES token for orderbook lookup
        yes_token = None
        if market.outcomes:
            for outcome in market.outcomes:
                if outcome.get("name", "").lower() == "yes":
                    yes_token = outcome.get("token_id")
                    break
            if not yes_token and market.outcomes:
                yes_token = market.outcomes[0].get("token_id")

        if yes_token:
            # Get latest orderbook snapshot
            ob_result = await session.execute(
                select(OrderBookSnapshot)
                .where(OrderBookSnapshot.token_id == yes_token)
                .order_by(OrderBookSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = ob_result.scalar_one_or_none()

            if snapshot:
                metrics.last_orderbook_time = snapshot.timestamp
                metrics.bid_depth_1pct = float(snapshot.bid_depth_1pct or 0)
                metrics.ask_depth_1pct = float(snapshot.ask_depth_1pct or 0)
                metrics.total_depth = metrics.bid_depth_1pct + metrics.ask_depth_1pct
                metrics.spread_pct = float(snapshot.spread_pct) if snapshot.spread_pct else None
                metrics.best_bid = float(snapshot.best_bid) if snapshot.best_bid else None
                metrics.best_ask = float(snapshot.best_ask) if snapshot.best_ask else None

            # Get latest trade
            trade_result = await session.execute(
                select(Trade.timestamp)
                .where(Trade.token_id == yes_token)
                .order_by(Trade.timestamp.desc())
                .limit(1)
            )
            trade_row = trade_result.first()
            if trade_row:
                metrics.last_trade_time = trade_row[0]

        # Calculate freshness (use most recent of trade or orderbook)
        latest_time = None
        if metrics.last_orderbook_time and metrics.last_trade_time:
            latest_time = max(metrics.last_orderbook_time, metrics.last_trade_time)
        elif metrics.last_orderbook_time:
            latest_time = metrics.last_orderbook_time
        elif metrics.last_trade_time:
            latest_time = metrics.last_trade_time

        if latest_time:
            metrics.freshness_minutes = (now - latest_time).total_seconds() / 60

        # Compute volume ratio (recent 1h vs baseline 24h)
        if yes_token:
            try:
                one_hour_ago = now - timedelta(hours=1)
                day_ago = now - timedelta(hours=24)

                recent_vol_result = await session.execute(
                    select(func.sum(Trade.size))
                    .where(Trade.token_id == yes_token)
                    .where(Trade.timestamp >= one_hour_ago)
                )
                recent_vol = float(recent_vol_result.scalar() or 0)

                baseline_result = await session.execute(
                    select(func.sum(Trade.size), func.count())
                    .where(Trade.token_id == yes_token)
                    .where(Trade.timestamp >= day_ago)
                    .where(Trade.timestamp < one_hour_ago)
                )
                baseline_row = baseline_result.first()
                baseline_vol = float(baseline_row[0] or 0)
                baseline_count = baseline_row[1] or 0
                baseline_hourly = baseline_vol / 23.0 if baseline_vol > 0 else 0

                # Require at least 10 baseline trades to avoid false spikes on thin data
                if baseline_hourly > 0 and baseline_count >= 10:
                    metrics.volume_ratio = round(recent_vol / baseline_hourly, 2)
            except Exception as e:
                logger.debug(f"Volume ratio calc failed for {market.id}: {e}")

            # Load latest raw orderbook for slippage calculation
            raw_result = await session.execute(
                select(OrderBookLatestRaw)
                .where(OrderBookLatestRaw.token_id == yes_token)
            )
            raw_ob = raw_result.scalar_one_or_none()

            # Compute slippage for 100 EUR buy from latest raw orderbook
            if raw_ob and raw_ob.asks and metrics.best_ask:
                try:
                    trade_size = 100.0
                    remaining = trade_size
                    total_cost = 0.0
                    total_shares = 0.0
                    best_price = float(metrics.best_ask)

                    for level in raw_ob.asks:
                        price = float(level.get("price", 0))
                        size_shares = float(level.get("size", 0))
                        if price <= 0 or size_shares <= 0:
                            continue
                        capacity = price * size_shares
                        if capacity >= remaining:
                            total_shares += remaining / price
                            total_cost += remaining
                            remaining = 0
                            break
                        total_cost += capacity
                        total_shares += size_shares
                        remaining -= capacity

                    if total_shares > 0 and best_price > 0:
                        avg_price = total_cost / total_shares
                        slippage = abs(avg_price - best_price) / best_price
                        metrics.slippage_100_eur = round(slippage, 4)
                except Exception as e:
                    logger.debug(f"Slippage calc failed for {market.id}: {e}")

        # Get active alerts for this market (signals)
        # Check both market_id (single-market alerts) and related_market_ids (cross-market)
        alert_result = await session.execute(
            select(Alert.alert_type)
            .where(or_(
                Alert.market_id == market.id,
                _json_array_contains(Alert.related_market_ids, market.id),
            ))
            .where(Alert.is_active == True)
        )
        alerts = alert_result.all()
        metrics.active_signals = list(set(a[0] for a in alerts))
        metrics.signal_count = len(metrics.active_signals)

        return metrics

    def _score_freshness(self, freshness_minutes: Optional[float]) -> int:
        """Score freshness component (0-30)."""
        if freshness_minutes is None:
            return 0
        if freshness_minutes < self.FRESHNESS_EXCELLENT:
            return 30
        if freshness_minutes < self.FRESHNESS_GOOD:
            return 20
        return 0

    def _score_liquidity(self, total_depth: float) -> int:
        """Score liquidity component (0-30)."""
        if total_depth >= self.LIQUIDITY_EXCELLENT:
            return 30
        if total_depth >= self.LIQUIDITY_GOOD:
            return 20
        return 0

    def _score_spread(self, spread_pct: Optional[float]) -> int:
        """Score spread component (0-20)."""
        if spread_pct is None:
            return 0
        if spread_pct < self.SPREAD_EXCELLENT:
            return 20
        if spread_pct < self.SPREAD_GOOD:
            return 10
        return 0

    def _score_alignment(self, signal_count: int) -> int:
        """Score signal alignment component (0-20)."""
        if signal_count >= 2:
            return 20
        if signal_count >= 1:
            return 10
        return 0

    def _explain_why_safe(self, metrics: SafetyMetrics, total_score: int) -> str:
        """Generate explanation of why this opportunity is safe."""
        reasons = []

        if metrics.freshness_minutes and metrics.freshness_minutes < 15:
            reasons.append("Data is very fresh (updated within 15 minutes)")
        elif metrics.freshness_minutes and metrics.freshness_minutes < 30:
            reasons.append("Data is recent (updated within 30 minutes)")

        if metrics.total_depth >= 2000:
            reasons.append(f"High liquidity (${metrics.total_depth:.0f} depth)")
        elif metrics.total_depth >= 500:
            reasons.append(f"Good liquidity (${metrics.total_depth:.0f} depth)")

        if metrics.spread_pct and metrics.spread_pct < 0.03:
            reasons.append(f"Tight spread ({metrics.spread_pct:.1%})")
        elif metrics.spread_pct and metrics.spread_pct < 0.05:
            reasons.append(f"Reasonable spread ({metrics.spread_pct:.1%})")

        if metrics.signal_count >= 2:
            signals = ", ".join(metrics.active_signals[:3])
            reasons.append(f"Multiple signals align ({signals})")
        elif metrics.signal_count == 1:
            reasons.append(f"One confirming signal ({metrics.active_signals[0]})")

        if not reasons:
            return "This market meets basic safety criteria."

        return " ".join(reasons) + f" Safety score: {total_score}/100."

    def _explain_risks(self, metrics: SafetyMetrics) -> str:
        """Generate explanation of potential risks."""
        risks = []

        if metrics.freshness_minutes and metrics.freshness_minutes > 15:
            risks.append("Data may have changed since last update")

        if metrics.total_depth < 1000:
            risks.append("Limited liquidity could cause slippage on larger orders")

        if metrics.spread_pct and metrics.spread_pct > 0.03:
            risks.append("Spread reduces profit margin")

        if metrics.signal_count < 2:
            risks.append("Limited signal confirmation - consider waiting for more data")

        # General risks
        risks.append("Market conditions can change quickly")
        risks.append("Past patterns don't guarantee future results")

        return " ".join(risks[:3]) + "."  # Limit to 3 risks
