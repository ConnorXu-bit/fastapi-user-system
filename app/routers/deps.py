"""路由层共享鉴权依赖：解析令牌、校验黑名单与权限。"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis, is_jti_revoked
from app.database import get_db
from app.models import User
from app.models.role import ROLE_ADMIN
from app.services import rbac_service, token_service, user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    """从请求头解析并验证 JWT，返回当前用户。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = token_service.decode_token(token)
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if (
            user_id is None
            or jti is None
            or payload.get("type") != token_service.TOKEN_TYPE_ACCESS
        ):
            raise credentials_exception
        uuid_id = UUID(user_id)
    except (JWTError, ValueError):
        raise credentials_exception
    if await is_jti_revoked(redis, jti):
        raise credentials_exception
    user = await user_service.get_user_by_id(db, uuid_id)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """校验当前用户处于激活状态。"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """校验当前用户拥有 admin 角色（兼容旧接口，推荐改用 require_permission）。"""
    if not any(role.name == ROLE_ADMIN for role in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def require_permission(permission_name: str):
    """生成校验指定权限的依赖，供路由通过 Depends 使用。"""

    async def checker(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not await rbac_service.user_has_permission(db, current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return checker
