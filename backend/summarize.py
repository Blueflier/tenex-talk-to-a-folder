"""Generate per-file and folder-level summary chunks during indexing.

These synthetic chunks embed close to broad queries like
"what are these files about?" or "give me an overview of this folder."
"""
from __future__ import annotations

import logging
from typing import Any

from backend.config import get_llm_client

logger = logging.getLogger(__name__)

# Max content chars sent to the LLM per file for summarization
_MAX_CONTENT_FOR_SUMMARY = 3000


async def _summarize_file(file_name: str, sample_text: str) -> str:
    """Ask the LLM for a 1-2 sentence summary of a single file."""
    client, model_name = get_llm_client()

    response = await client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize this file in 1-2 concise sentences. "
                    f"File name: {file_name}\n\nContent sample:\n{sample_text}"
                ),
            }
        ],
        max_tokens=150,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


async def generate_summary_chunks(
    all_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate synthetic summary chunks for each file and the whole folder.

    Returns a list of summary chunk dicts (same shape as regular chunks)
    that should be appended to all_chunks before embedding.
    """
    # Group chunks by file
    file_chunks: dict[str, list[dict[str, Any]]] = {}
    file_meta: dict[str, dict[str, str]] = {}  # file_id -> {file_name, file_id}

    for c in all_chunks:
        fid = c["file_id"]
        if fid not in file_chunks:
            file_chunks[fid] = []
            file_meta[fid] = {"file_id": fid, "file_name": c["file_name"]}
        file_chunks[fid].append(c)

    # Generate per-file summaries
    summaries: dict[str, str] = {}  # file_id -> summary text
    for fid, chunks in file_chunks.items():
        # Build a content sample from the first chunks
        sample = "\n".join(c["text"] for c in chunks)[:_MAX_CONTENT_FOR_SUMMARY]
        fname = file_meta[fid]["file_name"]
        try:
            summary = await _summarize_file(fname, sample)
            summaries[fid] = summary
            logger.info("file_summary file=%s summary=%s", fname, summary[:100])
        except Exception:
            logger.warning("file_summary_failed file=%s", fname, exc_info=True)
            # Fallback: use first chunk text
            summaries[fid] = chunks[0]["text"][:200]

    # Build synthetic chunks
    summary_chunks: list[dict[str, Any]] = []

    # 1) Per-file summary chunks
    for fid, summary in summaries.items():
        meta = file_meta[fid]
        summary_chunks.append({
            "text": f"Summary of {meta['file_name']}: {summary}",
            "file_id": fid,
            "file_name": meta["file_name"],
            "chunk_type": "file_summary",
        })

    # 2) Folder-level overview chunk
    if len(summaries) > 1:
        parts = []
        for fid, summary in summaries.items():
            fname = file_meta[fid]["file_name"]
            parts.append(f"- {fname}: {summary}")
        overview_text = (
            f"This folder contains {len(summaries)} files. "
            f"Here is an overview of each file:\n" + "\n".join(parts)
        )
        summary_chunks.append({
            "text": overview_text,
            "file_id": "folder_overview",
            "file_name": "Folder Overview",
            "chunk_type": "folder_summary",
        })

    return summary_chunks
