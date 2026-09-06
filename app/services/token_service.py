"""JWT 令牌签发、解码与撤销（不依赖 HTTP 上下文）。"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from jose import JWTError, jwt
from redis.asyncio import Redis

from app.config import settings
from app.core.redis import revoke_jti

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """签发 JWT 访问令牌，附带 type 与 jti 声明。"""
    if expires_delta is not None:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _issue_token(data, TOKEN_TYPE_ACCESS, expire)


def create_refresh_token(data: dict) -> str:
    """签发 JWT 刷新令牌。"""
    expire = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _issue_token(data, TOKEN_TYPE_REFRESH, expire)


def _issue_token(data: dict, token_type: str, expire: datetime) -> str:
    """按类型签发 JWT，附带唯一 jti 便于撤销。"""
    to_encode = data.copy()
    to_encode.update(
        {
            "type": token_type,
            "jti": str(uuid4()),
            "exp": expire,
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验签 JWT，失败抛出 JWTError。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def token_ttl_seconds(payload: dict) -> int:
    """令牌剩余有效秒数，用于黑名单 TTL。"""
    exp = payload.get("exp")
    if not exp:
        return 0
    return max(0, int(exp) - int(_utcnow().timestamp()))


async def revoke_token(redis: Redis, token: str) -> None:
    """解码任意令牌并将其 jti 加入黑名单（解码失败则忽略）。"""
    try:
        payload = decode_token(token)
    except JWTError:
        return
    jti = payload.get("jti")
    if jti:
        await revoke_jti(redis, jti, token_ttl_seconds(payload))
