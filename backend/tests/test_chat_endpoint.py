"""Integration tests for /chat SSE endpoint."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# We need to mock modal before importing app
import sys
from unittest.mock import MagicMock as _MagicMock

# Mock modal module before any import
_modal_mock = _MagicMock()
_modal_mock.App.return_value = _MagicMock()
_modal_mock.Volume.from_name.return_value = _MagicMock()
_modal_mock.Image.debian_slim.return_value.pip_install.return_value = _MagicMock()
_modal_mock.Secret.from_name.return_value = _MagicMock()
_modal_mock.asgi_app.return_value = lambda f: f
_modal_mock.function.return_value = lambda f: f
sys.modules["modal"] = _modal_mock

from backend.app import web_app


# ---- Fixtures ----

DIM = 8


def _make_chunks_and_embeddings(n=10, all_low_score=False):
    """Create synthetic chunks and embeddings."""
    chunks = [
        {
            "file_name": f"doc_{i}.pdf",
            "file_id": f"fid_{i}",
            "text": f"Content about topic {i}",
            "mime_type": "application/pdf",
            "page_number": i + 1,
        }
        for i in range(n)
    ]
    if all_low_score:
        # Embeddings that will produce low cosine similarity with the mock query
        # Mock query (seed=99) is random, so use orthogonal-ish vectors
        # Just override retrieve_mixed results via a separate mock instead
        embeddings = np.random.randn(n, DIM)
    else:
        np.random.seed(42)
        embeddings = np.random.randn(n, DIM)
    return chunks, embeddings


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---- Helpers ----

def _parse_sse_events(text: str) -> list:
    """Parse SSE text into list of events."""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        raw = line[6:].strip()
        if raw == "[DONE]":
            events.append("[DONE]")
        else:
            events.append(json.loads(raw))
    return events


# Shared mock patches
def _mock_auth(user_id="user_123"):
    return patch("backend.chat.get_google_user_id", new_callable=AsyncMock, return_value=user_id)


def _mock_session_data(chunks, embeddings):
    async def _load(uid, sid):
        return chunks, embeddings
    return patch("backend.chat._load_session_data", side_effect=_load)


def _mock_embed_query():
    async def _embed(query):
        np.random.seed(99)
        return np.random.randn(DIM)
    return patch("backend.chat._embed_query", side_effect=_embed)


def _mock_stream_llm(tokens=None):
    if tokens is None:
        tokens = ["Hello", " from", " the", " LLM", " [1]"]

    async def _stream(query, results, model_key="deepseek"):
        for t in tokens:
            yield t

    return patch("backend.chat.stream_llm", side_effect=_stream)


# ---- Tests ----

@pytest.mark.asyncio
async def test_chat_returns_sse_stream(client):
    """POST /chat returns SSE with token events, citations, and [DONE]."""
    chunks, embeddings = _make_chunks_and_embeddings()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "What is topic 1?"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_events(resp.text)
    # Should have token events
    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) >= 1

    # Should have citations event
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    assert "citations" in citation_events[0]

    # Should end with [DONE]
    assert events[-1] == "[DONE]"


def _mock_retrieve_mixed_low():
    """Mock retrieve_mixed to return results all below threshold."""
    low_results = [
        ({"file_name": "f.pdf", "file_id": "x", "text": "t", "mime_type": "application/pdf"}, 0.1),
        ({"file_name": "g.pdf", "file_id": "y", "text": "u", "mime_type": "application/pdf"}, 0.05),
    ]
    return patch("backend.chat.retrieve_mixed", return_value=low_results)


@pytest.mark.asyncio
async def test_chat_no_results_when_below_threshold(client):
    """When all scores below threshold, emit no_results and skip LLM."""
    chunks, embeddings = _make_chunks_and_embeddings()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_retrieve_mixed_low():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "Something irrelevant"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)

    # Should have no_results event
    no_results = [e for e in events if isinstance(e, dict) and e.get("type") == "no_results"]
    assert len(no_results) == 1

    # Should NOT have token events
    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) == 0

    # Should end with [DONE]
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_chat_401_without_auth(client):
    """POST /chat without Authorization header returns 401."""
    resp = await client.post(
        "/chat",
        json={"session_id": "sess_1", "query": "Hello"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_401_with_invalid_bearer(client):
    """POST /chat with non-Bearer auth returns 401."""
    resp = await client.post(
        "/chat",
        json={"session_id": "sess_1", "query": "Hello"},
        headers={"Authorization": "Basic abc123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_citations_contain_frozen_metadata(client):
    """Citations event contains correct frozen chunk_text and metadata."""
    chunks, embeddings = _make_chunks_and_embeddings(n=5)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Answer"]):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "Topic?"},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1

    citations = citation_events[0]["citations"]
    assert len(citations) > 0

    # Each citation should have required fields
    for cit in citations:
        assert "index" in cit
        assert "file_name" in cit
        assert "file_id" in cit
        assert "chunk_text" in cit
        assert isinstance(cit["chunk_text"], str)
        assert len(cit["chunk_text"]) > 0


@pytest.mark.asyncio
async def test_chat_sse_event_format(client):
    """SSE events follow data: {json}\n\n format."""
    chunks, embeddings = _make_chunks_and_embeddings(n=3)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Hi"]):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test"},
            headers={"Authorization": "Bearer valid_token"},
        )

    # Every non-empty line should start with "data: "
    for line in resp.text.split("\n"):
        line = line.strip()
        if line:
            assert line.startswith("data: "), f"Bad SSE line: {line}"


@pytest.mark.asyncio
async def test_chat_400_missing_fields(client):
    """POST /chat without session_id or query returns 400."""
    with _mock_auth():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1"},  # missing query
            headers={"Authorization": "Bearer valid_token"},
        )
    assert resp.status_code == 400
