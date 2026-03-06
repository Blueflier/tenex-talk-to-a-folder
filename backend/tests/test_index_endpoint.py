"""Integration tests for POST /index SSE streaming endpoint."""
from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Mock modal module before any import
_modal_mock = MagicMock()
_modal_mock.App.return_value = MagicMock()
_modal_mock.Volume.from_name.return_value = MagicMock()
_modal_mock.Image.debian_slim.return_value.pip_install.return_value = MagicMock()
_modal_mock.Secret.from_name.return_value = MagicMock()
_modal_mock.asgi_app.return_value = lambda f: f
_modal_mock.function.return_value = lambda f: f
sys.modules["modal"] = _modal_mock

from backend.app import web_app


# ---- Helpers ----

def _parse_sse_events(text: str) -> list:
    """Parse SSE text into list of (event_name, data) tuples."""
    events = []
    current_event = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            raw = line[6:]
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = raw
            events.append({"event": current_event, "data": data})
            current_event = None
    return events


def _get_events_by_type(events: list, event_type: str) -> list:
    """Filter parsed SSE events by event name."""
    return [e for e in events if e["event"] == event_type]


# ---- Mock helpers ----

def _mock_auth(user_id="user_123"):
    return patch("backend.index.get_google_user_id", new_callable=AsyncMock, return_value=user_id)


def _mock_extract_drive_id(drive_id="folder_abc"):
    return patch("backend.index.extract_drive_id", return_value=drive_id)


def _mock_resolve_drive_link(meta=None):
    if meta is None:
        meta = {
            "id": "folder_abc",
            "name": "My Folder",
            "mimeType": "application/vnd.google-apps.folder",
        }
    return patch("backend.index.resolve_drive_link", new_callable=AsyncMock, return_value=meta)


def _mock_list_folder_files(files=None):
    if files is None:
        files = [
            {"id": "file_1", "name": "doc.txt", "mimeType": "text/plain", "size": "100"},
            {"id": "file_2", "name": "sheet.csv", "mimeType": "application/vnd.google-apps.spreadsheet", "size": "200"},
        ]
    return patch("backend.index.list_folder_files", new_callable=AsyncMock, return_value=files)


def _mock_export_file(content=b"Hello world content for testing."):
    return patch("backend.index.export_file", new_callable=AsyncMock, return_value=content)


def _mock_embed_chunks(dim=1536):
    async def _embed(client, chunks, on_progress=None, max_retries=3):
        n = len(chunks)
        if on_progress:
            await on_progress(n, n)
        return np.random.randn(n, dim).astype(np.float32)
    return patch("backend.index.embed_chunks", side_effect=_embed)


def _mock_save_session():
    return patch("backend.index.append_session")


def _mock_volume():
    return patch("backend.index.router", wraps=None)  # volume mock handled via app_volume


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=web_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---- Tests ----

@pytest.mark.asyncio
async def test_valid_folder_url(client):
    """POST /index with valid folder URL: extraction events per file, embedding, complete."""
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(), _mock_export_file(), _mock_embed_chunks(), \
         _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/folder_abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_events(resp.text)

    # Should have extraction events for each file
    extraction_events = _get_events_by_type(events, "extraction")
    extracting = [e for e in extraction_events if e["data"].get("status") == "extracting"]
    done = [e for e in extraction_events if e["data"].get("status") == "done"]
    assert len(extracting) == 2
    assert len(done) == 2
    for d in done:
        assert "chunk_count" in d["data"]

    # Should have embedding events
    embedding_start = _get_events_by_type(events, "embedding_start")
    assert len(embedding_start) == 1
    assert "total_chunks" in embedding_start[0]["data"]

    # Should have complete event
    complete = _get_events_by_type(events, "complete")
    assert len(complete) == 1
    assert complete[0]["data"]["files_indexed"] == 2
    assert complete[0]["data"]["total_chunks"] > 0


@pytest.mark.asyncio
async def test_invalid_drive_url(client):
    """POST /index with invalid URL: receives error event."""
    with _mock_auth(), \
         patch("backend.index.extract_drive_id", return_value=None):
        resp = await client.post(
            "/index",
            json={"drive_url": "not-a-drive-url", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    error_events = _get_events_by_type(events, "error")
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "invalid_url"


@pytest.mark.asyncio
async def test_single_file_url(client):
    """POST /index with single file URL: extraction for one file, embedding, complete."""
    single_file_meta = {
        "id": "file_single",
        "name": "report.pdf",
        "mimeType": "application/pdf",
        "size": "5000",
    }
    # Mock chunk_pdf to return some chunks from bytes
    with _mock_auth(), _mock_extract_drive_id("file_single"), \
         _mock_resolve_drive_link(single_file_meta), \
         _mock_export_file(b"fake pdf content"), \
         patch("backend.index.chunk_pdf", return_value=[{"text": "chunk1", "source": "report.pdf", "page": 1, "chunk_index": 0}]), \
         _mock_embed_chunks(), _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/file/d/file_single/view", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)

    extraction_events = _get_events_by_type(events, "extraction")
    extracting = [e for e in extraction_events if e["data"].get("status") == "extracting"]
    done = [e for e in extraction_events if e["data"].get("status") == "done"]
    assert len(extracting) == 1
    assert len(done) == 1

    complete = _get_events_by_type(events, "complete")
    assert len(complete) == 1
    assert complete[0]["data"]["files_indexed"] == 1


@pytest.mark.asyncio
async def test_unsupported_file_in_folder(client):
    """Unsupported file in folder: receives skipped status, rest processed."""
    files = [
        {"id": "file_1", "name": "doc.txt", "mimeType": "text/plain", "size": "100"},
        {"id": "file_2", "name": "photo.jpg", "mimeType": "image/jpeg", "size": "500"},
    ]
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(files), _mock_export_file(), _mock_embed_chunks(), \
         _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)

    extraction_events = _get_events_by_type(events, "extraction")
    skipped = [e for e in extraction_events if e["data"].get("status") == "skipped"]
    assert len(skipped) == 1
    assert skipped[0]["data"]["file_id"] == "file_2"
    assert "reason" in skipped[0]["data"]

    done = [e for e in extraction_events if e["data"].get("status") == "done"]
    assert len(done) == 1

    complete = _get_events_by_type(events, "complete")
    assert len(complete) == 1
    assert complete[0]["data"]["files_indexed"] == 1
    assert len(complete[0]["data"]["skipped_files"]) == 1


@pytest.mark.asyncio
async def test_empty_folder(client):
    """Empty folder: receives error event with code 'empty_folder'."""
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files([]):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/empty", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    error_events = _get_events_by_type(events, "error")
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "empty_folder"
    assert "empty" in error_events[0]["data"]["message"].lower()


@pytest.mark.asyncio
async def test_folder_only_unsupported_files(client):
    """Folder with only unsupported files: error with code 'no_supported_files'."""
    files = [
        {"id": "file_1", "name": "photo.jpg", "mimeType": "image/jpeg", "size": "500"},
        {"id": "file_2", "name": "video.mp4", "mimeType": "video/mp4", "size": "10000"},
    ]
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(files):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    error_events = _get_events_by_type(events, "error")
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "no_supported_files"
    assert "skipped_files" in error_events[0]["data"]
    assert len(error_events[0]["data"]["skipped_files"]) == 2


@pytest.mark.asyncio
async def test_large_file_warning(client):
    """File >50MB: receives warning event before extraction event."""
    files = [
        {"id": "file_big", "name": "huge.txt", "mimeType": "text/plain", "size": str(60 * 1024 * 1024)},
    ]
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(files), _mock_export_file(), _mock_embed_chunks(), \
         _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)

    warning_events = _get_events_by_type(events, "warning")
    assert len(warning_events) == 1
    assert warning_events[0]["data"]["file_id"] == "file_big"
    assert "Large file" in warning_events[0]["data"]["message"]

    # Warning should come before extraction for that file
    all_event_types = [e["event"] for e in events]
    warning_idx = all_event_types.index("warning")
    # Find first extraction event for file_big
    extraction_indices = [
        i for i, e in enumerate(events)
        if e["event"] == "extraction" and e["data"].get("file_id") == "file_big"
    ]
    assert len(extraction_indices) > 0
    assert warning_idx < extraction_indices[0]


@pytest.mark.asyncio
async def test_event_format(client):
    """Each SSE event has correct event name and JSON data shape."""
    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(), _mock_export_file(), _mock_embed_chunks(), \
         _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)
    assert len(events) > 0

    valid_event_types = {"extraction", "embedding_start", "embedding_progress", "complete", "error", "warning"}
    for e in events:
        assert e["event"] in valid_event_types, f"Unexpected event type: {e['event']}"
        assert isinstance(e["data"], dict), f"Event data is not a dict: {e['data']}"


@pytest.mark.asyncio
async def test_401_without_auth(client):
    """POST /index without Authorization header returns 401."""
    resp = await client.post(
        "/index",
        json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extraction_failure_continues(client):
    """Per-file extraction error doesn't stop the pipeline."""
    files = [
        {"id": "file_1", "name": "doc.txt", "mimeType": "text/plain", "size": "100"},
        {"id": "file_2", "name": "doc2.txt", "mimeType": "text/plain", "size": "200"},
    ]

    call_count = 0

    async def _export_side_effect(token, file_id, mime):
        nonlocal call_count
        call_count += 1
        if file_id == "file_1":
            raise Exception("Download failed")
        return b"File 2 content here for testing."

    with _mock_auth(), _mock_extract_drive_id(), _mock_resolve_drive_link(), \
         _mock_list_folder_files(files), \
         patch("backend.index.export_file", new_callable=AsyncMock, side_effect=_export_side_effect), \
         _mock_embed_chunks(), _mock_save_session(), \
         patch("backend.index.os.environ", {"OPENAI_API_KEY": "test-key"}):
        resp = await client.post(
            "/index",
            json={"drive_url": "https://drive.google.com/drive/folders/abc", "session_id": "sess_1"},
            headers={"Authorization": "Bearer valid_token"},
        )

    events = _parse_sse_events(resp.text)

    extraction_events = _get_events_by_type(events, "extraction")
    failed = [e for e in extraction_events if e["data"].get("status") == "failed"]
    done = [e for e in extraction_events if e["data"].get("status") == "done"]
    assert len(failed) == 1
    assert failed[0]["data"]["file_id"] == "file_1"
    assert "error" in failed[0]["data"]
    assert len(done) == 1
    assert done[0]["data"]["file_id"] == "file_2"

    # Pipeline still completes
    complete = _get_events_by_type(events, "complete")
    assert len(complete) == 1
    assert complete[0]["data"]["files_indexed"] == 1
