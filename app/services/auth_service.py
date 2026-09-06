"""认证与令牌生命周期业务逻辑：注册、登录校验、刷新轮换、登出撤销。"""

from typing import Optional
from uuid import UUID

from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import is_jti_revoked, revoke_jti
from app.core.security import verify_password
from app.models import User
from app.schemas.user import UserCreate
from app.services import errors, token_service, user_service


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    """注册新用户：邮箱唯一性校验由业务层保证。"""
    existing = await user_service.get_user_by_email(db, payload.email)
    if existing is not None:
        raise errors.EmailAlreadyRegisteredError()
    return await user_service.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """按邮箱查询用户并验证密码，成功返回用户，失败返回 None。"""
    user = await user_service.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


async def issue_token_pair(user: User) -> tuple[str, str]:
    """为用户签发访问令牌与刷新令牌。"""
    access_token = token_service.create_access_token({"sub": str(user.id)})
    refresh_token = token_service.create_refresh_token({"sub": str(user.id)})
    return access_token, refresh_token


async def refresh_user_tokens(
    db: AsyncSession, redis: Redis, refresh_token: str
) -> Optional[tuple[User, str, str]]:
    """校验刷新令牌；合法则撤销旧令牌并签发新的令牌对（轮换防重放）。"""
    try:
        payload = token_service.decode_token(refresh_token)
    except JWTError:
        return None
    jti = payload.get("jti")
    if payload.get("type") != token_service.TOKEN_TYPE_REFRESH or jti is None:
        return None
    if await is_jti_revoked(redis, jti):
        return None
    try:
        user_id = UUID(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = await user_service.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    await revoke_jti(redis, jti, token_service.token_ttl_seconds(payload))
    access_token, new_refresh_token = await issue_token_pair(user)
    return user, access_token, new_refresh_token


async def logout(
    redis: Redis,
    access_token: str,
    refresh_token: Optional[str] = None,
) -> None:
    """将访问令牌（及可选的刷新令牌）加入黑名单。"""
    await token_service.revoke_token(redis, access_token)
    if refresh_token:
        await token_service.revoke_token(redis, refresh_token)
