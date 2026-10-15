from collections.abc import AsyncIterator, Callable
from pathlib import Path

from anyio import to_thread

from app.application.uow.workspace import WorkspaceUow
from app.domain.workspace import InvalidInput, LibraryDocument


class DocumentService:
    def __init__(self, uow: WorkspaceUow, *, storage, parse: Callable, extensions: set[str]):
        self.uow, self.storage, self.parse, self.extensions = uow, storage, parse, extensions

    def list(self, user_id: int):
        with self.uow:
            return self.uow.documents.list(user_id)

    async def upload(
        self, user_id: int, filename: str, media_type: str, content: AsyncIterator[bytes]
    ) -> LibraryDocument:
        # Both path conventions are normalized; the storage key is generated independently.
        filename = Path(filename.replace("\\", "/")).name[:255] or "upload"
        suffix = Path(filename).suffix.lower()
        if suffix not in self.extensions:
            raise InvalidInput("支持 TXT、Markdown、CSV、DOCX 和含文本的 PDF")
        path, size = await self.storage.save(content, user_id, suffix)
        document = LibraryDocument(None, user_id, filename, media_type, size, str(path))
        try:
            with self.uow:
                document = self.uow.documents.save(document)
                self.uow.commit()
        except BaseException:
            self.storage.remove(str(path))
            raise
        try:
            chunks = await to_thread.run_sync(self.parse, path)
            document.complete(chunks)
            with self.uow:
                self.uow.documents.replace_chunks(document.id, chunks)
                document = self.uow.documents.save(document)
                self.uow.commit()
        except Exception as error:  # noqa: BLE001 - parsers raise heterogeneous safe input errors.
            document.fail(str(error))
            with self.uow:
                document = self.uow.documents.save(document)
                self.uow.commit()
        return document

    def delete(self, user_id: int, document_id: int):
        with self.uow:
            document = self.uow.documents.owned(user_id, document_id)
            self.uow.documents.delete(document)
            self.uow.commit()
        self.storage.remove(document.stored_path)

    def search(self, user_id: int, query: str):
        with self.uow:
            return self.uow.documents.search(user_id, query)
