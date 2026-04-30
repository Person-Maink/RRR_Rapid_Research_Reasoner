import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover - local dev can still use lexical fallback.
    faiss = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - compatibility with the existing venv.
    from PyPDF2 import PdfReader

from services.environment import JOBS_DIR
from services.vectorize import embed_texts

LOGGER = logging.getLogger(__name__)


def extract_pdf_pages(file_path: str) -> list[str]:
    with Path(file_path).open("rb") as pdf_file:
        reader = PdfReader(pdf_file)
        return [page.extract_text() or "" for page in reader.pages]


def ingest_job_documents(job_id: str, store) -> list[dict[str, Any]]:
    documents = store.list_documents(job_id)
    pages: list[dict[str, Any]] = []

    for document in documents:
        extracted_pages = extract_pdf_pages(document["storage_path"])
        for index, text in enumerate(extracted_pages, start=1):
            pages.append(
                {
                    "job_id": job_id,
                    "document_id": document["id"],
                    "file_name": document["file_name"],
                    "page_number": index,
                    "text": text.strip(),
                }
            )

    store.replace_document_pages(job_id, pages)
    build_faiss_artifacts(job_id, pages)
    LOGGER.info(
        "Ingested job documents",
        extra={
            "job_id": job_id,
            "page_count": len(pages),
            "document_count": len(documents),
        },
    )
    return pages


def build_faiss_artifacts(job_id: str, pages: list[dict[str, Any]]) -> None:
    artifact_dir = JOBS_DIR / job_id / "faiss"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    metadata = [
        {
            "document_id": page["document_id"],
            "file_name": page["file_name"],
            "page_number": page["page_number"],
        }
        for page in pages
    ]
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    if faiss is None or not pages:
        return

    vectors = embed_texts([page["text"] for page in pages])
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.asarray(vectors, dtype="float32"))
    faiss.write_index(index, str(artifact_dir / "index.faiss"))
