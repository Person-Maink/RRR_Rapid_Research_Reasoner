import hashlib
import re

import numpy as np

VECTOR_DIMENSION = 128
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def embed_text(text: str, dimension: int = VECTOR_DIMENSION) -> np.ndarray:
    vector = np.zeros(dimension, dtype="float32")
    tokens = tokenize(text)

    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0

    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm

    return vector


def embed_texts(texts: list[str], dimension: int = VECTOR_DIMENSION) -> np.ndarray:
    if not texts:
        return np.empty((0, dimension), dtype="float32")
    return np.vstack([embed_text(text, dimension) for text in texts]).astype("float32")
