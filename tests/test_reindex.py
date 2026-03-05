"""Tests for per-file re-indexing with surgical chunk replacement."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

import sys

# Mock modal before imports
_modal_mock = MagicMock()
_modal_mock.App.return_value = MagicMock()
_modal_mock.Volume.from_name.return_value = MagicMock()
_modal_mock.Image.debian_slim.return_value.pip_install.return_value = MagicMock()
_modal_mock.Secret.from_name.return_value = MagicMock()
_modal_mock.asgi_app.return_value = lambda f: f
_modal_mock.function.return_value = lambda f: f
sys.modules["modal"] = _modal_mock


DIM = 1536


def _create_session(tmp_path: Path, user_id: str, session_id: str, chunks: list[dict], embeddings: np.ndarray):
    """Create a session on disk with chunks and embeddings."""
    user_dir = tmp_path / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = user_dir / f"{session_id}_chunks.json"
    emb_path = user_dir / f"{session_id}_embeddings.npy"
    with open(chunks_path, "w") as f:
        json.dump(chunks, f)
    np.save(str(emb_path), embeddings)


@pytest.mark.asyncio
async def test_surgical_replacement():
    """reindex_file drops file A chunks, keeps file B, appends new A chunks."""
    from backend.reindex import reindex_file

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        user_id = "user1"
        session_id = "sess1"

        # 2 files: A (2 chunks) and B (3 chunks)
        chunks = [
            {"file_id": "fA", "file_name": "a.pdf", "text": "old A chunk 0"},
            {"file_id": "fA", "file_name": "a.pdf", "text": "old A chunk 1"},
            {"file_id": "fB", "file_name": "b.pdf", "text": "B chunk 0"},
            {"file_id": "fB", "file_name": "b.pdf", "text": "B chunk 1"},
            {"file_id": "fB", "file_name": "b.pdf", "text": "B chunk 2"},
        ]
        embeddings = np.random.randn(5, DIM).astype(np.float32)
        _create_session(tmp_path, user_id, session_id, chunks, embeddings)

        # Keep original B embeddings for comparison
        original_b_embeddings = embeddings[2:5].copy()

        # Mock Drive fetch + chunking + embedding
        new_a_chunks = [
            {"file_id": "fA", "file_name": "a.pdf", "text": "new A chunk 0"},
        ]
        new_a_embeddings = np.random.randn(1, DIM).astype(np.float32)

        mock_volume = MagicMock()

        with patch("backend.reindex.fetch_and_chunk_file", new_callable=AsyncMock, return_value=new_a_chunks), \
             patch("backend.reindex.embed_new_chunks", new_callable=AsyncMock, return_value=new_a_embeddings), \
             patch("backend.reindex.invalidate_caches") as mock_invalidate:
            result = await reindex_file(
                user_id=user_id,
                session_id=session_id,
                file_id="fA",
                access_token="tok",
                volume=mock_volume,
                base_path=tmp_path,
            )

        # Load saved session
        saved_chunks_path = tmp_path / user_id / f"{session_id}_chunks.json"
        saved_emb_path = tmp_path / user_id / f"{session_id}_embeddings.npy"
        with open(saved_chunks_path) as f:
            saved_chunks = json.load(f)
        saved_embs = np.load(str(saved_emb_path))

        # File B chunks unchanged (3 chunks)
        b_chunks = [c for c in saved_chunks if c["file_id"] == "fB"]
        assert len(b_chunks) == 3
        for i, c in enumerate(b_chunks):
            assert c["text"] == f"B chunk {i}"

        # File A replaced (1 new chunk)
        a_chunks = [c for c in saved_chunks if c["file_id"] == "fA"]
        assert len(a_chunks) == 1
        assert a_chunks[0]["text"] == "new A chunk 0"

        # Total: 3 B + 1 A = 4
        assert len(saved_chunks) == 4
        assert saved_embs.shape == (4, DIM)

        # B embeddings preserved
        np.testing.assert_array_equal(saved_embs[:3], original_b_embeddings)


@pytest.mark.asyncio
async def test_cache_invalidation():
    """After reindex, invalidate_caches called with the file_id."""
    from backend.reindex import reindex_file

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        user_id = "user1"
        session_id = "sess1"

        chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "old"}]
        embeddings = np.random.randn(1, DIM).astype(np.float32)
        _create_session(tmp_path, user_id, session_id, chunks, embeddings)

        new_chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "new"}]
        new_embs = np.random.randn(1, DIM).astype(np.float32)

        mock_volume = MagicMock()

        with patch("backend.reindex.fetch_and_chunk_file", new_callable=AsyncMock, return_value=new_chunks), \
             patch("backend.reindex.embed_new_chunks", new_callable=AsyncMock, return_value=new_embs), \
             patch("backend.reindex.invalidate_caches") as mock_invalidate:
            await reindex_file(
                user_id=user_id, session_id=session_id, file_id="fA",
                access_token="tok", volume=mock_volume, base_path=tmp_path,
            )

        mock_invalidate.assert_called_once_with("fA")


@pytest.mark.asyncio
async def test_indexed_at_returned():
    """reindex_file returns file_id and ISO timestamp with Z suffix."""
    from backend.reindex import reindex_file

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        user_id = "user1"
        session_id = "sess1"

        chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "old"}]
        embeddings = np.random.randn(1, DIM).astype(np.float32)
        _create_session(tmp_path, user_id, session_id, chunks, embeddings)

        new_chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "new"}]
        new_embs = np.random.randn(1, DIM).astype(np.float32)

        mock_volume = MagicMock()

        with patch("backend.reindex.fetch_and_chunk_file", new_callable=AsyncMock, return_value=new_chunks), \
             patch("backend.reindex.embed_new_chunks", new_callable=AsyncMock, return_value=new_embs), \
             patch("backend.reindex.invalidate_caches"):
            result = await reindex_file(
                user_id=user_id, session_id=session_id, file_id="fA",
                access_token="tok", volume=mock_volume, base_path=tmp_path,
            )

        assert result["file_id"] == "fA"
        assert result["indexed_at"].endswith("Z")
        # Should be a valid ISO timestamp
        datetime.fromisoformat(result["indexed_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_volume_commit_called():
    """volume.commit() called after saving session."""
    from backend.reindex import reindex_file

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        user_id = "user1"
        session_id = "sess1"

        chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "old"}]
        embeddings = np.random.randn(1, DIM).astype(np.float32)
        _create_session(tmp_path, user_id, session_id, chunks, embeddings)

        new_chunks = [{"file_id": "fA", "file_name": "a.pdf", "text": "new"}]
        new_embs = np.random.randn(1, DIM).astype(np.float32)

        mock_volume = MagicMock()

        with patch("backend.reindex.fetch_and_chunk_file", new_callable=AsyncMock, return_value=new_chunks), \
             patch("backend.reindex.embed_new_chunks", new_callable=AsyncMock, return_value=new_embs), \
             patch("backend.reindex.invalidate_caches"):
            await reindex_file(
                user_id=user_id, session_id=session_id, file_id="fA",
                access_token="tok", volume=mock_volume, base_path=tmp_path,
            )

        mock_volume.commit.assert_called()


@pytest.mark.asyncio
async def test_reindex_401():
    """POST /reindex without auth returns 401."""
    from httpx import ASGITransport, AsyncClient
    from backend.app import web_app

    async with AsyncClient(transport=ASGITransport(app=web_app), base_url="http://test") as client:
        response = await client.post("/reindex", json={"session_id": "s1", "file_id": "f1"})

    assert response.status_code == 401
