import faiss
import numpy as np
import ollama
import psycopg2

from environment import (
    DB_PATH,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)


def get_pg_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def embed_query(query, model="nomic-embed-text"):
    response = ollama.embeddings(model=model, prompt=query)
    return np.array([response["embedding"]], dtype="float32")


def perform_similarity_search(query, faiss_index, top_k=5):
    query_embedding = embed_query(query)

    distances, ids = faiss_index.search(query_embedding, top_k)

    return ids[0], distances[0]


def retrieve_documents_by_ids(document_ids):
    valid_ids = [int(doc_id) for doc_id in document_ids if doc_id != -1]

    if not valid_ids:
        return []

    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, file_path, file_name, page_number
        FROM documents
        WHERE id = ANY(%s);
    """,
        (valid_ids,),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    row_map = {row[0]: row for row in rows}

    results = []
    for doc_id in valid_ids:
        row = row_map.get(doc_id)
        if row:
            results.append(
                {
                    "id": row[0],
                    "file_path": row[1],
                    "file_name": row[2],
                    "page_number": row[3],
                }
            )

    return results


def retrieve(query, top_k=5):
    index_path = DB_PATH / "faiss_index"
    faiss_index = faiss.read_index(str(index_path))
    document_ids, distances = perform_similarity_search(
        query=query, faiss_index=faiss_index, top_k=top_k
    )
    documents = retrieve_documents_by_ids(document_ids)
    # for doc, distance in zip(documents, distances):
    #     doc["distance"] = float(distance)
    return documents
