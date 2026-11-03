"""post single account

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 04:42:37.109060
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('account_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_posts_account_id'), 'posts', ['account_id'], unique=False)
    op.create_foreign_key('posts_account_id_fkey', 'posts', 'accounts', ['account_id'], ['id'], ondelete='SET NULL')
    # 已发布的内容发布记录在 publish_tasks 里，不需要这个字段；未发布的选过多个账号时只保留第一个
    op.execute(
        "UPDATE posts SET account_id = a.id FROM accounts a"
        " WHERE posts.review_status <> 'published' AND a.id = (posts.account_ids->>0)::int"
    )
    op.drop_column('posts', 'account_ids')


def downgrade() -> None:
    op.add_column('posts', sa.Column('account_ids', postgresql.JSON(astext_type=sa.Text()), server_default=sa.text("'[]'::json"), autoincrement=False, nullable=False))
    op.execute("UPDATE posts SET account_ids = json_build_array(account_id) WHERE account_id IS NOT NULL")
    op.drop_constraint('posts_account_id_fkey', 'posts', type_='foreignkey')
    op.drop_index(op.f('ix_posts_account_id'), table_name='posts')
    op.drop_column('posts', 'account_id')
