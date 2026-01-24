"""APScheduler setup for background data collection and analysis."""

import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def collect_markets_job():
    """Job: Fetch and update market data from Gamma API."""
    logger.info("Running market collection job...")
    client = None
    try:
        from services.polymarket_client import PolymarketClient
        from database import async_session_maker

        client = PolymarketClient()
        async with async_session_maker() as session:
            await client.sync_markets(session)
            await session.commit()
        logger.info("Market collection complete")
    except Exception as e:
        logger.error(f"Market collection failed: {e}")
    finally:
        if client:
            await client.close()


async def collect_orderbooks_job():
    """Job: Fetch order book snapshots for all active markets."""
    logger.info("Running order book collection job...")
    client = None
    try:
        from services.polymarket_client import PolymarketClient
        from database import async_session_maker

        client = PolymarketClient()
        async with async_session_maker() as session:
            await client.collect_orderbooks(session)
            await session.commit()
        logger.info("Order book collection complete")
    except Exception as e:
        logger.error(f"Order book collection failed: {e}")
    finally:
        if client:
            await client.close()


async def run_analysis_job():
    """Job: Run all analysis modules and generate alerts."""
    logger.info("Running analysis job...")
    try:
        # Analysis modules will be added in Phase 3
        # from services.arbitrage_detector import ArbitrageDetector
        # from services.volume_analyzer import VolumeAnalyzer
        # ...
        logger.info("Analysis complete (no analyzers configured yet)")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")


async def cleanup_old_data_job():
    """Job: Remove data older than retention period."""
    logger.info("Running data cleanup job...")
    try:
        from database import async_session_maker
        from sqlalchemy import text
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=settings.data_retention_days)

        async with async_session_maker() as session:
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
        logger.info(f"Cleaned up data older than {cutoff}")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


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


async def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
