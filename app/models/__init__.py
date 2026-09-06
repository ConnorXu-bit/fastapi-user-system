"""ORM 模型包：集中导入，供应用与 Alembic 的 metadata 使用。"""

from app.models.associations import role_permissions, user_roles
from app.models.permission import PERM_ROLE_ASSIGN, PERM_USER_DELETE, PERM_USER_LIST, Permission
from app.models.role import ROLE_ADMIN, ROLE_USER, Role
from app.models.user import User

__all__ = [
    "User",
    "Role",
    "Permission",
    "user_roles",
    "role_permissions",
    "ROLE_ADMIN",
    "ROLE_USER",
    "PERM_USER_LIST",
    "PERM_USER_DELETE",
    "PERM_ROLE_ASSIGN",
]
