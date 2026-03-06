"""Tests for session storage (save/load)."""

import json

import numpy as np
import pytest

from storage import save_session, load_session, append_session


@pytest.fixture
def sample_data():
    embeddings = np.random.rand(10, 1536).astype(np.float32)
    chunks = [
        {"text": f"chunk {i}", "source": "test.pdf", "chunk_index": i}
        for i in range(10)
    ]
    return embeddings, chunks


class TestSaveSession:
    def test_creates_embeddings_npy_file(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        assert (tmp_path / "user1" / "sess1_embeddings.npy").exists()

    def test_creates_chunks_json_file(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        assert (tmp_path / "user1" / "sess1_chunks.json").exists()

    def test_creates_user_directory(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        assert (tmp_path / "user1").is_dir()

    def test_correct_file_paths(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("userABC", "session123", embeddings, chunks, base_path=tmp_path)
        assert (tmp_path / "userABC" / "session123_embeddings.npy").exists()
        assert (tmp_path / "userABC" / "session123_chunks.json").exists()

    def test_chunks_json_contents(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        with open(tmp_path / "user1" / "sess1_chunks.json") as f:
            loaded = json.load(f)
        assert loaded == chunks


class TestLoadSession:
    def test_returns_tuple_of_embeddings_and_chunks(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        result = load_session("user1", "sess1", base_path=tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_loaded_embeddings_match_saved(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        loaded_emb, _ = load_session("user1", "sess1", base_path=tmp_path)
        np.testing.assert_array_almost_equal(loaded_emb, embeddings)

    def test_loaded_chunks_match_saved(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        _, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        assert loaded_chunks == chunks

    def test_raises_file_not_found_for_missing_session(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_session("nonexistent", "nope", base_path=tmp_path)


class TestAppendSession:
    def test_append_creates_files_when_none_exist(self, tmp_path):
        """When no session files exist, append_session behaves like save_session."""
        embeddings = np.random.rand(5, 1536).astype(np.float32)
        chunks = [{"text": f"chunk {i}", "source": "a.pdf", "chunk_index": i} for i in range(5)]
        append_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)

        loaded_emb, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        np.testing.assert_array_equal(loaded_emb, embeddings)
        assert loaded_chunks == chunks

    def test_append_concatenates_embeddings(self, tmp_path, sample_data):
        """When session exists, new embeddings are concatenated to existing."""
        embeddings, chunks = sample_data  # 10 rows
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)

        new_embeddings = np.random.rand(3, 1536).astype(np.float32)
        new_chunks = [{"text": f"new chunk {i}", "source": "b.pdf", "chunk_index": i} for i in range(3)]
        append_session("user1", "sess1", new_embeddings, new_chunks, base_path=tmp_path)

        loaded_emb, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        assert loaded_emb.shape[0] == 13  # 10 + 3
        np.testing.assert_array_equal(loaded_emb[:10], embeddings)
        np.testing.assert_array_equal(loaded_emb[10:], new_embeddings)

    def test_append_concatenates_chunks(self, tmp_path, sample_data):
        """When session exists, new chunks are appended to existing."""
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)

        new_embeddings = np.random.rand(2, 1536).astype(np.float32)
        new_chunks = [{"text": "appended A"}, {"text": "appended B"}]
        append_session("user1", "sess1", new_embeddings, new_chunks, base_path=tmp_path)

        _, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        assert len(loaded_chunks) == 12  # 10 + 2
        assert loaded_chunks[-2:] == new_chunks

    def test_multiple_appends(self, tmp_path):
        """Multiple appends accumulate correctly."""
        e1 = np.random.rand(2, 1536).astype(np.float32)
        c1 = [{"text": "a"}, {"text": "b"}]
        append_session("user1", "sess1", e1, c1, base_path=tmp_path)

        e2 = np.random.rand(3, 1536).astype(np.float32)
        c2 = [{"text": "c"}, {"text": "d"}, {"text": "e"}]
        append_session("user1", "sess1", e2, c2, base_path=tmp_path)

        e3 = np.random.rand(1, 1536).astype(np.float32)
        c3 = [{"text": "f"}]
        append_session("user1", "sess1", e3, c3, base_path=tmp_path)

        loaded_emb, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        assert loaded_emb.shape[0] == 6  # 2 + 3 + 1
        assert len(loaded_chunks) == 6


class TestRoundTrip:
    def test_save_then_load_identical(self, tmp_path, sample_data):
        embeddings, chunks = sample_data
        save_session("user1", "sess1", embeddings, chunks, base_path=tmp_path)
        loaded_emb, loaded_chunks = load_session("user1", "sess1", base_path=tmp_path)
        np.testing.assert_array_equal(loaded_emb, embeddings)
        assert loaded_chunks == chunks
