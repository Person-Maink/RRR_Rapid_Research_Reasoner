from services.worker import main as worker


class FakeStore:
    def __init__(self) -> None:
        self.job = {"id": "job-1", "query": "What matters?"}
        self.statuses: list[str] = []
        self.completed = False
        self.failed = False

    def get_job(self, job_id: str):
        return self.job if job_id == "job-1" else None

    def mark_processing(self, job_id: str) -> None:
        self.statuses.append(f"{job_id}:processing")

    def complete_job(
        self, job_id: str, answer: str, retrieved_pages: list[dict]
    ) -> None:
        self.completed = True
        self.answer = answer
        self.retrieved_pages = retrieved_pages

    def fail_job(self, job_id: str, error: str) -> None:
        self.failed = True
        self.error = error


def test_process_job_marks_processing_and_completes() -> None:
    store = FakeStore()
    pages = [{"document_id": "doc-1", "file_name": "paper.pdf", "page_number": 1}]

    worker.process_job(
        "job-1",
        store=store,
        ingest_documents=lambda job_id, store: [],
        retrieve_pages=lambda job_id, query, store: pages,
        reasoner=lambda query, docs: "answer",
    )

    assert store.statuses == ["job-1:processing"]
    assert store.completed
    assert store.answer == "answer"
    assert store.retrieved_pages == pages
    assert not store.failed
