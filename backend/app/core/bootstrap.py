from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.core.security import hash_password
from app.domain.workspace import Account
from app.infrastructure.uow.workspace import SqlWorkspaceUow


def ensure_admin() -> None:
    """Creates the environment-defined administrator once migrations exist."""
    with Session(engine) as session, SqlWorkspaceUow(session) as uow:
        email = str(settings.admin_email).lower()
        admin = uow.accounts.by_email(email)
        if admin:
            if not admin.is_admin or not admin.is_active:
                admin.is_admin = True
                admin.is_active = True
                uow.accounts.save(admin)
                uow.commit()
            return
        uow.accounts.save(
            Account(
                id=None,
                email=email,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
        )
        uow.commit()
