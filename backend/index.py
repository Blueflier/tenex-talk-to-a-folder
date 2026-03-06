"""POST /index SSE streaming endpoint: Drive -> extraction -> chunking -> embedding -> storage."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

import numpy as np
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

from backend.auth import get_google_user_id
from backend.chunking import chunk_pdf, chunk_sheet, chunk_slides, chunk_text
from backend.drive import (
    SUPPORTED_MIME_TYPES,
    classify_file,
    export_file,
    extract_drive_id,
    list_folder_files,
    resolve_drive_link,
)
from backend.embedding import embed_chunks
from backend.storage import append_session

router = APIRouter()

SIZE_WARNING_BYTES = 50 * 1024 * 1024  # 50MB

FOLDER_MIME = "application/vnd.google-apps.folder"


class IndexRequest(BaseModel):
    drive_url: str
    session_id: str


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _chunk_file_content(content: bytes, mime_type: str, file_name: str) -> list[dict]:
    """Route to the correct chunker based on mime type."""
    if mime_type == "application/pdf":
        return chunk_pdf(content, file_name)
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        return chunk_sheet(content.decode("utf-8", errors="replace"), file_name)
    elif mime_type == "application/vnd.google-apps.presentation":
        return chunk_slides(content.decode("utf-8", errors="replace"), file_name)
    else:
        # text/plain, text/markdown, google docs (exported as text)
        return chunk_text(content.decode("utf-8", errors="replace"), file_name)


async def _index_event_stream(
    drive_url: str,
    session_id: str,
    access_token: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for the full indexing pipeline."""
    try:
        # 1. Validate drive URL
        drive_id = extract_drive_id(drive_url)
        if drive_id is None:
            yield _sse_event("error", {"message": "Invalid Google Drive URL", "code": "invalid_url"})
            return

        # 2. Resolve link
        meta = await resolve_drive_link(access_token, drive_id)

        # 3. Build file list
        if meta.get("mimeType") == FOLDER_MIME:
            files = await list_folder_files(access_token, drive_id)
            # Empty folder check
            if not files:
                yield _sse_event("error", {"message": "This folder is empty", "code": "empty_folder"})
                return
        else:
            files = [meta]

        # 4. Classify files as supported/unsupported
        supported_files = []
        skipped_files = []
        for f in files:
            classification = classify_file(f.get("mimeType", ""))
            if classification["supported"]:
                supported_files.append(f)
            else:
                skipped_files.append({
                    "file_id": f["id"],
                    "file_name": f.get("name", "Unknown"),
                    "reason": classification["reason"],
                })

        # No supported files check
        if not supported_files:
            yield _sse_event("error", {
                "message": "No supported file types found. Supported: Google Docs, Sheets, Slides, PDF, TXT, MD",
                "code": "no_supported_files",
                "skipped_files": skipped_files,
            })
            return

        # Emit skipped file events
        for sf in skipped_files:
            yield _sse_event("extraction", {
                "file_id": sf["file_id"],
                "file_name": sf["file_name"],
                "status": "skipped",
                "reason": sf["reason"],
            })

        # 5. Phase 1 -- Extraction
        all_chunks: list[dict] = []
        files_indexed = 0

        for f in supported_files:
            file_id = f["id"]
            file_name = f.get("name", "Unknown")
            mime_type = f.get("mimeType", "")
            file_size = int(f.get("size", 0) or 0)

            # Large file warning
            if file_size > SIZE_WARNING_BYTES:
                size_mb = round(file_size / (1024 * 1024))
                yield _sse_event("warning", {
                    "file_id": file_id,
                    "file_name": file_name,
                    "message": f"Large file (~{size_mb}MB) - processing may be slow",
                })

            # Emit extracting status
            yield _sse_event("extraction", {
                "file_id": file_id,
                "file_name": file_name,
                "status": "extracting",
            })

            try:
                content = await export_file(access_token, file_id, mime_type)
                chunks = _chunk_file_content(content, mime_type, file_name)

                # Attach file_id and file_name to each chunk
                for c in chunks:
                    c["file_id"] = file_id
                    c["file_name"] = file_name

                all_chunks.extend(chunks)
                files_indexed += 1

                yield _sse_event("extraction", {
                    "file_id": file_id,
                    "file_name": file_name,
                    "status": "done",
                    "chunk_count": len(chunks),
                })
            except Exception as e:
                yield _sse_event("extraction", {
                    "file_id": file_id,
                    "file_name": file_name,
                    "status": "failed",
                    "error": str(e),
                })
                # Continue on per-file errors (best-effort)
                continue

        # 6. Phase 2 -- Embedding
        if not all_chunks:
            yield _sse_event("complete", {
                "files_indexed": 0,
                "total_chunks": 0,
                "skipped_files": skipped_files,
            })
            return

        yield _sse_event("embedding_start", {"total_chunks": len(all_chunks)})

        async def on_progress(embedded: int, total: int):
            # This callback is called by embed_chunks per batch
            pass

        # We need to yield progress from within the generator, so we collect progress
        # and use a custom approach
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        # Track progress via a list (mutable from callback)
        progress_events: list[dict] = []

        async def _progress_callback(embedded: int, total: int):
            progress_events.append({"embedded": embedded, "total": total})

        try:
            embeddings = await embed_chunks(client, all_chunks, on_progress=_progress_callback)
        except Exception:
            # Save what we have (nothing embedded if it failed on first batch)
            embeddings = np.empty((0, 1536), dtype=np.float32)

        # Emit progress events that were collected
        for pe in progress_events:
            yield _sse_event("embedding_progress", pe)

        # 7. Storage
        if embeddings.shape[0] > 0:
            append_session(user_id, session_id, embeddings, all_chunks)

        # 8. Complete
        indexed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        yield _sse_event("complete", {
            "files_indexed": files_indexed,
            "total_chunks": len(all_chunks),
            "skipped_files": skipped_files,
            "indexed_at": indexed_at,
        })

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})


@router.post("/index")
async def index_endpoint(
    body: IndexRequest,
    authorization: str = Header(None),
):
    """SSE streaming index endpoint.

    Accepts: { drive_url, session_id } with Authorization: Bearer <token>
    Returns: StreamingResponse with SSE events for extraction + embedding progress.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = await get_google_user_id(token)

    return StreamingResponse(
        _index_event_stream(body.drive_url, body.session_id, token, user_id),
        media_type="text/event-stream",
    )
