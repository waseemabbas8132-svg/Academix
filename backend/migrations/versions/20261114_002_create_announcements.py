"""create announcements

Revision ID: 20261114_announcements
Revises: 20261114_classes
Create Date: 2026-11-14 11:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261114_announcements"
down_revision = "20261114_classes"
branch_labels = None
depends_on = None


def _existing_announcements_table_matches() -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("announcements"):
        return False

    expected_columns = {
        "id": (sa.String, 36),
        "class_id": (sa.String, 36),
        "teacher_id": (sa.String, 255),
        "title": (sa.String, 200),
        "content": (sa.Text, None),
        "is_pinned": (sa.Boolean, None),
        "created_at": (sa.DateTime, None),
        "updated_at": (sa.DateTime, None),
    }
    columns = {column["name"]: column for column in inspector.get_columns("announcements")}
    if set(columns) != set(expected_columns):
        raise RuntimeError("The existing announcements table does not match this migration.")

    for name, (column_type, length) in expected_columns.items():
        existing_type = columns[name]["type"]
        if not isinstance(existing_type, column_type):
            raise RuntimeError("The existing announcements table does not match this migration.")
        if length is not None and getattr(existing_type, "length", None) != length:
            raise RuntimeError("The existing announcements table does not match this migration.")
        if columns[name]["nullable"]:
            raise RuntimeError("The existing announcements table does not match this migration.")

    primary_key = inspector.get_pk_constraint("announcements")
    if primary_key["constrained_columns"] != ["id"]:
        raise RuntimeError("The existing announcements table does not match this migration.")
    foreign_keys = inspector.get_foreign_keys("announcements")
    if not any(
        foreign_key["constrained_columns"] == ["class_id"]
        and foreign_key["referred_table"] == "classes"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in foreign_keys
    ):
        raise RuntimeError("The existing announcements table does not match this migration.")
    indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("announcements")
    }
    if not {("class_id",), ("teacher_id",)}.issubset(indexes):
        raise RuntimeError("The existing announcements table does not match this migration.")
    return True


def upgrade() -> None:
    if _existing_announcements_table_matches():
        return

    op.create_table(
        "announcements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name="fk_announcements_class_id_classes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_announcements_class_id"),
        "announcements",
        ["class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_announcements_teacher_id"),
        "announcements",
        ["teacher_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_announcements_teacher_id"), table_name="announcements")
    op.drop_index(op.f("ix_announcements_class_id"), table_name="announcements")
    op.drop_table("announcements")
