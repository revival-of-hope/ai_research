"""Composition root for request-scoped application services."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.application.service.accounts import AccountService
from app.application.service.documents import DocumentService
from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.core.endpoints import validate_provider_url
from app.core.security import hash_password, verify_password
from app.infrastructure.ingest.extract import SUPPORTED_EXTENSIONS
from app.infrastructure.ingest.pipeline import parse_document
from app.infrastructure.ingest.storage import LocalDocumentStorage
from app.infrastructure.uow.workspace import SqlWorkspaceUow


def account_service(session: SessionDep) -> AccountService:
    return AccountService(
        SqlWorkspaceUow(session),
        hash_password=hash_password,
        verify_password=verify_password,
        encrypt=encrypt_secret,
        validate_url=validate_provider_url,
    )


def document_service(session: SessionDep) -> DocumentService:
    storage = LocalDocumentStorage(settings.upload_dir, settings.max_upload_mb * 1024 * 1024)
    return DocumentService(
        SqlWorkspaceUow(session),
        storage=storage,
        parse=parse_document,
        extensions=SUPPORTED_EXTENSIONS,
    )


Accounts = Annotated[AccountService, Depends(account_service)]
Documents = Annotated[DocumentService, Depends(document_service)]
