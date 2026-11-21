from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AssignmentRubric(Base):
    __tablename__ = "assignment_rubrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
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

    questions: Mapped[list[RubricQuestion]] = relationship(
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="RubricQuestion.position",
    )


class RubricQuestion(Base):
    __tablename__ = "rubric_questions"
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_rubric_questions_max_marks_positive"),
        UniqueConstraint("rubric_id", "question_id", name="uq_rubric_question_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rubric_id: Mapped[str] = mapped_column(
        ForeignKey("assignment_rubrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptable_answers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    criteria: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    partial_credit_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    rubric: Mapped[AssignmentRubric] = relationship(back_populates="questions")
