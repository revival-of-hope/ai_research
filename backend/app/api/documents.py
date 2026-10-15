from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import CurrentUser
from app.api.services import Documents
from app.schemas.document import DocumentPublic, SearchHit

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentPublic])
def list_documents(user: CurrentUser, service: Documents):
    return service.list(user.id)


@router.post("", response_model=DocumentPublic, status_code=201)
async def upload_document(
    user: CurrentUser, service: Documents, upload: Annotated[UploadFile, File()]
):
    async def chunks():
        while chunk := await upload.read(1024 * 1024):
            yield chunk

    return await service.upload(
        user.id,
        upload.filename or "upload",
        upload.content_type or "application/octet-stream",
        chunks(),
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, user: CurrentUser, service: Documents):
    service.delete(user.id, document_id)


@router.get("/search", response_model=list[SearchHit])
def search_documents(
    user: CurrentUser, service: Documents, q: str = Query(min_length=2, max_length=500)
):
    return service.search(user.id, q)
