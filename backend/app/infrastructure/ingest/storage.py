import secrets
from collections.abc import AsyncIterator
from pathlib import Path

from app.domain.workspace import InvalidInput


class UploadTooLarge(InvalidInput):
    pass


class LocalDocumentStorage:
    def __init__(self, root: Path, max_bytes: int):
        self.root = root.resolve()
        self.max_bytes = max_bytes

    async def save(self, chunks: AsyncIterator[bytes], user_id: int, suffix: str):
        directory = self.root / str(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{secrets.token_hex(16)}{suffix}"
        size = 0
        try:
            with path.open("wb") as target:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise UploadTooLarge(f"文件不能超过 {self.max_bytes // 1024 // 1024} MB")
                    target.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path, size

    def remove(self, value: str):
        path = Path(value).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidInput("资料存储路径不在上传目录内")
        path.unlink(missing_ok=True)
