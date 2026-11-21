"""add assignment rubrics and teacher-reviewed AI evaluations

Revision ID: 20261114_ai_evaluations
Revises: 20261114_assignments
Create Date: 2026-11-14 14:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_ai_evaluations"
down_revision = "20261114_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assignment_rubrics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("model_answer", sa.Text(), nullable=True),
        sa.Column("teacher_instructions", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_assignment_rubrics_assignment_id_assignments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assignment_rubrics_assignment_id",
        "assignment_rubrics",
        ["assignment_id"],
        unique=True,
    )

    op.create_table(
        "rubric_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rubric_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("max_marks", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("model_answer", sa.Text(), nullable=True),
        sa.Column("acceptable_answers", sa.JSON(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("partial_credit_rules", sa.JSON(), nullable=False),
        sa.CheckConstraint("max_marks > 0", name="ck_rubric_questions_max_marks_positive"),
        sa.ForeignKeyConstraint(
            ["rubric_id"],
            ["assignment_rubrics.id"],
            name="fk_rubric_questions_rubric_id_assignment_rubrics",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rubric_id", "question_id", name="uq_rubric_question_id"),
    )
    op.create_index(op.f("ix_rubric_questions_rubric_id"), "rubric_questions", ["rubric_id"])

    op.create_table(
        "evaluation_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rubric_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_evaluation_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name="fk_evaluation_jobs_submission_id_submissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_jobs_submission_id"),
        "evaluation_jobs",
        ["submission_id"],
    )
    op.create_index(
        "ix_evaluation_jobs_status_created",
        "evaluation_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "uq_evaluation_jobs_active_submission",
        "evaluation_jobs",
        ["submission_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
        sqlite_where=sa.text("status IN ('pending', 'processing')"),
    )

    op.create_table(
        "extracted_answers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("segment_number", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ck_extracted_answers_ocr_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["evaluation_jobs.id"],
            name="fk_extracted_answers_job_id_evaluation_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extracted_answers_job_id"), "extracted_answers", ["job_id"])
    op.create_index(
        "uq_extracted_answers_job_segment",
        "extracted_answers",
        ["job_id", "segment_number"],
        unique=True,
    )

    op.create_table(
        "ai_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("suggested_total", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("maximum_marks", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_marks", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "suggested_total IS NULL OR suggested_total >= 0",
            name="ck_ai_evaluations_suggested_total_nonnegative",
        ),
        sa.CheckConstraint(
            "approved_marks IS NULL OR approved_marks >= 0",
            name="ck_ai_evaluations_approved_marks_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_ai_evaluations_confidence_range",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_ai_evaluations_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["evaluation_jobs.id"],
            name="fk_ai_evaluations_job_id_evaluation_jobs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_evaluations_job_id"),
        "ai_evaluations",
        ["job_id"],
        unique=True,
    )

    op.create_table(
        "question_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("suggested_marks", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("teacher_marks", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("maximum_marks", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "suggested_marks IS NULL OR suggested_marks >= 0",
            name="ck_question_evaluations_marks_nonnegative",
        ),
        sa.CheckConstraint(
            "teacher_marks IS NULL OR teacher_marks >= 0",
            name="ck_question_evaluations_teacher_marks_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_question_evaluations_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["ai_evaluations.id"],
            name="fk_question_evaluations_evaluation_id_ai_evaluations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_question_evaluations_evaluation_id"),
        "question_evaluations",
        ["evaluation_id"],
    )
    op.create_index(
        "uq_question_evaluations_evaluation_question",
        "question_evaluations",
        ["evaluation_id", "question_id"],
        unique=True,
    )

    op.create_table(
        "evaluation_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("other_submission_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "similarity_score IS NULL OR "
            "(similarity_score >= 0 AND similarity_score <= 1)",
            name="ck_evaluation_feedback_similarity_range",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["ai_evaluations.id"],
            name="fk_evaluation_feedback_evaluation_id_ai_evaluations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["other_submission_id"],
            ["submissions.id"],
            name="fk_evaluation_feedback_other_submission_id_submissions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_feedback_evaluation_id"),
        "evaluation_feedback",
        ["evaluation_id"],
    )
    op.create_index(
        "ix_evaluation_feedback_other_submission",
        "evaluation_feedback",
        ["other_submission_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_feedback_other_submission", table_name="evaluation_feedback")
    op.drop_index(op.f("ix_evaluation_feedback_evaluation_id"), table_name="evaluation_feedback")
    op.drop_table("evaluation_feedback")
    op.drop_index("uq_question_evaluations_evaluation_question", table_name="question_evaluations")
    op.drop_index(
        op.f("ix_question_evaluations_evaluation_id"),
        table_name="question_evaluations",
    )
    op.drop_table("question_evaluations")
    op.drop_index(op.f("ix_ai_evaluations_job_id"), table_name="ai_evaluations")
    op.drop_table("ai_evaluations")
    op.drop_index("uq_extracted_answers_job_segment", table_name="extracted_answers")
    op.drop_index(op.f("ix_extracted_answers_job_id"), table_name="extracted_answers")
    op.drop_table("extracted_answers")
    op.drop_index(
        "uq_evaluation_jobs_active_submission",
        table_name="evaluation_jobs",
    )
    op.drop_index("ix_evaluation_jobs_status_created", table_name="evaluation_jobs")
    op.drop_index(op.f("ix_evaluation_jobs_submission_id"), table_name="evaluation_jobs")
    op.drop_table("evaluation_jobs")
    op.drop_index(op.f("ix_rubric_questions_rubric_id"), table_name="rubric_questions")
    op.drop_table("rubric_questions")
    op.drop_index("ix_assignment_rubrics_assignment_id", table_name="assignment_rubrics")
    op.drop_table("assignment_rubrics")
