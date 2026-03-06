"""Shared aiohttp client for Google Drive API calls with timeouts."""
from __future__ import annotations

import aiohttp

# 30s total timeout for all Drive API calls
DRIVE_TIMEOUT = aiohttp.ClientTimeout(total=30)

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3/files"


def drive_session(access_token: str) -> aiohttp.ClientSession:
    """Create an aiohttp session pre-configured for Drive API calls.

    Usage:
        async with drive_session(token) as session:
            async with session.get(url) as r:
                ...
    """
    return aiohttp.ClientSession(
        timeout=DRIVE_TIMEOUT,
        headers={"Authorization": f"Bearer {access_token}"},
    )
