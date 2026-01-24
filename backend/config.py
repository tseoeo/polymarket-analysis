"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://localhost/polymarket"

    # Polymarket APIs
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"

    # Scheduler settings
    enable_scheduler: bool = False  # Set ENABLE_SCHEDULER=true on ONE worker only
    scheduler_interval_minutes: int = 15
    orderbook_concurrency: int = 10  # Max concurrent orderbook fetches

    # Data retention
    data_retention_days: int = 30

    # Logging
    log_level: str = "INFO"

    # Analysis thresholds
    arbitrage_min_profit: float = 0.02  # 2% minimum profit for alerts
    volume_spike_threshold: float = 3.0  # 3x normal volume
    spread_alert_threshold: float = 0.05  # 5% spread

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
