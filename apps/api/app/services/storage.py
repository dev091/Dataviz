from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


class LocalStorage:
    def __init__(self) -> None:
        self.root = Path(settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, prefix: str = "uploads") -> str:
        folder = self.root / prefix
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = upload.filename or "file"
        target = folder / f"{uuid4()}_{safe_name}"
        content = await upload.read()
        target.write_bytes(content)
        return str(target)


storage = LocalStorage()
