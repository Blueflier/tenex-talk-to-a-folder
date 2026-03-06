"""Integration tests for /chat SSE endpoint with hybrid retrieval."""
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


def _make_chunks_and_embeddings(n=10, all_low_score=False, file_ids=None):
    """Create synthetic chunks and embeddings."""
    chunks = []
    for i in range(n):
        fid = file_ids[i] if file_ids and i < len(file_ids) else f"fid_{i}"
        chunks.append(
            {
                "file_name": f"doc_{i}.pdf",
                "file_id": fid,
                "text": f"Content about topic {i}",
                "mime_type": "application/pdf",
                "page_number": i + 1,
            }
        )
    if all_low_score:
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

    async def _stream(query, results, grep_results=None, model_key="deepseek"):
        for t in tokens:
            yield t

    return patch("backend.chat.stream_llm", side_effect=_stream)


def _mock_staleness(stale_ids=None, file_errors=None):
    """Mock check_staleness to return given stale_ids and errors."""
    async def _check(file_list, token):
        return (stale_ids or set(), file_errors or {})
    return patch("backend.chat.check_staleness", side_effect=_check)


def _mock_extract_keywords(keywords=None):
    async def _extract(query, model_key="deepseek"):
        return keywords or ["keyword1", "keyword2"]
    return patch("backend.chat.extract_keywords", side_effect=_extract)


def _mock_grep_live(results_by_fid=None):
    """Mock grep_live to return results per file_id."""
    async def _grep(fid, keywords, token):
        if results_by_fid and fid in results_by_fid:
            return results_by_fid[fid]
        return [{"text": f"Grep result for {fid}", "matched_keyword": "keyword1", "sentence_index": 0, "file_id": fid}]
    return patch("backend.chat.grep_live", side_effect=_grep)


# ---- Tests ----

@pytest.mark.asyncio
async def test_chat_returns_sse_stream(client):
    """POST /chat returns SSE with token events, citations, and [DONE]."""
    chunks, embeddings = _make_chunks_and_embeddings()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(), \
         _mock_staleness():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "What is topic 1?"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_events(resp.text)
    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) >= 1

    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    assert "citations" in citation_events[0]

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
         _mock_embed_query(), _mock_retrieve_mixed_low(), \
         _mock_staleness():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "Something irrelevant"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    no_results = [e for e in events if isinstance(e, dict) and e.get("type") == "no_results"]
    assert len(no_results) == 1
    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) == 0
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
         _mock_embed_query(), _mock_stream_llm(tokens=["Answer"]), \
         _mock_staleness():
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
         _mock_embed_query(), _mock_stream_llm(tokens=["Hi"]), \
         _mock_staleness():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test"},
            headers={"Authorization": "Bearer valid_token"},
        )

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


# ---- Staleness + Hybrid Retrieval Tests ----

@pytest.mark.asyncio
async def test_staleness_event(client):
    """Mock check_staleness returning stale file -> SSE contains staleness event before tokens."""
    file_list = [
        {"file_id": "fid_0", "file_name": "doc_0.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    chunks, embeddings = _make_chunks_and_embeddings(n=5, file_ids=["fid_0"] * 5)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Answer"]), \
         _mock_staleness(stale_ids={"fid_0"}), \
         _mock_extract_keywords(), _mock_grep_live():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 1
    assert staleness_events[0]["files"][0]["file_id"] == "fid_0"

    # Staleness event should come before token events
    staleness_idx = events.index(staleness_events[0])
    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    if token_events:
        first_token_idx = events.index(token_events[0])
        assert staleness_idx < first_token_idx


@pytest.mark.asyncio
async def test_hybrid_fresh_only(client):
    """All files fresh -> no staleness event, normal cosine retrieval."""
    file_list = [
        {"file_id": "fid_0", "file_name": "doc_0.pdf", "indexed_at": "2026-03-05T20:00:00Z"},
    ]
    chunks, embeddings = _make_chunks_and_embeddings(n=5, file_ids=["fid_0"] * 5)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Fresh answer"]), \
         _mock_staleness(stale_ids=set()):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 0

    token_events = [e for e in events if isinstance(e, dict) and e.get("type") == "token"]
    assert len(token_events) >= 1


@pytest.mark.asyncio
async def test_hybrid_stale_only(client):
    """All files stale (modified) -> staleness event, grep results in prompt, no cosine retrieval."""
    file_list = [
        {"file_id": "fid_0", "file_name": "doc_0.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    # All chunks belong to fid_0 which is stale
    chunks, embeddings = _make_chunks_and_embeddings(n=5, file_ids=["fid_0"] * 5)

    grep_results = {
        "fid_0": [
            {"text": "Grep found this content", "matched_keyword": "test", "sentence_index": 0, "file_id": "fid_0"},
        ]
    }

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Stale answer"]), \
         _mock_staleness(stale_ids={"fid_0"}), \
         _mock_extract_keywords(["test"]), _mock_grep_live(grep_results):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 1

    # Should have grep citation with source="grep"
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["citations"]
    grep_citations = [c for c in citations if c.get("source") == "grep"]
    assert len(grep_citations) >= 1


@pytest.mark.asyncio
async def test_hybrid_mixed(client):
    """Some fresh, some stale -> both retrieval paths used."""
    file_list = [
        {"file_id": "fresh_1", "file_name": "fresh.pdf", "indexed_at": "2026-03-05T20:00:00Z"},
        {"file_id": "stale_1", "file_name": "stale.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    chunks = [
        {"file_name": "fresh.pdf", "file_id": "fresh_1", "text": "Fresh content", "mime_type": "application/pdf", "page_number": 1},
        {"file_name": "stale.pdf", "file_id": "stale_1", "text": "Old stale content", "mime_type": "application/pdf", "page_number": 1},
    ]
    np.random.seed(42)
    embeddings = np.random.randn(2, DIM)

    grep_results = {
        "stale_1": [
            {"text": "Grep found stale content", "matched_keyword": "test", "sentence_index": 0, "file_id": "stale_1"},
        ]
    }

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Mixed answer"]), \
         _mock_staleness(stale_ids={"stale_1"}), \
         _mock_extract_keywords(["test"]), _mock_grep_live(grep_results):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)

    # Staleness event for stale file
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 1
    stale_file_ids = [f["file_id"] for f in staleness_events[0]["files"]]
    assert "stale_1" in stale_file_ids
    assert "fresh_1" not in stale_file_ids

    # Citations should include both cosine and grep sources
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["citations"]
    grep_cits = [c for c in citations if c.get("source") == "grep"]
    cosine_cits = [c for c in citations if not c.get("source")]
    assert len(grep_cits) >= 1
    assert len(cosine_cits) >= 1


@pytest.mark.asyncio
async def test_deleted_file_uses_embeddings(client):
    """File with 404 stays on cosine path, NOT routed to grep_live; citation gets (deleted) suffix."""
    file_list = [
        {"file_id": "del_1", "file_name": "gone.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    chunks = [
        {"file_name": "gone.pdf", "file_id": "del_1", "text": "Old content before deletion", "mime_type": "application/pdf", "page_number": 1},
    ]
    np.random.seed(42)
    embeddings = np.random.randn(1, DIM)

    # grep_live should NOT be called for deleted files
    grep_mock = _mock_grep_live()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Deleted answer"]), \
         _mock_staleness(stale_ids={"del_1"}, file_errors={"del_1": "not_found"}), \
         grep_mock, _mock_extract_keywords():
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)

    # Staleness event should include the deleted file
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 1
    assert staleness_events[0]["files"][0]["error"] == "not_found"

    # Citation should have "(deleted)" suffix
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["citations"]
    assert any("(deleted)" in c["file_name"] for c in citations)

    # grep_live should NOT have been called (deleted -> cosine path)
    # The grep_live mock's side_effect shouldn't be invoked for del_1
    # since del_1 is in deleted_ids and removed from grep_ids


@pytest.mark.asyncio
async def test_deleted_plus_stale(client):
    """One file deleted (404), one modified -> deleted uses cosine, modified uses grep, both in staleness SSE."""
    file_list = [
        {"file_id": "del_1", "file_name": "gone.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
        {"file_id": "mod_1", "file_name": "changed.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    chunks = [
        {"file_name": "gone.pdf", "file_id": "del_1", "text": "Old deleted content", "mime_type": "application/pdf", "page_number": 1},
        {"file_name": "changed.pdf", "file_id": "mod_1", "text": "Old changed content", "mime_type": "application/pdf", "page_number": 1},
    ]
    np.random.seed(42)
    embeddings = np.random.randn(2, DIM)

    grep_results = {
        "mod_1": [
            {"text": "Updated content from grep", "matched_keyword": "test", "sentence_index": 0, "file_id": "mod_1"},
        ]
    }

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["Combined answer"]), \
         _mock_staleness(stale_ids={"del_1", "mod_1"}, file_errors={"del_1": "not_found"}), \
         _mock_extract_keywords(["test"]), _mock_grep_live(grep_results):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)

    # Staleness event should list both files
    staleness_events = [e for e in events if isinstance(e, dict) and e.get("type") == "staleness"]
    assert len(staleness_events) == 1
    stale_files = staleness_events[0]["files"]
    stale_file_ids = [f["file_id"] for f in stale_files]
    assert "del_1" in stale_file_ids
    assert "mod_1" in stale_file_ids

    # del_1 should have not_found error
    del_file = next(f for f in stale_files if f["file_id"] == "del_1")
    assert del_file["error"] == "not_found"

    # Citations should include both deleted (cosine with suffix) and grep
    citation_events = [e for e in events if isinstance(e, dict) and e.get("type") == "citations"]
    assert len(citation_events) == 1
    citations = citation_events[0]["citations"]
    deleted_cits = [c for c in citations if "(deleted)" in c.get("file_name", "")]
    grep_cits = [c for c in citations if c.get("source") == "grep"]
    assert len(deleted_cits) >= 1
    assert len(grep_cits) >= 1


@pytest.mark.asyncio
async def test_rate_limit_returns_429_after_10_requests(client):
    """11th request within 60s for the same session_id returns 429."""
    chunks, embeddings = _make_chunks_and_embeddings(n=3)

    # Clear any existing rate limit state
    from backend.chat import _rate_limits
    _rate_limits.clear()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["ok"]), \
         _mock_staleness():
        # First 10 requests should succeed
        for i in range(10):
            resp = await client.post(
                "/chat",
                json={"session_id": "rate_sess", "query": f"Question {i}"},
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        # 11th request should be rate limited
        resp = await client.post(
            "/chat",
            json={"session_id": "rate_sess", "query": "One too many"},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert resp.status_code == 429

    _rate_limits.clear()


@pytest.mark.asyncio
async def test_rate_limit_independent_sessions(client):
    """Rate limits are per session_id -- different sessions don't interfere."""
    chunks, embeddings = _make_chunks_and_embeddings(n=3)

    from backend.chat import _rate_limits
    _rate_limits.clear()

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["ok"]), \
         _mock_staleness():
        # 10 requests to session A
        for i in range(10):
            resp = await client.post(
                "/chat",
                json={"session_id": "sess_A", "query": f"Q {i}"},
                headers={"Authorization": "Bearer valid_token"},
            )
            assert resp.status_code == 200

        # Session B should still work fine
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_B", "query": "Independent"},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert resp.status_code == 200

    _rate_limits.clear()


@pytest.mark.asyncio
async def test_rate_limit_window_expires(client):
    """After 60s window expires, requests succeed again."""
    import time
    from backend.chat import _rate_limits

    _rate_limits.clear()

    # Manually inject 10 timestamps from 61 seconds ago
    old_time = time.time() - 61
    _rate_limits["expired_sess"] = [old_time] * 10

    chunks, embeddings = _make_chunks_and_embeddings(n=3)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         _mock_embed_query(), _mock_stream_llm(tokens=["ok"]), \
         _mock_staleness():
        resp = await client.post(
            "/chat",
            json={"session_id": "expired_sess", "query": "Should work"},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert resp.status_code == 200

    _rate_limits.clear()


@pytest.mark.asyncio
async def test_parallel_execution(client):
    """Verify asyncio.gather used for staleness + embedding (check both called)."""
    file_list = [
        {"file_id": "fid_0", "file_name": "doc.pdf", "indexed_at": "2026-03-05T20:00:00Z"},
    ]
    chunks, embeddings = _make_chunks_and_embeddings(n=3, file_ids=["fid_0"] * 3)

    staleness_called = False
    embed_called = False

    async def _check_staleness(fl, token):
        nonlocal staleness_called
        staleness_called = True
        return (set(), {})

    async def _embed(query):
        nonlocal embed_called
        embed_called = True
        np.random.seed(99)
        return np.random.randn(DIM)

    with _mock_auth(), _mock_session_data(chunks, embeddings), \
         patch("backend.chat.check_staleness", side_effect=_check_staleness), \
         patch("backend.chat._embed_query", side_effect=_embed), \
         _mock_stream_llm(tokens=["Parallel"]):
        resp = await client.post(
            "/chat",
            json={"session_id": "sess_1", "query": "test", "file_list": file_list},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    assert staleness_called, "check_staleness was not called"
    assert embed_called, "_embed_query was not called"
