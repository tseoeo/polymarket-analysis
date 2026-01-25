"""System status and observability API.

Provides endpoints for monitoring system health, job execution status,
and data freshness. Protected by ENABLE_SYSTEM_STATUS env var.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.job_run import JobRun
from models.trade import Trade
from models.orderbook import OrderBookSnapshot
from models.alert import Alert

router = APIRouter()


class JobStatus(BaseModel):
    """Status of a single job type."""

    id: str
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None  # "running", "success", "failed"
    run_id: Optional[str] = None
    records_processed: Optional[int] = None
    error_message: Optional[str] = None


class SchedulerStatus(BaseModel):
    """Scheduler health status."""

    enabled: bool
    jobs: List[JobStatus]


class DataFreshness(BaseModel):
    """Data freshness timestamps."""

    last_trade: Optional[datetime] = None
    last_orderbook: Optional[datetime] = None
    last_analysis: Optional[datetime] = None
    last_market_sync: Optional[datetime] = None


class DataCounts(BaseModel):
    """Optional data counts (expensive queries)."""

    markets_active: int = 0
    trades_24h: int = 0
    orderbooks_24h: int = 0
    alerts_active: int = 0


class SystemStatusResponse(BaseModel):
    """Full system status response."""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    scheduler: SchedulerStatus
    data_freshness: DataFreshness
    counts: Optional[DataCounts] = None


# Job IDs that we track
TRACKED_JOBS = [
    "collect_markets",
    "collect_orderbooks",
    "collect_trades",
    "run_analysis",
    "cleanup_old_data",
]


async def get_job_statuses(session: AsyncSession) -> List[JobStatus]:
    """Get latest status for each tracked job type.

    Uses a subquery to efficiently get the most recent run per job_id.
    """
    # Subquery to get max started_at per job_id
    subq = (
        select(JobRun.job_id, func.max(JobRun.started_at).label("max_started"))
        .where(JobRun.job_id.in_(TRACKED_JOBS))
        .group_by(JobRun.job_id)
        .subquery()
    )

    # Join to get full JobRun records
    result = await session.execute(
        select(JobRun).join(
            subq,
            and_(
                JobRun.job_id == subq.c.job_id,
                JobRun.started_at == subq.c.max_started,
            ),
        )
    )

    job_runs = {jr.job_id: jr for jr in result.scalars().all()}

    # Build status list for all tracked jobs
    statuses = []
    for job_id in TRACKED_JOBS:
        jr = job_runs.get(job_id)
        if jr:
            statuses.append(
                JobStatus(
                    id=job_id,
                    last_run=jr.started_at,
                    last_status=jr.status,
                    run_id=jr.run_id,
                    records_processed=jr.records_processed,
                    error_message=jr.error_message if jr.status == "failed" else None,
                )
            )
        else:
            statuses.append(JobStatus(id=job_id))

    return statuses


async def get_data_freshness(
    session: AsyncSession, job_statuses: List[JobStatus]
) -> DataFreshness:
    """Get data freshness using fast MAX(timestamp) queries."""
    # Get latest trade timestamp
    trade_result = await session.execute(select(func.max(Trade.timestamp)))
    last_trade = trade_result.scalar()

    # Get latest orderbook timestamp
    orderbook_result = await session.execute(
        select(func.max(OrderBookSnapshot.timestamp))
    )
    last_orderbook = orderbook_result.scalar()

    # Get last analysis run from job_runs table
    analysis_job = next((j for j in job_statuses if j.id == "run_analysis"), None)
    last_analysis = analysis_job.last_run if analysis_job else None

    # Get last market sync from job_runs table
    market_job = next((j for j in job_statuses if j.id == "collect_markets"), None)
    last_market_sync = market_job.last_run if market_job else None

    return DataFreshness(
        last_trade=last_trade,
        last_orderbook=last_orderbook,
        last_analysis=last_analysis,
        last_market_sync=last_market_sync,
    )


async def get_data_counts(session: AsyncSession) -> DataCounts:
    """Get data counts (more expensive queries)."""
    from models.market import Market

    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)

    # Active markets count
    markets_result = await session.execute(
        select(func.count()).select_from(Market).where(Market.active == True)
    )
    markets_active = markets_result.scalar() or 0

    # Trades in last 24h
    trades_result = await session.execute(
        select(func.count())
        .select_from(Trade)
        .where(Trade.timestamp >= day_ago)
    )
    trades_24h = trades_result.scalar() or 0

    # Orderbooks in last 24h
    orderbooks_result = await session.execute(
        select(func.count())
        .select_from(OrderBookSnapshot)
        .where(OrderBookSnapshot.timestamp >= day_ago)
    )
    orderbooks_24h = orderbooks_result.scalar() or 0

    # Active alerts
    alerts_result = await session.execute(
        select(func.count()).select_from(Alert).where(Alert.is_active == True)
    )
    alerts_active = alerts_result.scalar() or 0

    return DataCounts(
        markets_active=markets_active,
        trades_24h=trades_24h,
        orderbooks_24h=orderbooks_24h,
        alerts_active=alerts_active,
    )


def determine_health_status(
    job_statuses: List[JobStatus],
    data_freshness: DataFreshness,
) -> str:
    """Determine overall system health.

    Returns:
        "healthy" - All jobs succeeded recently, data is fresh
        "degraded" - Some jobs failed or data is stale
        "unhealthy" - Critical failures or very stale data
    """
    now = datetime.utcnow()

    # Check for recent failures
    failed_jobs = [j for j in job_statuses if j.last_status == "failed"]
    running_jobs = [j for j in job_statuses if j.last_status == "running"]

    # Check data freshness thresholds
    stale_threshold = timedelta(hours=2)
    critical_threshold = timedelta(hours=6)

    trade_stale = False
    trade_critical = False
    if data_freshness.last_trade:
        trade_age = now - data_freshness.last_trade
        trade_stale = trade_age > stale_threshold
        trade_critical = trade_age > critical_threshold

    orderbook_stale = False
    orderbook_critical = False
    if data_freshness.last_orderbook:
        orderbook_age = now - data_freshness.last_orderbook
        orderbook_stale = orderbook_age > stale_threshold
        orderbook_critical = orderbook_age > critical_threshold

    # Determine status
    if failed_jobs or trade_critical or orderbook_critical:
        return "unhealthy"
    elif trade_stale or orderbook_stale or running_jobs:
        return "degraded"
    else:
        return "healthy"


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    include_counts: bool = Query(
        False, description="Include data counts (more expensive queries)"
    ),
    session: AsyncSession = Depends(get_db),
):
    """Get comprehensive system status.

    Returns scheduler health, job execution history, and data freshness.
    Use ?include_counts=true for additional statistics (more expensive).

    This endpoint is protected by the ENABLE_SYSTEM_STATUS env var.
    """
    # Check if endpoint is enabled
    if not settings.enable_system_status:
        raise HTTPException(
            status_code=404,
            detail="System status endpoint is disabled",
        )

    # Get job statuses (fast query)
    job_statuses = await get_job_statuses(session)

    # Get data freshness (fast MAX queries)
    data_freshness = await get_data_freshness(session, job_statuses)

    # Determine health
    health_status = determine_health_status(job_statuses, data_freshness)

    # Build response
    response = SystemStatusResponse(
        status=health_status,
        timestamp=datetime.now(timezone.utc),
        scheduler=SchedulerStatus(
            enabled=settings.enable_scheduler,
            jobs=job_statuses,
        ),
        data_freshness=data_freshness,
        counts=None,
    )

    # Optionally include counts
    if include_counts:
        response.counts = await get_data_counts(session)

    return response
