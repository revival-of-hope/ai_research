from fastapi import APIRouter, Response

from app.api.deps import CurrentUser
from app.api.services import Accounts
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic

router = APIRouter(tags=["authentication"])


def set_login_cookie(response: Response, user_id: int):
    response.set_cookie(
        "access_token",
        create_access_token(user_id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/register", response_model=UserPublic, status_code=201)
def register(payload: RegisterRequest, response: Response, service: Accounts):
    user = service.register(str(payload.email), payload.password)
    set_login_cookie(response, user.id)
    return user


@router.post("/auth/login", response_model=UserPublic)
def login(payload: LoginRequest, response: Response, service: Accounts):
    user = service.login(str(payload.email), payload.password)
    set_login_cookie(response, user.id)
    return user


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("access_token", path="/")


@router.get("/account/me", response_model=UserPublic)
def me(user: CurrentUser):
    return user
