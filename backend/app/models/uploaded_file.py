from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        CheckConstraint(
            "(assignment_id IS NOT NULL AND submission_id IS NULL AND submission_revision_id IS NULL) OR "
            "(assignment_id IS NULL AND submission_id IS NOT NULL AND submission_revision_id IS NULL) OR "
            "(assignment_id IS NULL AND submission_id IS NULL AND submission_revision_id IS NOT NULL)",
            name="ck_uploaded_files_single_parent",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    submission_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("submission_revisions.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    assignment: Mapped["Assignment | None"] = relationship(
        back_populates="attachments",
        foreign_keys=[assignment_id],
    )
    submission: Mapped["Submission | None"] = relationship(
        back_populates="attachments",
        foreign_keys=[submission_id],
    )
    revision: Mapped["SubmissionRevision | None"] = relationship(
        back_populates="attachments", foreign_keys=[submission_revision_id],
    )
