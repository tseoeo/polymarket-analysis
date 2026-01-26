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

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.market import Market
from models.orderbook import OrderBookSnapshot
from models.trade import Trade
from models.alert import Alert

logger = logging.getLogger(__name__)


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

    # Safe filter defaults
    DEFAULT_MAX_FRESHNESS = 30  # minutes
    DEFAULT_MIN_DEPTH = 500     # EUR
    DEFAULT_MAX_SPREAD = 0.05   # 5%
    DEFAULT_MIN_SIGNALS = 2

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

    async def get_safe_opportunities(
        self,
        session: AsyncSession,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get top safe opportunities for daily briefing.

        Returns markets that pass all safety filters, sorted by score.

        Args:
            session: Database session
            limit: Maximum number of opportunities to return

        Returns:
            List of opportunity dicts with market info, scores, and explanations
        """
        now = datetime.utcnow()
        freshness_cutoff = now - timedelta(minutes=self.max_freshness)

        # Get active markets with recent orderbook data
        result = await session.execute(
            select(Market)
            .where(Market.active == True)
        )
        markets = result.scalars().all()

        opportunities = []

        for market in markets:
            try:
                score = await self.calculate_score(session, market)

                if not score.is_safe:
                    continue

                opportunities.append({
                    "market_id": market.id,
                    "market_question": market.question,
                    "category": market.category,
                    "outcomes": market.outcomes,
                    "safety_score": score.total,
                    "scores": {
                        "freshness": score.freshness_score,
                        "liquidity": score.liquidity_score,
                        "spread": score.spread_score,
                        "alignment": score.alignment_score,
                    },
                    "metrics": {
                        "freshness_minutes": score.metrics.freshness_minutes,
                        "spread_pct": score.metrics.spread_pct,
                        "total_depth": score.metrics.total_depth,
                        "bid_depth_1pct": score.metrics.bid_depth_1pct,
                        "ask_depth_1pct": score.metrics.ask_depth_1pct,
                        "best_bid": score.metrics.best_bid,
                        "best_ask": score.metrics.best_ask,
                        "signal_count": score.metrics.signal_count,
                        "active_signals": score.metrics.active_signals,
                    },
                    "why_safe": score.why_safe,
                    "what_could_go_wrong": score.what_could_go_wrong,
                    "last_updated": score.metrics.last_orderbook_time.isoformat()
                        if score.metrics.last_orderbook_time else None,
                })
            except Exception as e:
                logger.warning(f"Error scoring market {market.id}: {e}")
                continue

        # Sort by score descending
        opportunities.sort(key=lambda x: x["safety_score"], reverse=True)

        return opportunities[:limit]

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

        # Get active alerts for this market (signals)
        alert_result = await session.execute(
            select(Alert.alert_type)
            .where(Alert.related_market_ids.contains([market.id]))
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
