import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from services.environment import JOBS_DIR, MAX_UPLOAD_BYTES

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredFile:
    document_id: str
    job_id: str
    file_name: str
    storage_path: str
    content_type: str
    size_bytes: int


def is_pdf_upload(file_name: str | None, content_type: str | None) -> bool:
    if not file_name or not file_name.lower().endswith(".pdf"):
        return False
    return content_type in PDF_CONTENT_TYPES or content_type is None


def sanitize_file_name(file_name: str) -> str:
    cleaned = FILENAME_RE.sub("_", Path(file_name).name).strip("._")
    return cleaned or "document.pdf"


class LocalStorageAdapter:
    def __init__(self, root: Path = JOBS_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(
        self,
        job_id: str,
        upload: UploadFile,
        max_bytes: int = MAX_UPLOAD_BYTES,
    ) -> StoredFile:
        document_id = str(uuid.uuid4())
        safe_name = sanitize_file_name(upload.filename or "document.pdf")
        job_dir = self.root / job_id / "uploads"
        job_dir.mkdir(parents=True, exist_ok=True)

        destination = job_dir / f"{document_id}-{safe_name}"
        total = 0

        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise ValueError(
                        f"{safe_name} exceeds the {max_bytes // (1024 * 1024)} MB limit"
                    )
                output.write(chunk)

        await upload.seek(0)
        return StoredFile(
            document_id=document_id,
            job_id=job_id,
            file_name=safe_name,
            storage_path=str(destination),
            content_type=upload.content_type or "application/pdf",
            size_bytes=total,
        )

    def open_pdf(self, storage_path: str) -> BinaryIO:
        return Path(storage_path).open("rb")
