"""Modal Volume save/load for session embeddings and chunk metadata."""

import json
from pathlib import Path

import numpy as np

VOLUME_PATH = Path("/data")


def save_session(
    user_id: str,
    session_id: str,
    embeddings: np.ndarray,
    chunks: list[dict],
    volume,
    base_path: Path | None = None,
) -> None:
    """Save embeddings (.npy) and chunks (.json) to Modal Volume.

    Args:
        user_id: User identifier for namespacing.
        session_id: Session identifier.
        embeddings: (n, 1536) float32 array of embeddings.
        chunks: List of chunk dicts with text, source, etc.
        volume: Modal Volume instance (must have .commit()).
        base_path: Override VOLUME_PATH for testing.
    """
    root = base_path if base_path is not None else VOLUME_PATH
    session_dir = root / user_id
    session_dir.mkdir(parents=True, exist_ok=True)

    emb_path = session_dir / f"{session_id}_embeddings.npy"
    chunks_path = session_dir / f"{session_id}_chunks.json"

    np.save(str(emb_path), embeddings)
    volume.commit()

    with open(chunks_path, "w") as f:
        json.dump(chunks, f)
    volume.commit()


def load_session(
    user_id: str,
    session_id: str,
    base_path: Path | None = None,
) -> tuple[np.ndarray, list[dict]]:
    """Load embeddings and chunks for a session.

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        base_path: Override VOLUME_PATH for testing.

    Returns:
        Tuple of (embeddings array, chunks list).

    Raises:
        FileNotFoundError: If session data does not exist.
    """
    root = base_path if base_path is not None else VOLUME_PATH
    emb_path = root / user_id / f"{session_id}_embeddings.npy"
    chunks_path = root / user_id / f"{session_id}_chunks.json"

    if not emb_path.exists():
        raise FileNotFoundError(f"Session not found: {user_id}/{session_id}")

    embeddings = np.load(str(emb_path))
    with open(chunks_path) as f:
        chunks = json.load(f)

    return embeddings, chunks


def append_session(
    user_id: str,
    session_id: str,
    new_embeddings: np.ndarray,
    new_chunks: list[dict],
    volume,
    base_path: Path | None = None,
) -> None:
    """Append embeddings and chunks to an existing session, or create if none exists.

    Args:
        user_id: User identifier for namespacing.
        session_id: Session identifier.
        new_embeddings: New embeddings to append.
        new_chunks: New chunk dicts to append.
        volume: Modal Volume instance (must have .commit()).
        base_path: Override VOLUME_PATH for testing.
    """
    root = base_path if base_path is not None else VOLUME_PATH
    emb_path = root / user_id / f"{session_id}_embeddings.npy"

    if emb_path.exists():
        existing_emb, existing_chunks = load_session(user_id, session_id, base_path=base_path)
        combined_emb = np.concatenate([existing_emb, new_embeddings])
        combined_chunks = existing_chunks + new_chunks
        save_session(user_id, session_id, combined_emb, combined_chunks, volume, base_path=base_path)
    else:
        save_session(user_id, session_id, new_embeddings, new_chunks, volume, base_path=base_path)
