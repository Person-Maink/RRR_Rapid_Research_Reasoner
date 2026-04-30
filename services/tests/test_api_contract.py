from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("multipart")

from services.api_gateway import main as api


class FakeStore:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, object]] = {}
        self.documents: dict[str, dict[str, object]] = {}
        self.failed: list[str] = []

    def init_db(self) -> None:
        return None

    def create_job(self, query: str) -> str:
        self.jobs["job-1"] = {
            "id": "job-1",
            "query": query,
            "status": "queued",
            "answer": None,
            "error": None,
        }
        return "job-1"

    def add_document(self, file) -> None:
        self.documents[file.document_id] = {
            "id": file.document_id,
            "file_name": file.file_name,
            "storage_path": file.storage_path,
        }

    def fail_job(self, job_id: str, error: str) -> None:
        self.failed.append(job_id)
        self.jobs[job_id]["status"] = "failed"
        self.jobs[job_id]["error"] = error

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def list_retrieved_pages(self, _job_id: str):
        return []

    def get_document(self, document_id: str):
        return self.documents.get(document_id)


class FakeQueue:
    def __init__(self) -> None:
        self.published: list[str] = []

    def publish_job(self, job_id: str) -> None:
        self.published.append(job_id)


def test_create_chat_job_accepts_pdf_and_returns_poll_url(
    monkeypatch, tmp_path
) -> None:
    fake_store = FakeStore()
    fake_queue = FakeQueue()

    monkeypatch.setattr(api, "JOB_STORE", fake_store)
    monkeypatch.setattr(api, "QUEUE", fake_queue)
    monkeypatch.setattr(api, "STORAGE", api.LocalStorageAdapter(Path(tmp_path)))

    with TestClient(api.app) as client:
        response = client.post(
            "/chat/jobs",
            data={"query": "What is the contribution?"},
            files={"files": ("paper.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-1"
    assert fake_queue.published == ["job-1"]


def test_create_chat_job_rejects_non_pdf(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(api, "JOB_STORE", FakeStore())
    monkeypatch.setattr(api, "QUEUE", FakeQueue())
    monkeypatch.setattr(api, "STORAGE", api.LocalStorageAdapter(Path(tmp_path)))

    with TestClient(api.app) as client:
        response = client.post(
            "/chat/jobs",
            data={"query": "What is this?"},
            files={"files": ("notes.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 400
    assert "Only PDF uploads" in response.json()["detail"]
