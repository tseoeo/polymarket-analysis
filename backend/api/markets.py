"""Market API endpoints."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.market import Market
from models.alert import Alert

router = APIRouter()


class MarketResponse(BaseModel):
    """Market response schema.

    Note: yes_price and no_price come from cached Gamma API data.
    For live prices, check the latest orderbook snapshots.
    """

    id: str
    question: str
    description: Optional[str] = None
    outcomes: Optional[list] = None
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    active: bool
    end_date: Optional[datetime] = None
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    active_alerts: int = 0
    token_ids: List[str] = []

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    """Paginated market list."""

    markets: List[MarketResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=MarketListResponse)
async def list_markets(
    active: Optional[bool] = Query(True, description="Filter by active status"),
    has_alerts: Optional[bool] = Query(None, description="Filter to markets with/without active alerts"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List markets with optional filters and pagination.

    When has_alerts is specified, filtering is done at the DB level
    so total count and pagination are accurate.
    """
    # Subquery to count active alerts per market
    alert_count_subq = (
        select(Alert.market_id, func.count(Alert.id).label("alert_count"))
        .where(Alert.is_active == True)
        .group_by(Alert.market_id)
        .subquery()
    )

    # Base query joining markets with alert counts
    base_query = (
        select(
            Market,
            func.coalesce(alert_count_subq.c.alert_count, 0).label("active_alerts"),
        )
        .outerjoin(alert_count_subq, Market.id == alert_count_subq.c.market_id)
    )

    # Apply filters
    if active is not None:
        base_query = base_query.where(Market.active == active)

    if has_alerts is True:
        base_query = base_query.where(alert_count_subq.c.alert_count > 0)
    elif has_alerts is False:
        base_query = base_query.where(
            (alert_count_subq.c.alert_count == None) | (alert_count_subq.c.alert_count == 0)
        )

    # Get total count (from filtered query)
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = base_query.order_by(desc(Market.volume)).offset(offset).limit(limit)
    result = await session.execute(query)
    rows = result.all()

    # Build response
    market_responses = []
    for row in rows:
        market = row[0]
        alert_count = row[1]
        market_responses.append(
            MarketResponse(
                id=market.id,
                question=market.question,
                description=market.description,
                outcomes=market.outcomes,
                volume=float(market.volume) if market.volume else None,
                liquidity=float(market.liquidity) if market.liquidity else None,
                active=market.active,
                end_date=market.end_date,
                yes_price=market.yes_price,
                no_price=market.no_price,
                active_alerts=alert_count,
            )
        )

    return MarketListResponse(
        markets=market_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(
    market_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get a single market by ID with its active alert count."""
    result = await session.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Get active alert count
    alert_result = await session.execute(
        select(func.count(Alert.id))
        .where(Alert.market_id == market_id)
        .where(Alert.is_active == True)
    )
    alert_count = alert_result.scalar() or 0

    return MarketResponse(
        id=market.id,
        question=market.question,
        description=market.description,
        outcomes=market.outcomes,
        volume=float(market.volume) if market.volume else None,
        liquidity=float(market.liquidity) if market.liquidity else None,
        active=market.active,
        end_date=market.end_date,
        yes_price=market.yes_price,
        no_price=market.no_price,
        active_alerts=alert_count,
    )


@router.get("/{market_id}/alerts")
async def get_market_alerts(
    market_id: str,
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    session: AsyncSession = Depends(get_db),
):
    """Get alerts for a specific market."""
    from api.alerts import AlertResponse

    # Verify market exists
    market_result = await session.execute(select(Market.id).where(Market.id == market_id))
    if not market_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Market not found")

    query = select(Alert).where(Alert.market_id == market_id)
    if is_active is not None:
        query = query.where(Alert.is_active == is_active)
    query = query.order_by(desc(Alert.created_at))

    result = await session.execute(query)
    alerts = result.scalars().all()
    return [AlertResponse.model_validate(a) for a in alerts]
