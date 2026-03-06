"""Embedding cache for eval pipeline.

Saves per-paper .npy embeddings and .json chunks to eval/cache/,
mirroring the storage.py base_path pattern.
"""

import json
from pathlib import Path

import numpy as np

CACHE_DIR = Path("eval/cache")


def save_paper_cache(
    paper_id: str, embeddings: np.ndarray, chunks: list[dict]
) -> None:
    """Cache embeddings and chunks for a paper.

    Creates eval/cache/ directory if it does not exist.
    Saves {paper_id}_embeddings.npy and {paper_id}_chunks.json.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(CACHE_DIR / f"{paper_id}_embeddings.npy"), embeddings)
    with open(CACHE_DIR / f"{paper_id}_chunks.json", "w") as f:
        json.dump(chunks, f)


def load_paper_cache(
    paper_id: str,
) -> tuple[np.ndarray, list[dict]] | None:
    """Load cached embeddings and chunks for a paper.

    Returns None if cache files do not exist.
    """
    emb_path = CACHE_DIR / f"{paper_id}_embeddings.npy"
    chunks_path = CACHE_DIR / f"{paper_id}_chunks.json"
    if not emb_path.exists() or not chunks_path.exists():
        return None
    embeddings = np.load(str(emb_path))
    with open(chunks_path) as f:
        chunks = json.load(f)
    return embeddings, chunks
