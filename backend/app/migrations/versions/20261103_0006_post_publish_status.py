"""审核状态和发布状态分开；草稿

审核状态去掉 published（改为 approved），发布状态改由 posts.current_task_id 指向的任务决定。
单账号之前的旧内容 account_id 为空，从它的发布任务补上（账号已移除的仍为空）。

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('current_task_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'posts_current_task_id_fkey', 'posts', 'publish_tasks', ['current_task_id'], ['id'], ondelete='SET NULL'
    )
    # 旧数据一条内容可能有多个任务（多账号时期），取最新的一个
    op.execute(
        "UPDATE posts SET current_task_id = (SELECT max(t.id) FROM publish_tasks t WHERE t.post_id = posts.id)"
        " WHERE review_status = 'published'"
    )
    op.execute(
        "UPDATE posts SET account_id = t.account_id FROM publish_tasks t"
        " WHERE t.id = posts.current_task_id AND posts.account_id IS NULL AND t.account_id IS NOT NULL"
    )
    op.execute("UPDATE posts SET review_status = 'approved' WHERE review_status = 'published'")
    op.alter_column('posts', 'review_status', server_default=None)


def downgrade() -> None:
    op.alter_column('posts', 'review_status', server_default='published')
    op.execute("UPDATE posts SET review_status = 'published' WHERE current_task_id IS NOT NULL")
    op.execute("UPDATE posts SET review_status = 'pending' WHERE review_status = 'draft'")
    op.drop_constraint('posts_current_task_id_fkey', 'posts', type_='foreignkey')
    op.drop_column('posts', 'current_task_id')
