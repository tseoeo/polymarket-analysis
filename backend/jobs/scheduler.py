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
    """Job: Run all analysis modules concurrently and generate alerts.

    Runs five analyzer modules in parallel using asyncio.gather:
    1. VolumeAnalyzer - Detects unusual trading volume spikes
    2. SpreadAnalyzer - Detects wide spreads indicating poor liquidity
    3. MarketMakerAnalyzer - Detects MM liquidity withdrawals
    4. ArbitrageDetector - Detects intra-market pricing anomalies
    5. CrossMarketArbitrageDetector - Detects cross-market pricing anomalies

    Arbitrage opportunities can appear and vanish in minutes, so this runs
    every 15 minutes. Each analyzer gets its own DB session to avoid contention.
    """
    async with track_job_run("run_analysis") as run_id:
        from services.volume_analyzer import VolumeAnalyzer
        from services.spread_analyzer import SpreadAnalyzer
        from services.mm_analyzer import MarketMakerAnalyzer
        from services.arbitrage_detector import ArbitrageDetector
        from services.cross_market_arbitrage import CrossMarketArbitrageDetector
        from database import async_session_maker

        all_alerts = []

        async def run_analyzer(AnalyzerClass, method="analyze"):
            async with async_session_maker() as session:
                analyzer = AnalyzerClass()
                alerts = await getattr(analyzer, method)(session)
                await session.commit()
                return alerts

        results = await asyncio.gather(
            run_analyzer(VolumeAnalyzer),
            run_analyzer(SpreadAnalyzer),
            run_analyzer(MarketMakerAnalyzer),
            run_analyzer(ArbitrageDetector),
            run_analyzer(CrossMarketArbitrageDetector),
            return_exceptions=True,
        )

        analyzer_names = ["Volume", "Spread", "MM", "Arbitrage", "Cross-Market Arbitrage"]
        for name, result in zip(analyzer_names, results):
            if isinstance(result, Exception):
                logger.error(f"{name} analysis failed: {result}")
            else:
                all_alerts.extend(result)

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


async def aggregate_volume_job():
    """Job: Aggregate trade data into VolumeStats for analytics."""
    async with track_job_run("aggregate_volume") as run_id:
        from services.volume_analyzer import aggregate_volume_stats
        from database import async_session_maker

        async with async_session_maker() as session:
            # Aggregate hourly stats (runs every hour)
            hourly_count = await aggregate_volume_stats(session, "hour")

            # Also aggregate daily stats once per day (at midnight UTC)
            now = datetime.utcnow()
            if now.hour == 0:
                daily_count = await aggregate_volume_stats(session, "day")
                hourly_count += daily_count

        await update_job_records("aggregate_volume", run_id, hourly_count)


async def cleanup_old_data_job():
    """Job: Expire stale alerts and remove old data."""
    async with track_job_run("cleanup_old_data") as run_id:
        from database import async_session_maker
        from sqlalchemy import text, update
        from models.alert import Alert

        now = datetime.utcnow()
        orderbook_cutoff = now - timedelta(days=settings.orderbook_retention_days)
        trade_cutoff = now - timedelta(days=settings.data_retention_days)
        alert_cutoff = now - timedelta(days=settings.alert_retention_days)

        async with async_session_maker() as session:
            # Expire alerts past their expires_at timestamp
            expire_result = await session.execute(
                update(Alert)
                .where(Alert.expires_at < now)
                .where(Alert.is_active == True)
                .values(is_active=False, dismissed_at=now)
            )
            expired_count = expire_result.rowcount

            # Delete old order book snapshots (per-table retention)
            await session.execute(
                text("DELETE FROM orderbook_snapshots WHERE timestamp < :cutoff"),
                {"cutoff": orderbook_cutoff},
            )
            # Delete old trades
            await session.execute(
                text("DELETE FROM trades WHERE timestamp < :cutoff"),
                {"cutoff": trade_cutoff},
            )
            # Delete old dismissed alerts (shorter retention)
            await session.execute(
                text("DELETE FROM alerts WHERE dismissed_at < :cutoff"),
                {"cutoff": alert_cutoff},
            )

            # Row cap safety nets: delete oldest rows beyond the cap
            for table, cap, ts_col in [
                ("orderbook_snapshots", settings.max_orderbook_rows, "timestamp"),
                ("trades", settings.max_trade_rows, "timestamp"),
            ]:
                count_result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                row_count = count_result.scalar()
                if row_count and row_count > cap:
                    excess = row_count - cap
                    await session.execute(
                        text(
                            f"DELETE FROM {table} WHERE id IN "
                            f"(SELECT id FROM {table} ORDER BY {ts_col} ASC LIMIT :excess)"
                        ),
                        {"excess": excess},
                    )
                    logger.warning(
                        f"Row cap enforced: deleted {excess} oldest rows from {table} "
                        f"(was {row_count}, cap {cap})"
                    )

            await session.commit()

        # Run VACUUM (ANALYZE) outside a transaction to reclaim disk space
        try:
            from database import engine
            from sqlalchemy import text as sa_text

            async with engine.connect() as conn:
                conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn.execute(sa_text("VACUUM (ANALYZE)"))
            logger.info("VACUUM (ANALYZE) completed after cleanup")
        except Exception as e:
            logger.warning(f"VACUUM after cleanup failed (non-fatal): {e}")

        # Log table sizes for monitoring
        try:
            from database import engine
            from sqlalchemy import text as sa_text

            async with engine.connect() as conn:
                result = await conn.execute(sa_text(
                    "SELECT relname, pg_size_pretty(pg_total_relation_size(C.oid)), "
                    "pg_total_relation_size(C.oid) as raw_bytes "
                    "FROM pg_class C JOIN pg_namespace N ON N.oid = C.relnamespace "
                    "WHERE nspname = 'public' AND relkind = 'r' "
                    "ORDER BY pg_total_relation_size(C.oid) DESC"
                ))
                rows = result.fetchall()
                total_bytes = sum(r[2] for r in rows)
                sizes = ", ".join(f"{r[0]}={r[1]}" for r in rows[:5])
                logger.info(
                    f"Disk usage after cleanup: total={total_bytes / (1024*1024):.1f}MB "
                    f"(top tables: {sizes})"
                )
        except Exception as e:
            logger.warning(f"Disk usage logging failed (non-fatal): {e}")

        await update_job_records("cleanup_old_data", run_id, expired_count)
        logger.info(
            f"Cleanup complete: {expired_count} alerts expired, "
            f"orderbook>{settings.orderbook_retention_days}d, "
            f"trades>{settings.data_retention_days}d, "
            f"alerts>{settings.alert_retention_days}d removed"
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

    # Analysis job - runs every 15 minutes
    # Arbitrage opportunities can appear and vanish in minutes,
    # so 15-minute analysis is the minimum useful cadence
    scheduler.add_job(
        run_analysis_job,
        IntervalTrigger(minutes=15),
        id="run_analysis",
        name="Run analysis and generate alerts",
        replace_existing=True,
    )

    # Volume aggregation job - runs every hour
    scheduler.add_job(
        aggregate_volume_job,
        IntervalTrigger(hours=1),
        id="aggregate_volume",
        name="Aggregate volume statistics",
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
