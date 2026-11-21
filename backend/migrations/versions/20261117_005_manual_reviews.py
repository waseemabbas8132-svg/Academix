"""Private manual review history and revision attachment ownership.

Revision ID: 20261117_manual_reviews
Revises: 20261114_ai_evaluations
"""
from alembic import op
import sqlalchemy as sa

revision = '20261117_manual_reviews'
down_revision = '20261114_ai_evaluations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('submission_reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('submission_id', sa.String(36), sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rubric_signature', sa.String(64), nullable=False),
        sa.Column('assignment_version',sa.DateTime(timezone=True),nullable=False),
        sa.Column('rubric_version',sa.DateTime(timezone=True),nullable=True),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('actor', sa.String(255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('submission_id','version', name='uq_review_version'),
        sa.CheckConstraint("version > 0",name='ck_review_version'),
        sa.CheckConstraint("state IN ('draft','reviewed','released','returned')",name='ck_review_state'))
    op.create_index('ix_submission_reviews_submission_id','submission_reviews',['submission_id'])
    with op.batch_alter_table('uploaded_files') as batch:
        batch.add_column(sa.Column('submission_revision_id', sa.String(36), nullable=True))
        batch.create_foreign_key('fk_file_revision','submission_revisions',['submission_revision_id'],['id'],ondelete='CASCADE')
        batch.create_index('ix_uploaded_files_submission_revision_id',['submission_revision_id'])
        batch.drop_constraint('ck_uploaded_files_single_parent',type_='check')
        batch.create_check_constraint('ck_uploaded_files_single_parent',
            '(assignment_id IS NOT NULL AND submission_id IS NULL AND submission_revision_id IS NULL) OR '
            '(assignment_id IS NULL AND submission_id IS NOT NULL AND submission_revision_id IS NULL) OR '
            '(assignment_id IS NULL AND submission_id IS NULL AND submission_revision_id IS NOT NULL)')


def downgrade():
    # No silent history loss or re-merging old files into the current attempt.
    raise RuntimeError('History-preserving migration: downgrade requires an explicit archival plan.')
