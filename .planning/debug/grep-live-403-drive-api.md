---
status: diagnosed
trigger: "403 Forbidden error when grep_live tries to fetch file content from Google Drive API during hybrid retrieval for stale files"
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: grep_live uses `?alt=media` to download Google Workspace files (Docs/Sheets/Slides) which requires the `/export` endpoint, not the download endpoint. The `?alt=media` approach only works for binary files (PDF, plain text). Google Workspace files return 403 when accessed via `?alt=media` because they have no binary content -- they must be exported.
test: Compare grep.py fetch_and_extract() vs drive.py export_file() API calls
expecting: grep.py always uses `?alt=media`; drive.py correctly branches on mime type
next_action: Report root cause

## Symptoms

expected: grep_live fetches fresh file content from Drive API for stale files during hybrid retrieval
actual: 403 Forbidden from `https://www.googleapis.com/drive/v3/files/{id}?alt=media`
errors: `403, message='Forbidden', url='https://www.googleapis.com/drive/v3/files/...?alt=media'`
reproduction: Chat query that triggers hybrid retrieval on a stale Google Workspace file (Doc, Sheet, or Slides)
started: Phase 04 implementation

## Eliminated

(none needed -- root cause found on first hypothesis)

## Evidence

- timestamp: 2026-03-05T00:00:00Z
  checked: frontend/src/lib/auth.ts line 15
  found: OAuth scope is `drive.readonly` -- this grants both metadata AND content access. Scope is NOT the issue.
  implication: Rules out insufficient OAuth scopes

- timestamp: 2026-03-05T00:00:00Z
  checked: backend/chat.py lines 293, 312
  found: Token extracted from `Authorization: Bearer` header, passed as `token` to `_chat_event_stream`, then to both `check_staleness()` and `grep_live()`. Same token used for both calls.
  implication: Rules out token not being passed or different tokens

- timestamp: 2026-03-05T00:00:00Z
  checked: backend/staleness.py line 18
  found: Staleness uses `?fields=id,name,modifiedTime` (metadata-only endpoint). This works fine with `drive.readonly` scope.
  implication: Metadata access works because it uses the correct endpoint

- timestamp: 2026-03-05T00:00:00Z
  checked: backend/grep.py lines 60-68
  found: `fetch_and_extract()` ALWAYS uses `?alt=media` regardless of file type. URL is `https://www.googleapis.com/drive/v3/files/{file_id}?alt=media`
  implication: This is the problematic call -- `?alt=media` fails on Google Workspace files

- timestamp: 2026-03-05T00:00:00Z
  checked: backend/drive.py lines 107-120
  found: `export_file()` correctly branches: Google Workspace files (Docs/Sheets/Slides) use `/export` endpoint with target mimeType; binary files (PDF, text) use `?alt=media`. This works during indexing.
  implication: The indexing path handles this correctly; grep.py does not

## Resolution

root_cause: `fetch_and_extract()` in `backend/grep.py` (line 62) unconditionally uses `?alt=media` to download file content. This works for binary files (PDF, plain text) but returns **403 Forbidden** for Google Workspace files (Docs, Sheets, Slides). Google Workspace files have no downloadable binary -- they must be accessed via the `/export` endpoint with a target mimeType (e.g., `text/plain` for Docs, `text/csv` for Sheets). The working code path in `backend/drive.py:export_file()` already handles this correctly by branching on mime type, but `grep.py` does not use that logic.

fix: (not applied per instructions)
verification: (not applied per instructions)
files_changed: []
