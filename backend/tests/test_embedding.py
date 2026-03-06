"""Tests for batch embedding with progress and retry."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from embedding import embed_chunks, EMBED_MODEL
from backend.config import EMBED_BATCH_SIZE


def _make_chunks(n: int) -> list[dict]:
    """Create n fake chunks with text fields."""
    return [{"text": f"chunk {i}", "source": "test.pdf", "chunk_index": i} for i in range(n)]


def _fake_embedding_response(texts: list[str]):
    """Return a mock response with fake 1536-dim embeddings."""
    data = []
    for i, _ in enumerate(texts):
        obj = MagicMock()
        obj.embedding = [float(i)] * 1536
        data.append(obj)
    resp = MagicMock()
    resp.data = data
    return resp


@pytest.fixture
def mock_client():
    """AsyncOpenAI client mock."""
    client = AsyncMock()
    client.embeddings = AsyncMock()
    client.embeddings.create = AsyncMock(side_effect=lambda **kwargs: _fake_embedding_response(kwargs["input"]))
    return client


class TestBatchSplitting:
    @pytest.mark.asyncio
    async def test_150_chunks_produce_2_api_calls(self, mock_client):
        chunks = _make_chunks(150)
        result = await embed_chunks(mock_client, chunks)
        assert mock_client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_100_chunks_produce_1_api_call(self, mock_client):
        chunks = _make_chunks(100)
        result = await embed_chunks(mock_client, chunks)
        assert mock_client.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_first_batch_has_100_texts(self, mock_client):
        chunks = _make_chunks(150)
        await embed_chunks(mock_client, chunks)
        first_call = mock_client.embeddings.create.call_args_list[0]
        assert len(first_call.kwargs["input"]) == 100

    @pytest.mark.asyncio
    async def test_second_batch_has_50_texts(self, mock_client):
        chunks = _make_chunks(150)
        await embed_chunks(mock_client, chunks)
        second_call = mock_client.embeddings.create.call_args_list[1]
        assert len(second_call.kwargs["input"]) == 50


class TestReturnShape:
    @pytest.mark.asyncio
    async def test_returns_ndarray_shape_n_1536(self, mock_client):
        chunks = _make_chunks(150)
        result = await embed_chunks(mock_client, chunks)
        assert isinstance(result, np.ndarray)
        assert result.shape == (150, 1536)

    @pytest.mark.asyncio
    async def test_returns_float32_dtype(self, mock_client):
        chunks = _make_chunks(10)
        result = await embed_chunks(mock_client, chunks)
        assert result.dtype == np.float32

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty_array(self, mock_client):
        result = await embed_chunks(mock_client, [])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 1536)


class TestProgressCallback:
    @pytest.mark.asyncio
    async def test_progress_called_after_each_batch(self, mock_client):
        on_progress = AsyncMock()
        chunks = _make_chunks(150)
        await embed_chunks(mock_client, chunks, on_progress=on_progress)
        assert on_progress.call_count == 2

    @pytest.mark.asyncio
    async def test_progress_receives_correct_counts(self, mock_client):
        on_progress = AsyncMock()
        chunks = _make_chunks(150)
        await embed_chunks(mock_client, chunks, on_progress=on_progress)
        calls = on_progress.call_args_list
        assert calls[0].args == (100, 150)
        assert calls[1].args == (150, 150)


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self):
        from openai import APIConnectionError
        client = AsyncMock()
        client.embeddings = AsyncMock()
        call_count = 0

        async def flaky_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise APIConnectionError(request=MagicMock())
            return _fake_embedding_response(kwargs["input"])

        client.embeddings.create = AsyncMock(side_effect=flaky_create)
        chunks = _make_chunks(5)
        result = await embed_chunks(client, chunks, max_retries=3)
        assert result.shape == (5, 1536)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        from openai import APIConnectionError
        client = AsyncMock()
        client.embeddings = AsyncMock()
        client.embeddings.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )
        chunks = _make_chunks(5)
        with pytest.raises(APIConnectionError):
            await embed_chunks(client, chunks, max_retries=3)
        assert client.embeddings.create.call_count == 3


class TestConstants:
    def test_batch_size_is_100(self):
        assert EMBED_BATCH_SIZE == 100

    def test_embed_model_is_text_embedding_3_small(self):
        assert EMBED_MODEL == "text-embedding-3-small"
