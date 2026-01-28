"""Watchlist API endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.watchlist import WatchlistItem
from models.market import Market
from services.safety_scorer import SafetyScorer

router = APIRouter()


# ============================================================================
# Request/Response Schemas
# ============================================================================

class AddToWatchlistRequest(BaseModel):
    """Request to add a market to watchlist."""

    market_id: str
    notes: Optional[str] = None


class UpdateWatchlistItemRequest(BaseModel):
    """Request to update a watchlist item."""

    notes: Optional[str] = None


class WatchlistItemResponse(BaseModel):
    """A watchlist item with current market data."""

    id: int
    market_id: str
    market_question: Optional[str] = None
    category: Optional[str] = None

    added_at: str
    last_viewed_at: Optional[str] = None
    notes: Optional[str] = None

    # Current safety score
    current_safety_score: Optional[int] = None
    initial_safety_score: Optional[int] = None
    score_change: Optional[int] = None

    # Key metrics
    spread_pct: Optional[float] = None
    total_depth: Optional[float] = None
    freshness_minutes: Optional[float] = None

    # Alerts since last view
    new_alerts_count: int = 0


class WatchlistResponse(BaseModel):
    """Full watchlist."""

    items: List[WatchlistItemResponse]
    total_count: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    session: AsyncSession = Depends(get_db),
):
    """Get all watchlist items with current market data."""
    result = await session.execute(
        select(WatchlistItem).order_by(WatchlistItem.added_at.desc())
    )
    items = result.scalars().all()

    scorer = SafetyScorer()
    response_items = []

    for item in items:
        # Get market info
        market_result = await session.execute(
            select(Market).where(Market.id == item.market_id)
        )
        market = market_result.scalar_one_or_none()

        if not market:
            continue  # Market was deleted

        # Calculate current safety score
        try:
            score = await scorer.calculate_score(session, market)
            current_score = score.total
            score_change = None
            if item.initial_safety_score is not None:
                score_change = current_score - item.initial_safety_score
        except Exception:
            current_score = None
            score_change = None

        # Count alerts since last view
        from models.alert import Alert
        alert_query = select(Alert).where(
            or_(
                Alert.market_id == item.market_id,
                cast(Alert.related_market_ids, String).like(f'%"{item.market_id}"%'),
            )
        ).where(Alert.is_active == True)

        if item.last_viewed_at:
            alert_query = alert_query.where(Alert.created_at > item.last_viewed_at)

        alert_result = await session.execute(alert_query)
        new_alerts = len(alert_result.scalars().all())

        response_items.append(WatchlistItemResponse(
            id=item.id,
            market_id=item.market_id,
            market_question=market.question,
            category=market.category,
            added_at=item.added_at.isoformat(),
            last_viewed_at=item.last_viewed_at.isoformat() if item.last_viewed_at else None,
            notes=item.notes,
            current_safety_score=current_score,
            initial_safety_score=item.initial_safety_score,
            score_change=score_change,
            spread_pct=float(score.metrics.spread_pct) if score and score.metrics.spread_pct else None,
            total_depth=score.metrics.total_depth if score else None,
            freshness_minutes=score.metrics.freshness_minutes if score else None,
            new_alerts_count=new_alerts,
        ))

    return WatchlistResponse(
        items=response_items,
        total_count=len(response_items),
    )


@router.post("", response_model=WatchlistItemResponse)
async def add_to_watchlist(
    request: AddToWatchlistRequest,
    session: AsyncSession = Depends(get_db),
):
    """Add a market to the watchlist."""
    # Check if market exists
    market_result = await session.execute(
        select(Market).where(Market.id == request.market_id)
    )
    market = market_result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Check if already in watchlist
    existing = await session.execute(
        select(WatchlistItem).where(WatchlistItem.market_id == request.market_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Market already in watchlist")

    # Calculate initial safety score
    scorer = SafetyScorer()
    try:
        score = await scorer.calculate_score(session, market)
        initial_score = score.total
    except Exception:
        initial_score = None

    # Create watchlist item
    item = WatchlistItem.create(
        market_id=request.market_id,
        notes=request.notes,
        initial_safety_score=initial_score,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return WatchlistItemResponse(
        id=item.id,
        market_id=item.market_id,
        market_question=market.question,
        category=market.category,
        added_at=item.added_at.isoformat(),
        last_viewed_at=None,
        notes=item.notes,
        current_safety_score=initial_score,
        initial_safety_score=initial_score,
        score_change=0,
        spread_pct=float(score.metrics.spread_pct) if score and score.metrics.spread_pct else None,
        total_depth=score.metrics.total_depth if score else None,
        freshness_minutes=score.metrics.freshness_minutes if score else None,
        new_alerts_count=0,
    )


@router.patch("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    item_id: int,
    request: UpdateWatchlistItemRequest,
    session: AsyncSession = Depends(get_db),
):
    """Update a watchlist item (e.g., add notes)."""
    result = await session.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    if request.notes is not None:
        item.notes = request.notes

    await session.commit()
    await session.refresh(item)

    # Get market for response
    market_result = await session.execute(
        select(Market).where(Market.id == item.market_id)
    )
    market = market_result.scalar_one_or_none()

    return WatchlistItemResponse(
        id=item.id,
        market_id=item.market_id,
        market_question=market.question if market else None,
        category=market.category if market else None,
        added_at=item.added_at.isoformat(),
        last_viewed_at=item.last_viewed_at.isoformat() if item.last_viewed_at else None,
        notes=item.notes,
        current_safety_score=None,
        initial_safety_score=item.initial_safety_score,
        score_change=None,
        new_alerts_count=0,
    )


@router.post("/{item_id}/viewed")
async def mark_as_viewed(
    item_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Mark a watchlist item as viewed (resets new alerts count)."""
    result = await session.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    item.last_viewed_at = datetime.utcnow()
    await session.commit()

    return {"status": "ok", "last_viewed_at": item.last_viewed_at.isoformat()}


@router.delete("/{item_id}")
async def remove_from_watchlist(
    item_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Remove a market from the watchlist."""
    result = await session.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    await session.delete(item)
    await session.commit()

    return {"status": "ok", "deleted_id": item_id}
