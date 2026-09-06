"""用户实体相关业务逻辑：查询、创建、资料更新与角色分配。"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models import Role, User
from app.models.role import ROLE_USER
from app.services import errors


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """按邮箱查询用户。"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """按主键查询用户。"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession) -> list[User]:
    """按创建时间倒序返回全部用户。"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: Optional[str] = None,
) -> User:
    """创建用户：bcrypt 哈希密码并默认分配 user 角色。"""
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    default_role = (
        await db.execute(select(Role).where(Role.name == ROLE_USER))
    ).scalar_one_or_none()
    if default_role is not None:
        user.roles.append(default_role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_profile(
    db: AsyncSession, user: User, updates: dict
) -> User:
    """仅允许更新白名单字段（当前仅 full_name）。"""
    allowed = {"full_name"}
    for field, value in updates.items():
        if field not in allowed:
            continue
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def assign_role(
    db: AsyncSession, user_id: UUID, role_name: str
) -> User:
    """为用户分配角色（幂等）。"""
    role = (
        await db.execute(select(Role).where(Role.name == role_name))
    ).scalar_one_or_none()
    if role is None:
        raise errors.RoleNotFoundError()
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise errors.UserNotFoundError()
    if not any(r.id == role.id for r in user.roles):
        user.roles.append(role)
    await db.commit()
    await db.refresh(user)
    return user


async def remove_role(
    db: AsyncSession, user_id: UUID, role_name: str
) -> User:
    """移除用户角色。"""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise errors.UserNotFoundError()
    role = (
        await db.execute(select(Role).where(Role.name == role_name))
    ).scalar_one_or_none()
    if role is None:
        raise errors.RoleNotFoundError()
    user.roles = [r for r in user.roles if r.id != role.id]
    await db.commit()
    await db.refresh(user)
    return user


async def soft_delete_user(db: AsyncSession, user_id: UUID) -> User:
    """软删除：将 is_active 置为 False，保留数据完整性。"""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise errors.UserNotFoundError()
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user
