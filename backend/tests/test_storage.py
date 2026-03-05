"""Tests for Modal Volume session storage (save/load)."""

import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from storage import save_session, load_session, VOLUME_PATH


@pytest.fixture
def mock_volume():
    return MagicMock()


@pytest.fixture
def sample_data():
    embeddings = np.random.rand(10, 1536).astype(np.float32)
    chunks = [
        {"text": f"chunk {i}", "source": "test.pdf", "chunk_index": i}
        for i in range(10)
    ]
    return embeddings, chunks


class TestSaveSession:
    def test_creates_embeddings_npy_file(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        assert (tmp_path / "user1" / "sess1_embeddings.npy").exists()

    def test_creates_chunks_json_file(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        assert (tmp_path / "user1" / "sess1_chunks.json").exists()

    def test_volume_commit_called_twice(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        assert mock_volume.commit.call_count == 2

    def test_creates_user_directory(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        assert (tmp_path / "user1").is_dir()

    def test_correct_file_paths(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("userABC", "session123", embeddings, chunks, mock_volume, base_path=tmp_path)
        assert (tmp_path / "userABC" / "session123_embeddings.npy").exists()
        assert (tmp_path / "userABC" / "session123_chunks.json").exists()

    def test_chunks_json_contents(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        with open(tmp_path / "user1" / "sess1_chunks.json") as f:
            loaded = json.load(f)
        assert loaded == chunks


class TestLoadSession:
    def test_returns_tuple_of_embeddings_and_chunks(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        result = load_session("user1", "sess1", base_path=tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_loaded_embeddings_match_saved(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        loaded_emb, _ = load_session("user1", "sess1", base_path=tmp_path)
        np.testing.assert_array_almost_equal(loaded_emb, embeddings)

    def test_loaded_chunks_match_saved(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        _, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        assert loaded_chunks == chunks

    def test_raises_file_not_found_for_missing_session(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_session("nonexistent", "nope", base_path=tmp_path)


class TestRoundTrip:
    def test_save_then_load_identical(self, tmp_path, mock_volume, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, mock_volume, base_path=tmp_path)
        loaded_emb, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        np.testing.assert_array_equal(loaded_emb, embeddings)
        assert loaded_chunks == chunks
