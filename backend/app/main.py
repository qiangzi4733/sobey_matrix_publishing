from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.migrate import upgrade
from app.routers import accounts, auth, posts, wechat_mp


@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade()
    yield


app = FastAPI(title="Matrix Publishing", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(posts.router)
app.include_router(wechat_mp.router)

if get_settings().wechat_mp_mock:
    from app import mock_wechat

    app.include_router(mock_wechat.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
