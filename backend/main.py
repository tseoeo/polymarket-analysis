"""FastAPI application entry point."""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database import init_db, close_db


class JSONFormatter(logging.Formatter):
    """JSON log formatter for Railway compatibility."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


# Configure logging - use JSON in production (Railway), plain text locally
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
handler = logging.StreamHandler()

if os.environ.get("RAILWAY_ENVIRONMENT"):
    # JSON format for Railway
    handler.setFormatter(JSONFormatter())
else:
    # Plain text for local development
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

logging.basicConfig(level=log_level, handlers=[handler])
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Polymarket Analyzer...")

    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Import and start scheduler after DB is ready (if enabled)
    # Use ENABLE_SCHEDULER=false to disable in multi-process deployments
    if settings.enable_scheduler:
        try:
            from jobs.scheduler import start_scheduler
            await start_scheduler()
            logger.info("Scheduler started")
        except Exception as e:
            logger.warning(f"Scheduler not started: {e}")
    else:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER=false")

    logger.info("Startup complete")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if settings.enable_scheduler:
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
    """Health check endpoint for Railway with data freshness verification."""
    from database import async_session_maker
    from sqlalchemy import select, func

    result = {"status": "healthy", "service": "polymarket-analyzer"}

    try:
        async with async_session_maker() as session:
            from models.trade import Trade
            from models.orderbook import OrderBookSnapshot

            now = datetime.utcnow()

            # Check latest trade timestamp
            trade_result = await session.execute(
                select(func.max(Trade.timestamp))
            )
            latest_trade = trade_result.scalar()

            # Check latest orderbook timestamp
            ob_result = await session.execute(
                select(func.max(OrderBookSnapshot.timestamp))
            )
            latest_ob = ob_result.scalar()

            trade_age = (now - latest_trade).total_seconds() / 60 if latest_trade else None
            ob_age = (now - latest_ob).total_seconds() / 60 if latest_ob else None

            result["trade_data_age_minutes"] = round(trade_age, 1) if trade_age else None
            result["orderbook_data_age_minutes"] = round(ob_age, 1) if ob_age else None

            if (trade_age and trade_age > 60) or (ob_age and ob_age > 60):
                result["status"] = "unhealthy"
            elif (trade_age and trade_age > 30) or (ob_age and ob_age > 30):
                result["status"] = "degraded"
    except Exception:
        # If DB query fails, still return basic health (server is running)
        result["status"] = "degraded"
        result["note"] = "Could not check data freshness"

    return result


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


# Include API routers
from api import alerts, markets, system, arbitrage, orderbook, volume, mm, briefing, watchlist

app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(markets.router, prefix="/api/markets", tags=["Markets"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(arbitrage.router, prefix="/api/arbitrage", tags=["Arbitrage"])
app.include_router(orderbook.router, prefix="/api/orderbook", tags=["Orderbook"])
app.include_router(volume.router, prefix="/api/volume", tags=["Volume"])
app.include_router(mm.router, prefix="/api/mm", tags=["Market Maker"])
app.include_router(briefing.router, prefix="/api/briefing", tags=["Briefing"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["Watchlist"])


# Serve React frontend (static files) - only if frontend is built
static_path = Path(__file__).parent / "static"
assets_path = static_path / "assets"
index_path = static_path / "index.html"

if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React frontend for all non-API routes."""
        # Return 404 for unknown API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        # Serve index.html for all frontend routes (React handles routing)
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Frontend not built yet"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
