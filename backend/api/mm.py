"""Market Maker analysis API endpoints."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.alert import Alert
from models.orderbook import OrderBookSnapshot

router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================

class MMPresenceResponse(BaseModel):
    """Market maker presence score."""

    token_id: str
    presence_score: float  # 0-1 scale
    avg_spread_pct: float
    avg_depth_1pct: float
    spread_consistency: float  # Lower = more consistent
    depth_consistency: float
    snapshot_count: int
    analysis_period_hours: int


class MMPatternResponse(BaseModel):
    """MM activity patterns by hour."""

    token_id: str
    hourly_patterns: Dict[int, Dict[str, float]]
    best_mm_hours: List[int]
    worst_mm_hours: List[int]


class MMPullbackResponse(BaseModel):
    """Market maker pullback alert."""

    id: int
    market_id: str
    token_id: str
    title: str
    depth_drop_pct: float
    previous_depth: float
    current_depth: float
    created_at: datetime
    is_active: bool


class BestTradingHoursResponse(BaseModel):
    """Best trading hours across markets."""

    hour: int
    avg_spread_pct: float
    avg_depth: float
    market_count: int
    quality_score: float


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{token_id}/presence", response_model=MMPresenceResponse)
async def get_mm_presence(
    token_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to analyze"),
    session: AsyncSession = Depends(get_db),
):
    """Get market maker presence score for a token.

    Presence is measured by:
    - Tight spreads
    - Consistent depth
    - Low spread variance
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    result = await session.execute(
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.token_id == token_id)
        .where(OrderBookSnapshot.timestamp >= cutoff)
    )
    snapshots = result.scalars().all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="No orderbook data found")

    # Calculate metrics
    spreads = [float(s.spread_pct) for s in snapshots if s.spread_pct is not None]
    depths = [float(s.bid_depth_1pct or 0) + float(s.ask_depth_1pct or 0)
              for s in snapshots if s.bid_depth_1pct or s.ask_depth_1pct]

    if not spreads or not depths:
        raise HTTPException(status_code=404, detail="Insufficient data")

    avg_spread = sum(spreads) / len(spreads)
    avg_depth = sum(depths) / len(depths) if depths else 0

    # Calculate variance (consistency)
    spread_var = sum((s - avg_spread) ** 2 for s in spreads) / len(spreads)
    depth_var = sum((d - avg_depth) ** 2 for d in depths) / len(depths) if depths else 0

    # Presence score: lower spread + higher depth + higher consistency = higher score
    # Normalize components to 0-1
    spread_score = max(0, 1 - (avg_spread / 0.10))  # 10% spread = 0, 0% = 1
    depth_score = min(1, avg_depth / 10000)  # $10k depth = 1
    consistency_score = max(0, 1 - (spread_var ** 0.5 / 0.05))  # 5% std dev = 0

    presence_score = (spread_score * 0.4 + depth_score * 0.3 + consistency_score * 0.3)

    return MMPresenceResponse(
        token_id=token_id,
        presence_score=presence_score,
        avg_spread_pct=avg_spread,
        avg_depth_1pct=avg_depth,
        spread_consistency=spread_var ** 0.5,
        depth_consistency=depth_var ** 0.5 if depth_var else 0,
        snapshot_count=len(snapshots),
        analysis_period_hours=hours,
    )


@router.get("/{token_id}/patterns", response_model=MMPatternResponse)
async def get_mm_patterns(
    token_id: str,
    hours: int = Query(168, ge=24, le=720, description="Hours of history"),
    session: AsyncSession = Depends(get_db),
):
    """Get market maker activity patterns by hour of day."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    result = await session.execute(
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.token_id == token_id)
        .where(OrderBookSnapshot.timestamp >= cutoff)
    )
    snapshots = result.scalars().all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="No orderbook data found")

    # Group by hour
    hourly_data: Dict[int, List[Dict]] = {h: [] for h in range(24)}
    for s in snapshots:
        hour = s.timestamp.hour
        hourly_data[hour].append({
            "spread_pct": float(s.spread_pct) if s.spread_pct else None,
            "depth": (float(s.bid_depth_1pct or 0) + float(s.ask_depth_1pct or 0)),
        })

    # Calculate hourly averages
    hourly_patterns = {}
    for hour, data in hourly_data.items():
        if not data:
            continue
        spreads = [d["spread_pct"] for d in data if d["spread_pct"] is not None]
        depths = [d["depth"] for d in data]

        if spreads:
            hourly_patterns[hour] = {
                "avg_spread_pct": sum(spreads) / len(spreads),
                "avg_depth": sum(depths) / len(depths) if depths else 0,
                "snapshot_count": len(data),
            }

    # Find best/worst hours (best = tight spread + high depth)
    scored_hours = [
        (hour, -data["avg_spread_pct"] + data["avg_depth"] / 10000)
        for hour, data in hourly_patterns.items()
    ]
    scored_hours.sort(key=lambda x: x[1], reverse=True)

    best_hours = [h for h, _ in scored_hours[:5]]
    worst_hours = [h for h, _ in scored_hours[-5:]]

    return MMPatternResponse(
        token_id=token_id,
        hourly_patterns=hourly_patterns,
        best_mm_hours=best_hours,
        worst_mm_hours=worst_hours,
    )


@router.get("/pullbacks", response_model=List[MMPullbackResponse])
async def get_mm_pullbacks(
    is_active: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Get active market maker pullback alerts."""
    query = (
        select(Alert)
        .where(Alert.alert_type == "mm_pullback")
    )
    if is_active:
        query = query.where(Alert.is_active == True)

    query = query.order_by(desc(Alert.created_at)).limit(limit)

    result = await session.execute(query)
    alerts = result.scalars().all()

    return [
        MMPullbackResponse(
            id=a.id,
            market_id=a.market_id or "",
            token_id=a.data.get("token_id", "") if a.data else "",
            title=a.title,
            depth_drop_pct=a.data.get("depth_drop_pct", 0) if a.data else 0,
            previous_depth=a.data.get("previous_depth", 0) if a.data else 0,
            current_depth=a.data.get("current_depth", 0) if a.data else 0,
            created_at=a.created_at,
            is_active=a.is_active,
        )
        for a in alerts
    ]


@router.get("/best-hours", response_model=List[BestTradingHoursResponse])
async def get_best_hours_overall(
    hours: int = Query(168, ge=24, le=720),
    limit: int = Query(24, ge=1, le=24),
    session: AsyncSession = Depends(get_db),
):
    """Get best trading hours across all markets."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    result = await session.execute(
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.timestamp >= cutoff)
        .where(OrderBookSnapshot.spread_pct.isnot(None))
    )
    snapshots = result.scalars().all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="No orderbook data found")

    # Group by hour across all markets
    hourly_data: Dict[int, List[Dict]] = {h: [] for h in range(24)}
    for s in snapshots:
        hour = s.timestamp.hour
        hourly_data[hour].append({
            "spread_pct": float(s.spread_pct) if s.spread_pct else None,
            "depth": float(s.bid_depth_1pct or 0) + float(s.ask_depth_1pct or 0),
            "token_id": s.token_id,
        })

    # Calculate hourly aggregates
    results = []
    for hour in range(24):
        data = hourly_data[hour]
        if not data:
            continue

        spreads = [d["spread_pct"] for d in data if d["spread_pct"]]
        depths = [d["depth"] for d in data]
        unique_markets = len(set(d["token_id"] for d in data))

        if spreads:
            avg_spread = sum(spreads) / len(spreads)
            avg_depth = sum(depths) / len(depths) if depths else 0
            # Quality score: lower spread is better, higher depth is better
            quality = (1 - min(avg_spread / 0.10, 1)) * 0.6 + min(avg_depth / 5000, 1) * 0.4

            results.append(BestTradingHoursResponse(
                hour=hour,
                avg_spread_pct=avg_spread,
                avg_depth=avg_depth,
                market_count=unique_markets,
                quality_score=quality,
            ))

    # Sort by quality score
    results.sort(key=lambda x: x.quality_score, reverse=True)

    return results[:limit]
