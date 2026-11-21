from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class EvaluationJob(Base):
    __tablename__ = "evaluation_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_evaluation_jobs_status",
        ),
        Index(
            "uq_evaluation_jobs_active_submission",
            "submission_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
            sqlite_where=text("status IN ('pending', 'processing')"),
        ),
        Index("ix_evaluation_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rubric_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    extracted_answers: Mapped[list[ExtractedAnswer]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ExtractedAnswer.segment_number",
    )
    evaluation: Mapped[AIEvaluation | None] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ExtractedAnswer(Base):
    __tablename__ = "extracted_answers"
    __table_args__ = (
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ck_extracted_answers_ocr_confidence_range",
        ),
        Index("uq_extracted_answers_job_segment", "job_id", "segment_number", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[EvaluationJob] = relationship(back_populates="extracted_answers")


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_ai_evaluations_review_status",
        ),
        CheckConstraint(
            "suggested_total IS NULL OR suggested_total >= 0",
            name="ck_ai_evaluations_suggested_total_nonnegative",
        ),
        CheckConstraint(
            "approved_marks IS NULL OR approved_marks >= 0",
            name="ck_ai_evaluations_approved_marks_nonnegative",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_ai_evaluations_confidence_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    suggested_total: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    maximum_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_marks: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[EvaluationJob] = relationship(back_populates="evaluation")
    question_evaluations: Mapped[list[QuestionEvaluation]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="QuestionEvaluation.question_id",
    )
    feedback_items: Mapped[list[EvaluationFeedback]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        order_by="EvaluationFeedback.created_at",
    )


class QuestionEvaluation(Base):
    __tablename__ = "question_evaluations"
    __table_args__ = (
        CheckConstraint(
            "suggested_marks IS NULL OR suggested_marks >= 0",
            name="ck_question_evaluations_marks_nonnegative",
        ),
        CheckConstraint(
            "teacher_marks IS NULL OR teacher_marks >= 0",
            name="ck_question_evaluations_teacher_marks_nonnegative",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_question_evaluations_confidence_range",
        ),
        Index(
            "uq_question_evaluations_evaluation_question",
            "evaluation_id",
            "question_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    suggested_marks: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    teacher_marks: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    maximum_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    evaluation: Mapped[AIEvaluation] = relationship(back_populates="question_evaluations")


class EvaluationFeedback(Base):
    __tablename__ = "evaluation_feedback"
    __table_args__ = (
        CheckConstraint(
            "similarity_score IS NULL OR "
            "(similarity_score >= 0 AND similarity_score <= 1)",
            name="ck_evaluation_feedback_similarity_range",
        ),
        Index("ix_evaluation_feedback_other_submission", "other_submission_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    other_submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    evaluation: Mapped[AIEvaluation] = relationship(back_populates="feedback_items")
