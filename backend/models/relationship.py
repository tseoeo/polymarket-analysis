"""Market relationship model for tracking related markets."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MarketRelationship(Base):
    """Tracks relationships between markets for cross-market analysis.

    Relationship types:
    - 'mutually_exclusive': Markets that cannot both resolve YES (e.g., "Team A wins" vs "Team B wins")
    - 'conditional': Child market's probability depends on parent (e.g., "X wins primary" -> "X wins election")
    - 'time_sequence': Earlier event should price lower than later (e.g., "by March" vs "by December")
    - 'subset': Specific market is subset of general (e.g., "wins by 10+" is subset of "wins")
    """

    __tablename__ = "market_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Relationship classification
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'mutually_exclusive', 'conditional', 'time_sequence', 'subset'

    # Market references
    parent_market_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("markets.id"), nullable=False, index=True
    )
    child_market_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("markets.id"), nullable=False, index=True
    )

    # Group identifier for mutually exclusive sets (all markets in group compete)
    group_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Optional notes explaining the relationship
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Confidence score for auto-detected relationships (1.0 = manually verified)
    confidence: Mapped[float] = mapped_column(default=1.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        # Ensure no duplicate relationships between same markets
        Index(
            "ix_unique_relationship",
            "parent_market_id",
            "child_market_id",
            "relationship_type",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketRelationship {self.relationship_type}: "
            f"{self.parent_market_id} -> {self.child_market_id}>"
        )

    @classmethod
    def create_mutually_exclusive(
        cls,
        market_ids: list[str],
        group_id: str,
        notes: Optional[str] = None,
        confidence: float = 1.0,
    ) -> list["MarketRelationship"]:
        """Create relationships for a set of mutually exclusive markets.

        For N markets, creates N*(N-1)/2 bidirectional relationships.
        """
        relationships = []
        for i, market_a in enumerate(market_ids):
            for market_b in market_ids[i + 1:]:
                # Create bidirectional relationship
                relationships.append(
                    cls(
                        relationship_type="mutually_exclusive",
                        parent_market_id=market_a,
                        child_market_id=market_b,
                        group_id=group_id,
                        notes=notes,
                        confidence=confidence,
                    )
                )
        return relationships

    @classmethod
    def create_conditional(
        cls,
        parent_id: str,
        child_id: str,
        notes: Optional[str] = None,
        confidence: float = 1.0,
    ) -> "MarketRelationship":
        """Create a conditional relationship where child depends on parent."""
        return cls(
            relationship_type="conditional",
            parent_market_id=parent_id,
            child_market_id=child_id,
            notes=notes,
            confidence=confidence,
        )

    @classmethod
    def create_time_sequence(
        cls,
        earlier_id: str,
        later_id: str,
        group_id: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: float = 1.0,
    ) -> "MarketRelationship":
        """Create a time sequence relationship (earlier event should price <= later)."""
        return cls(
            relationship_type="time_sequence",
            parent_market_id=earlier_id,  # Parent = earlier
            child_market_id=later_id,  # Child = later
            group_id=group_id,
            notes=notes,
            confidence=confidence,
        )

    @classmethod
    def create_subset(
        cls,
        general_id: str,
        specific_id: str,
        notes: Optional[str] = None,
        confidence: float = 1.0,
    ) -> "MarketRelationship":
        """Create a subset relationship (specific is subset of general)."""
        return cls(
            relationship_type="subset",
            parent_market_id=general_id,  # Parent = general/superset
            child_market_id=specific_id,  # Child = specific/subset
            notes=notes,
            confidence=confidence,
        )
