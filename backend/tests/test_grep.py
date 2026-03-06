"""Tests for keyword extraction and grep_live module."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from backend.grep import (
    GREP_TEXT_TTL,
    _grep_text_cache,
    extract_keywords,
    fetch_and_extract,
    grep_live,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear grep text cache before each test."""
    _grep_text_cache.clear()
    yield
    _grep_text_cache.clear()


def _mock_llm_response(content: str):
    """Create a mock LLM completion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_extract_keywords():
    """Returns list of strings from valid JSON LLM response."""
    keywords_json = '["revenue", "sales", "income", "ARR", "Q3"]'
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response(keywords_json))

    with patch("backend.grep.get_llm_client", return_value=(mock_client, "deepseek-chat")):
        result = await extract_keywords("What is the revenue for Q3?")

    assert isinstance(result, list)
    assert "revenue" in result
    assert "sales" in result
    assert len(result) >= 3


@pytest.mark.asyncio
async def test_extract_keywords_fallback():
    """Returns stopword-filtered words on invalid JSON response."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response("not valid json at all"))

    with patch("backend.grep.get_llm_client", return_value=(mock_client, "deepseek-chat")):
        result = await extract_keywords("What is the revenue for Q3?")

    assert isinstance(result, list)
    # Should filter stopwords like "what", "is", "the", "for"
    assert "what" not in result
    assert "is" not in result
    assert "revenue" in result
    assert "q3?" in result or "q3" in result


@pytest.mark.asyncio
async def test_extract_keywords_strips_fences():
    """Handles ```json wrapped response correctly."""
    keywords_json = '```json\n["revenue", "sales", "income"]\n```'
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_llm_response(keywords_json))

    with patch("backend.grep.get_llm_client", return_value=(mock_client, "deepseek-chat")):
        result = await extract_keywords("What is the revenue?")

    assert isinstance(result, list)
    assert "revenue" in result
    assert "sales" in result


@pytest.mark.asyncio
async def test_grep_live_matches():
    """Returns matches with context windows (1 sentence before + after)."""
    text = "First sentence about nothing. Revenue was 100M in Q3. Another sentence here. Unrelated content follows."

    async def _fetch(fid, token, *, mime_type=""):
        return text

    with patch("backend.grep.fetch_and_extract", side_effect=_fetch):
        results = await grep_live("f1", ["revenue", "Q3"], "token123")

    assert len(results) >= 1
    match = results[0]
    assert "text" in match
    assert "matched_keyword" in match
    assert "sentence_index" in match
    assert match["file_id"] == "f1"
    # Context window should include surrounding sentences
    assert "First sentence" in match["text"]


@pytest.mark.asyncio
async def test_grep_live_cap():
    """Stops at 15 results."""
    # Create text with many matching sentences
    sentences = [f"Revenue item {i} is important." for i in range(30)]
    text = " ".join(sentences)

    async def _fetch(fid, token, *, mime_type=""):
        return text

    with patch("backend.grep.fetch_and_extract", side_effect=_fetch):
        results = await grep_live("f1", ["Revenue"], "token123")

    assert len(results) == 15


@pytest.mark.asyncio
async def test_grep_text_cache():
    """Second call within 5min uses cached text, no re-fetch."""
    text = "Some document text. Revenue was high. End of doc."
    fetch_mock = AsyncMock(return_value=text)

    with patch("backend.grep.fetch_and_extract", fetch_mock):
        await grep_live("f1", ["Revenue"], "token123")
        await grep_live("f1", ["Revenue"], "token123")

    # fetch called only once (cached on second call)
    assert fetch_mock.call_count == 1


# -- mime-type branching tests --


@pytest.mark.asyncio
async def test_fetch_and_extract_workspace_uses_export():
    """Workspace mimeType (google-apps.document) uses /export endpoint, not ?alt=media."""
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = AsyncMock(return_value="exported doc text")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.grep.drive_session", return_value=mock_session):
        result = await fetch_and_extract(
            "file123", "tok", mime_type="application/vnd.google-apps.document"
        )

    assert result == "exported doc text"
    # Verify /export URL was used
    call_args = mock_session.get.call_args
    url = call_args[0][0]
    assert "/export" in url
    assert "alt=media" not in url


@pytest.mark.asyncio
async def test_fetch_and_extract_binary_uses_alt_media():
    """Binary mimeType (application/pdf) uses ?alt=media as before."""
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = AsyncMock(return_value="binary content")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.grep.drive_session", return_value=mock_session):
        result = await fetch_and_extract(
            "file456", "tok", mime_type="application/pdf"
        )

    assert result == "binary content"
    # Verify ?alt=media URL was used
    call_args = mock_session.get.call_args
    url = call_args[0][0]
    assert "alt=media" in url
    assert "/export" not in url


@pytest.mark.asyncio
async def test_grep_live_passes_mime_type():
    """grep_live passes mime_type through to fetch_and_extract."""
    text = "Some document. Revenue was high. End."
    fetch_mock = AsyncMock(return_value=text)

    with patch("backend.grep.fetch_and_extract", fetch_mock):
        await grep_live(
            "f1", ["Revenue"], "token123",
            mime_type="application/vnd.google-apps.spreadsheet",
        )

    # Verify mime_type was passed through
    fetch_mock.assert_called_once()
    _, kwargs = fetch_mock.call_args
    assert kwargs.get("mime_type") == "application/vnd.google-apps.spreadsheet"
