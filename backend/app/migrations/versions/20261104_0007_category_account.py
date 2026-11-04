"""category account

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04 06:19:47.111251
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('account_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_categories_account_id'), 'categories', ['account_id'], unique=False)
    op.create_foreign_key('categories_account_id_fkey', 'categories', 'accounts', ['account_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('categories_account_id_fkey', 'categories', type_='foreignkey')
    op.drop_index(op.f('ix_categories_account_id'), table_name='categories')
    op.drop_column('categories', 'account_id')
