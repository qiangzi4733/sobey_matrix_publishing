from alembic import context

from app import models  # noqa: F401  注册所有表，autogenerate 才能比较
from app.db import Base, engine


def run(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


# 启动时由 app.migrate 传入已持有迁移锁的连接；命令行运行时自己连
connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with engine.connect() as connection:
        run(connection)
