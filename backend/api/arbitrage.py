"""Arbitrage API endpoints."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.alert import Alert
from models.relationship import MarketRelationship
from services.cross_market_arbitrage import CrossMarketArbitrageDetector
from services.relationship_detector import RelationshipDetector

router = APIRouter()


# ============================================================================
# Response Schemas
# ============================================================================

class ArbitrageOpportunityResponse(BaseModel):
    """Arbitrage opportunity response schema."""

    id: int
    type: Optional[str] = None
    title: str
    description: Optional[str] = None
    profit_estimate: Optional[float] = None
    market_ids: Optional[List[str]] = None
    strategy: Optional[str] = None
    created_at: datetime
    is_active: bool


class ArbitrageListResponse(BaseModel):
    """Paginated arbitrage opportunities list."""

    opportunities: List[ArbitrageOpportunityResponse]
    total: int


class RelationshipGroupResponse(BaseModel):
    """Market relationship group response."""

    group_id: str
    relationship_type: str
    market_ids: List[str]
    notes: Optional[str] = None
    confidence: float


class RelationshipResponse(BaseModel):
    """Single relationship response."""

    id: int
    relationship_type: str
    parent_market_id: str
    child_market_id: str
    group_id: Optional[str] = None
    notes: Optional[str] = None
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateRelationshipRequest(BaseModel):
    """Request to create a relationship."""

    relationship_type: str  # mutually_exclusive, conditional, time_sequence, subset
    parent_market_id: str
    child_market_id: str
    group_id: Optional[str] = None
    notes: Optional[str] = None
    confidence: float = 1.0


class PotentialRelationshipResponse(BaseModel):
    """Potential relationship detected by heuristics."""

    type: str
    confidence: float
    reason: str
    market_ids: Optional[List[str]] = None
    parent_market_id: Optional[str] = None
    child_market_id: Optional[str] = None
    earlier_market_id: Optional[str] = None
    later_market_id: Optional[str] = None
    general_market_id: Optional[str] = None
    specific_market_id: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/opportunities", response_model=ArbitrageListResponse)
async def list_arbitrage_opportunities(
    type: Optional[str] = Query(None, description="Filter by type (mutually_exclusive, conditional, etc.)"),
    is_active: bool = Query(True, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List all arbitrage opportunities (cross-market alerts)."""
    detector = CrossMarketArbitrageDetector()
    opportunities = await detector.get_arbitrage_opportunities(
        session, include_inactive=not is_active
    )

    # Filter by type if specified
    if type:
        opportunities = [o for o in opportunities if o.get("type") == type]

    # Paginate
    total = len(opportunities)
    opportunities = opportunities[offset:offset + limit]

    return ArbitrageListResponse(
        opportunities=[
            ArbitrageOpportunityResponse(
                id=o["id"],
                type=o.get("type"),
                title=o["title"],
                description=o.get("description"),
                profit_estimate=o.get("profit_estimate"),
                market_ids=o.get("market_ids"),
                strategy=o.get("strategy"),
                created_at=datetime.fromisoformat(o["created_at"]),
                is_active=o["is_active"],
            )
            for o in opportunities
        ],
        total=total,
    )


@router.get("/groups")
async def list_relationship_groups(
    session: AsyncSession = Depends(get_db),
):
    """List all market relationship groups."""
    result = await session.execute(
        select(MarketRelationship)
        .where(MarketRelationship.group_id.isnot(None))
    )
    relationships = result.scalars().all()

    # Group by group_id
    groups = {}
    for rel in relationships:
        if rel.group_id not in groups:
            groups[rel.group_id] = {
                "group_id": rel.group_id,
                "relationship_type": rel.relationship_type,
                "market_ids": set(),
                "notes": rel.notes,
                "confidence": rel.confidence,
            }
        groups[rel.group_id]["market_ids"].add(rel.parent_market_id)
        groups[rel.group_id]["market_ids"].add(rel.child_market_id)

    return {
        "groups": [
            RelationshipGroupResponse(
                group_id=g["group_id"],
                relationship_type=g["relationship_type"],
                market_ids=list(g["market_ids"]),
                notes=g["notes"],
                confidence=g["confidence"],
            )
            for g in groups.values()
        ]
    }


@router.get("/groups/{group_id}")
async def get_relationship_group(
    group_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get details for a specific relationship group."""
    result = await session.execute(
        select(MarketRelationship)
        .where(MarketRelationship.group_id == group_id)
    )
    relationships = result.scalars().all()

    if not relationships:
        raise HTTPException(status_code=404, detail="Group not found")

    market_ids = set()
    for rel in relationships:
        market_ids.add(rel.parent_market_id)
        market_ids.add(rel.child_market_id)

    # Get market details
    from models.market import Market
    market_result = await session.execute(
        select(Market).where(Market.id.in_(list(market_ids)))
    )
    markets = {m.id: m for m in market_result.scalars().all()}

    return {
        "group_id": group_id,
        "relationship_type": relationships[0].relationship_type,
        "market_ids": list(market_ids),
        "notes": relationships[0].notes,
        "confidence": relationships[0].confidence,
        "markets": [
            {
                "id": m.id,
                "question": m.question,
                "yes_price": m.yes_price,
                "no_price": m.no_price,
            }
            for m in markets.values()
        ],
        "relationships": [
            RelationshipResponse.model_validate(r) for r in relationships
        ],
    }


@router.get("/relationships", response_model=List[RelationshipResponse])
async def list_relationships(
    relationship_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List all market relationships."""
    query = select(MarketRelationship)
    if relationship_type:
        query = query.where(MarketRelationship.relationship_type == relationship_type)
    query = query.order_by(desc(MarketRelationship.created_at)).limit(limit)

    result = await session.execute(query)
    return [RelationshipResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/relationships", response_model=RelationshipResponse)
async def create_relationship(
    request: CreateRelationshipRequest,
    session: AsyncSession = Depends(get_db),
):
    """Create a new market relationship (admin)."""
    # Verify markets exist
    from models.market import Market

    parent_result = await session.execute(
        select(Market).where(Market.id == request.parent_market_id)
    )
    if not parent_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Parent market not found")

    child_result = await session.execute(
        select(Market).where(Market.id == request.child_market_id)
    )
    if not child_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Child market not found")

    # Create relationship
    rel = MarketRelationship(
        relationship_type=request.relationship_type,
        parent_market_id=request.parent_market_id,
        child_market_id=request.child_market_id,
        group_id=request.group_id,
        notes=request.notes,
        confidence=request.confidence,
    )
    session.add(rel)
    await session.commit()
    await session.refresh(rel)

    return RelationshipResponse.model_validate(rel)


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    relationship_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Delete a market relationship (admin)."""
    result = await session.execute(
        select(MarketRelationship).where(MarketRelationship.id == relationship_id)
    )
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    await session.delete(rel)
    await session.commit()

    return {"status": "deleted", "id": relationship_id}


@router.get("/detect", response_model=List[PotentialRelationshipResponse])
async def detect_relationships(
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_db),
):
    """Auto-detect potential market relationships using heuristics."""
    detector = RelationshipDetector(min_confidence=min_confidence)
    potential = await detector.find_potential_relationships(session)

    return [PotentialRelationshipResponse(**p) for p in potential]
