from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.db import engine

# 引入 Alembic 之前由 create_all 建的库，表结构等于 0001
BASELINE = "0001"


def upgrade() -> None:
    """启动时把数据库升级到最新版本。

    用 advisory lock 串行化：以后多个进程同时启动时只有一个在迁移。"""
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(20261103)"))
        try:
            tables = inspect(connection).get_table_names()
            config.attributes["connection"] = connection
            if "posts" in tables and "alembic_version" not in tables:
                command.stamp(config, BASELINE)
            command.upgrade(config, "head")
            connection.commit()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(20261103)"))
