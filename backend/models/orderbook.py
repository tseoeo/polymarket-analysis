"""Order book snapshot model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, JSON, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class OrderBookSnapshot(Base):
    """Snapshot of an order book at a point in time."""

    __tablename__ = "orderbook_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Market reference
    token_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    market_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Order book data (stored as JSON)
    # bids: [{"price": 0.64, "size": 100.0}, ...]
    # asks: [{"price": 0.66, "size": 150.0}, ...]
    bids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    asks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Calculated metrics
    best_bid: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    best_ask: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    spread: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    spread_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    mid_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    # Depth metrics (total $ within X% of best price)
    bid_depth_1pct: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    ask_depth_1pct: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    bid_depth_5pct: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    ask_depth_5pct: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)

    # Book imbalance: (bid_depth - ask_depth) / (bid_depth + ask_depth)
    # Positive = buying pressure, Negative = selling pressure
    imbalance: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    def __repr__(self) -> str:
        return f"<OrderBookSnapshot {self.token_id} @ {self.timestamp}>"

    @classmethod
    def from_api_response(cls, token_id: str, market_id: str, data: dict) -> "OrderBookSnapshot":
        """Create snapshot from CLOB API response."""
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        # Calculate metrics
        best_bid = float(bids[0]["price"]) if bids else None
        best_ask = float(asks[0]["price"]) if asks else None

        spread = None
        spread_pct = None
        mid_price = None

        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            mid_price = (best_ask + best_bid) / 2
            spread_pct = (spread / mid_price) * 100 if mid_price > 0 else None

        # Calculate depth at 1% and 5%
        def calculate_depth(levels: list, best_price: float, pct: float, is_bid: bool) -> float:
            if not levels or best_price is None:
                return 0.0
            total = 0.0
            threshold = best_price * (1 - pct) if is_bid else best_price * (1 + pct)
            for level in levels:
                price = float(level["price"])
                if is_bid and price >= threshold:
                    total += float(level["size"])
                elif not is_bid and price <= threshold:
                    total += float(level["size"])
            return total

        bid_depth_1pct = calculate_depth(bids, best_bid, 0.01, True) if best_bid else None
        ask_depth_1pct = calculate_depth(asks, best_ask, 0.01, False) if best_ask else None
        bid_depth_5pct = calculate_depth(bids, best_bid, 0.05, True) if best_bid else None
        ask_depth_5pct = calculate_depth(asks, best_ask, 0.05, False) if best_ask else None

        # Calculate imbalance
        imbalance = None
        if bid_depth_1pct and ask_depth_1pct:
            total_depth = bid_depth_1pct + ask_depth_1pct
            if total_depth > 0:
                imbalance = (bid_depth_1pct - ask_depth_1pct) / total_depth

        return cls(
            token_id=token_id,
            market_id=market_id,
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_pct=spread_pct,
            mid_price=mid_price,
            bid_depth_1pct=bid_depth_1pct,
            ask_depth_1pct=ask_depth_1pct,
            bid_depth_5pct=bid_depth_5pct,
            ask_depth_5pct=ask_depth_5pct,
            imbalance=imbalance,
        )
