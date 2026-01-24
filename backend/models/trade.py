"""Trade history model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Trade(Base):
    """Individual trade record."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Trade identifier from API (for deduplication)
    trade_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    # Market reference
    token_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    market_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Trade details
    price: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)  # Dollar amount
    side: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 'buy' or 'sell'

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Optional: trader addresses (if available from API)
    maker_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    taker_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Trade {self.token_id} {self.side} {self.size}@{self.price}>"

    @classmethod
    def from_api_response(cls, token_id: str, market_id: str, data: dict) -> "Trade":
        """Create trade from CLOB API response."""
        from dateutil.parser import parse as parse_date

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = parse_date(timestamp)
        elif isinstance(timestamp, (int, float)):
            # Handle milliseconds (13+ digits) vs seconds (10 digits)
            if timestamp > 1e12:
                timestamp = datetime.fromtimestamp(timestamp / 1000)
            else:
                timestamp = datetime.fromtimestamp(timestamp)

        return cls(
            trade_id=data.get("id"),
            token_id=token_id,
            market_id=market_id,
            price=float(data.get("price", 0)),
            size=float(data.get("size", 0)),
            side=data.get("side"),
            timestamp=timestamp or datetime.utcnow(),
            maker_address=data.get("maker"),
            taker_address=data.get("taker"),
        )
