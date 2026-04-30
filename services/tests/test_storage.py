import asyncio
from io import BytesIO

import pytest
from services.storage import LocalStorageAdapter, is_pdf_upload, sanitize_file_name


class FakeUpload:
    def __init__(
        self,
        filename: str,
        body: bytes,
        content_type: str = "application/pdf",
    ):
        self.filename = filename
        self.content_type = content_type
        self._file = BytesIO(body)

    async def read(self, size: int = -1) -> bytes:
        return self._file.read(size)

    async def seek(self, offset: int) -> None:
        self._file.seek(offset)


def test_pdf_upload_validation_accepts_pdf() -> None:
    assert is_pdf_upload("paper.pdf", "application/pdf")


def test_pdf_upload_validation_rejects_non_pdf() -> None:
    assert not is_pdf_upload("paper.txt", "text/plain")


def test_sanitize_file_name_removes_path_and_unsafe_characters() -> None:
    assert sanitize_file_name("../My Paper (final).pdf") == "My_Paper_final_.pdf"


def test_local_storage_saves_upload_under_job_directory(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)
    stored = asyncio.run(
        storage.save_upload(
            "job-1",
            FakeUpload("paper.pdf", b"%PDF-1.4"),
        )
    )

    assert stored.job_id == "job-1"
    assert stored.file_name == "paper.pdf"
    assert stored.size_bytes == 8
    assert (tmp_path / "job-1" / "uploads").exists()


def test_local_storage_rejects_oversized_upload(tmp_path) -> None:
    storage = LocalStorageAdapter(tmp_path)

    with pytest.raises(ValueError):
        asyncio.run(
            storage.save_upload(
                "job-1",
                FakeUpload("paper.pdf", b"123456"),
                max_bytes=3,
            )
        )
