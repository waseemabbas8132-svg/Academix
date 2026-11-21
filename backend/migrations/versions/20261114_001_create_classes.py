"""create classes and memberships

Revision ID: 20261114_classes
Revises: 
Create Date: 2026-11-14 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20261114_classes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "classes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("room", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("class_code", sa.String(length=12), nullable=False),
        sa.Column("teacher_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_code", name="uq_classes_class_code"),
    )
    op.create_index(op.f("ix_classes_teacher_id"), "classes", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_classes_class_code"), "classes", ["class_code"], unique=False)

    op.create_table(
        "class_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=255), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], name="fk_class_memberships_class_id_classes"),
        sa.UniqueConstraint("class_id", "student_id", name="uq_class_student_membership"),
    )
    op.create_index(op.f("ix_class_memberships_class_id"), "class_memberships", ["class_id"], unique=False)
    op.create_index(op.f("ix_class_memberships_student_id"), "class_memberships", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_class_memberships_student_id"), table_name="class_memberships")
    op.drop_index(op.f("ix_class_memberships_class_id"), table_name="class_memberships")
    op.drop_table("class_memberships")
    op.drop_index(op.f("ix_classes_class_code"), table_name="classes")
    op.drop_index(op.f("ix_classes_teacher_id"), table_name="classes")
    op.drop_table("classes")
