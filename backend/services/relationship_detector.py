"""Market relationship detection service.

Identifies potential relationships between markets for cross-market arbitrage detection:
- Mutually exclusive: Markets that can't both resolve YES
- Conditional: Child market depends on parent (must win primary to win election)
- Time sequence: Earlier deadline should price <= later deadline
- Subset: Specific outcome is subset of general outcome
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.market import Market
from models.relationship import MarketRelationship

logger = logging.getLogger(__name__)


class RelationshipDetector:
    """Detects potential relationships between prediction markets.

    Uses NLP-style heuristics on market questions and metadata to identify
    related markets. Auto-detected relationships have lower confidence scores.
    """

    def __init__(
        self,
        min_confidence: float = 0.6,  # Minimum confidence to suggest relationship
    ):
        self.min_confidence = min_confidence

        # Common patterns for relationship detection
        self._exclusive_keywords = [
            "win", "winner", "champion", "elected", "nominee", "first",
        ]
        self._time_patterns = [
            r"by (\w+ \d{1,2}|\d{4})",
            r"before (\w+ \d{1,2}|\d{4})",
            r"in (\w+|\d{4})",
        ]
        self._subset_patterns = [
            r"by (\d+)\+",  # "wins by 10+"
            r"over (\d+)",   # "over 50%"
            r"more than",
        ]

    async def find_potential_relationships(
        self,
        session: AsyncSession,
    ) -> List[Dict]:
        """Find all potential relationships between markets.

        Returns a list of potential relationships with confidence scores
        for manual review and confirmation.
        """
        result = await session.execute(
            select(Market).where(Market.active == True)
        )
        markets = result.scalars().all()

        potential = []
        potential.extend(await self.detect_mutually_exclusive(session, markets))
        potential.extend(await self.detect_conditional(session, markets))
        potential.extend(await self.detect_time_sequence(session, markets))
        potential.extend(await self.detect_subset(session, markets))

        # Filter by minimum confidence
        return [p for p in potential if p["confidence"] >= self.min_confidence]

    async def detect_mutually_exclusive(
        self,
        session: AsyncSession,
        markets: List[Market],
    ) -> List[Dict]:
        """Detect mutually exclusive market groups (Type A).

        Looks for markets with similar questions that represent competing outcomes.
        E.g., "Will Team A win?" vs "Will Team B win?" for the same event.
        """
        potential = []

        # Group markets by category and similarity
        category_groups = defaultdict(list)
        for market in markets:
            if market.category:
                category_groups[market.category].append(market)

        # Also group by question similarity
        question_groups = self._group_by_question_similarity(markets)

        # Check each group for mutually exclusive patterns
        for group_id, group_markets in {**category_groups, **question_groups}.items():
            if len(group_markets) < 2:
                continue

            # Look for "who will X" pattern
            win_pattern_markets = []
            for market in group_markets:
                q_lower = market.question.lower()
                if any(kw in q_lower for kw in self._exclusive_keywords):
                    win_pattern_markets.append(market)

            if len(win_pattern_markets) >= 2:
                # Check if questions differ only in the subject
                subjects = self._extract_subjects(win_pattern_markets)
                if len(subjects) == len(win_pattern_markets):
                    confidence = 0.7 if len(win_pattern_markets) <= 5 else 0.5
                    potential.append({
                        "type": "mutually_exclusive",
                        "market_ids": [m.id for m in win_pattern_markets],
                        "group_id": f"auto-exclusive-{group_id[:20]}",
                        "confidence": confidence,
                        "reason": f"Similar questions with different subjects: {subjects}",
                    })

        return potential

    async def detect_conditional(
        self,
        session: AsyncSession,
        markets: List[Market],
    ) -> List[Dict]:
        """Detect conditional relationships (Type B).

        Looks for parent-child relationships where child event requires parent.
        E.g., "X wins primary" -> "X wins general election"
        """
        potential = []

        # Group by common entities (names, subjects)
        entity_markets = defaultdict(list)
        for market in markets:
            entities = self._extract_entities(market.question)
            for entity in entities:
                entity_markets[entity.lower()].append(market)

        # Find conditional pairs
        for entity, entity_mkt_list in entity_markets.items():
            if len(entity_mkt_list) < 2:
                continue

            # Look for stage progressions (primary -> general, nomination -> election)
            stage_order = ["nominee", "primary", "nomination", "win", "president", "elected"]

            for i, mkt1 in enumerate(entity_mkt_list):
                for mkt2 in entity_mkt_list[i+1:]:
                    q1_lower = mkt1.question.lower()
                    q2_lower = mkt2.question.lower()

                    # Find which stage each market is
                    stage1 = self._find_stage(q1_lower, stage_order)
                    stage2 = self._find_stage(q2_lower, stage_order)

                    if stage1 is not None and stage2 is not None and stage1 != stage2:
                        parent, child = (mkt1, mkt2) if stage1 < stage2 else (mkt2, mkt1)
                        potential.append({
                            "type": "conditional",
                            "parent_market_id": parent.id,
                            "child_market_id": child.id,
                            "confidence": 0.65,
                            "reason": f"Stage progression for '{entity}'",
                        })

        return potential

    async def detect_time_sequence(
        self,
        session: AsyncSession,
        markets: List[Market],
    ) -> List[Dict]:
        """Detect time sequence relationships (Type C).

        Looks for markets with same event but different deadlines.
        E.g., "X by March 2025" vs "X by December 2025"
        """
        potential = []

        # Group markets by base question (removing time references)
        base_question_groups = defaultdict(list)
        for market in markets:
            base = self._extract_base_question(market.question)
            if base:
                time_ref = self._extract_time_reference(market.question)
                if time_ref:
                    base_question_groups[base].append((market, time_ref))

        # Find time-ordered pairs
        for base, markets_with_times in base_question_groups.items():
            if len(markets_with_times) < 2:
                continue

            # Sort by time reference
            try:
                sorted_markets = sorted(
                    markets_with_times,
                    key=lambda x: self._parse_time_reference(x[1])
                )
            except (ValueError, TypeError):
                continue

            # Create relationships for adjacent pairs
            for i in range(len(sorted_markets) - 1):
                earlier, earlier_time = sorted_markets[i]
                later, later_time = sorted_markets[i + 1]

                potential.append({
                    "type": "time_sequence",
                    "earlier_market_id": earlier.id,
                    "later_market_id": later.id,
                    "group_id": f"auto-time-{base[:30]}",
                    "confidence": 0.75,
                    "reason": f"Same event with different deadlines: {earlier_time} < {later_time}",
                })

        return potential

    async def detect_subset(
        self,
        session: AsyncSession,
        markets: List[Market],
    ) -> List[Dict]:
        """Detect subset relationships (Type D).

        Looks for markets where one is a more specific version of another.
        E.g., "X wins" vs "X wins by 10+"
        """
        potential = []

        # Group by similar base questions
        for i, market1 in enumerate(markets):
            for market2 in markets[i+1:]:
                q1_lower = market1.question.lower()
                q2_lower = market2.question.lower()

                # Check if one contains subset-indicating patterns
                is_q1_subset = any(
                    re.search(pat, q1_lower) for pat in self._subset_patterns
                )
                is_q2_subset = any(
                    re.search(pat, q2_lower) for pat in self._subset_patterns
                )

                if is_q1_subset and not is_q2_subset:
                    # q1 is the specific (subset), q2 is general
                    if self._questions_are_related(q1_lower, q2_lower):
                        potential.append({
                            "type": "subset",
                            "general_market_id": market2.id,
                            "specific_market_id": market1.id,
                            "confidence": 0.7,
                            "reason": "Specific version with threshold/qualifier",
                        })
                elif is_q2_subset and not is_q1_subset:
                    if self._questions_are_related(q1_lower, q2_lower):
                        potential.append({
                            "type": "subset",
                            "general_market_id": market1.id,
                            "specific_market_id": market2.id,
                            "confidence": 0.7,
                            "reason": "Specific version with threshold/qualifier",
                        })

        return potential

    async def create_relationship(
        self,
        session: AsyncSession,
        relationship_data: Dict,
    ) -> MarketRelationship:
        """Create a MarketRelationship from detected data."""
        rel_type = relationship_data["type"]

        if rel_type == "mutually_exclusive":
            relationships = MarketRelationship.create_mutually_exclusive(
                market_ids=relationship_data["market_ids"],
                group_id=relationship_data["group_id"],
                notes=relationship_data.get("reason"),
                confidence=relationship_data["confidence"],
            )
            for rel in relationships:
                session.add(rel)
            await session.commit()
            return relationships[0] if relationships else None

        elif rel_type == "conditional":
            rel = MarketRelationship.create_conditional(
                parent_id=relationship_data["parent_market_id"],
                child_id=relationship_data["child_market_id"],
                notes=relationship_data.get("reason"),
                confidence=relationship_data["confidence"],
            )
            session.add(rel)
            await session.commit()
            return rel

        elif rel_type == "time_sequence":
            rel = MarketRelationship.create_time_sequence(
                earlier_id=relationship_data["earlier_market_id"],
                later_id=relationship_data["later_market_id"],
                group_id=relationship_data.get("group_id"),
                notes=relationship_data.get("reason"),
                confidence=relationship_data["confidence"],
            )
            session.add(rel)
            await session.commit()
            return rel

        elif rel_type == "subset":
            rel = MarketRelationship.create_subset(
                general_id=relationship_data["general_market_id"],
                specific_id=relationship_data["specific_market_id"],
                notes=relationship_data.get("reason"),
                confidence=relationship_data["confidence"],
            )
            session.add(rel)
            await session.commit()
            return rel

        raise ValueError(f"Unknown relationship type: {rel_type}")

    # Helper methods

    def _group_by_question_similarity(self, markets: List[Market]) -> Dict[str, List[Market]]:
        """Group markets by question word overlap."""
        groups = defaultdict(list)
        for market in markets:
            # Create a simple signature from main words
            words = set(re.findall(r'\b\w+\b', market.question.lower()))
            # Remove common words
            stop_words = {"will", "the", "a", "an", "be", "is", "to", "in", "of", "for"}
            words = words - stop_words
            # Sort FIRST to ensure deterministic order, THEN slice
            sorted_words = sorted(words)
            signature = "_".join(sorted_words[:5])
            if signature:
                groups[signature].append(market)
        return dict(groups)

    def _extract_subjects(self, markets: List[Market]) -> List[str]:
        """Extract differing subjects from similar questions."""
        subjects = []
        for market in markets:
            # Simple extraction - look for capitalized words
            caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', market.question)
            if caps:
                subjects.append(caps[0])
        return subjects

    def _extract_entities(self, question: str) -> List[str]:
        """Extract named entities from question."""
        # Simple approach - find capitalized multi-word names
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', question)
        return entities

    def _find_stage(self, question: str, stage_order: List[str]) -> Optional[int]:
        """Find the stage index in a progression."""
        for i, stage in enumerate(stage_order):
            if stage in question:
                return i
        return None

    def _extract_base_question(self, question: str) -> Optional[str]:
        """Remove time references to get base question."""
        # Remove common time patterns
        base = re.sub(r'\s+by\s+\w+\s+\d{1,2}(,\s*\d{4})?', '', question, flags=re.I)
        base = re.sub(r'\s+before\s+\w+\s+\d{1,2}(,\s*\d{4})?', '', base, flags=re.I)
        base = re.sub(r'\s+in\s+\d{4}', '', base, flags=re.I)
        base = base.strip()
        return base if base != question else None

    def _extract_time_reference(self, question: str) -> Optional[str]:
        """Extract time reference from question."""
        for pattern in self._time_patterns:
            match = re.search(pattern, question, re.I)
            if match:
                return match.group(0)
        return None

    def _parse_time_reference(self, time_ref: str) -> datetime:
        """Parse time reference to datetime for comparison."""
        # Simple parsing - could be enhanced
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }

        lower = time_ref.lower()
        for month_name, month_num in months.items():
            if month_name in lower:
                year_match = re.search(r'\d{4}', lower)
                year = int(year_match.group()) if year_match else 2025
                return datetime(year, month_num, 1)

        # Year only
        year_match = re.search(r'\d{4}', lower)
        if year_match:
            return datetime(int(year_match.group()), 1, 1)

        raise ValueError(f"Could not parse time reference: {time_ref}")

    def _questions_are_related(self, q1: str, q2: str) -> bool:
        """Check if two questions are related (high word overlap)."""
        words1 = set(re.findall(r'\b\w{3,}\b', q1))
        words2 = set(re.findall(r'\b\w{3,}\b', q2))
        overlap = len(words1 & words2)
        total = max(len(words1), len(words2))
        return overlap / total > 0.5 if total > 0 else False
