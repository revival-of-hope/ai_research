from fastapi import APIRouter

from app.api.deps import AdminUser
from app.api.services import Accounts
from app.schemas.admin import AdminUserPublic, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserPublic])
def list_users(actor: AdminUser, service: Accounts):
    return service.users(actor)


@router.patch("/users/{user_id}", response_model=AdminUserPublic)
def update_user(user_id: int, payload: AdminUserUpdate, actor: AdminUser, service: Accounts):
    return service.change_user(actor, user_id, payload.model_dump(exclude_none=True))
