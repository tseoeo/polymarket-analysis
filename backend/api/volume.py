"""Volume API endpoints."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.trade import Trade
from models.alert import Alert
from models.volume_stats import VolumeStats
from services.volume_analyzer import VolumeAnalyzer

router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================

class VolumeStatsResponse(BaseModel):
    """Current volume metrics for a token."""

    token_id: str
    period_days: int
    total_volume: float
    daily_avg: float
    min_daily: float
    max_daily: float
    trend_pct: float
    source: str


class VolumeHistoryResponse(BaseModel):
    """Historical volume data."""

    token_id: str
    period_type: str
    data: List[dict]


class VolumeAccelerationResponse(BaseModel):
    """Volume acceleration metrics."""

    token_id: str
    window_hours: int
    recent_volume: float
    recent_trade_count: int
    previous_volume: float
    previous_trade_count: int
    volume_acceleration: float
    trade_acceleration: float
    signal: str


class VolumePriceCorrelationResponse(BaseModel):
    """Volume-price correlation analysis."""

    token_id: str
    analysis_hours: int
    data_points: int
    correlation: float
    price_change_pct: float
    volume_trend_pct: float
    total_volume: float
    avg_hourly_volume: float
    price_start: float
    price_end: float
    interpretation: str


class VolumeSpikeResponse(BaseModel):
    """Volume spike alert."""

    id: int
    market_id: str
    token_id: str
    title: str
    volume_ratio: float
    current_volume: float
    average_volume: float
    created_at: datetime
    is_active: bool


class VolumeLeaderResponse(BaseModel):
    """Top volume market."""

    market_id: str
    token_id: str
    volume_24h: float
    trade_count_24h: int
    avg_trade_size: float


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{token_id}/stats", response_model=VolumeStatsResponse)
async def get_volume_stats(
    token_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get 7-day volume baseline statistics for a token."""
    analyzer = VolumeAnalyzer()
    result = await analyzer.calculate_7day_baseline(session, token_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return VolumeStatsResponse(**result)


@router.get("/{token_id}/acceleration", response_model=VolumeAccelerationResponse)
async def get_volume_acceleration(
    token_id: str,
    window_hours: int = Query(6, ge=1, le=24, description="Window size in hours"),
    session: AsyncSession = Depends(get_db),
):
    """Get volume acceleration (rate of change) for a token."""
    analyzer = VolumeAnalyzer()
    result = await analyzer.calculate_acceleration(session, token_id, window_hours)

    return VolumeAccelerationResponse(**result)


@router.get("/{token_id}/correlation", response_model=VolumePriceCorrelationResponse)
async def get_volume_price_correlation(
    token_id: str,
    hours: int = Query(24, ge=6, le=168, description="Hours of history to analyze"),
    session: AsyncSession = Depends(get_db),
):
    """Analyze volume-price correlation for a token."""
    analyzer = VolumeAnalyzer()
    result = await analyzer.analyze_volume_price_relationship(session, token_id, hours)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return VolumePriceCorrelationResponse(**result)


@router.get("/{token_id}/history", response_model=VolumeHistoryResponse)
async def get_volume_history(
    token_id: str,
    period: str = Query("hour", description="Period type: hour, day, week"),
    limit: int = Query(24, ge=1, le=168),
    session: AsyncSession = Depends(get_db),
):
    """Get historical volume data from VolumeStats."""
    if period not in ["hour", "day", "week"]:
        raise HTTPException(status_code=400, detail="Period must be hour, day, or week")

    result = await session.execute(
        select(VolumeStats)
        .where(VolumeStats.token_id == token_id)
        .where(VolumeStats.period_type == period)
        .order_by(desc(VolumeStats.period_start))
        .limit(limit)
    )
    stats = result.scalars().all()

    return VolumeHistoryResponse(
        token_id=token_id,
        period_type=period,
        data=[
            {
                "period_start": s.period_start.isoformat(),
                "period_end": s.period_end.isoformat(),
                "volume": float(s.volume),
                "trade_count": s.trade_count,
                "avg_trade_size": float(s.avg_trade_size) if s.avg_trade_size else None,
                "price_open": float(s.price_open) if s.price_open else None,
                "price_close": float(s.price_close) if s.price_close else None,
                "price_high": float(s.price_high) if s.price_high else None,
                "price_low": float(s.price_low) if s.price_low else None,
            }
            for s in reversed(stats)
        ],
    )


@router.get("/spikes", response_model=List[VolumeSpikeResponse])
async def get_volume_spikes(
    is_active: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Get markets with volume spike alerts."""
    query = (
        select(Alert)
        .where(Alert.alert_type == "volume_spike")
    )
    if is_active:
        query = query.where(Alert.is_active == True)

    query = query.order_by(desc(Alert.created_at)).limit(limit)

    result = await session.execute(query)
    alerts = result.scalars().all()

    return [
        VolumeSpikeResponse(
            id=a.id,
            market_id=a.market_id or "",
            token_id=a.data.get("token_id", "") if a.data else "",
            title=a.title,
            volume_ratio=a.data.get("current_volume", 0) / a.data.get("average_volume", 1)
                if a.data and a.data.get("average_volume", 0) > 0 else 0,
            current_volume=a.data.get("current_volume", 0) if a.data else 0,
            average_volume=a.data.get("average_volume", 0) if a.data else 0,
            created_at=a.created_at,
            is_active=a.is_active,
        )
        for a in alerts
    ]


@router.get("/leaders", response_model=List[VolumeLeaderResponse])
async def get_volume_leaders(
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """Get top volume markets in the last 24 hours."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=24)

    result = await session.execute(
        select(
            Trade.market_id,
            Trade.token_id,
            func.sum(Trade.size).label("volume_24h"),
            func.count().label("trade_count"),
        )
        .where(Trade.timestamp >= cutoff)
        .group_by(Trade.market_id, Trade.token_id)
        .order_by(desc("volume_24h"))
        .limit(limit)
    )
    leaders = result.all()

    return [
        VolumeLeaderResponse(
            market_id=r[0] or "",
            token_id=r[1] or "",
            volume_24h=float(r[2] or 0),
            trade_count_24h=r[3] or 0,
            avg_trade_size=float(r[2] / r[3]) if r[3] and r[3] > 0 else 0,
        )
        for r in leaders
    ]
