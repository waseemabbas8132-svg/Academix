"""Private append-only teacher review snapshots, independent of AI evaluations."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SubmissionReview(Base):
    __tablename__ = "submission_reviews"
    __table_args__ = (
        UniqueConstraint("submission_id", "version", name="uq_review_version"),
        CheckConstraint("version > 0",name="ck_review_version"),
        CheckConstraint("state IN ('draft','reviewed','released','returned')",name="ck_review_state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rubric_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    assignment_version: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rubric_version: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
