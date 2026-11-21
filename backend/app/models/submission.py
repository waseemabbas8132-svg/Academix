from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "student_id",
            name="uq_submission_assignment_student",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'returned', 'graded')",
            name="ck_submissions_status",
        ),
        CheckConstraint(
            "marks_obtained IS NULL OR marks_obtained >= 0",
            name="ck_submissions_marks_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    submission_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    attachments: Mapped[list["UploadedFile"]] = relationship(
        back_populates="submission",
        cascade="all",
        foreign_keys="UploadedFile.submission_id",
    )
    revisions: Mapped[list["SubmissionRevision"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionRevision.revision_number",
    )


class SubmissionRevision(Base):
    __tablename__ = "submission_revisions"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "revision_number",
            name="uq_submission_revision_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submission_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    submission: Mapped[Submission] = relationship(back_populates="revisions")
    attachments: Mapped[list["UploadedFile"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan",
        foreign_keys="UploadedFile.submission_revision_id",
    )
