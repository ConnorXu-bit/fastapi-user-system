"""认证相关的请求/响应模型。"""

from typing import Optional

from pydantic import BaseModel, EmailStr


class UserLogin(BaseModel):
    """登录请求（兼容 JSON 表单之外的场景）。"""

    email: EmailStr
    password: str


class Token(BaseModel):
    """登录/刷新成功返回的令牌对。"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """使用刷新令牌换取新的令牌对。"""

    refresh_token: str


class LogoutRequest(BaseModel):
    """登出时可一并撤销刷新令牌。"""

    refresh_token: Optional[str] = None
