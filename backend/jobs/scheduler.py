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


async def collect_trades_job():
    """Job: Fetch recent trades for all active markets."""
    logger.info("Running trade collection job...")
    client = None
    try:
        from services.polymarket_client import PolymarketClient
        from database import async_session_maker

        client = PolymarketClient()
        async with async_session_maker() as session:
            new_count, dup_count = await client.collect_trades(session)
            await session.commit()
        logger.info(f"Trade collection complete: {new_count} new, {dup_count} duplicates")
    except Exception as e:
        logger.error(f"Trade collection failed: {e}")
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
    logger.info("Running analysis job...")
    try:
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

        # Log summary by alert type
        alert_summary = {}
        for alert in all_alerts:
            alert_summary[alert.alert_type] = alert_summary.get(alert.alert_type, 0) + 1

        logger.info(
            f"Analysis complete: {len(all_alerts)} alerts generated "
            f"{alert_summary if alert_summary else ''}"
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")


async def cleanup_old_data_job():
    """Job: Expire stale alerts and remove old data."""
    logger.info("Running data cleanup job...")
    try:
        from database import async_session_maker
        from sqlalchemy import text, update
        from datetime import datetime, timedelta
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

        logger.info(
            f"Cleanup complete: {expired_count} alerts expired, "
            f"data older than {cutoff} removed"
        )
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


async def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
