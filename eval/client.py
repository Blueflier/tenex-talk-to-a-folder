"""Async HTTP client for POST /chat with SSE parsing.

Sends queries to the chat endpoint and parses the SSE stream
into text + citations.
"""

import json

import httpx


async def query_chat(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    query: str,
    auth_token: str = "",
) -> dict:
    """Send query to /chat and parse SSE response into text + citations.

    Args:
        client: httpx async client instance.
        base_url: Server base URL (e.g. http://localhost:8000).
        session_id: Session ID for the chat.
        query: User question text.
        auth_token: Optional Bearer token for Authorization header.

    Returns:
        {"text": str, "citations": list} parsed from SSE stream.
    """
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with client.stream(
        "POST",
        f"{base_url}/chat",
        json={"session_id": session_id, "query": query},
        headers=headers,
        timeout=120.0,
    ) as response:
        full_text = ""
        citations = []

        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]  # strip "data: "
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "token":
                full_text += event.get("content", "")
            elif event.get("type") == "citations":
                citations = event.get("citations", [])
            elif event.get("type") == "no_results":
                full_text = "I couldn't find that in the provided files."

    return {"text": full_text, "citations": citations}
