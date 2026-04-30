import logging
import time
from collections.abc import Callable
from typing import Any

from services.job_store import PostgresJobStore
from services.logging_config import configure_logging
from services.queue import RabbitMQClient

configure_logging("worker")
LOGGER = logging.getLogger(__name__)
JOB_STORE = PostgresJobStore()
QUEUE = RabbitMQClient()


def process_job(
    job_id: str,
    store: PostgresJobStore = JOB_STORE,
    ingest_documents: Callable[[str, Any], list[dict[str, Any]]] | None = None,
    retrieve_pages: Callable[[str, str, Any], list[dict[str, Any]]] | None = None,
    reasoner: Callable[[str, list[dict[str, Any]]], str] | None = None,
) -> None:
    if ingest_documents is None:
        from services.ingestion_service import ingest_job_documents as ingest_documents
    if retrieve_pages is None:
        from services.retrieval_service import retrieve_for_job as retrieve_pages
    if reasoner is None:
        from services.reasoning_service import reason as reasoner

    started = time.perf_counter()
    job = store.get_job(job_id)
    if not job:
        LOGGER.warning("Skipping unknown job", extra={"job_id": job_id})
        return

    try:
        store.mark_processing(job_id)
        ingest_documents(job_id, store)
        retrieved_pages = retrieve_pages(job_id, job["query"], store)
        answer = reasoner(job["query"], retrieved_pages)
        store.complete_job(job_id, answer, retrieved_pages)
        LOGGER.info(
            "Completed job",
            extra={
                "job_id": job_id,
                "status": "completed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
    except Exception as exc:
        store.fail_job(job_id, str(exc))
        LOGGER.exception(
            "Failed job",
            extra={
                "job_id": job_id,
                "status": "failed",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        raise


def main() -> None:
    JOB_STORE.init_db()
    QUEUE.consume_jobs(process_job)


if __name__ == "__main__":
    main()
