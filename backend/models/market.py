"""Market model for storing Polymarket market data."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Numeric, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Market(Base):
    """Represents a Polymarket prediction market."""

    __tablename__ = "markets"

    # Primary identifiers
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    condition_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Market details
    question: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Outcomes (stored as JSON array)
    # Example: [{"name": "Yes", "token_id": "abc123", "price": 0.65}, {"name": "No", "token_id": "def456", "price": 0.35}]
    outcomes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timing
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Market metrics
    volume: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)

    # Status
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_order_book: Mapped[bool] = mapped_column(Boolean, default=True)

    # Category/tags for grouping related markets
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Market {self.id}: {self.question[:50]}...>"

    @property
    def token_ids(self) -> List[str]:
        """Extract token IDs from outcomes."""
        if not self.outcomes:
            return []
        return [o.get("token_id") for o in self.outcomes if o.get("token_id")]

    @property
    def yes_price(self) -> Optional[float]:
        """Get the 'Yes' outcome price if available."""
        if not self.outcomes:
            return None
        for outcome in self.outcomes:
            if outcome.get("name", "").lower() == "yes":
                return outcome.get("price")
        return self.outcomes[0].get("price") if self.outcomes else None

    @property
    def no_price(self) -> Optional[float]:
        """Get the 'No' outcome price if available."""
        if not self.outcomes:
            return None
        for outcome in self.outcomes:
            if outcome.get("name", "").lower() == "no":
                return outcome.get("price")
        return self.outcomes[1].get("price") if len(self.outcomes) > 1 else None
