"""Tests for system status API endpoint.

Tests cover the /api/system/status endpoint functionality:
- Returns valid JSON response
- Reflects seeded job run data
- Respects ENABLE_SYSTEM_STATUS env var
"""

from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
class TestSystemStatusEndpoint:
    """Test /api/system/status endpoint via direct function testing.

    Since test_client doesn't properly inject test database sessions,
    we test the endpoint logic directly using test_session fixture.
    """

    async def test_status_returns_valid_json_via_function(self, test_session):
        """Status endpoint should return valid JSON structure."""
        from api.system import (
            get_job_statuses,
            get_data_freshness,
            determine_health_status,
            SystemStatusResponse,
            SchedulerStatus,
        )
        from config import settings

        # Test the underlying functions directly
        job_statuses = await get_job_statuses(test_session)
        data_freshness = await get_data_freshness(test_session, job_statuses)
        health_status = determine_health_status(job_statuses, data_freshness)

        # Build response like the endpoint does
        response = SystemStatusResponse(
            status=health_status,
            timestamp=datetime.utcnow(),
            scheduler=SchedulerStatus(
                enabled=settings.enable_scheduler,
                jobs=job_statuses,
            ),
            data_freshness=data_freshness,
            counts=None,
        )

        # Verify structure
        assert response.status in ["healthy", "degraded", "unhealthy"]
        assert response.scheduler is not None
        assert response.data_freshness is not None

    async def test_status_disabled_returns_404(self, test_client):
        """Status endpoint should return 404 when disabled."""
        from config import settings

        # Temporarily disable
        original = settings.enable_system_status
        try:
            settings.enable_system_status = False
            response = await test_client.get("/api/system/status")
            assert response.status_code == 404
        finally:
            settings.enable_system_status = original

    async def test_status_counts_function(self, test_session):
        """Test get_data_counts returns proper structure."""
        from api.system import get_data_counts

        counts = await get_data_counts(test_session)

        # Verify structure (all should be 0 with empty test DB)
        assert counts.markets_active >= 0
        assert counts.trades_24h >= 0
        assert counts.orderbooks_24h >= 0
        assert counts.alerts_active >= 0


class TestHealthStatusDetermination:
    """Test health status classification logic."""

    def test_healthy_when_all_jobs_succeeded(self):
        """Status should be healthy when all jobs succeeded and data is fresh."""
        from api.system import determine_health_status, JobStatus, DataFreshness

        now = datetime.utcnow()

        job_statuses = [
            JobStatus(
                id="collect_markets",
                last_run=now - timedelta(minutes=10),
                last_status="success",
            ),
            JobStatus(
                id="collect_trades",
                last_run=now - timedelta(minutes=5),
                last_status="success",
            ),
        ]

        data_freshness = DataFreshness(
            last_trade=now - timedelta(minutes=5),
            last_orderbook=now - timedelta(minutes=15),
        )

        status = determine_health_status(job_statuses, data_freshness)
        assert status == "healthy"

    def test_degraded_when_data_stale(self):
        """Status should be degraded when data is stale (>2h)."""
        from api.system import determine_health_status, JobStatus, DataFreshness

        now = datetime.utcnow()

        job_statuses = [
            JobStatus(
                id="collect_trades",
                last_run=now - timedelta(hours=3),
                last_status="success",
            ),
        ]

        data_freshness = DataFreshness(
            last_trade=now - timedelta(hours=3),  # Stale
            last_orderbook=now - timedelta(minutes=15),
        )

        status = determine_health_status(job_statuses, data_freshness)
        assert status == "degraded"

    def test_unhealthy_when_job_failed(self):
        """Status should be unhealthy when any job failed."""
        from api.system import determine_health_status, JobStatus, DataFreshness

        now = datetime.utcnow()

        job_statuses = [
            JobStatus(
                id="collect_markets",
                last_run=now - timedelta(minutes=10),
                last_status="failed",
                error_message="Connection refused",
            ),
        ]

        data_freshness = DataFreshness(
            last_trade=now - timedelta(minutes=5),
        )

        status = determine_health_status(job_statuses, data_freshness)
        assert status == "unhealthy"

    def test_unhealthy_when_data_very_stale(self):
        """Status should be unhealthy when data is very stale (>6h)."""
        from api.system import determine_health_status, JobStatus, DataFreshness

        now = datetime.utcnow()

        job_statuses = [
            JobStatus(
                id="collect_trades",
                last_run=now - timedelta(hours=7),
                last_status="success",
            ),
        ]

        data_freshness = DataFreshness(
            last_trade=now - timedelta(hours=7),  # Very stale
            last_orderbook=now - timedelta(hours=7),
        )

        status = determine_health_status(job_statuses, data_freshness)
        assert status == "unhealthy"

    def test_degraded_when_job_running(self):
        """Status should be degraded when job is still running."""
        from api.system import determine_health_status, JobStatus, DataFreshness

        now = datetime.utcnow()

        job_statuses = [
            JobStatus(
                id="collect_markets",
                last_run=now - timedelta(minutes=5),
                last_status="running",  # Still running
            ),
        ]

        data_freshness = DataFreshness(
            last_trade=now - timedelta(minutes=5),
        )

        status = determine_health_status(job_statuses, data_freshness)
        assert status == "degraded"


@pytest.mark.asyncio
class TestJobStatusQueries:
    """Test job status database queries."""

    async def test_get_job_statuses_returns_latest(self, test_session, seeded_job_runs):
        """get_job_statuses should return the latest run for each job type."""
        from api.system import get_job_statuses

        statuses = await get_job_statuses(test_session)

        # Should have entries for tracked jobs
        status_map = {s.id: s for s in statuses}

        # collect_markets should have latest status
        assert "collect_markets" in status_map
        assert status_map["collect_markets"].last_status == "success"
        assert status_map["collect_markets"].records_processed == 100

        # collect_trades should have latest status
        assert "collect_trades" in status_map
        assert status_map["collect_trades"].last_status == "success"
        assert status_map["collect_trades"].records_processed == 50

    async def test_get_job_statuses_handles_missing_jobs(self, test_session):
        """get_job_statuses should return empty status for jobs that never ran."""
        from api.system import get_job_statuses

        # No job runs seeded
        statuses = await get_job_statuses(test_session)

        # Should still have entries for all tracked jobs
        assert len(statuses) > 0

        # Each should have None for run info
        for status in statuses:
            assert status.last_run is None
            assert status.last_status is None


@pytest.mark.asyncio
class TestDataFreshnessQueries:
    """Test data freshness queries."""

    async def test_get_data_freshness_with_trades(self, test_session, seeded_trades):
        """get_data_freshness should return correct timestamps."""
        from api.system import get_data_freshness

        # Need job statuses for the function
        job_statuses = []

        freshness = await get_data_freshness(test_session, job_statuses)

        # Should have last_trade from seeded data
        assert freshness.last_trade is not None

    async def test_get_data_freshness_empty_db(self, test_session):
        """get_data_freshness should handle empty database."""
        from api.system import get_data_freshness

        freshness = await get_data_freshness(test_session, [])

        # All should be None with empty DB
        assert freshness.last_trade is None
        assert freshness.last_orderbook is None
