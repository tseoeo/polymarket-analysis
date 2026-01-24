"""Tests for scheduler job registration."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_scheduler_registers_jobs():
    """Scheduler should register all 4 jobs when started."""
    from jobs.scheduler import start_scheduler, stop_scheduler, scheduler

    with patch("jobs.scheduler.AsyncIOScheduler") as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        await start_scheduler()

        # Should have added 5 jobs total:
        # 1. collect_markets (interval)
        # 2. collect_orderbooks (interval)
        # 3. run_analysis (interval)
        # 4. cleanup_old_data (interval)
        # 5. initial_market_sync (one-time)
        assert mock_scheduler.add_job.call_count == 5

        # Verify job IDs
        job_ids = [call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list]
        assert "collect_markets" in job_ids
        assert "collect_orderbooks" in job_ids
        assert "run_analysis" in job_ids
        assert "cleanup_old_data" in job_ids
        assert "initial_market_sync" in job_ids

        # Scheduler should have been started
        mock_scheduler.start.assert_called_once()

        await stop_scheduler()


@pytest.mark.asyncio
async def test_scheduler_disabled_when_flag_false():
    """Scheduler should not start when enable_scheduler is False."""
    from main import lifespan, app
    from config import settings

    original_value = settings.enable_scheduler

    try:
        # Disable scheduler
        settings.enable_scheduler = False

        # Mock both database and scheduler
        with patch("main.init_db", return_value=None) as mock_init_db, \
             patch("main.close_db", return_value=None), \
             patch("jobs.scheduler.start_scheduler") as mock_start:
            async with lifespan(app):
                # Scheduler start should not be called when disabled
                mock_start.assert_not_called()
    finally:
        settings.enable_scheduler = original_value


@pytest.mark.asyncio
async def test_scheduler_enabled_when_flag_true():
    """Scheduler should start when enable_scheduler is True."""
    from main import lifespan, app
    from config import settings

    original_value = settings.enable_scheduler

    try:
        settings.enable_scheduler = True

        # Mock both database and scheduler
        with patch("main.init_db", return_value=None), \
             patch("main.close_db", return_value=None), \
             patch("jobs.scheduler.start_scheduler", return_value=None) as mock_start, \
             patch("jobs.scheduler.stop_scheduler", return_value=None):
            async with lifespan(app):
                # Scheduler start should be called when enabled
                mock_start.assert_called_once()
    finally:
        settings.enable_scheduler = original_value


@pytest.mark.asyncio
async def test_scheduler_job_functions_exist():
    """All scheduler job functions should be importable and callable."""
    from jobs.scheduler import (
        collect_markets_job,
        collect_orderbooks_job,
        run_analysis_job,
        cleanup_old_data_job,
    )

    # All should be coroutine functions
    import asyncio

    assert asyncio.iscoroutinefunction(collect_markets_job)
    assert asyncio.iscoroutinefunction(collect_orderbooks_job)
    assert asyncio.iscoroutinefunction(run_analysis_job)
    assert asyncio.iscoroutinefunction(cleanup_old_data_job)


@pytest.mark.asyncio
async def test_stop_scheduler_when_not_started():
    """stop_scheduler should handle case when scheduler is None."""
    from jobs import scheduler as scheduler_module

    # Ensure scheduler is None
    scheduler_module.scheduler = None

    # Should not raise
    await scheduler_module.stop_scheduler()

    # Still None
    assert scheduler_module.scheduler is None
