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

    # Polymarket CLOB API credentials (for authenticated endpoints like /trades)
    # Get these from your Polymarket account settings
    polymarket_api_key: Optional[str] = None
    polymarket_api_secret: Optional[str] = None
    polymarket_api_passphrase: Optional[str] = None
    polymarket_wallet_address: Optional[str] = None  # Your wallet address (0x...)

    # Scheduler settings
    enable_scheduler: bool = False  # Set ENABLE_SCHEDULER=true on ONE worker only
    scheduler_interval_minutes: int = 15
    orderbook_concurrency: int = 3  # Max concurrent orderbook/trade fetches (low to avoid 429s)

    # Trade collection settings
    trade_collection_interval_minutes: int = 5  # More frequent than orderbooks
    trade_lookback_minutes: int = 30  # How far back to look for trades

    # API retry settings
    api_max_retries: int = 3
    api_retry_base_delay: float = 1.0  # Base delay in seconds

    # Data retention
    data_retention_days: int = 30

    # Logging
    log_level: str = "INFO"

    # Analysis thresholds
    arbitrage_min_profit: float = 0.02  # 2% minimum profit for alerts
    volume_spike_threshold: float = 3.0  # 3x normal volume
    spread_alert_threshold: float = 0.05  # 5% spread

    # Cross-market arbitrage settings
    arb_min_liquidity: float = 1000.0  # Minimum liquidity for arbitrage opportunities

    # Volume analysis settings
    volume_baseline_days: int = 7  # Days of history for baseline calculation
    volume_acceleration_threshold: float = 0.5  # 50% increase signals acceleration

    # Orderbook analysis settings
    orderbook_depth_levels: str = "0.01,0.05,0.10"  # Price levels for depth analysis
    orderbook_max_age_minutes: int = 30  # Max age for "current" snapshot

    # System status endpoint access control
    enable_system_status: bool = True  # Set ENABLE_SYSTEM_STATUS=false to disable

    @property
    def orderbook_depth_levels_list(self) -> list:
        """Parse orderbook depth levels from comma-separated string."""
        return [float(x) for x in self.orderbook_depth_levels.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
