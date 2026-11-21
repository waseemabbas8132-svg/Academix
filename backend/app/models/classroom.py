from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AcademicClass(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    teacher_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
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
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    memberships: Mapped[list["ClassMembership"]] = relationship(
        back_populates="class_",
        cascade="all, delete-orphan",
    )
    announcements: Mapped[list["Announcement"]] = relationship(
        back_populates="class_",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="class_",
        cascade="all, delete-orphan",
    )


class ClassMembership(Base):
    __tablename__ = "class_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    class_: Mapped[AcademicClass] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student_membership"),
    )
