from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, engine
from app.routers import accounts, auth, posts


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 骨架阶段直接建表；模型稳定后改用 Alembic 迁移
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Matrix Publishing", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(posts.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
