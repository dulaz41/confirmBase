"""Initial waitlist table migration for ConfirmBase

Revision ID: 001_initial_waitlist
Revises: 
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_waitlist'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=50), server_default='tenant', nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('phone_normalized', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('email_normalized', sa.String(length=255), nullable=True),
        sa.Column('areas', sa.String(length=255), nullable=True),
        sa.Column('budget', sa.String(length=100), nullable=True),
        sa.Column('timing', sa.String(length=100), nullable=True),
        sa.Column('redflags', sa.String(length=500), nullable=True),
        sa.Column('taste', sa.String(length=1000), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=True),
        sa.Column('listings', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('marketing_consent', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('consent_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_waitlist_entries'),
        sa.UniqueConstraint('phone_normalized', 'type', name='uq_waitlist_entries_phone_type'),
    )
    op.create_index(
        'ix_waitlist_entries_phone_normalized',
        'waitlist_entries',
        ['phone_normalized'],
        unique=False,
    )
    op.create_index(
        'ix_waitlist_entries_email_normalized',
        'waitlist_entries',
        ['email_normalized'],
        unique=False,
    )
    op.create_index(
        'ix_waitlist_entries_type',
        'waitlist_entries',
        ['type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_waitlist_entries_type', table_name='waitlist_entries')
    op.drop_index('ix_waitlist_entries_email_normalized', table_name='waitlist_entries')
    op.drop_index('ix_waitlist_entries_phone_normalized', table_name='waitlist_entries')
    op.drop_table('waitlist_entries')
