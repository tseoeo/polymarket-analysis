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


# Include API routers
from api import alerts, markets

app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(markets.router, prefix="/api/markets", tags=["Markets"])


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
