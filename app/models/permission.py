"""权限点 ORM 模型与内置权限常量。"""

import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import role_permissions

PERM_USER_LIST = "user:list"
PERM_USER_DELETE = "user:delete"
PERM_ROLE_ASSIGN = "role:assign"


class Permission(Base):
    """权限点，如 user:list / user:delete。"""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    roles: Mapped[list["Role"]] = relationship(
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )
