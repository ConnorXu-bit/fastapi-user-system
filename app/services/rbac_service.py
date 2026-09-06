"""RBAC 业务逻辑：默认种子数据与权限判定。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Permission, Role, User, role_permissions, user_roles
from app.models.permission import PERM_ROLE_ASSIGN, PERM_USER_DELETE, PERM_USER_LIST
from app.models.role import ROLE_ADMIN, ROLE_USER

DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: [PERM_USER_LIST, PERM_USER_DELETE, PERM_ROLE_ASSIGN],
    ROLE_USER: [],
}


async def seed_rbac(db: AsyncSession) -> None:
    """幂等写入默认角色与权限（角色表为空时执行）。"""
    exists = (await db.execute(select(Role.id).limit(1))).first()
    if exists is not None:
        return
    permission_objs: dict[str, Permission] = {}
    for permissions in DEFAULT_PERMISSIONS.values():
        for name in permissions:
            if name not in permission_objs:
                permission_objs[name] = Permission(name=name)
                db.add(permission_objs[name])
    for name, permissions in DEFAULT_PERMISSIONS.items():
        role = Role(
            name=name,
            description=f"Default {name} role",
            permissions=[permission_objs[p] for p in permissions],
        )
        db.add(role)
    await db.commit()


async def user_has_permission(
    db: AsyncSession, user: User, permission_name: str
) -> bool:
    """判断用户是否通过其角色拥有指定权限。"""
    stmt = (
        select(Permission.id)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
        .where(
            user_roles.c.user_id == user.id,
            Permission.name == permission_name,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.first() is not None
