"""Volume statistics model for aggregated trading data."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class VolumeStats(Base):
    """Aggregated volume statistics for a token over a time period.

    Used for:
    - Historical baseline calculations (7-day average)
    - Volume trend analysis
    - Volume spike detection with proper baselines
    - OHLC price data per period
    """

    __tablename__ = "volume_stats"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Market and token identification
    market_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("markets.id"), nullable=False, index=True
    )
    token_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Time period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'hour', 'day', 'week'

    # Volume metrics
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=0)
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_trade_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)

    # OHLC price data
    price_open: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    price_close: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    price_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    price_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    # Additional metrics
    buy_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    sell_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Ensure unique stats per token per period
        Index(
            "ix_volume_stats_unique_period",
            "token_id",
            "period_type",
            "period_start",
            unique=True,
        ),
        # For efficient time-range queries
        Index("ix_volume_stats_period_range", "token_id", "period_type", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return (
            f"<VolumeStats {self.token_id} {self.period_type}: "
            f"${self.volume} ({self.trade_count} trades)>"
        )

    @property
    def buy_sell_ratio(self) -> Optional[float]:
        """Calculate buy/sell volume ratio."""
        if not self.buy_volume or not self.sell_volume or self.sell_volume == 0:
            return None
        return float(self.buy_volume / self.sell_volume)

    @property
    def price_change(self) -> Optional[float]:
        """Calculate price change over period."""
        if not self.price_open or not self.price_close or self.price_open == 0:
            return None
        return float((self.price_close - self.price_open) / self.price_open)

    @property
    def price_range(self) -> Optional[float]:
        """Calculate price range (high - low) over period."""
        if not self.price_high or not self.price_low:
            return None
        return float(self.price_high - self.price_low)

    @classmethod
    def from_trades(
        cls,
        market_id: str,
        token_id: str,
        trades: list,
        period_start: datetime,
        period_end: datetime,
        period_type: str,
    ) -> "VolumeStats":
        """Create VolumeStats from a list of Trade objects.

        Args:
            market_id: Market identifier
            token_id: Token identifier
            trades: List of Trade objects (must have price, size, side, timestamp)
            period_start: Start of aggregation period
            period_end: End of aggregation period
            period_type: 'hour', 'day', or 'week'
        """
        if not trades:
            return cls(
                market_id=market_id,
                token_id=token_id,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                volume=Decimal(0),
                trade_count=0,
            )

        # Sort by timestamp for OHLC
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)

        # Convert to float to handle Decimal/Numeric values from database
        total_volume = sum(float(t.size) for t in trades)
        buy_volume = sum(float(t.size) for t in trades if t.side == "buy")
        sell_volume = sum(float(t.size) for t in trades if t.side == "sell")
        trade_count = len(trades)

        prices = [float(t.price) for t in sorted_trades]

        return cls(
            market_id=market_id,
            token_id=token_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            volume=Decimal(str(total_volume)),
            trade_count=trade_count,
            avg_trade_size=Decimal(str(total_volume / trade_count)) if trade_count > 0 else None,
            price_open=Decimal(str(prices[0])) if prices else None,
            price_close=Decimal(str(prices[-1])) if prices else None,
            price_high=Decimal(str(max(prices))) if prices else None,
            price_low=Decimal(str(min(prices))) if prices else None,
            buy_volume=Decimal(str(buy_volume)) if buy_volume else None,
            sell_volume=Decimal(str(sell_volume)) if sell_volume else None,
        )
