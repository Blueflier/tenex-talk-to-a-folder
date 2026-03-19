"""Per-file re-indexing: surgical chunk replacement and cache invalidation."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI

from backend.config import VOLUME_PATH
from backend.chunking import chunk_text, chunk_pdf, chunk_sheet, chunk_slides
from backend.drive import export_file, resolve_drive_link
from backend.embedding import embed_chunks, EMBED_DIM
from backend.staleness import invalidate_caches
from backend.summarize import generate_summary_chunks


async def fetch_and_chunk_file(file_id: str, access_token: str) -> list[dict]:
    """Fetch file from Drive, determine type, chunk it. Returns chunk dicts with file_id."""
    meta = await resolve_drive_link(access_token, file_id)

    mime_type = meta["mimeType"]
    file_name = meta["name"]

    # Fetch content
    content = await export_file(access_token, file_id, mime_type)

    # Chunk based on type
    if mime_type == "application/pdf":
        chunks = chunk_pdf(content, file_name)
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        chunks = chunk_sheet(content.decode("utf-8", errors="replace"), file_name)
    elif mime_type == "application/vnd.google-apps.presentation":
        chunks = chunk_slides(content.decode("utf-8", errors="replace"), file_name)
    else:
        # text/plain, markdown, google docs (exported as text)
        chunks = chunk_text(content.decode("utf-8", errors="replace"), file_name)

    # Attach file_id and file_name to each chunk
    for c in chunks:
        c["file_id"] = file_id
        c["file_name"] = file_name

    return chunks


async def embed_new_chunks(chunks: list[dict]) -> np.ndarray:
    """Embed chunks using OpenAI text-embedding-3-small."""
    if not chunks:
        return np.empty((0, EMBED_DIM), dtype=np.float32)
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return await embed_chunks(client, chunks)


async def reindex_file(
    user_id: str,
    session_id: str,
    file_id: str,
    access_token: str,
    base_path: Path | None = None,
) -> dict:
    """Surgically replace one file's chunks in a session.

    1. Fetch + chunk the file from Drive
    2. Embed new chunks
    3. Load existing session, remove old file chunks, merge new
    4. Save, commit volume, invalidate caches
    5. Return {file_id, indexed_at}
    """
    root = base_path if base_path is not None else VOLUME_PATH

    # Step 1-2: fetch/chunk and embed
    new_chunks = await fetch_and_chunk_file(file_id, access_token)
    new_embeddings = await embed_new_chunks(new_chunks)

    # Step 3: load existing session
    chunks_path = root / user_id / f"{session_id}_chunks.json"
    emb_path = root / user_id / f"{session_id}_embeddings.npy"

    with open(chunks_path) as f:
        old_chunks = json.load(f)
    old_embeddings = np.load(str(emb_path))

    # Build keep mask: remove old chunks for this file AND old folder_overview summary
    keep_indices = [
        i for i, c in enumerate(old_chunks)
        if c["file_id"] != file_id and c.get("file_id") != "folder_overview"
    ]

    kept_chunks = [old_chunks[i] for i in keep_indices]
    if keep_indices:
        kept_embeddings = old_embeddings[keep_indices]
    else:
        kept_embeddings = np.empty((0, old_embeddings.shape[1]), dtype=np.float32)

    # Merge content chunks first
    merged_chunks = kept_chunks + new_chunks

    # Regenerate summary chunks for the updated file set
    # Filter to only content chunks (not old summaries) for summary generation
    content_chunks = [c for c in merged_chunks if not c.get("chunk_type")]
    try:
        summary_chunks = await generate_summary_chunks(content_chunks)
        summary_embeddings = await embed_new_chunks(summary_chunks)
        merged_chunks.extend(summary_chunks)
    except Exception:
        summary_embeddings = np.empty((0, EMBED_DIM), dtype=np.float32)

    # Stack all embeddings
    all_emb_parts = [e for e in [kept_embeddings, new_embeddings, summary_embeddings] if e.shape[0] > 0]
    if all_emb_parts:
        merged_embeddings = np.vstack(all_emb_parts)
    else:
        merged_embeddings = np.empty((0, EMBED_DIM), dtype=np.float32)

    # Step 4: save
    np.save(str(emb_path), merged_embeddings)
    with open(chunks_path, "w") as f:
        json.dump(merged_chunks, f)

    # Invalidate caches
    invalidate_caches(file_id)

    # Step 5: return result
    indexed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    return {"file_id": file_id, "indexed_at": indexed_at}


# --- FastAPI endpoint ---

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()


@router.post("/reindex")
async def reindex_endpoint(
    request: Request,
    authorization: str = Header(None),
):
    """Re-index a single file in an existing session.

    Accepts: { session_id, file_id }
    Returns: { file_id, indexed_at }
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    from backend.auth import get_google_user_id
    user_id = await get_google_user_id(token)

    body = await request.json()
    session_id = body.get("session_id")
    file_id = body.get("file_id")

    if not session_id or not file_id:
        raise HTTPException(status_code=400, detail="session_id and file_id required")

    try:
        result = await reindex_file(
            user_id=user_id,
            session_id=session_id,
            file_id=file_id,
            access_token=token,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result
