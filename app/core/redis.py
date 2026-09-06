"""Redis 客户端与 JWT 撤销（黑名单）工具。"""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis

from app.config import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

BLACKLIST_PREFIX = "token:blacklist:"


def blacklist_key(jti: str) -> str:
    """按 jti 生成黑名单键。"""
    return f"{BLACKLIST_PREFIX}{jti}"


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI 依赖：提供共享 Redis 客户端。"""
    yield redis_client


async def revoke_jti(redis: Redis, jti: str, ttl_seconds: int) -> None:
    """将 jti 加入黑名单，TTL 等于 token 剩余寿命。"""
    if ttl_seconds > 0:
        await redis.set(blacklist_key(jti), "1", ex=ttl_seconds)


async def is_jti_revoked(redis: Redis, jti: str) -> bool:
    """判断 jti 是否已被撤销。"""
    return bool(await redis.exists(blacklist_key(jti)))
