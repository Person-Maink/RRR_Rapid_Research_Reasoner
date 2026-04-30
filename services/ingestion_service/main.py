import os
from pathlib import Path

import faiss
import numpy as np
import ollama
import psycopg2
import PyPDF2

from environment import (
    DB_PATH,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

# Input = pdf file
# Output = faiss index


def get_pg_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def init_postgres():
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_path, page_number)
        );
    """
    )

    conn.commit()
    cur.close()
    conn.close()


# Load and process PDF documents
def load_and_process_pdf_documents(file_paths):
    records = []

    for file_path in file_paths:
        file_path = Path(file_path)

        with open(file_path, "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text() or ""

                records.append(
                    {
                        "file_path": str(file_path),
                        "file_name": file_path.name,
                        "page_number": page_num,
                        "text": page_text,
                    }
                )

    return records


def insert_documents_metadata(records):
    conn = get_pg_connection()
    cur = conn.cursor()

    inserted = []

    for r in records:
        cur.execute(
            """
            INSERT INTO documents (file_path, file_name, page_number, text)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (file_path, page_number) DO NOTHING
            RETURNING id;
        """,
            (r["file_path"], r["file_name"], r["page_number"], r["text"]),
        )

        result = cur.fetchone()
        if result:
            inserted.append((result[0], r))  # (id, record)

    conn.commit()
    cur.close()
    conn.close()

    return inserted


def embed_texts(texts, model="nomic-embed-text"):
    embeddings = []

    for text in texts:
        response = ollama.embeddings(model=model, prompt=text)
        embeddings.append(response["embedding"])

    return np.array(embeddings, dtype="float32")


def load_or_create_faiss_index(index_path, embeddings, dimension=768):
    if os.path.exists(index_path):
        return faiss.read_index(str(index_path))

    base_index = faiss.IndexFlatL2(dimension)
    faiss_index = faiss.IndexIDMap(base_index)

    return faiss_index


def encode_documents(records, faiss_index):
    inserted = insert_documents_metadata(records)

    if not inserted:
        return faiss_index, None  # nothing new

    ids = [i[0] for i in inserted]
    texts = [i[1]["text"] for i in inserted]

    embeddings = embed_texts(texts)
    faiss_index.add_with_ids(embeddings, np.array(ids, dtype="int64"))
    return faiss_index


def save_faissIndex(faiss_index, index_path):
    faiss.write_index(faiss_index, str(index_path))


def ingest_documents(file_paths):
    index_path = DB_PATH / "faiss_index"
    init_postgres()
    records = load_and_process_pdf_documents(file_paths)
    faiss_index = load_or_create_faiss_index(index_path)
    faiss_index, embeddings = encode_documents(records, faiss_index)
    save_faissIndex(faiss_index, index_path)
    return faiss_index, embeddings
