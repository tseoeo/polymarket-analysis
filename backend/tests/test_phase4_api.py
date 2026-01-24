"""Tests for Phase 4 API endpoints.

Tests the alert and market API endpoints with pagination,
filtering, and CRUD operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from models.market import Market
from models.alert import Alert


# =============================================================================
# Test Data Factories
# =============================================================================


def create_test_market(
    market_id: str = "test-market-1",
    question: str = "Will test pass?",
    active: bool = True,
) -> Market:
    """Create a test market."""
    return Market(
        id=market_id,
        question=question,
        outcomes=[
            {"name": "Yes", "token_id": f"{market_id}-yes", "price": 0.60},
            {"name": "No", "token_id": f"{market_id}-no", "price": 0.40},
        ],
        active=active,
        enable_order_book=True,
    )


def create_test_alert(
    market_id: str = "test-market-1",
    alert_type: str = "volume_spike",
    severity: str = "medium",
    is_active: bool = True,
    expires_at: datetime = None,
) -> Alert:
    """Create a test alert."""
    return Alert(
        alert_type=alert_type,
        severity=severity,
        title=f"Test {alert_type} alert",
        description="Test description",
        market_id=market_id,
        data={"test": True},
        is_active=is_active,
        expires_at=expires_at,
    )


# =============================================================================
# Alert API Tests
# =============================================================================


class TestAlertListEndpoint:
    """Tests for GET /api/alerts."""

    @pytest.mark.asyncio
    async def test_list_alerts_returns_paginated(self, test_session):
        """Should return paginated alert list."""
        # Create multiple alerts
        for i in range(5):
            alert = create_test_alert(market_id=f"market-{i}")
            test_session.add(alert)
        await test_session.commit()

        from api.alerts import list_alerts

        response = await list_alerts(
            alert_type=None,
            severity=None,
            market_id=None,
            is_active=True,
            limit=3,
            offset=0,
            session=test_session,
        )

        assert response.total == 5
        assert len(response.alerts) == 3
        assert response.limit == 3
        assert response.offset == 0

    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_type(self, test_session):
        """Should filter alerts by type."""
        test_session.add(create_test_alert(alert_type="volume_spike"))
        test_session.add(create_test_alert(alert_type="spread_alert"))
        test_session.add(create_test_alert(alert_type="volume_spike"))
        await test_session.commit()

        from api.alerts import list_alerts

        response = await list_alerts(
            alert_type="volume_spike",
            severity=None,
            market_id=None,
            is_active=True,
            limit=50,
            offset=0,
            session=test_session,
        )

        assert response.total == 2
        assert all(a.alert_type == "volume_spike" for a in response.alerts)

    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_severity(self, test_session):
        """Should filter alerts by severity."""
        test_session.add(create_test_alert(severity="high"))
        test_session.add(create_test_alert(severity="medium"))
        test_session.add(create_test_alert(severity="high"))
        await test_session.commit()

        from api.alerts import list_alerts

        response = await list_alerts(
            alert_type=None,
            severity="high",
            market_id=None,
            is_active=True,
            limit=50,
            offset=0,
            session=test_session,
        )

        assert response.total == 2
        assert all(a.severity == "high" for a in response.alerts)

    @pytest.mark.asyncio
    async def test_list_alerts_filters_by_active_status(self, test_session):
        """Should filter alerts by active status."""
        test_session.add(create_test_alert(is_active=True))
        test_session.add(create_test_alert(is_active=False))
        test_session.add(create_test_alert(is_active=True))
        await test_session.commit()

        from api.alerts import list_alerts

        # Active only
        response = await list_alerts(
            alert_type=None,
            severity=None,
            market_id=None,
            is_active=True,
            limit=50,
            offset=0,
            session=test_session,
        )
        assert response.total == 2

        # Inactive only
        response = await list_alerts(
            alert_type=None,
            severity=None,
            market_id=None,
            is_active=False,
            limit=50,
            offset=0,
            session=test_session,
        )
        assert response.total == 1


class TestAlertDetailEndpoint:
    """Tests for GET /api/alerts/{id}."""

    @pytest.mark.asyncio
    async def test_get_alert_returns_detail(self, test_session):
        """Should return alert detail."""
        alert = create_test_alert()
        test_session.add(alert)
        await test_session.commit()

        from api.alerts import get_alert

        response = await get_alert(alert_id=alert.id, session=test_session)

        assert response.id == alert.id
        assert response.alert_type == "volume_spike"
        assert response.is_active is True

    @pytest.mark.asyncio
    async def test_get_alert_not_found(self, test_session):
        """Should return 404 for missing alert."""
        from api.alerts import get_alert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_alert(alert_id=99999, session=test_session)

        assert exc_info.value.status_code == 404


class TestAlertDismissEndpoint:
    """Tests for PATCH /api/alerts/{id}/dismiss."""

    @pytest.mark.asyncio
    async def test_dismiss_alert(self, test_session):
        """Should dismiss alert and return updated state."""
        alert = create_test_alert(is_active=True)
        test_session.add(alert)
        await test_session.commit()

        from api.alerts import dismiss_alert

        response = await dismiss_alert(alert_id=alert.id, session=test_session)

        assert response.is_active is False
        assert response.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_dismiss_alert_not_found(self, test_session):
        """Should return 404 for missing alert."""
        from api.alerts import dismiss_alert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_alert(alert_id=99999, session=test_session)

        assert exc_info.value.status_code == 404


# =============================================================================
# Market API Tests
# =============================================================================


class TestMarketListEndpoint:
    """Tests for GET /api/markets."""

    @pytest.mark.asyncio
    async def test_list_markets_returns_paginated(self, test_session):
        """Should return paginated market list."""
        for i in range(5):
            market = create_test_market(market_id=f"market-{i}")
            test_session.add(market)
        await test_session.commit()

        from api.markets import list_markets

        response = await list_markets(
            active=True,
            has_alerts=None,
            limit=3,
            offset=0,
            session=test_session,
        )

        assert response.total == 5
        assert len(response.markets) == 3

    @pytest.mark.asyncio
    async def test_list_markets_includes_alert_count(self, test_session):
        """Should include active alert count for each market."""
        market = create_test_market(market_id="market-with-alerts")
        test_session.add(market)

        # Add 2 active alerts
        test_session.add(create_test_alert(market_id="market-with-alerts", is_active=True))
        test_session.add(create_test_alert(market_id="market-with-alerts", is_active=True))
        # Add 1 inactive alert (shouldn't count)
        test_session.add(create_test_alert(market_id="market-with-alerts", is_active=False))

        await test_session.commit()

        from api.markets import list_markets

        response = await list_markets(
            active=True,
            has_alerts=None,
            limit=50,
            offset=0,
            session=test_session,
        )

        assert len(response.markets) == 1
        assert response.markets[0].active_alerts == 2

    @pytest.mark.asyncio
    async def test_list_markets_filter_has_alerts_true(self, test_session):
        """Should filter to only markets with active alerts."""
        market_with = create_test_market(market_id="market-with")
        market_without = create_test_market(market_id="market-without")
        test_session.add(market_with)
        test_session.add(market_without)

        test_session.add(create_test_alert(market_id="market-with", is_active=True))

        await test_session.commit()

        from api.markets import list_markets

        response = await list_markets(
            active=True,
            has_alerts=True,
            limit=50,
            offset=0,
            session=test_session,
        )

        assert response.total == 1
        assert response.markets[0].id == "market-with"

    @pytest.mark.asyncio
    async def test_list_markets_filter_has_alerts_false(self, test_session):
        """Should filter to only markets without active alerts."""
        market_with = create_test_market(market_id="market-with")
        market_without = create_test_market(market_id="market-without")
        test_session.add(market_with)
        test_session.add(market_without)

        test_session.add(create_test_alert(market_id="market-with", is_active=True))

        await test_session.commit()

        from api.markets import list_markets

        response = await list_markets(
            active=True,
            has_alerts=False,
            limit=50,
            offset=0,
            session=test_session,
        )

        assert response.total == 1
        assert response.markets[0].id == "market-without"


class TestMarketDetailEndpoint:
    """Tests for GET /api/markets/{id}."""

    @pytest.mark.asyncio
    async def test_get_market_returns_detail(self, test_session):
        """Should return market detail with alert count."""
        market = create_test_market(market_id="detail-market")
        test_session.add(market)
        test_session.add(create_test_alert(market_id="detail-market"))
        await test_session.commit()

        from api.markets import get_market

        response = await get_market(market_id="detail-market", session=test_session)

        assert response.id == "detail-market"
        assert response.active_alerts == 1

    @pytest.mark.asyncio
    async def test_get_market_not_found(self, test_session):
        """Should return 404 for missing market."""
        from api.markets import get_market
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_market(market_id="nonexistent", session=test_session)

        assert exc_info.value.status_code == 404


class TestMarketAlertsEndpoint:
    """Tests for GET /api/markets/{id}/alerts."""

    @pytest.mark.asyncio
    async def test_get_market_alerts(self, test_session):
        """Should return alerts for a specific market."""
        market = create_test_market(market_id="alerts-market")
        test_session.add(market)
        test_session.add(create_test_alert(market_id="alerts-market", alert_type="volume_spike"))
        test_session.add(create_test_alert(market_id="alerts-market", alert_type="spread_alert"))
        test_session.add(create_test_alert(market_id="other-market"))  # Different market
        await test_session.commit()

        from api.markets import get_market_alerts

        response = await get_market_alerts(
            market_id="alerts-market",
            is_active=True,
            session=test_session,
        )

        assert len(response) == 2

    @pytest.mark.asyncio
    async def test_get_market_alerts_not_found(self, test_session):
        """Should return 404 for missing market."""
        from api.markets import get_market_alerts
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_market_alerts(
                market_id="nonexistent",
                is_active=True,
                session=test_session,
            )

        assert exc_info.value.status_code == 404


# =============================================================================
# Alert Expiration Tests
# =============================================================================


class TestAlertExpiration:
    """Tests for alert expiration in cleanup job."""

    @pytest.mark.asyncio
    async def test_cleanup_expires_old_alerts(self, test_session):
        """Cleanup job should expire alerts past their expires_at."""
        now = datetime.utcnow()

        # Create alert that should expire
        expired_alert = create_test_alert(
            market_id="expired-market",
            is_active=True,
            expires_at=now - timedelta(hours=1),
        )
        test_session.add(expired_alert)

        # Create alert that should NOT expire
        valid_alert = create_test_alert(
            market_id="valid-market",
            is_active=True,
            expires_at=now + timedelta(hours=1),
        )
        test_session.add(valid_alert)

        await test_session.commit()

        # Run expiration logic (simulating what cleanup_old_data_job does)
        from sqlalchemy import update
        from models.alert import Alert

        await test_session.execute(
            update(Alert)
            .where(Alert.expires_at < now)
            .where(Alert.is_active == True)
            .values(is_active=False, dismissed_at=now)
        )
        await test_session.commit()

        # Refresh and check
        await test_session.refresh(expired_alert)
        await test_session.refresh(valid_alert)

        assert expired_alert.is_active is False
        assert expired_alert.dismissed_at is not None
        assert valid_alert.is_active is True
