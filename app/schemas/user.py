"""用户相关的请求/响应模型。"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.role import RoleOut


class UserCreate(BaseModel):
    """注册新用户。"""

    email: EmailStr
    password: str = Field(min_length=6)
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    """更新当前用户资料（仅允许 full_name）。"""

    full_name: Optional[str] = None


class UserOut(BaseModel):
    """用户响应模型（绝不包含 hashed_password）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    roles: list[RoleOut] = []
    created_at: datetime
