"""Cosine similarity retrieval engine with top-k selection and citation extraction."""
from __future__ import annotations

from typing import Any

import numpy as np

SIMILARITY_THRESHOLD = 0.3

SHEET_MIME = "application/vnd.google-apps.spreadsheet"


def cosine_sim(query_vec: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and each embedding row."""
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
    return np.dot(embeddings, query_vec) / (norms + 1e-9)


def retrieve(
    query_embedding: np.ndarray,
    chunks: list[dict[str, Any]],
    embeddings: np.ndarray,
    top_k: int = 8,
) -> list[tuple[dict[str, Any], float]]:
    """Return top-k (chunk, score) pairs sorted by cosine similarity descending."""
    scores = cosine_sim(query_embedding, embeddings)
    k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:k]
    return [(chunks[i], float(scores[i])) for i in top_indices]


def retrieve_mixed(
    query_embedding: np.ndarray,
    chunks: list[dict[str, Any]],
    embeddings: np.ndarray,
) -> list[tuple[dict[str, Any], float]]:
    """Retrieve from separate doc/sheet pools, merge by score, cap at 10.

    - Docs: top-8
    - Sheets: top-5
    - Mixed: merge both pools by score, cap at 10
    - Single type: fall back to appropriate top-k
    """
    doc_indices = [i for i, c in enumerate(chunks) if c.get("mime_type") != SHEET_MIME]
    sheet_indices = [i for i, c in enumerate(chunks) if c.get("mime_type") == SHEET_MIME]

    has_docs = len(doc_indices) > 0
    has_sheets = len(sheet_indices) > 0

    if has_docs and has_sheets:
        # Retrieve from separate pools
        doc_chunks = [chunks[i] for i in doc_indices]
        doc_embeddings = embeddings[doc_indices]
        doc_results = retrieve(query_embedding, doc_chunks, doc_embeddings, top_k=8)

        sheet_chunks = [chunks[i] for i in sheet_indices]
        sheet_embeddings = embeddings[sheet_indices]
        sheet_results = retrieve(query_embedding, sheet_chunks, sheet_embeddings, top_k=5)

        merged = doc_results + sheet_results
        merged.sort(key=lambda x: x[1], reverse=True)
        return merged[:10]
    elif has_sheets:
        return retrieve(query_embedding, chunks, embeddings, top_k=5)
    else:
        return retrieve(query_embedding, chunks, embeddings, top_k=8)


def check_threshold(results: list[tuple[dict[str, Any], float]]) -> bool:
    """Return True if ALL scores are below the similarity threshold."""
    return all(score < SIMILARITY_THRESHOLD for _, score in results)


def extract_citations(
    retrieved_chunks: list[tuple[dict[str, Any], float]],
) -> list[dict[str, Any]]:
    """Build citation metadata list with frozen chunk_text snapshot."""
    return [
        {
            "index": i + 1,
            "file_name": c["file_name"],
            "file_id": c["file_id"],
            "page_number": c.get("page_number"),
            "row_number": c.get("row_number"),
            "slide_index": c.get("slide_index"),
            "chunk_text": c["text"],
        }
        for i, (c, _score) in enumerate(retrieved_chunks)
    ]
