"""Tests for Google auth verification."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_google_user_id_returns_sub_on_200():
    """get_google_user_id returns sub claim when Google API returns 200."""
    from auth import get_google_user_id

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"sub": "123456789"})

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("aiohttp.ClientSession", return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_session),
        __aexit__=AsyncMock(return_value=False),
    )):
        result = await get_google_user_id("valid-token")
        assert result == "123456789"


@pytest.mark.asyncio
async def test_get_google_user_id_raises_401_on_non_200():
    """get_google_user_id raises HTTPException(401) when Google API returns non-200."""
    from auth import get_google_user_id

    mock_response = AsyncMock()
    mock_response.status = 401

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("aiohttp.ClientSession", return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_session),
        __aexit__=AsyncMock(return_value=False),
    )):
        with pytest.raises(HTTPException) as exc_info:
            await get_google_user_id("invalid-token")
        assert exc_info.value.status_code == 401
