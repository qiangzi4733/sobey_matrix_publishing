"""post video cover options

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03 09:20:32.937096
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('cover_path', sa.String(length=500), nullable=True))
    op.add_column('posts', sa.Column('options', sa.JSON(), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('posts', 'options')
    op.drop_column('posts', 'cover_path')
