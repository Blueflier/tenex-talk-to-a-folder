"""Staleness detection via Google Drive metadata comparison.

NOTE: _staleness_cache is in-memory and per-process. With multiple
replicas, each process maintains its own cache. This is acceptable since the
cache is a performance optimization with a short TTL, not a correctness
requirement — redundant Drive API calls are safe, just slower.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.drive_client import DRIVE_API_BASE, drive_session

logger = logging.getLogger(__name__)


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp to a timezone-aware datetime."""
    # Handle both "2026-03-05T20:00:00Z" and "2026-03-05T20:00:00.000Z"
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


# Cache: file_id -> (is_stale, error_or_None, checked_at_epoch)
_staleness_cache: dict[str, tuple[bool, str | None, float]] = {}
STALENESS_TTL = 60


async def get_file_metadata(
    session, file_id: str,
) -> dict:
    """Fetch Drive file metadata. Returns error dict on 404/403."""
    url = f"{DRIVE_API_BASE}/{file_id}?fields=id,name,modifiedTime"
    async with session.get(url) as r:
        if r.status == 404:
            return {"file_id": file_id, "error": "not_found"}
        if r.status == 403:
            return {"file_id": file_id, "error": "access_denied"}
        return await r.json()


async def check_staleness(
    file_list: list[dict], access_token: str
) -> tuple[set[str], dict[str, str]]:
    """Check which files are stale by comparing Drive modifiedTime to indexed_at.

    Returns (stale_ids, file_errors) where file_errors maps file_id to error type.
    Uses in-memory cache with STALENESS_TTL second TTL.
    """
    now = time.time()
    stale_ids: set[str] = set()
    file_errors: dict[str, str] = {}

    # Separate cached vs uncached files
    uncached_files = []
    for f in file_list:
        fid = f["file_id"]
        cached = _staleness_cache.get(fid)
        if cached and (now - cached[2]) < STALENESS_TTL:
            is_stale, error, _ = cached
            if is_stale:
                stale_ids.add(fid)
            if error:
                file_errors[fid] = error
        else:
            uncached_files.append(f)

    if not uncached_files:
        return stale_ids, file_errors

    # Fetch metadata for uncached files
    async with drive_session(access_token) as session:
        tasks = [
            get_file_metadata(session, f["file_id"])
            for f in uncached_files
        ]
        results = await asyncio.gather(*tasks)

    now = time.time()
    for f, meta in zip(uncached_files, results):
        fid = f["file_id"]
        if "error" in meta:
            stale_ids.add(fid)
            file_errors[fid] = meta["error"]
            _staleness_cache[fid] = (True, meta["error"], now)
            logger.info("staleness_check file_id=%s error=%s", fid, meta["error"])
        elif _parse_iso(meta["modifiedTime"]) > _parse_iso(f["indexed_at"]):
            stale_ids.add(fid)
            _staleness_cache[fid] = (True, None, now)
            logger.info("staleness_check file_id=%s stale=true", fid)
        else:
            _staleness_cache[fid] = (False, None, now)

    return stale_ids, file_errors


def invalidate_caches(file_id: str) -> None:
    """Remove file_id from both staleness and grep text caches."""
    _staleness_cache.pop(file_id, None)
    # Import at function level to avoid circular imports
    from backend.grep import _grep_text_cache
    _grep_text_cache.pop(file_id, None)
