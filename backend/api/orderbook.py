"""Orderbook API endpoints."""

from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.orderbook import OrderBookSnapshot
from services.orderbook_analyzer import OrderbookAnalyzer

router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================

class OrderbookMetricsResponse(BaseModel):
    """Current orderbook metrics."""

    token_id: str
    timestamp: str
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread_pct: Optional[float] = None
    imbalance: Optional[float] = None
    depth: Dict[str, Dict[str, float]]


class SlippageResponse(BaseModel):
    """Slippage calculation response.

    Note: All dollar amounts are in USD. trade_size, filled_dollars, and
    unfilled_dollars represent the dollar value of the trade.
    """

    token_id: str
    side: str
    trade_size: float  # Requested trade size in dollars
    filled_dollars: Optional[float] = None  # Total dollars successfully filled
    unfilled_dollars: Optional[float] = None  # Dollars that couldn't be filled
    filled_shares: Optional[float] = None  # Total shares/contracts filled
    best_price: Optional[float] = None
    expected_price: Optional[float] = None  # Volume-weighted average price
    slippage_pct: Optional[float] = None
    levels_consumed: Optional[int] = None
    snapshot_age_seconds: Optional[float] = None
    error: Optional[str] = None


class SpreadPatternResponse(BaseModel):
    """Spread patterns analysis response."""

    token_id: str
    analysis_period_hours: int
    snapshot_count: int
    hourly_spreads: Dict[int, Dict[str, float]]
    best_hour: int
    best_hour_spread: float
    worst_hour: int
    worst_hour_spread: float
    overall_avg_spread: float


class BestHourResponse(BaseModel):
    """Best trading hour recommendation."""

    hour: int
    avg_spread_pct: float
    min_spread_pct: float
    snapshot_count: int
    recommendation: str


class HistoricalSnapshotResponse(BaseModel):
    """Historical orderbook snapshot."""

    timestamp: str
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread_pct: Optional[float] = None
    mid_price: Optional[float] = None
    imbalance: Optional[float] = None
    bid_depth_1pct: Optional[float] = None
    ask_depth_1pct: Optional[float] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{token_id}", response_model=OrderbookMetricsResponse)
async def get_orderbook(
    token_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get current orderbook with depth metrics for a token."""
    analyzer = OrderbookAnalyzer()
    result = await analyzer.get_depth_at_levels(session, token_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return OrderbookMetricsResponse(
        token_id=result["token_id"],
        timestamp=result["timestamp"],
        best_bid=result["best_bid"],
        best_ask=result["best_ask"],
        spread_pct=result["spread_pct"],
        imbalance=result["imbalance"],
        depth=result.get("depth", {}),
    )


@router.get("/{token_id}/slippage", response_model=SlippageResponse)
async def calculate_slippage(
    token_id: str,
    size: float = Query(..., gt=0, description="Trade size in dollars"),
    side: str = Query("buy", description="Trade side: buy or sell"),
    session: AsyncSession = Depends(get_db),
):
    """Calculate expected slippage for a given trade size."""
    if side not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")

    analyzer = OrderbookAnalyzer()
    result = await analyzer.calculate_slippage(session, token_id, size, side)

    return SlippageResponse(**result)


@router.get("/{token_id}/patterns")
async def get_spread_patterns(
    token_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to analyze"),
    session: AsyncSession = Depends(get_db),
):
    """Get spread patterns by hour of day."""
    analyzer = OrderbookAnalyzer()
    result = await analyzer.analyze_spread_patterns(session, token_id, hours)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return SpreadPatternResponse(
        token_id=result["token_id"],
        analysis_period_hours=result["analysis_period_hours"],
        snapshot_count=result["snapshot_count"],
        hourly_spreads=result["hourly_spreads"],
        best_hour=result["best_hour"],
        best_hour_spread=result["best_hour_spread"],
        worst_hour=result["worst_hour"],
        worst_hour_spread=result["worst_hour_spread"],
        overall_avg_spread=result["overall_avg_spread"],
    )


@router.get("/{token_id}/best-hours", response_model=List[BestHourResponse])
async def get_best_trading_hours(
    token_id: str,
    hours: int = Query(168, ge=24, le=720, description="Hours of history to analyze"),
    top_n: int = Query(5, ge=1, le=24, description="Number of best hours to return"),
    session: AsyncSession = Depends(get_db),
):
    """Get the best hours to trade based on historical spread data."""
    analyzer = OrderbookAnalyzer()
    result = await analyzer.get_best_trading_hours(session, token_id, hours, top_n)

    if result and "error" in result[0]:
        raise HTTPException(status_code=404, detail=result[0]["error"])

    return [BestHourResponse(**r) for r in result]


@router.get("/{token_id}/history", response_model=List[HistoricalSnapshotResponse])
async def get_orderbook_history(
    token_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    session: AsyncSession = Depends(get_db),
):
    """Get historical orderbook snapshots."""
    analyzer = OrderbookAnalyzer()
    result = await analyzer.get_orderbook_history(session, token_id, hours)

    if not result:
        raise HTTPException(status_code=404, detail="No orderbook history found")

    return [HistoricalSnapshotResponse(**r) for r in result]


@router.get("/{token_id}/raw")
async def get_raw_orderbook(
    token_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get raw orderbook data (bids/asks arrays)."""
    result = await session.execute(
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.token_id == token_id)
        .order_by(desc(OrderBookSnapshot.timestamp))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No orderbook data found")

    return {
        "token_id": snapshot.token_id,
        "timestamp": snapshot.timestamp.isoformat(),
        "bids": snapshot.bids or [],
        "asks": snapshot.asks or [],
        "metrics": {
            "best_bid": float(snapshot.best_bid) if snapshot.best_bid else None,
            "best_ask": float(snapshot.best_ask) if snapshot.best_ask else None,
            "spread": float(snapshot.spread) if snapshot.spread else None,
            "spread_pct": float(snapshot.spread_pct) if snapshot.spread_pct else None,
            "mid_price": float(snapshot.mid_price) if snapshot.mid_price else None,
            "imbalance": float(snapshot.imbalance) if snapshot.imbalance else None,
        },
    }
