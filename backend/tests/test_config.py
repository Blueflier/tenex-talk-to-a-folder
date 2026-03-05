"""Tests for model strategy config."""
import pytest


def test_get_llm_client_deepseek_default(monkeypatch):
    """get_llm_client with ACTIVE_MODEL='deepseek' returns client with deepseek base_url."""
    monkeypatch.setenv("ACTIVE_MODEL", "deepseek")

    # Force reimport to pick up env change
    import importlib
    import config
    importlib.reload(config)

    client, model_name = config.get_llm_client()
    assert "deepseek" in str(client.base_url)
    assert model_name == "deepseek-chat"


def test_get_llm_client_openai(monkeypatch):
    """get_llm_client with ACTIVE_MODEL='openai' returns client with openai base_url."""
    monkeypatch.setenv("ACTIVE_MODEL", "openai")

    import importlib
    import config
    importlib.reload(config)

    client, model_name = config.get_llm_client()
    assert "openai" in str(client.base_url)
    assert model_name == "gpt-4o-mini"


def test_health_endpoint():
    """Health endpoint returns {'status': 'ok'}."""
    from httpx import ASGITransport, AsyncClient
    import asyncio
    from app import web_app

    async def _test():
        async with AsyncClient(
            transport=ASGITransport(app=web_app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    asyncio.run(_test())
