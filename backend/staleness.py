"""Staleness detection via Google Drive metadata comparison."""
from __future__ import annotations

import asyncio
import time

import aiohttp

# Cache: file_id -> (is_stale, error_or_None, checked_at_epoch)
_staleness_cache: dict[str, tuple[bool, str | None, float]] = {}
STALENESS_TTL = 60


async def get_file_metadata(
    session: aiohttp.ClientSession, file_id: str, access_token: str
) -> dict:
    """Fetch Drive file metadata. Returns error dict on 404/403."""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,modifiedTime"
    async with session.get(url, headers={"Authorization": f"Bearer {access_token}"}) as r:
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
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_file_metadata(session, f["file_id"], access_token)
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
        elif meta["modifiedTime"] > f["indexed_at"]:
            stale_ids.add(fid)
            _staleness_cache[fid] = (True, None, now)
        else:
            _staleness_cache[fid] = (False, None, now)

    return stale_ids, file_errors


def invalidate_caches(file_id: str) -> None:
    """Remove file_id from both staleness and grep text caches."""
    _staleness_cache.pop(file_id, None)
    # Import at function level to avoid circular imports
    from backend import grep
    grep._grep_text_cache.pop(file_id, None)
