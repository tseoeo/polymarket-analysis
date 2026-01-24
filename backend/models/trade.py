"""Trade history model."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# Valid trade sides
VALID_SIDES = {"buy", "sell"}


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

    def is_valid(self) -> bool:
        """Validate trade data quality.

        Returns:
            True if trade has valid data for analysis.
        """
        # Price must be positive and between 0 and 1 (probability)
        if self.price is None or self.price <= 0 or self.price > 1:
            return False

        # Size must be positive
        if self.size is None or self.size <= 0:
            return False

        # Side must be buy or sell (if provided)
        if self.side is not None and self.side.lower() not in VALID_SIDES:
            return False

        # Timestamp must be present
        if self.timestamp is None:
            return False

        # Normalize to naive UTC for comparison
        ts = self.timestamp
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)  # Already UTC from parsing

        now = datetime.utcnow()
        if ts > now + timedelta(hours=1):  # Allow 1hr clock skew
            return False

        return True

    def compute_dedup_key(self) -> str:
        """Generate deterministic key for trades missing trade_id.

        Used to prevent duplicate inserts when API doesn't provide trade_id.
        Creates a hash from token_id, price, size, side, and timestamp.
        """
        ts_str = self.timestamp.isoformat() if self.timestamp else ""
        key_parts = f"{self.token_id}:{self.price}:{self.size}:{self.side}:{ts_str}"
        return hashlib.sha256(key_parts.encode()).hexdigest()[:32]

    @classmethod
    def from_api_response(cls, token_id: str, market_id: str, data: dict) -> "Trade":
        """Create trade from CLOB API response.

        Normalizes all timestamps to naive UTC for consistent comparison.
        Generates a dedup key if trade_id is missing from the API.
        """
        from dateutil.parser import parse as parse_date

        raw_timestamp = data.get("timestamp")
        parsed_timestamp = None

        if isinstance(raw_timestamp, str):
            try:
                parsed_timestamp = parse_date(raw_timestamp)
                # Normalize to naive UTC
                if parsed_timestamp.tzinfo is not None:
                    parsed_timestamp = parsed_timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass  # Will be caught by is_valid()
        elif isinstance(raw_timestamp, (int, float)):
            try:
                # Handle milliseconds (13+ digits) vs seconds (10 digits)
                if raw_timestamp > 1e12:
                    parsed_timestamp = datetime.utcfromtimestamp(raw_timestamp / 1000)
                else:
                    parsed_timestamp = datetime.utcfromtimestamp(raw_timestamp)
            except Exception:
                pass  # Will be caught by is_valid()

        # Normalize side to lowercase
        side = data.get("side")
        if side:
            side = side.lower().strip()

        trade = cls(
            trade_id=data.get("id"),
            token_id=token_id,
            market_id=market_id,
            price=float(data.get("price", 0)),
            size=float(data.get("size", 0)),
            side=side,
            timestamp=parsed_timestamp,  # None if parsing failed
            maker_address=data.get("maker"),
            taker_address=data.get("taker"),
        )

        # Generate dedup key if trade_id is missing
        if not trade.trade_id and trade.timestamp:
            trade.trade_id = trade.compute_dedup_key()

        return trade
