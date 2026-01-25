"""Job run tracking model for observability.

Persists job execution status in the database for cross-worker visibility
and survival across restarts. Used by /api/system/status endpoint.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class JobRun(Base):
    """Tracks individual job executions for observability.

    Each scheduler job creates a JobRun record when it starts and updates
    it when it completes (success or failure). This provides:
    - Last run status for each job type
    - Correlation IDs for log debugging
    - Records processed count for monitoring
    """

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Job identification
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str] = mapped_column(String(36))  # UUID for correlation

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status: "running", "success", "failed"
    status: Mapped[str] = mapped_column(String(16), default="running")

    # Error details (only populated on failure)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metrics
    records_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Composite index for efficient "latest run per job" queries
    __table_args__ = (
        Index("ix_job_runs_job_id_started_at", "job_id", "started_at"),
    )

    def mark_success(self, records_processed: Optional[int] = None) -> None:
        """Mark job as successfully completed."""
        self.status = "success"
        self.completed_at = datetime.utcnow()
        if records_processed is not None:
            self.records_processed = records_processed

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed with error details."""
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.error_message = error_message

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
