"""Tests for health and info API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from pathlib import Path


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(test_client):
    """Health endpoint should return 200 with status and service fields.

    Without a real DB, the endpoint falls back to 'degraded' status
    (data freshness can't be verified). This is by design — the server
    is running but can't confirm data is fresh.
    """
    response = await test_client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert data["service"] == "polymarket-analyzer"


@pytest.mark.asyncio
async def test_info_endpoint_returns_features(test_client):
    """Info endpoint should return API info with features list."""
    response = await test_client.get("/api/info")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Polymarket Analyzer API"
    assert data["version"] == "1.0.0"
    assert "features" in data
    assert len(data["features"]) > 0
    assert "Cross-market arbitrage detection" in data["features"]


@pytest.mark.asyncio
async def test_unknown_api_route_returns_404_default():
    """Unknown API routes should return 404 from FastAPI's default handler.

    When assets folder doesn't exist, the catch-all route isn't registered,
    so FastAPI returns its default 404 for unknown routes.
    """
    from httpx import AsyncClient, ASGITransport

    with patch("main.init_db", new_callable=AsyncMock), \
         patch("main.close_db", new_callable=AsyncMock):

        from main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/nonexistent-route")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unknown_api_route_returns_404_with_catchall():
    """Unknown API routes should return 404 when catch-all route IS registered.

    This specifically tests the fix in main.py where api/ routes raise
    HTTPException(404) instead of returning {"error": "Not found"} with 200.

    We create a temporary static/assets directory so the catch-all route
    gets registered, then verify API routes return 404 (not 200).
    """
    import sys
    import os
    import tempfile
    import shutil
    from httpx import AsyncClient, ASGITransport

    # Remove main from cache so it reimports fresh
    modules_to_remove = [k for k in sys.modules if k == "main" or k.startswith("main.")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Create temporary static/assets directory structure
    backend_dir = Path(__file__).parent.parent
    static_dir = backend_dir / "static"
    assets_dir = static_dir / "assets"

    created_static = False
    created_assets = False

    try:
        if not static_dir.exists():
            static_dir.mkdir()
            created_static = True
        if not assets_dir.exists():
            assets_dir.mkdir()
            created_assets = True

        # Now import main - the catch-all route will be registered
        with patch("main.init_db", new_callable=AsyncMock), \
             patch("main.close_db", new_callable=AsyncMock):

            import main

            transport = ASGITransport(app=main.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/nonexistent-route")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"].lower() == "not found"

    finally:
        # Clean up temporary directories
        if created_assets and assets_dir.exists():
            assets_dir.rmdir()
        if created_static and static_dir.exists():
            static_dir.rmdir()

        # Clean up module cache
        modules_to_remove = [k for k in sys.modules if k == "main" or k.startswith("main.")]
        for mod in modules_to_remove:
            del sys.modules[mod]
