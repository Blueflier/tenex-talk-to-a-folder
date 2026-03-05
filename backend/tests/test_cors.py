"""Tests for CORS configuration."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_cors_allows_localhost_5173():
    """CORS allows localhost:5173 origin."""
    from app import web_app

    async with AsyncClient(
        transport=ASGITransport(app=web_app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_rejects_unlisted_origin():
    """CORS rejects unlisted origin (no CORS headers)."""
    from app import web_app

    async with AsyncClient(
        transport=ASGITransport(app=web_app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers
