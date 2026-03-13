from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


class StorageAdapter(ABC):
    @abstractmethod
    async def save_upload(self, upload: UploadFile, prefix: str = "uploads") -> str:
        raise NotImplementedError


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, prefix: str = "uploads") -> str:
        folder = self.root / prefix
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = upload.filename or "file"
        target = folder / f"{uuid4()}_{safe_name}"
        content = await upload.read()
        target.write_bytes(content)
        return str(target)


class S3StorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        self.bucket = settings.s3_bucket

    async def save_upload(self, upload: UploadFile, prefix: str = "uploads") -> str:
        raise NotImplementedError("S3 storage adapter is not configured in this build. Use STORAGE_BACKEND=local for local development.")


def build_storage() -> StorageAdapter:
    backend = settings.storage_backend.lower().strip()
    if backend == "local":
        return LocalStorageAdapter(settings.storage_root)
    if backend == "s3":
        return S3StorageAdapter()
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


storage = build_storage()
