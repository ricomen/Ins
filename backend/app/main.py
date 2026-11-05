from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import protected_router, public_router
from .config import get_settings
from .database import engine, init_db
from .queue import create_redis_pool
from .storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    Storage(settings.storage_dir).ensure_root()
    await init_db()
    app.state.redis = await create_redis_pool()
    try:
        yield
    finally:
        await app.state.redis.close()
        await engine.dispose()


app = FastAPI(
    title="Ins API",
    version="0.0.1",
    description="Сервис скачивания публичного контента Instagram",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(protected_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "Ins API", "docs": "/docs", "health": "/api/health"}


@app.get("/health")
async def health_root() -> dict[str, str]:
    return {"status": "ok"}
