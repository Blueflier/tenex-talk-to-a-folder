"""Diagnostic classification for eval failures.

Heuristic-based: CRAWL_MISS, RETRIEVAL_MISS, or SYNTHESIS_FAIL.
"""

import numpy as np


def classify_failure(
    gold_text: str,
    all_chunks: list[dict],
    retrieved_chunks: list[dict],
    gold_embedding: np.ndarray,
    retrieved_embeddings: np.ndarray,
    similarity_threshold: float = 0.7,
) -> str:
    """Classify why retrieval/generation failed.

    Args:
        gold_text: The gold answer text.
        all_chunks: All chunks extracted from the paper.
        retrieved_chunks: Chunks returned by retrieval.
        gold_embedding: Embedding of the gold answer.
        retrieved_embeddings: Embeddings of retrieved chunks (N x D).
        similarity_threshold: Cosine similarity threshold for retrieval match.

    Returns:
        "CRAWL_MISS" if gold text not in any chunk,
        "RETRIEVAL_MISS" if not semantically retrieved,
        "SYNTHESIS_FAIL" if retrieved but LLM failed.
    """
    # CRAWL_MISS: gold answer text not found in ANY chunk
    gold_normalized = gold_text.lower().strip()
    found_in_chunks = any(
        gold_normalized in chunk["text"].lower() for chunk in all_chunks
    )
    if not found_in_chunks:
        return "CRAWL_MISS"

    # RETRIEVAL_MISS: gold embedding not similar to any retrieved embedding
    if retrieved_embeddings.size == 0:
        return "RETRIEVAL_MISS"

    sims = np.dot(retrieved_embeddings, gold_embedding) / (
        np.linalg.norm(retrieved_embeddings, axis=1) * np.linalg.norm(gold_embedding)
        + 1e-9
    )
    if np.max(sims) < similarity_threshold:
        return "RETRIEVAL_MISS"

    # Answer was in retrieved chunks but LLM got it wrong
    return "SYNTHESIS_FAIL"
