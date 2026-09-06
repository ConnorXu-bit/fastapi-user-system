"""角色相关的请求/响应模型。"""

import uuid

from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    """角色响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class RoleAssign(BaseModel):
    """为指定用户分配角色。"""

    user_id: uuid.UUID
    role_name: str
