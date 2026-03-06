"""Google Drive link resolution, file listing, and export."""
import re
from typing import Optional

import aiohttp

DRIVE_FOLDER_PATTERN = re.compile(r"/folders/([-\w]+)")
DRIVE_FILE_PATTERN = re.compile(r"/d/([-\w]+)")
DRIVE_OPEN_PATTERN = re.compile(r"[?&]id=([-\w]+)")
DRIVE_URL_PATTERN = re.compile(r"[-\w]{25,}")
# Google Docs/Sheets/Slides URL patterns: {service}.google.com/{type}/d/{id}
DOCS_PATTERN = re.compile(r"docs\.google\.com/document/d/([-\w]+)")
SHEETS_PATTERN = re.compile(r"sheets\.google\.com/spreadsheets/d/([-\w]+)")
SLIDES_PATTERN = re.compile(r"slides\.google\.com/presentation/d/([-\w]+)")

SUPPORTED_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "text/plain",
    "text/markdown",
}

EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

SKIP_REASONS = {
    "image/": "Image files are not supported",
    "video/": "Video files are not supported",
    "application/zip": "ZIP archives are not supported",
    "application/x-zip": "ZIP archives are not supported",
}

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3/files"


def extract_drive_id(url: str) -> Optional[str]:
    """Extract file or folder ID from a Google Drive, Docs, Sheets, or Slides URL."""
    m = DRIVE_FOLDER_PATTERN.search(url)
    if m:
        return m.group(1)
    m = DOCS_PATTERN.search(url)
    if m:
        return m.group(1)
    m = SHEETS_PATTERN.search(url)
    if m:
        return m.group(1)
    m = SLIDES_PATTERN.search(url)
    if m:
        return m.group(1)
    m = DRIVE_FILE_PATTERN.search(url)
    if m:
        return m.group(1)
    m = DRIVE_OPEN_PATTERN.search(url)
    if m:
        return m.group(1)
    m = DRIVE_URL_PATTERN.search(url)
    if m:
        return m.group(0)
    return None


def classify_file(mime_type: str) -> dict:
    """Check if a mime type is supported. Returns {supported, reason}."""
    if mime_type in SUPPORTED_MIME_TYPES:
        return {"supported": True, "reason": None}
    for prefix, reason in SKIP_REASONS.items():
        if mime_type.startswith(prefix):
            return {"supported": False, "reason": reason}
    return {"supported": False, "reason": f"Unsupported file type: {mime_type}"}


async def resolve_drive_link(access_token: str, drive_id: str) -> dict:
    """Get metadata for a file/folder. Returns {id, name, mimeType, size}."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{DRIVE_API_BASE}/{drive_id}",
            params={"fields": "id,name,mimeType,size"},
            headers={"Authorization": f"Bearer {access_token}"},
        ) as r:
            if r.status == 404:
                raise ValueError("File or folder not found")
            if r.status == 403:
                raise PermissionError("No access to this file/folder")
            r.raise_for_status()
            return await r.json()


async def list_folder_files(access_token: str, folder_id: str) -> list[dict]:
    """List all files in a folder (non-recursive), handling pagination."""
    files = []
    page_token = None
    async with aiohttp.ClientSession() as session:
        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, size)",
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token
            async with session.get(
                DRIVE_API_BASE,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as r:
                r.raise_for_status()
                data = await r.json()
                files.extend(data.get("files", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
    return files


async def export_file(access_token: str, file_id: str, mime_type: str) -> bytes:
    """Export a Google Workspace file or download a binary file."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        if mime_type in EXPORT_MIME_MAP:
            url = f"{DRIVE_API_BASE}/{file_id}/export"
            params = {"mimeType": EXPORT_MIME_MAP[mime_type]}
        else:
            url = f"{DRIVE_API_BASE}/{file_id}"
            params = {"alt": "media"}

        async with session.get(url, params=params, headers=headers) as r:
            r.raise_for_status()
            return await r.read()
