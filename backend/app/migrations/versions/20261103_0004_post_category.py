"""post category

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 07:17:37.370903
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_parent_id'), 'categories', ['parent_id'], unique=False)
    op.create_index(op.f('ix_categories_tenant_id'), 'categories', ['tenant_id'], unique=False)
    op.add_column('posts', sa.Column('category_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_posts_category_id'), 'posts', ['category_id'], unique=False)
    op.create_foreign_key('posts_category_id_fkey', 'posts', 'categories', ['category_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('posts_category_id_fkey', 'posts', type_='foreignkey')
    op.drop_index(op.f('ix_posts_category_id'), table_name='posts')
    op.drop_column('posts', 'category_id')
    op.drop_index(op.f('ix_categories_tenant_id'), table_name='categories')
    op.drop_index(op.f('ix_categories_parent_id'), table_name='categories')
    op.drop_table('categories')
