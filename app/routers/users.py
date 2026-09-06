"""用户管理 API 路由：个人信息与管理员操作。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.permission import PERM_ROLE_ASSIGN, PERM_USER_DELETE, PERM_USER_LIST
from app.routers.deps import get_current_active_user, require_permission
from app.schemas import RoleAssign, UserOut, UserUpdate
from app.services import errors, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user=Depends(get_current_active_user),
):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    updates = payload.model_dump(exclude_unset=True)
    return await user_service.update_user_profile(db, current_user, updates)


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(PERM_USER_LIST)),
):
    return await user_service.list_users(db)


@router.post("/assign-role", response_model=UserOut)
async def assign_role(
    payload: RoleAssign,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(PERM_ROLE_ASSIGN)),
):
    try:
        return await user_service.assign_role(db, payload.user_id, payload.role_name)
    except errors.RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found",
        )
    except errors.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.delete("/{user_id}/roles/{role_name}", response_model=UserOut)
async def remove_role(
    user_id: UUID,
    role_name: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(PERM_ROLE_ASSIGN)),
):
    try:
        return await user_service.remove_role(db, user_id, role_name)
    except errors.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except errors.RoleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found",
        )


@router.delete("/{user_id}", response_model=dict[str, str])
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(PERM_USER_DELETE)),
) -> dict[str, str]:
    try:
        await user_service.soft_delete_user(db, user_id)
    except errors.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"message": "User deactivated"}
