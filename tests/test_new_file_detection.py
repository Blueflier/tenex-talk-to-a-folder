"""
Integration test for new file detection in Google Drive folders.

This test uses a REAL Google OAuth token and a REAL Google Drive folder.
It does NOT mock the Drive API -- it creates actual files and verifies
the server detects them as new.

Usage:
    1. Set GOOGLE_TOKEN and DRIVE_FOLDER_ID in .env (root of project)
       Get token from https://developers.google.com/oauthplayground
       Select "Drive API v3 > drive" scope, authorize, copy access token.
    2. Run:
         python -m pytest tests/test_new_file_detection.py -v -s

    Or interactive mode:
         python tests/test_new_file_detection.py --interactive

Requires: backend running on localhost:8000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Load .env from project root so GOOGLE_TOKEN / DRIVE_FOLDER_ID are available
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import aiohttp
import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"


# ── Helpers ──────────────────────────────────────────────────────────────────


async def get_user_id(token: str) -> str:
    """Verify token works by calling Drive API (tokeninfo). No openid scope needed."""
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={token}",
        ) as r:
            if r.status != 200:
                raise RuntimeError(f"Token invalid: {r.status} {await r.text()}")
            info = await r.json()
            return info.get("azp", "unknown")


async def list_folder_files(token: str, folder_id: str) -> list[dict]:
    """List files in a Drive folder."""
    async with aiohttp.ClientSession() as s:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "files(id, name, mimeType)",
            "pageSize": 100,
        }
        async with s.get(
            DRIVE_API_BASE,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        ) as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("files", [])


async def create_test_file(
    token: str, folder_id: str, name: str, content: str
) -> str:
    """Create a plain text file in the Drive folder. Returns file ID."""
    metadata = {
        "name": name,
        "parents": [folder_id],
        "mimeType": "text/plain",
    }
    # Use multipart upload
    async with aiohttp.ClientSession() as s:
        # Simple upload with metadata
        boundary = "test_boundary_123"
        body_parts = []
        body_parts.append(f"--{boundary}")
        body_parts.append("Content-Type: application/json; charset=UTF-8")
        body_parts.append("")
        body_parts.append(json.dumps(metadata))
        body_parts.append(f"--{boundary}")
        body_parts.append("Content-Type: text/plain")
        body_parts.append("")
        body_parts.append(content)
        body_parts.append(f"--{boundary}--")
        body = "\r\n".join(body_parts)

        async with s.post(
            f"{DRIVE_UPLOAD_URL}?uploadType=multipart",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            data=body.encode(),
        ) as r:
            if r.status not in (200, 201):
                text = await r.text()
                raise RuntimeError(f"Failed to create file: {r.status} {text}")
            result = await r.json()
            return result["id"]


async def delete_test_file(token: str, file_id: str) -> None:
    """Delete a file from Drive (cleanup)."""
    async with aiohttp.ClientSession() as s:
        async with s.delete(
            f"{DRIVE_API_BASE}/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
        ) as r:
            # 204 = success, 404 = already gone
            if r.status not in (204, 404):
                print(f"Warning: cleanup failed for {file_id}: {r.status}")


async def index_folder(token: str, folder_id: str, session_id: str) -> dict:
    """Index a folder via the backend /index SSE endpoint. Returns completion data."""
    url = f"{BACKEND_URL}/index"
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            url,
            json={
                "drive_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "session_id": session_id,
            },
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            response.raise_for_status()
            complete_data = None
            error_data = None
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    if event_type == "complete":
                        complete_data = data
                    elif event_type == "error":
                        error_data = data
                    elif event_type == "extraction":
                        status = data.get("status", "")
                        print(f"  [extraction] {data.get('file_name', '?')} -> {status}")
                    elif event_type == "embedding_progress":
                        print(f"  [embedding] {data.get('embedded', 0)}/{data.get('total', 0)}")

            if error_data:
                raise RuntimeError(f"Indexing failed: {error_data}")
            if not complete_data:
                raise RuntimeError("No complete event received")
            return complete_data


async def send_chat_and_check_new_files(
    token: str,
    session_id: str,
    file_list: list[dict],
    folder_id: str,
    query: str = "What files are in this folder?",
) -> list[dict] | None:
    """Send a chat message and check if the backend emits a new_files event.

    Returns the new_files list if found, or None.
    """
    url = f"{BACKEND_URL}/chat"
    new_files = None
    events_received = []

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            url,
            json={
                "session_id": session_id,
                "query": query,
                "file_list": file_list,
                "folder_id": folder_id,
            },
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                    event_type = event.get("type")
                    events_received.append(event_type)
                    if event_type == "new_files":
                        new_files = event.get("files", [])
                        print(f"  [new_files] Detected: {[f['file_name'] for f in new_files]}")
                    elif event_type == "error":
                        print(f"  [error] {event.get('message')}")
                except json.JSONDecodeError:
                    pass

    print(f"  Events received: {events_received}")
    return new_files


# ── Test Scenarios ───────────────────────────────────────────────────────────


async def scenario_detect_new_file(token: str, folder_id: str, rw_token: str | None = None):
    """
    Full end-to-end test:
    1. Index a Drive folder
    2. Create a NEW file in that folder (uses rw_token if provided, else token)
    3. Send a chat message
    4. Verify the backend detects the new file
    5. Clean up

    Args:
        token: App token (drive.readonly + openid) for backend API calls
        rw_token: Optional token with full drive scope for creating/deleting test files
    """
    file_token = rw_token or token  # Token used for file create/delete
    session_id = str(uuid.uuid4())
    created_file_id = None

    try:
        # Step 1: Verify token
        print("\n=== Step 1: Verify token ===")
        user_id = await get_user_id(token)
        print(f"  Authenticated as user: {user_id[:8]}...")

        # Step 2: Check current folder contents
        print("\n=== Step 2: Check folder contents ===")
        existing_files = await list_folder_files(token, folder_id)
        print(f"  Found {len(existing_files)} existing files:")
        for f in existing_files:
            print(f"    - {f['name']} ({f['id'][:12]}...)")

        # Step 3: Index the folder
        print(f"\n=== Step 3: Index folder (session={session_id[:8]}...) ===")
        complete = await index_folder(token, folder_id, session_id)
        print(f"  Indexed {complete['files_indexed']} files, {complete['total_chunks']} chunks")
        print(f"  folder_id in response: {complete.get('folder_id')}")
        indexed_at = complete.get("indexed_at", "")

        # Build file_list as the frontend would
        file_list = [
            {
                "file_id": f["id"],
                "file_name": f["name"],
                "indexed_at": indexed_at,
            }
            for f in existing_files
            if f.get("mimeType") in {
                "application/vnd.google-apps.document",
                "application/vnd.google-apps.spreadsheet",
                "application/vnd.google-apps.presentation",
                "application/pdf",
                "text/plain",
                "text/markdown",
            }
        ]
        print(f"  file_list for chat: {len(file_list)} files")

        # Step 4: Chat BEFORE adding new file (baseline -- no new files expected)
        print("\n=== Step 4: Baseline chat (no new files expected) ===")
        baseline_new = await send_chat_and_check_new_files(
            token, session_id, file_list, folder_id, "summarize the contents"
        )
        if baseline_new:
            print(f"  WARNING: Baseline detected {len(baseline_new)} new files (unexpected)")
        else:
            print("  OK: No new files detected (expected)")

        # Step 5: Create a new file in the folder
        print("\n=== Step 5: Create new test file ===")
        test_file_name = f"_test_new_file_{int(time.time())}.txt"
        test_content = "This is a test file created to verify new file detection."
        created_file_id = await create_test_file(
            file_token, folder_id, test_file_name, test_content
        )
        print(f"  Created: {test_file_name} (id={created_file_id[:12]}...)")

        # Small delay for Drive API consistency
        await asyncio.sleep(2)

        # Step 6: Chat AFTER adding new file (should detect it)
        print("\n=== Step 6: Chat after new file (should detect it) ===")
        detected_new = await send_chat_and_check_new_files(
            token, session_id, file_list, folder_id, "what is new?"
        )

        if detected_new:
            detected_names = [f["file_name"] for f in detected_new]
            if test_file_name in detected_names:
                print(f"\n  ✅ SUCCESS: New file '{test_file_name}' was detected!")
            else:
                print(f"\n  ⚠️  PARTIAL: Detected new files {detected_names} but not our test file")
        else:
            print(f"\n  ❌ FAIL: No new_files event emitted!")
            print("     Possible causes:")
            print("     - folder_id not sent in request")
            print("     - file_list mismatch")
            print("     - list_folder_files() failed silently")
            print("     - Drive API latency")

        return detected_new is not None and any(
            f["file_name"] == test_file_name for f in (detected_new or [])
        )

    finally:
        # Cleanup
        if created_file_id:
            print(f"\n=== Cleanup: Deleting test file {created_file_id[:12]}... ===")
            await delete_test_file(file_token, created_file_id)
            print("  Done")


async def scenario_folder_id_persistence(token: str, folder_id: str):
    """
    Test that folder_id is correctly emitted in the /index complete event.
    This validates the backend side of the persistence chain.
    """
    session_id = str(uuid.uuid4())

    print("\n=== Test: folder_id in /index complete event ===")
    complete = await index_folder(token, folder_id, session_id)

    returned_folder_id = complete.get("folder_id")
    if returned_folder_id == folder_id:
        print(f"  ✅ folder_id correctly returned: {returned_folder_id}")
        return True
    elif returned_folder_id is None:
        print(f"  ❌ folder_id is None in complete event!")
        return False
    else:
        print(f"  ❌ folder_id mismatch: expected {folder_id}, got {returned_folder_id}")
        return False


# ── CLI ──────────────────────────────────────────────────────────────────────


async def interactive_mode():
    """Run interactively, prompting for token and folder ID."""
    print("=" * 60)
    print("New File Detection - Interactive Test")
    print("=" * 60)
    print()
    print("To get your token:")
    print("  1. Open http://localhost:5173 and sign in")
    print("  2. In Chrome DevTools Console, run:")
    print('     sessionStorage.getItem("google_access_token")')
    print()

    token = input("Paste your Google access token: ").strip()
    if not token:
        print("No token provided, exiting.")
        return

    # Verify token
    try:
        user_id = await get_user_id(token)
        print(f"Token valid! User: {user_id[:8]}...")
    except Exception as e:
        print(f"Token invalid: {e}")
        return

    folder_id = input("Paste the Google Drive folder ID to test: ").strip()
    if not folder_id:
        print("No folder ID provided, exiting.")
        return

    print("\nRunning tests...\n")

    # Test 1: folder_id persistence
    ok1 = await scenario_folder_id_persistence(token, folder_id)

    # Test 2: new file detection
    ok2 = await scenario_detect_new_file(token, folder_id)

    print("\n" + "=" * 60)
    print("Results:")
    print(f"  folder_id persistence: {'PASS' if ok1 else 'FAIL'}")
    print(f"  new file detection:    {'PASS' if ok2 else 'FAIL'}")
    print("=" * 60)


# ── pytest entry points ─────────────────────────────────────────────────────

import pytest


@pytest.fixture
def google_token():
    token = os.environ.get("GOOGLE_TOKEN")
    if not token:
        pytest.skip("Set GOOGLE_TOKEN env var (from sessionStorage)")
    return token


@pytest.fixture
def drive_rw_token():
    """Token with full drive scope for creating/deleting test files.
    Get from OAuth Playground with 'Drive API v3 > drive' scope."""
    token = os.environ.get("GOOGLE_DRIVE_RW_TOKEN")
    if not token:
        pytest.skip("Set GOOGLE_DRIVE_RW_TOKEN env var (from OAuth Playground with full drive scope)")
    return token


@pytest.fixture
def drive_folder_id():
    fid = os.environ.get("DRIVE_FOLDER_ID")
    if not fid:
        pytest.skip("Set DRIVE_FOLDER_ID env var")
    return fid


@pytest.mark.asyncio
async def test_folder_id_in_complete_event(google_token, drive_folder_id):
    """Backend /index should return folder_id in the complete SSE event."""
    result = await scenario_folder_id_persistence(google_token, drive_folder_id)
    assert result, "folder_id not returned in /index complete event"


@pytest.mark.asyncio
async def test_new_file_detected_in_chat(google_token, drive_rw_token, drive_folder_id):
    """Adding a file to a folder should trigger new_files event in /chat."""
    result = await scenario_detect_new_file(google_token, drive_folder_id, rw_token=drive_rw_token)
    assert result, "New file was not detected in chat response"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    args = parser.parse_args()

    if args.interactive:
        asyncio.run(interactive_mode())
    else:
        # Run with env vars
        token = os.environ.get("GOOGLE_TOKEN")
        folder_id = os.environ.get("DRIVE_FOLDER_ID")
        if not token or not folder_id:
            print("Set GOOGLE_TOKEN and DRIVE_FOLDER_ID, or use --interactive")
            sys.exit(1)
        asyncio.run(scenario_detect_new_file(token, folder_id))
