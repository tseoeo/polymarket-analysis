"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database import init_db, close_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Polymarket Analyzer...")
    logger.info(f"Database URL: {settings.database_url[:20]}...")

    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Import and start scheduler after DB is ready
    try:
        from jobs.scheduler import start_scheduler, stop_scheduler
        await start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    logger.info("Startup complete")
    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        from jobs.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Polymarket Analyzer",
    description="Analysis tool for Polymarket trading opportunities",
    version="1.0.0",
    lifespan=lifespan,
)


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "ok", "service": "polymarket-analyzer"}


# API info endpoint
@app.get("/api/info")
async def api_info():
    """API information endpoint."""
    return {
        "name": "Polymarket Analyzer API",
        "version": "1.0.0",
        "features": [
            "Cross-market arbitrage detection",
            "Order book analysis",
            "Volume anomaly detection",
            "Market maker pattern analysis",
        ],
    }


# Include API routers (will be added in Phase 4)
# from api import arbitrage, orderbook, volume, marketmaker, alerts
# app.include_router(arbitrage.router, prefix="/api/arbitrage", tags=["Arbitrage"])
# app.include_router(orderbook.router, prefix="/api/orderbook", tags=["Order Book"])
# app.include_router(volume.router, prefix="/api/volume", tags=["Volume"])
# app.include_router(marketmaker.router, prefix="/api/mm", tags=["Market Maker"])
# app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])


# Serve React frontend (static files)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/assets", StaticFiles(directory=static_path / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React frontend for all non-API routes."""
        # Don't serve frontend for API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}
        # Serve index.html for all frontend routes (React handles routing)
        index_path = static_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Frontend not built yet"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
