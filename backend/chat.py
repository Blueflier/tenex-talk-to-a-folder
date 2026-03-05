"""/chat SSE endpoint with streaming LLM responses and citation extraction."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator

import numpy as np
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from backend.auth import get_google_user_id
from backend.config import VOLUME_PATH, get_llm_client
from backend.retrieval import (
    check_threshold,
    extract_citations,
    retrieve_mixed,
)

router = APIRouter()

# Embedding model for queries
EMBEDDING_MODEL = "text-embedding-3-small"


def build_prompt(query: str, retrieved_chunks: list[tuple[dict[str, Any], float]]) -> str:
    """Format numbered sources into a system prompt constraining the LLM."""
    sources = "\n\n".join(
        f"[{i + 1}] {c['file_name']}"
        + (f", p.{c['page_number']}" if c.get("page_number") else "")
        + (f", row {c['row_number']}" if c.get("row_number") else "")
        + (f", slide {c['slide_index']}" if c.get("slide_index") else "")
        + f"\n{c['text']}"
        for i, (c, _) in enumerate(retrieved_chunks)
    )

    return f"""You are an assistant answering questions about a user's Google Drive files.
Answer using ONLY the sources below. Cite inline as [1], [2], etc.
If the answer is not in the sources, say "I couldn't find that in the provided files."
Do not guess or use outside knowledge.

SOURCES:
{sources}

QUESTION: {query}"""


async def stream_llm(
    query: str,
    retrieved_chunks: list[tuple[dict[str, Any], float]],
    model_key: str = "deepseek",
) -> AsyncGenerator[str, None]:
    """Stream LLM response token-by-token."""
    client, model_name = get_llm_client()
    prompt = build_prompt(query, retrieved_chunks)

    response = await client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=2000,
        temperature=0.1,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


async def _embed_query(query: str) -> np.ndarray:
    """Embed a query string using OpenAI text-embedding-3-small."""
    import os

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    return np.array(response.data[0].embedding)


async def _load_session_data(
    user_id: str, session_id: str
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Load chunks and embeddings from Volume storage."""
    base = VOLUME_PATH / user_id
    chunks_path = base / f"{session_id}_chunks.json"
    embeddings_path = base / f"{session_id}_embeddings.npy"

    if not chunks_path.exists() or not embeddings_path.exists():
        raise HTTPException(status_code=404, detail="Session data not found")

    with open(chunks_path) as f:
        chunks = json.load(f)

    embeddings = np.load(str(embeddings_path))
    return chunks, embeddings


async def _chat_event_stream(
    query: str, user_id: str, session_id: str
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a chat query."""
    try:
        # Load session data
        chunks, embeddings = await _load_session_data(user_id, session_id)

        # Embed query
        query_embedding = await _embed_query(query)

        # Retrieve relevant chunks
        results = retrieve_mixed(query_embedding, chunks, embeddings)

        # Check threshold
        if check_threshold(results):
            yield f'data: {json.dumps({"type": "no_results"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Stream LLM response
        async for token in stream_llm(query, results):
            yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

        # Emit citations after stream completes
        citations = extract_citations(results)
        yield f'data: {json.dumps({"type": "citations", "citations": citations})}\n\n'

        # Done
        yield "data: [DONE]\n\n"

    except HTTPException:
        raise
    except Exception as e:
        yield f'data: {json.dumps({"type": "error", "message": str(e)})}\n\n'
        yield "data: [DONE]\n\n"


@router.post("/chat")
async def chat_endpoint(
    request: Request,
    authorization: str = Header(None),
):
    """SSE streaming chat endpoint.

    Accepts: { session_id, query, file_list }
    Returns: StreamingResponse with SSE events.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = await get_google_user_id(token)

    body = await request.json()
    session_id = body.get("session_id")
    query = body.get("query")

    if not session_id or not query:
        raise HTTPException(status_code=400, detail="session_id and query required")

    return StreamingResponse(
        _chat_event_stream(query, user_id, session_id),
        media_type="text/event-stream",
    )
