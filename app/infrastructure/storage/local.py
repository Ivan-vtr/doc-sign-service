from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings

from app.domain.exceptions import FileStorageError
from app.domain.ports import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.MEDIA_ROOT)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _full_path(self, file_path: str) -> Path:
        full = (self.base_dir / file_path).resolve()
        if not str(full).startswith(str(self.base_dir.resolve())):
            raise FileStorageError("Path traversal detected")
        return full

    def save_file(self, file_path: str, data: bytes) -> str:
        full = self._full_path(file_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        try:
            full.write_bytes(data)
        except OSError as e:
            raise FileStorageError(f"Failed to save file: {e}")
        return file_path

    def read_file(self, file_path: str) -> bytes:
        full = self._full_path(file_path)
        if not full.exists():
            raise FileStorageError(f"File not found: {file_path}")
        try:
            return full.read_bytes()
        except OSError as e:
            raise FileStorageError(f"Failed to read file: {e}")

    def delete_file(self, file_path: str) -> None:
        full = self._full_path(file_path)
        if full.exists():
            try:
                full.unlink()
            except OSError as e:
                raise FileStorageError(f"Failed to delete file: {e}")

    def file_exists(self, file_path: str) -> bool:
        return self._full_path(file_path).exists()
