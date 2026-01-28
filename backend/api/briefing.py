"""Daily briefing API endpoints.

Provides safe trading opportunities for beginners with educational content.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.market import Market
from services.safety_scorer import SafetyScorer

router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================

class MetricsResponse(BaseModel):
    """Raw metrics for an opportunity."""

    freshness_minutes: Optional[float] = None
    spread_pct: Optional[float] = None
    total_depth: float = 0
    bid_depth_1pct: float = 0
    ask_depth_1pct: float = 0
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    signal_count: int = 0
    active_signals: List[str] = []
    volume_ratio: Optional[float] = None
    slippage_100_eur: Optional[float] = None


class ScoresResponse(BaseModel):
    """Component scores breakdown."""

    freshness: int
    liquidity: int
    spread: int
    alignment: int


class OutcomeResponse(BaseModel):
    """Market outcome info."""

    name: str
    token_id: Optional[str] = None
    price: Optional[float] = None


class OpportunityResponse(BaseModel):
    """A safe trading opportunity."""

    market_id: str
    market_question: str
    category: Optional[str] = None
    outcomes: Optional[List[dict]] = None

    safety_score: int
    scores: ScoresResponse
    metrics: MetricsResponse

    why_safe: str
    what_could_go_wrong: str

    last_updated: Optional[str] = None


class DailyBriefingResponse(BaseModel):
    """Daily briefing with safe opportunities."""

    generated_at: str
    opportunity_count: int
    opportunities: List[OpportunityResponse]
    learning_tip: str


class MarketDetailResponse(BaseModel):
    """Detailed market info for opportunity detail page."""

    market_id: str
    market_question: str
    category: Optional[str] = None
    outcomes: Optional[List[dict]] = None

    safety_score: int
    scores: ScoresResponse
    metrics: MetricsResponse

    why_safe: str
    what_could_go_wrong: str

    # Teaching content
    teach_me: dict
    checklist: List[dict]

    last_updated: Optional[str] = None


# ============================================================================
# Learning Tips
# ============================================================================

LEARNING_TIPS = [
    "Start small. With a 100 EUR bankroll, consider risking only 5-10 EUR per trade to learn the mechanics.",
    "Spread is your enemy. A 5% spread means you lose 5% immediately - look for tighter spreads.",
    "Liquidity matters. Low depth means your order might move the price against you (slippage).",
    "Fresh data is safer. If the last update was 30+ minutes ago, the market may have moved.",
    "Multiple signals are better. When spread, volume, and orderbook all look good, confidence is higher.",
    "Don't chase. If you missed an opportunity, wait for the next one rather than forcing a trade.",
    "Understand the market. Read the question carefully - prediction markets can have tricky resolution criteria.",
]


# ============================================================================
# Teaching Content Templates
# ============================================================================

def generate_teach_me_content(opp: dict) -> dict:
    """Generate educational content for an opportunity."""
    spread = opp["metrics"].get("spread_pct")
    depth = opp["metrics"].get("total_depth", 0)
    signals = opp["metrics"].get("active_signals", [])

    what_signal_means = ""
    if "arbitrage" in signals:
        what_signal_means = (
            "This market shows an arbitrage signal, meaning the prices are temporarily "
            "misaligned. In theory, you could profit by buying low and selling high, "
            "but the window is usually short."
        )
    elif "volume_spike" in signals:
        what_signal_means = (
            "This market has unusual trading volume. High volume often indicates "
            "new information or changing sentiment. It can mean opportunity, but also risk."
        )
    elif "spread_alert" in signals:
        what_signal_means = (
            "The bid-ask spread on this market is wider than usual, which can mean "
            "less competition from market makers. You might get better fills."
        )
    elif "mm_pullback" in signals:
        what_signal_means = (
            "Market makers have pulled back liquidity in this market. This often precedes "
            "significant price movement and can create short-term opportunities."
        )
    else:
        what_signal_means = (
            "This market meets our safety criteria based on fresh data, good liquidity, "
            "and reasonable spread. It's a solid candidate for learning."
        )

    why_safe = (
        f"The data is fresh, there's ${depth:.0f} in orderbook depth, "
        f"and the spread is {spread:.1%}. " if spread else
        f"The data is fresh and there's ${depth:.0f} in orderbook depth. "
    )
    why_safe += "These conditions reduce the chance of unexpected slippage."

    what_invalidates = (
        "This signal could become invalid if: (1) the spread widens significantly, "
        "(2) liquidity drops below $500, (3) the data becomes stale (>30 min), or "
        "(4) market sentiment shifts suddenly due to news."
    )

    risk_with_100 = (
        "With a 100 EUR position, your maximum loss would be 100 EUR if the market "
        f"goes to zero. More realistically, with a {spread:.1%} spread, you'd lose "
        f"about {100 * (spread or 0.05):.1f} EUR immediately to the spread." if spread else
        "With a 100 EUR position, consider the spread cost and potential market movement."
    )

    return {
        "what_signal_means": what_signal_means,
        "why_safe": why_safe,
        "what_invalidates": what_invalidates,
        "risk_with_100_eur": risk_with_100,
    }


def generate_checklist(opp: dict) -> List[dict]:
    """Generate Go/No-Go checklist for an opportunity."""
    metrics = opp["metrics"]

    freshness_ok = metrics.get("freshness_minutes", 999) < 30
    liquidity_ok = metrics.get("total_depth", 0) >= 500
    spread_ok = (metrics.get("spread_pct") or 1) < 0.05
    signals_ok = metrics.get("signal_count", 0) >= 2

    return [
        {
            "label": "Data is fresh (<30 min)",
            "passed": freshness_ok,
            "detail": f"Last update: {metrics.get('freshness_minutes', 'N/A'):.0f} min ago"
                      if metrics.get('freshness_minutes') else "No recent data",
        },
        {
            "label": "Liquidity sufficient for 100 EUR",
            "passed": liquidity_ok,
            "detail": f"Depth: ${metrics.get('total_depth', 0):.0f}",
        },
        {
            "label": "Spread below 5%",
            "passed": spread_ok,
            "detail": f"Spread: {metrics.get('spread_pct', 0):.1%}"
                      if metrics.get('spread_pct') else "N/A",
        },
        {
            "label": "At least 2 signals align",
            "passed": signals_ok,
            "detail": f"Signals: {', '.join(metrics.get('active_signals', [])) or 'None'}",
        },
        {
            "label": "I understand the 'why'",
            "passed": None,  # User must confirm
            "detail": "Review the 'Teach Me' section before trading",
        },
    ]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/daily", response_model=DailyBriefingResponse)
async def get_daily_briefing(
    limit: int = Query(5, ge=1, le=10, description="Number of opportunities"),
    session: AsyncSession = Depends(get_db),
):
    """Get today's safe trading opportunities.

    Returns the top opportunities that pass all safety filters:
    - Freshness: data updated within 30 minutes
    - Liquidity: at least 500 EUR depth
    - Spread: less than 5%
    - Signals: at least 2 confirming signals
    """
    scorer = SafetyScorer()
    opportunities = await scorer.get_safe_opportunities(session, limit=limit)

    # Select a learning tip based on the day
    import random
    tip = random.choice(LEARNING_TIPS)

    return DailyBriefingResponse(
        generated_at=datetime.utcnow().isoformat(),
        opportunity_count=len(opportunities),
        opportunities=[
            OpportunityResponse(
                market_id=opp["market_id"],
                market_question=opp["market_question"],
                category=opp.get("category"),
                outcomes=opp.get("outcomes"),
                safety_score=opp["safety_score"],
                scores=ScoresResponse(**opp["scores"]),
                metrics=MetricsResponse(**opp["metrics"]),
                why_safe=opp["why_safe"],
                what_could_go_wrong=opp["what_could_go_wrong"],
                last_updated=opp.get("last_updated"),
            )
            for opp in opportunities
        ],
        learning_tip=tip,
    )


@router.get("/opportunity/{market_id}", response_model=MarketDetailResponse)
async def get_opportunity_detail(
    market_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get detailed info for a specific opportunity.

    Includes educational content and Go/No-Go checklist.
    """
    # Get market
    result = await session.execute(
        select(Market).where(Market.id == market_id)
    )
    market = result.scalar_one_or_none()

    if not market:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Market not found")

    # Calculate safety score
    scorer = SafetyScorer()
    score = await scorer.calculate_score(session, market)

    opp = {
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
            "volume_ratio": score.metrics.volume_ratio,
            "slippage_100_eur": score.metrics.slippage_100_eur,
        },
        "why_safe": score.why_safe,
        "what_could_go_wrong": score.what_could_go_wrong,
        "last_updated": score.metrics.last_orderbook_time.isoformat()
            if score.metrics.last_orderbook_time else None,
    }

    return MarketDetailResponse(
        market_id=opp["market_id"],
        market_question=opp["market_question"],
        category=opp.get("category"),
        outcomes=opp.get("outcomes"),
        safety_score=opp["safety_score"],
        scores=ScoresResponse(**opp["scores"]),
        metrics=MetricsResponse(**opp["metrics"]),
        why_safe=opp["why_safe"],
        what_could_go_wrong=opp["what_could_go_wrong"],
        teach_me=generate_teach_me_content(opp),
        checklist=generate_checklist(opp),
        last_updated=opp.get("last_updated"),
    )
