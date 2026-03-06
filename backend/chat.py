"""/chat SSE endpoint with streaming LLM responses, hybrid retrieval, and staleness detection.

NOTE: _rate_limits is in-memory and per-process. With multiple replicas,
each process enforces its own rate limit independently. A shared Redis counter
would be the fix if abuse becomes an issue.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, AsyncGenerator

import numpy as np
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from backend.auth import get_google_user_id
from backend.config import VOLUME_PATH, get_llm_client
from backend.grep import extract_keywords, grep_live
from backend.retrieval import (
    check_threshold,
    extract_citations,
    retrieve_mixed,
)
from backend.staleness import check_staleness

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiting: sliding window of timestamps per session_id (per-container)
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60  # seconds


def _check_rate_limit(session_id: str) -> bool:
    """Check if session_id has exceeded the rate limit.

    Uses a sliding window: prune timestamps older than 60s,
    return True if limit exceeded (>= 10 requests in window).
    """
    now = time.time()
    timestamps = _rate_limits[session_id]
    # Prune old timestamps
    _rate_limits[session_id] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    return len(_rate_limits[session_id]) >= _RATE_LIMIT_MAX

# Embedding model for queries
EMBEDDING_MODEL = "text-embedding-3-small"


def build_prompt(
    query: str,
    retrieved_chunks: list[tuple[dict[str, Any], float]],
    grep_results: list[dict[str, Any]] | None = None,
) -> str:
    """Format numbered sources into a system prompt constraining the LLM."""
    sources_parts = []
    idx = 1

    for c, _ in retrieved_chunks:
        header = f"[{idx}] {c['file_name']}"
        if c.get("page_number"):
            header += f", p.{c['page_number']}"
        if c.get("row_number"):
            header += f", row {c['row_number']}"
        if c.get("slide_index"):
            header += f", slide {c['slide_index']}"
        sources_parts.append(f"{header}\n{c['text']}")
        idx += 1

    for g in grep_results or []:
        sources_parts.append(f"[{idx}] {g.get('file_name', g['file_id'])} (live search)\n{g['text']}")
        idx += 1

    sources = "\n\n".join(sources_parts)

    return f"""You are an assistant answering questions about a user's Google Drive files.
Answer using ONLY the sources below. Cite inline as [1], [2], etc.
If the answer is not in the sources, say "I couldn't find that in the provided files."
Do not guess or use outside knowledge.

FORMAT: Use Markdown for readability. Use **bold** for key terms, bullet points (- ) for lists,
and ### headings to organize longer answers. Keep answers well-structured but concise.

SOURCES:
{sources}

QUESTION: {query}"""


async def stream_llm(
    query: str,
    retrieved_chunks: list[tuple[dict[str, Any], float]],
    grep_results: list[dict[str, Any]] | None = None,
    model_key: str = "deepseek",
) -> AsyncGenerator[str, None]:
    """Stream LLM response token-by-token."""
    client, model_name = get_llm_client()
    prompt = build_prompt(query, retrieved_chunks, grep_results)

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
        logger.warning("session_data_missing user=%s session=%s path=%s", user_id, session_id, chunks_path)
        raise HTTPException(status_code=404, detail="Session data not found")

    with open(chunks_path) as f:
        chunks = json.load(f)

    embeddings = np.load(str(embeddings_path))
    return chunks, embeddings


async def _chat_event_stream(
    query: str,
    user_id: str,
    session_id: str,
    file_list: list[dict[str, Any]] | None = None,
    access_token: str = "",
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a chat query with hybrid retrieval."""
    try:
        # Load session data
        chunks, embeddings = await _load_session_data(user_id, session_id)

        # Run staleness check and query embedding in parallel
        if file_list:
            staleness_result, query_embedding = await asyncio.gather(
                check_staleness(file_list, access_token),
                _embed_query(query),
            )
            stale_ids, file_errors = staleness_result
        else:
            stale_ids, file_errors = set(), {}
            query_embedding = await _embed_query(query)

        # Emit staleness SSE event BEFORE any tokens
        if stale_ids and file_list:
            stale_file_info = [
                {
                    "file_name": f["file_name"],
                    "file_id": f["file_id"],
                    "error": file_errors.get(f["file_id"]),
                }
                for f in file_list
                if f["file_id"] in stale_ids
            ]
            yield f'data: {json.dumps({"type": "staleness", "files": stale_file_info})}\n\n'

        # Three-way partition per CONTEXT.md:
        # deleted_ids: 404 files -> still use cosine (old embeddings valid)
        # grep_ids: modified + 403 files -> route to grep_live
        # fresh_ids: everything else -> cosine
        deleted_ids = {fid for fid, err in file_errors.items() if err == "not_found"}
        grep_ids = stale_ids - deleted_ids
        fresh_mask = [i for i, c in enumerate(chunks) if c["file_id"] not in grep_ids]

        # Fresh path (includes deleted files -- use old embeddings)
        retrieved: list[tuple[dict[str, Any], float]] = []
        if fresh_mask:
            fresh_chunks = [chunks[i] for i in fresh_mask]
            fresh_embeddings = embeddings[fresh_mask]
            retrieved = retrieve_mixed(query_embedding, fresh_chunks, fresh_embeddings)

        # Mark deleted file citations with "(deleted)" suffix
        if deleted_ids:
            retrieved = [
                (
                    {**c, "file_name": c["file_name"] + " (deleted)"}
                    if c["file_id"] in deleted_ids
                    else c,
                    score,
                )
                for c, score in retrieved
            ]

        # Stale/grep path
        all_grep_results: list[dict[str, Any]] = []
        if grep_ids and file_list:
            keywords = await extract_keywords(query)
            mime_map = {f["file_id"]: f.get("mimeType", "") for f in file_list}
            grep_tasks = [
                grep_live(fid, keywords, access_token, mime_type=mime_map.get(fid, ""))
                for fid in grep_ids
            ]
            grep_results_list = await asyncio.gather(*grep_tasks)
            for fid, results in zip(grep_ids, grep_results_list):
                # Attach file_name for prompt formatting
                file_name_map = {f["file_id"]: f["file_name"] for f in file_list}
                for r in results:
                    r["file_name"] = file_name_map.get(r["file_id"], r["file_id"])
                    r["source"] = "grep"
                all_grep_results.extend(results)

        # Check if we have any results at all
        if not retrieved and not all_grep_results:
            yield f'data: {json.dumps({"type": "no_results"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Check threshold only if no grep results to supplement
        # Skip threshold for broad queries (summarize, overview, etc.)
        _broad_keywords = {"summarize", "summary", "overview", "explain", "describe", "tell me about", "what is"}
        is_broad = any(kw in query.lower() for kw in _broad_keywords)
        if not is_broad and not all_grep_results and check_threshold(retrieved):
            yield f'data: {json.dumps({"type": "no_results"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # Stream LLM response
        async for token in stream_llm(query, retrieved, all_grep_results):
            yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

        # Emit citations after stream completes
        citations = extract_citations(retrieved)
        # Add grep citations
        base_idx = len(citations)
        for i, g in enumerate(all_grep_results):
            citations.append(
                {
                    "index": base_idx + i + 1,
                    "file_name": g.get("file_name", g["file_id"]),
                    "file_id": g["file_id"],
                    "page_number": None,
                    "row_number": None,
                    "slide_index": None,
                    "chunk_text": g["text"],
                    "source": "grep",
                }
            )

        yield f'data: {json.dumps({"type": "citations", "citations": citations})}\n\n'

        # Done
        yield "data: [DONE]\n\n"

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("chat_stream_error user=%s session=%s", user_id, session_id)
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
    file_list = body.get("file_list")  # [{file_id, file_name, indexed_at}, ...]

    if not session_id or not query:
        raise HTTPException(status_code=400, detail="session_id and query required")

    if _check_rate_limit(session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    _rate_limits[session_id].append(time.time())

    logger.info("chat_request user=%s session=%s query=%r", user_id, session_id, query)

    return StreamingResponse(
        _chat_event_stream(query, user_id, session_id, file_list, token),
        media_type="text/event-stream",
    )
