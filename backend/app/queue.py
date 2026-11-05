from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from .config import get_settings


async def create_redis_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
