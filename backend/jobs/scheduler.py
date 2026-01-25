"""APScheduler setup for background data collection and analysis."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from contextlib import asynccontextmanager

from typing import Optional, Tuple, Any

from config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


@asynccontextmanager
async def track_job_run(job_id: str):
    """Context manager to track job execution in the database.

    Creates a JobRun record on entry and updates it on exit with
    success/failure status. Generates a UUID for log correlation.

    Usage:
        async with track_job_run("collect_markets") as run_id:
            # Do work...
            # Return records_processed to record_result()
    """
    from database import async_session_maker
    from models.job_run import JobRun

    run_id = str(uuid.uuid4())
    job_run = JobRun(job_id=job_id, run_id=run_id)

    try:
        async with async_session_maker() as session:
            session.add(job_run)
            await session.commit()
            await session.refresh(job_run)

        logger.info(f"[{run_id[:8]}] Starting {job_id}")
        yield run_id

        # Mark success
        async with async_session_maker() as session:
            result = await session.execute(
                __import__("sqlalchemy").select(JobRun).where(JobRun.id == job_run.id)
            )
            job_run = result.scalar_one()
            job_run.mark_success()
            await session.commit()

        logger.info(f"[{run_id[:8]}] Completed {job_id}")

    except Exception as e:
        # Mark failure
        try:
            async with async_session_maker() as session:
                from sqlalchemy import select

                result = await session.execute(
                    select(JobRun).where(JobRun.id == job_run.id)
                )
                job_run = result.scalar_one()
                job_run.mark_failed(str(e)[:500])  # Truncate long errors
                await session.commit()
        except Exception as db_err:
            logger.error(f"Failed to record job failure: {db_err}")

        logger.error(f"[{run_id[:8]}] Failed {job_id}: {e}")
        raise


async def update_job_records(job_id: str, run_id: str, records_processed: int):
    """Update job run with records processed count."""
    from database import async_session_maker
    from models.job_run import JobRun
    from sqlalchemy import select

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(JobRun).where(JobRun.run_id == run_id)
            )
            job_run = result.scalar_one_or_none()
            if job_run:
                job_run.records_processed = records_processed
                await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update records count: {e}")


async def collect_markets_job():
    """Job: Fetch and update market data from Gamma API."""
    async with track_job_run("collect_markets") as run_id:
        client = None
        try:
            from services.polymarket_client import PolymarketClient
            from database import async_session_maker

            client = PolymarketClient()
            async with async_session_maker() as session:
                count = await client.sync_markets(session)
                await session.commit()

            # Update records count if sync_markets returns it
            if isinstance(count, int):
                await update_job_records("collect_markets", run_id, count)
        finally:
            if client:
                await client.close()


async def collect_orderbooks_job():
    """Job: Fetch order book snapshots for all active markets."""
    async with track_job_run("collect_orderbooks") as run_id:
        client = None
        try:
            from services.polymarket_client import PolymarketClient
            from database import async_session_maker

            client = PolymarketClient()
            async with async_session_maker() as session:
                count = await client.collect_orderbooks(session)
                await session.commit()

            if isinstance(count, int):
                await update_job_records("collect_orderbooks", run_id, count)
        finally:
            if client:
                await client.close()


async def collect_trades_job():
    """Job: Fetch recent trades for all active markets."""
    async with track_job_run("collect_trades") as run_id:
        client = None
        try:
            from services.polymarket_client import PolymarketClient
            from database import async_session_maker

            client = PolymarketClient()
            async with async_session_maker() as session:
                new_count, dup_count = await client.collect_trades(session)
                await session.commit()

            await update_job_records("collect_trades", run_id, new_count)
            logger.info(f"Trade collection: {new_count} new, {dup_count} duplicates")
        finally:
            if client:
                await client.close()


async def run_analysis_job():
    """Job: Run all analysis modules and generate alerts.

    Runs four analyzer modules:
    1. VolumeAnalyzer - Detects unusual trading volume spikes
    2. SpreadAnalyzer - Detects wide spreads indicating poor liquidity
    3. MarketMakerAnalyzer - Detects MM liquidity withdrawals
    4. ArbitrageDetector - Detects intra-market pricing anomalies

    Each analyzer handles its own deduplication to avoid duplicate alerts.
    """
    async with track_job_run("run_analysis") as run_id:
        from services.volume_analyzer import VolumeAnalyzer
        from services.spread_analyzer import SpreadAnalyzer
        from services.mm_analyzer import MarketMakerAnalyzer
        from services.arbitrage_detector import ArbitrageDetector
        from database import async_session_maker

        async with async_session_maker() as session:
            all_alerts = []

            # Volume spike analysis
            try:
                volume_analyzer = VolumeAnalyzer()
                volume_alerts = await volume_analyzer.analyze(session)
                all_alerts.extend(volume_alerts)
            except Exception as e:
                logger.error(f"Volume analysis failed: {e}")

            # Spread/liquidity analysis
            try:
                spread_analyzer = SpreadAnalyzer()
                spread_alerts = await spread_analyzer.analyze(session)
                all_alerts.extend(spread_alerts)
            except Exception as e:
                logger.error(f"Spread analysis failed: {e}")

            # Market maker pullback analysis
            try:
                mm_analyzer = MarketMakerAnalyzer()
                mm_alerts = await mm_analyzer.analyze(session)
                all_alerts.extend(mm_alerts)
            except Exception as e:
                logger.error(f"MM analysis failed: {e}")

            # Arbitrage detection
            try:
                arb_detector = ArbitrageDetector()
                arb_alerts = await arb_detector.analyze(session)
                all_alerts.extend(arb_alerts)
            except Exception as e:
                logger.error(f"Arbitrage analysis failed: {e}")

            await session.commit()

        # Record alerts generated count
        await update_job_records("run_analysis", run_id, len(all_alerts))

        # Log summary by alert type
        alert_summary = {}
        for alert in all_alerts:
            alert_summary[alert.alert_type] = alert_summary.get(alert.alert_type, 0) + 1

        logger.info(
            f"Analysis complete: {len(all_alerts)} alerts generated "
            f"{alert_summary if alert_summary else ''}"
        )


async def cleanup_old_data_job():
    """Job: Expire stale alerts and remove old data."""
    async with track_job_run("cleanup_old_data") as run_id:
        from database import async_session_maker
        from sqlalchemy import text, update
        from models.alert import Alert

        cutoff = datetime.utcnow() - timedelta(days=settings.data_retention_days)
        now = datetime.utcnow()

        async with async_session_maker() as session:
            # Expire alerts past their expires_at timestamp
            expire_result = await session.execute(
                update(Alert)
                .where(Alert.expires_at < now)
                .where(Alert.is_active == True)
                .values(is_active=False, dismissed_at=now)
            )
            expired_count = expire_result.rowcount

            # Delete old order book snapshots
            await session.execute(
                text("DELETE FROM orderbook_snapshots WHERE timestamp < :cutoff"),
                {"cutoff": cutoff},
            )
            # Delete old trades
            await session.execute(
                text("DELETE FROM trades WHERE timestamp < :cutoff"),
                {"cutoff": cutoff},
            )
            # Delete old dismissed alerts
            await session.execute(
                text("DELETE FROM alerts WHERE dismissed_at < :cutoff"),
                {"cutoff": cutoff},
            )
            await session.commit()

        await update_job_records("cleanup_old_data", run_id, expired_count)
        logger.info(
            f"Cleanup complete: {expired_count} alerts expired, "
            f"data older than {cutoff} removed"
        )


async def start_scheduler():
    """Initialize and start the scheduler."""
    global scheduler

    scheduler = AsyncIOScheduler()

    interval = settings.scheduler_interval_minutes

    # Market sync job - runs every interval
    scheduler.add_job(
        collect_markets_job,
        IntervalTrigger(minutes=interval),
        id="collect_markets",
        name="Sync markets from Gamma API",
        replace_existing=True,
    )

    # Order book collection - runs every interval
    scheduler.add_job(
        collect_orderbooks_job,
        IntervalTrigger(minutes=interval),
        id="collect_orderbooks",
        name="Collect order book snapshots",
        replace_existing=True,
    )

    # Trade collection - runs more frequently
    scheduler.add_job(
        collect_trades_job,
        IntervalTrigger(minutes=settings.trade_collection_interval_minutes),
        id="collect_trades",
        name="Collect recent trades",
        replace_existing=True,
    )

    # Analysis job - runs every hour
    scheduler.add_job(
        run_analysis_job,
        IntervalTrigger(hours=1),
        id="run_analysis",
        name="Run analysis and generate alerts",
        replace_existing=True,
    )

    # Cleanup job - runs daily
    scheduler.add_job(
        cleanup_old_data_job,
        IntervalTrigger(days=1),
        id="cleanup_old_data",
        name="Remove old data",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started with {interval} minute interval")

    # Schedule initial market sync to run shortly after startup (non-blocking)
    # This avoids blocking the healthcheck during startup
    scheduler.add_job(
        collect_markets_job,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=5)),
        id="initial_market_sync",
        name="Initial market sync",
        replace_existing=True,
    )

    # Schedule initial orderbook and trade collection after market sync completes
    # Market sync takes ~30s, so schedule these at 45s and 60s after startup
    scheduler.add_job(
        collect_orderbooks_job,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=45)),
        id="initial_orderbook_sync",
        name="Initial orderbook collection",
        replace_existing=True,
    )
    scheduler.add_job(
        collect_trades_job,
        DateTrigger(run_date=datetime.now() + timedelta(seconds=60)),
        id="initial_trade_sync",
        name="Initial trade collection",
        replace_existing=True,
    )


async def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
