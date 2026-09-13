"""认证相关 API 路由：注册、登录、刷新、登出。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.database import get_db
from app.routers.deps import oauth2_scheme
from app.schemas import LogoutRequest, RefreshTokenRequest, Token, UserCreate, UserOut
from app.services import auth_service, errors

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await auth_service.register_user(db, payload)
    except errors.EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    try:
        user = await auth_service.authenticate_user(
            db, form_data.username, form_data.password
        )
    except errors.InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token, refresh_token = await auth_service.issue_token_pair(user)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Token:
    result = await auth_service.refresh_user_tokens(db, redis, payload.refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    _, access_token, refresh_token = result
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=dict[str, str])
async def logout(
    token: str = Depends(oauth2_scheme),
    payload: Optional[LogoutRequest] = None,
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    await auth_service.logout(
        redis,
        access_token=token,
        refresh_token=payload.refresh_token if payload else None,
    )
    return {"message": "Logged out"}
