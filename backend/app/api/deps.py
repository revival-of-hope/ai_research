from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from jwt import InvalidTokenError
from sqlmodel import Session

from app.core.db import get_session
from app.core.security import decode_access_token
from app.domain.workspace import Account
from app.infrastructure.uow.workspace import SqlWorkspaceUow

SessionDep = Annotated[Session, Depends(get_session)]


def current_user(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Account:
    token = access_token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        user_id = decode_access_token(token)
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from None
    with SqlWorkspaceUow(session) as uow:
        user = uow.accounts.get(user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is unavailable")
    return user


CurrentUser = Annotated[Account, Depends(current_user)]


def require_admin(user: CurrentUser) -> Account:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


AdminUser = Annotated[Account, Depends(require_admin)]
