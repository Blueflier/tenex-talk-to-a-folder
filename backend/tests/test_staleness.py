"""Tests for staleness detection module."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.staleness import (
    STALENESS_TTL,
    _staleness_cache,
    check_staleness,
    invalidate_caches,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear module caches before each test."""
    _staleness_cache.clear()
    yield
    _staleness_cache.clear()


def _mock_aiohttp_response(status, json_data):
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    return resp


def _mock_session(responses: dict):
    """Create mock aiohttp.ClientSession with per-file_id responses."""
    session = AsyncMock()

    async def _get(url, headers=None):
        # Extract file_id from URL
        file_id = url.split("/files/")[1].split("?")[0]
        return responses[file_id]

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(side_effect=lambda url, **kw: _make_ctx(responses, url))
    return ctx


def _make_ctx(responses, url):
    """Create async context manager for a single GET call."""
    file_id = url.split("/files/")[1].split("?")[0]
    resp = responses[file_id]
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_check_staleness_fresh():
    """Files with modifiedTime < indexed_at are NOT in stale_ids."""
    file_list = [
        {"file_id": "f1", "file_name": "doc.pdf", "indexed_at": "2026-03-05T20:00:00Z"},
    ]
    responses = {
        "f1": _mock_aiohttp_response(200, {
            "id": "f1", "name": "doc.pdf", "modifiedTime": "2026-03-05T19:00:00Z",
        }),
    }

    with patch("backend.staleness.aiohttp.ClientSession", return_value=_mock_session(responses)):
        stale_ids, file_errors = await check_staleness(file_list, "token123")

    assert "f1" not in stale_ids
    assert len(file_errors) == 0


@pytest.mark.asyncio
async def test_check_staleness_stale():
    """Files with modifiedTime > indexed_at ARE in stale_ids."""
    file_list = [
        {"file_id": "f1", "file_name": "doc.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    responses = {
        "f1": _mock_aiohttp_response(200, {
            "id": "f1", "name": "doc.pdf", "modifiedTime": "2026-03-05T20:00:00Z",
        }),
    }

    with patch("backend.staleness.aiohttp.ClientSession", return_value=_mock_session(responses)):
        stale_ids, file_errors = await check_staleness(file_list, "token123")

    assert "f1" in stale_ids
    assert len(file_errors) == 0


@pytest.mark.asyncio
async def test_staleness_error_handling():
    """404 -> not_found error, 403 -> access_denied error; both in stale_ids."""
    file_list = [
        {"file_id": "f1", "file_name": "gone.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
        {"file_id": "f2", "file_name": "locked.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    responses = {
        "f1": _mock_aiohttp_response(404, {}),
        "f2": _mock_aiohttp_response(403, {}),
    }

    with patch("backend.staleness.aiohttp.ClientSession", return_value=_mock_session(responses)):
        stale_ids, file_errors = await check_staleness(file_list, "token123")

    assert "f1" in stale_ids
    assert "f2" in stale_ids
    assert file_errors["f1"] == "not_found"
    assert file_errors["f2"] == "access_denied"


@pytest.mark.asyncio
async def test_staleness_cache_ttl():
    """Second call within 60s returns cached result, no API call."""
    file_list = [
        {"file_id": "f1", "file_name": "doc.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    responses = {
        "f1": _mock_aiohttp_response(200, {
            "id": "f1", "name": "doc.pdf", "modifiedTime": "2026-03-05T20:00:00Z",
        }),
    }

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = _mock_session(responses)

    with patch("backend.staleness.aiohttp.ClientSession", mock_session_cls):
        stale1, _ = await check_staleness(file_list, "token123")
        stale2, _ = await check_staleness(file_list, "token123")

    # Session created only once (cached on second call)
    assert mock_session_cls.call_count == 1
    assert stale1 == stale2


@pytest.mark.asyncio
async def test_staleness_cache_expired():
    """Call after 60s re-checks Drive API."""
    file_list = [
        {"file_id": "f1", "file_name": "doc.pdf", "indexed_at": "2026-03-05T18:00:00Z"},
    ]
    responses = {
        "f1": _mock_aiohttp_response(200, {
            "id": "f1", "name": "doc.pdf", "modifiedTime": "2026-03-05T20:00:00Z",
        }),
    }

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = _mock_session(responses)

    with patch("backend.staleness.aiohttp.ClientSession", mock_session_cls), \
         patch("backend.staleness.time") as mock_time:
        mock_time.time.side_effect = [100.0, 100.0, 200.0, 200.0]
        await check_staleness(file_list, "token123")
        await check_staleness(file_list, "token123")

    # Session created twice (cache expired on second call)
    assert mock_session_cls.call_count == 2


@pytest.mark.asyncio
async def test_invalidate_caches():
    """invalidate_caches removes entries from both staleness and grep text caches."""
    from backend.grep import _grep_text_cache

    # Populate both caches
    _staleness_cache["f1"] = (True, None, time.time())
    _grep_text_cache["f1"] = ("some text", time.time())

    invalidate_caches("f1")

    assert "f1" not in _staleness_cache
    assert "f1" not in _grep_text_cache
    _grep_text_cache.clear()
