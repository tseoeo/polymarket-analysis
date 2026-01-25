"""Base analyzer class for optional inheritance.

Provides default deduplication and error handling patterns that analyzers
can opt into. Analyzers are NOT required to inherit from this class.

Key features:
- Default deduplication by (market_id, token_id)
- Customizable _dedup_key() for analyzers with different needs
- Structured logging with analyzer name
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert


class BaseAnalyzer(ABC):
    """Optional base class for analyzers with common deduplication logic.

    Subclasses must implement:
    - alert_type: The alert type string (e.g., "volume_spike")
    - _analyze_impl: The actual analysis logic
    - _dedup_key (optional): Override for custom dedup key extraction

    The base class provides:
    - Automatic deduplication checking before creating alerts
    - Structured logging with analyzer name
    - Error handling wrapper

    Example:
        class MyAnalyzer(BaseAnalyzer):
            @property
            def alert_type(self) -> str:
                return "my_alert"

            async def _analyze_impl(self, session) -> List[Alert]:
                # Analysis logic here
                return alerts
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def alert_type(self) -> str:
        """Return the alert type string for this analyzer."""
        ...

    @abstractmethod
    async def _analyze_impl(self, session: AsyncSession) -> List[Alert]:
        """Implement the actual analysis logic.

        This method should:
        1. Query for relevant data
        2. Check for conditions that warrant alerts
        3. Create Alert objects (but NOT check for duplicates)

        Deduplication is handled by the base class analyze() method.

        Returns:
            List of Alert objects to potentially create.
        """
        ...

    async def analyze(self, session: AsyncSession) -> List[Alert]:
        """Run analysis with automatic deduplication.

        This wrapper:
        1. Fetches existing active alerts of this type
        2. Calls _analyze_impl to get candidate alerts
        3. Filters out duplicates based on _dedup_key
        4. Adds non-duplicate alerts to session

        Returns:
            List of newly created (non-duplicate) alerts.
        """
        # Get existing alerts for dedup checking
        existing_keys = await self._get_existing_alert_keys(session)

        # Run analysis
        candidate_alerts = await self._analyze_impl(session)

        # Filter duplicates
        new_alerts = []
        for alert in candidate_alerts:
            key = self._dedup_key(alert)
            if key not in existing_keys:
                session.add(alert)
                new_alerts.append(alert)
                existing_keys.add(key)  # Prevent duplicates within same run

        if new_alerts:
            self.logger.info(f"Created {len(new_alerts)} {self.alert_type} alerts")
        else:
            self.logger.debug(f"No new {self.alert_type} alerts")

        return new_alerts

    def _dedup_key(self, alert: Alert) -> Tuple[Any, ...]:
        """Extract deduplication key from an alert.

        Default implementation uses (market_id, token_id) from alert.data.
        Subclasses can override for different dedup strategies.

        Args:
            alert: The alert to extract key from.

        Returns:
            Tuple used as dedup key (must be hashable).
        """
        market_id = alert.market_id
        token_id = (alert.data or {}).get("token_id")
        return (market_id, token_id)

    async def _get_existing_alert_keys(self, session: AsyncSession) -> Set[Tuple]:
        """Get dedup keys for existing active alerts of this type.

        Returns:
            Set of dedup keys for existing active alerts.
        """
        result = await session.execute(
            select(Alert.market_id, Alert.data)
            .where(Alert.alert_type == self.alert_type)
            .where(Alert.is_active == True)
        )

        existing = set()
        for row in result.all():
            market_id = row[0]
            data = row[1] or {}
            token_id = data.get("token_id")
            if market_id and token_id:
                existing.add((market_id, token_id))

        return existing


class RelatedMarketsAnalyzer(BaseAnalyzer):
    """Base for analyzers that use related_market_ids instead of market_id.

    Used by ArbitrageDetector which tracks alerts by related_market_ids
    (a list) rather than a single market_id.
    """

    def _dedup_key(self, alert: Alert) -> Tuple[Any, ...]:
        """Extract dedup key from related_market_ids.

        Returns tuple of sorted market IDs for consistent hashing.
        """
        market_ids = alert.related_market_ids or []
        return tuple(sorted(market_ids))

    async def _get_existing_alert_keys(self, session: AsyncSession) -> Set[Tuple]:
        """Get dedup keys for existing alerts using related_market_ids."""
        result = await session.execute(
            select(Alert.related_market_ids)
            .where(Alert.alert_type == self.alert_type)
            .where(Alert.is_active == True)
        )

        existing = set()
        for row in result.all():
            market_ids = row[0]
            if market_ids:
                existing.add(tuple(sorted(market_ids)))

        return existing
