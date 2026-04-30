import json
import logging
from typing import Any

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover - fallback covers local environments.
    faiss = None

from services.environment import JOBS_DIR, RETRIEVAL_TOP_K
from services.vectorize import embed_text, embed_texts

LOGGER = logging.getLogger(__name__)


def retrieve_for_job(
    job_id: str,
    query: str,
    store,
    top_k: int = RETRIEVAL_TOP_K,
) -> list[dict[str, Any]]:
    pages = store.list_pages(job_id)
    if not pages:
        return []

    results = retrieve_with_faiss(job_id, query, pages, top_k)
    if results is None:
        results = retrieve_with_numpy(query, pages, top_k)

    LOGGER.info(
        "Retrieved pages for job",
        extra={"job_id": job_id, "result_count": len(results)},
    )
    return results


def retrieve_with_faiss(
    job_id: str,
    query: str,
    pages: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]] | None:
    artifact_dir = JOBS_DIR / job_id / "faiss"
    index_path = artifact_dir / "index.faiss"
    metadata_path = artifact_dir / "metadata.json"

    if faiss is None or not index_path.exists() or not metadata_path.exists():
        return None

    try:
        index = faiss.read_index(str(index_path))
        metadata = json.loads(metadata_path.read_text())
        query_vector = embed_text(query).reshape(1, -1).astype("float32")
        scores, indexes = index.search(query_vector, min(top_k, len(pages)))
    except Exception:
        LOGGER.exception("FAISS retrieval failed; falling back to numpy")
        return None

    page_lookup = {(page["document_id"], page["page_number"]): page for page in pages}
    results: list[dict[str, Any]] = []
    for score, index_value in zip(scores[0], indexes[0]):
        if index_value < 0 or index_value >= len(metadata):
            continue
        match = metadata[index_value]
        page = page_lookup.get((match["document_id"], match["page_number"]))
        if page:
            results.append({**page, "score": float(score)})
    return results


def retrieve_with_numpy(
    query: str,
    pages: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    query_vector = embed_text(query)
    page_vectors = embed_texts([page["text"] for page in pages])
    scores = page_vectors @ query_vector
    ranked_indexes = np.argsort(scores)[::-1][:top_k]

    return [{**pages[index], "score": float(scores[index])} for index in ranked_indexes]


def retrieve(query: str, top_k: int = RETRIEVAL_TOP_K):
    raise RuntimeError(
        "retrieve(query) has been replaced by retrieve_for_job(job_id, query, store)."
    )
