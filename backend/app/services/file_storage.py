from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

from fastapi import UploadFile


@dataclass(frozen=True)
class StoredBlob:
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int


class UploadRejected(Exception):
    def __init__(self, message: str, status_code: int = 415) -> None:
        super().__init__(message)
        self.status_code = status_code


class FileStorage(Protocol):
    async def store(self, upload: UploadFile) -> StoredBlob: ...

    def resolve(self, storage_key: str) -> Path: ...

    def delete(self, storage_key: str) -> None: ...


class LocalFileStorage:
    _allowed = {
        ".pdf": ("application/pdf", b"%PDF-"),
        ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
        ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
        ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
        ".doc": ("application/msword", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK\x03\x04",
        ),
    }

    def __init__(self, root: Path, max_file_size_bytes: int) -> None:
        self._root = root.expanduser().resolve()
        self._max_file_size_bytes = max_file_size_bytes

    async def store(self, upload: UploadFile) -> StoredBlob:
        supplied_name = (upload.filename or "").replace("\\", "/")
        extension = PurePosixPath(supplied_name).suffix.lower()
        allowed = self._allowed.get(extension)
        if allowed is None:
            raise UploadRejected("Unsupported file extension.")

        expected_content_type, signature = allowed
        content_type = (upload.content_type or "").split(";", maxsplit=1)[0].strip().lower()
        if content_type != expected_content_type:
            raise UploadRejected("File extension and MIME type do not match.")

        content = await upload.read(self._max_file_size_bytes + 1)
        if len(content) > self._max_file_size_bytes:
            raise UploadRejected("File exceeds the configured size limit.", status_code=413)
        if not content or not content.startswith(signature):
            raise UploadRejected("File content does not match the allowed format.")

        original_filename = PurePosixPath(supplied_name).name
        original_filename = "".join(
            character for character in original_filename if character.isprintable()
        )[:255]
        if not original_filename:
            raise UploadRejected("A valid filename is required.")

        self._root.mkdir(parents=True, exist_ok=True)
        storage_key = f"{uuid4().hex}{extension}"
        temporary_path = self._root / f".{uuid4().hex}.tmp"
        target_path = self._path_for_key(storage_key)
        try:
            temporary_path.write_bytes(content)
            temporary_path.replace(target_path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise

        return StoredBlob(
            storage_key=storage_key,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=len(content),
        )

    def resolve(self, storage_key: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{32}\.(pdf|jpg|jpeg|png|doc|docx)", storage_key) is None:
            raise FileNotFoundError("Invalid storage key.")
        return self._path_for_key(storage_key)

    def delete(self, storage_key: str) -> None:
        try:
            self.resolve(storage_key).unlink(missing_ok=True)
        except FileNotFoundError:
            return

    def _path_for_key(self, storage_key: str) -> Path:
        path = (self._root / storage_key).resolve()
        if path.parent != self._root:
            raise FileNotFoundError("Invalid storage key.")
        return path


def get_file_storage() -> FileStorage:
    from app.core.config import get_settings

    settings = get_settings()
    return LocalFileStorage(
        settings.upload_storage_path,
        settings.upload_max_file_size_bytes,
    )
