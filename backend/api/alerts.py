"""Alert API endpoints."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.alert import Alert

router = APIRouter()


class AlertResponse(BaseModel):
    """Alert response schema."""

    id: int
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    market_id: Optional[str] = None
    related_market_ids: Optional[List[str]] = None
    data: Optional[dict] = None
    is_active: bool
    created_at: datetime
    dismissed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated alert list."""

    alerts: List[AlertResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    alert_type: Optional[str] = Query(None, description="Filter by type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    market_id: Optional[str] = Query(None, description="Filter by market"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List alerts with optional filters and pagination."""
    # Build filters
    filters = []
    if alert_type:
        filters.append(Alert.alert_type == alert_type)
    if severity:
        filters.append(Alert.severity == severity)
    if market_id:
        filters.append(Alert.market_id == market_id)
    if is_active is not None:
        filters.append(Alert.is_active == is_active)

    # Build base query with filters
    base_query = select(Alert)
    if filters:
        base_query = base_query.where(and_(*filters))

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = base_query.order_by(desc(Alert.created_at)).offset(offset).limit(limit)
    result = await session.execute(query)
    alerts = result.scalars().all()

    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get a single alert by ID."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.patch("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Dismiss an alert. Returns the updated alert."""
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.dismiss()
    await session.commit()
    await session.refresh(alert)
    return AlertResponse.model_validate(alert)
