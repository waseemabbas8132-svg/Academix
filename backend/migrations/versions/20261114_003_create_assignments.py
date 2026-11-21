"""create assignments, submissions, and uploaded files

Revision ID: 20261114_assignments
Revises: 20261114_announcements
Create Date: 2026-11-14 12:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_assignments"
down_revision = "20261114_announcements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("total_marks", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("total_marks > 0", name="ck_assignments_total_marks_positive"),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name="fk_assignments_class_id_classes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assignments_class_id"), "assignments", ["class_id"])
    op.create_index(op.f("ix_assignments_teacher_id"), "assignments", ["teacher_id"])
    op.create_index(op.f("ix_assignments_due_date"), "assignments", ["due_date"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=255), nullable=False),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("marks_obtained", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'returned', 'graded')",
            name="ck_submissions_status",
        ),
        sa.CheckConstraint(
            "marks_obtained IS NULL OR marks_obtained >= 0",
            name="ck_submissions_marks_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_submissions_assignment_id_assignments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            "student_id",
            name="uq_submission_assignment_student",
        ),
    )
    op.create_index(op.f("ix_submissions_assignment_id"), "submissions", ["assignment_id"])
    op.create_index(op.f("ix_submissions_student_id"), "submissions", ["student_id"])

    op.create_table(
        "submission_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marks_obtained", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name="fk_submission_revisions_submission_id_submissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id",
            "revision_number",
            name="uq_submission_revision_number",
        ),
    )
    op.create_index(
        op.f("ix_submission_revisions_submission_id"),
        "submission_revisions",
        ["submission_id"],
    )

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=True),
        sa.Column("submission_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(assignment_id IS NOT NULL AND submission_id IS NULL) OR "
            "(assignment_id IS NULL AND submission_id IS NOT NULL)",
            name="ck_uploaded_files_single_parent",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_uploaded_files_assignment_id_assignments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name="fk_uploaded_files_submission_id_submissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_uploaded_files_assignment_id"), "uploaded_files", ["assignment_id"])
    op.create_index(op.f("ix_uploaded_files_submission_id"), "uploaded_files", ["submission_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_uploaded_files_submission_id"), table_name="uploaded_files")
    op.drop_index(op.f("ix_uploaded_files_assignment_id"), table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.drop_index(op.f("ix_submission_revisions_submission_id"), table_name="submission_revisions")
    op.drop_table("submission_revisions")
    op.drop_index(op.f("ix_submissions_student_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_assignment_id"), table_name="submissions")
    op.drop_table("submissions")
    op.drop_index(op.f("ix_assignments_due_date"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_teacher_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_class_id"), table_name="assignments")
    op.drop_table("assignments")
