import logging
import time
import uuid
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from services.environment import (
    DATABASE_URL,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from services.storage import StoredFile

LOGGER = logging.getLogger(__name__)


class PostgresJobStore:
    def connect(self):
        if DATABASE_URL:
            return psycopg2.connect(DATABASE_URL)

        return psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )

    def init_db(self, retries: int = 10, delay_seconds: float = 2.0) -> None:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                with self.connect() as conn:
                    self._create_tables(conn)
                return
            except psycopg2.OperationalError as exc:
                last_error = exc
                LOGGER.warning(
                    "Postgres is not ready yet",
                    extra={"attempt": attempt, "max_attempts": retries},
                )
                time.sleep(delay_seconds)

        if last_error:
            raise last_error

    def _create_tables(self, conn) -> None:
        with conn.cursor() as cur:
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_jobs (
                        id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        status TEXT NOT NULL,
                        answer TEXT,
                        error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS uploaded_documents (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES chat_jobs(id) ON DELETE CASCADE,
                        file_name TEXT NOT NULL,
                        storage_path TEXT NOT NULL,
                        content_type TEXT,
                        size_bytes BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS document_pages (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES chat_jobs(id) ON DELETE CASCADE,
                        document_id TEXT NOT NULL REFERENCES uploaded_documents(id)
                            ON DELETE CASCADE,
                        file_name TEXT NOT NULL,
                        page_number INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(document_id, page_number)
                    );
                    """)
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS retrieved_pages (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES chat_jobs(id) ON DELETE CASCADE,
                        document_id TEXT NOT NULL REFERENCES uploaded_documents(id)
                            ON DELETE CASCADE,
                        file_name TEXT NOT NULL,
                        page_number INTEGER NOT NULL,
                        score DOUBLE PRECISION,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)

    def create_job(self, query: str) -> str:
        job_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_jobs (id, query, status)
                    VALUES (%s, %s, 'queued');
                    """,
                    (job_id, query),
                )
        return job_id

    def add_document(self, file: StoredFile) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO uploaded_documents (
                        id, job_id, file_name, storage_path, content_type, size_bytes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        file.document_id,
                        file.job_id,
                        file.file_name,
                        file.storage_path,
                        file.content_type,
                        file.size_bytes,
                    ),
                )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM chat_jobs WHERE id = %s;", (job_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM uploaded_documents WHERE id = %s;",
                    (document_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def list_documents(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM uploaded_documents
                    WHERE job_id = %s
                    ORDER BY created_at ASC;
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def replace_document_pages(self, job_id: str, pages: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_pages WHERE job_id = %s;", (job_id,))
                for page in pages:
                    cur.execute(
                        """
                        INSERT INTO document_pages (
                            job_id, document_id, file_name, page_number, text
                        )
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            job_id,
                            page["document_id"],
                            page["file_name"],
                            page["page_number"],
                            page["text"],
                        ),
                    )

    def list_pages(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM document_pages
                    WHERE job_id = %s
                    ORDER BY document_id ASC, page_number ASC;
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def replace_retrieved_pages(self, job_id: str, pages: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM retrieved_pages WHERE job_id = %s;", (job_id,))
                for page in pages:
                    cur.execute(
                        """
                        INSERT INTO retrieved_pages (
                            job_id, document_id, file_name, page_number, score
                        )
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            job_id,
                            page["document_id"],
                            page["file_name"],
                            page["page_number"],
                            page.get("score"),
                        ),
                    )

    def list_retrieved_pages(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT document_id, file_name, page_number, score
                    FROM retrieved_pages
                    WHERE job_id = %s
                    ORDER BY id ASC;
                    """,
                    (job_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def mark_processing(self, job_id: str) -> None:
        self._set_status(job_id, "processing")

    def complete_job(
        self, job_id: str, answer: str, retrieved_pages: list[dict[str, Any]]
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM retrieved_pages WHERE job_id = %s;", (job_id,))
                for page in retrieved_pages:
                    cur.execute(
                        """
                        INSERT INTO retrieved_pages (
                            job_id, document_id, file_name, page_number, score
                        )
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            job_id,
                            page["document_id"],
                            page["file_name"],
                            page["page_number"],
                            page.get("score"),
                        ),
                    )
                cur.execute(
                    """
                    UPDATE chat_jobs
                    SET status = 'completed',
                        answer = %s,
                        error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (answer, job_id),
                )

    def fail_job(self, job_id: str, error: str) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE chat_jobs
                    SET status = 'failed',
                        error = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (error, job_id),
                )

    def _set_status(self, job_id: str, status: str) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE chat_jobs
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (status, job_id),
                )
