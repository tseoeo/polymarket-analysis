"""Watchlist model for tracking markets."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class WatchlistItem(Base):
    """A market added to the user's watchlist.

    Allows users to track markets they're learning about without
    the pressure of immediate trading.
    """

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Market reference
    market_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamps
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # User notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot of safety score when added (for comparison)
    initial_safety_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    def __repr__(self) -> str:
        return f"<WatchlistItem market={self.market_id} added={self.added_at}>"

    @classmethod
    def create(
        cls,
        market_id: str,
        notes: Optional[str] = None,
        initial_safety_score: Optional[int] = None,
    ) -> "WatchlistItem":
        """Create a new watchlist item."""
        return cls(
            market_id=market_id,
            notes=notes,
            initial_safety_score=initial_safety_score,
        )
