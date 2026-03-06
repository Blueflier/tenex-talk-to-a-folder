---
status: diagnosed
phase: 04-staleness-hybrid-retrieval
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md]
started: 2026-03-05T23:30:00Z
updated: 2026-03-06T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Start backend and frontend from scratch. Server boots without errors. App loads in browser. Previously indexed folder is accessible.
result: issue
reported: "when i reloaded the page all the messages disappeared. when i upload the same link, the chat reappears again and the selection of that chat appears in the sidebar"
severity: major

### 2. Staleness Banner on Modified File
expected: After indexing a folder, modify a file in Google Drive. Then ask a question in chat that references that file. A yellow staleness banner appears above the assistant's response indicating the file has been modified since indexing.
result: issue
reported: "it worked but it outputted two yellow banners. StalenessBannerList.tsx:19 duplicate key error. Also shows '4 files indexed — 12 chunks' even though there are only 2 files and 6 chunks. Modal storage confirms only 6 chunks."
severity: major

### 3. Staleness Banner for Deleted File
expected: After indexing a folder, delete (or trash) a file in Google Drive. Ask a question referencing that file. A red staleness banner appears indicating the file was deleted/not found.
result: skipped
reason: Session isolation makes deleted-file scenario untestable — each session has its own files, can't reference across sessions

### 4. Hybrid Retrieval Still Answers Despite Stale Files
expected: With a modified file detected as stale, the chat response still provides a relevant answer using grep-based retrieval for the stale file's content. The answer should reference actual current content from the modified file.
result: issue
reported: "403 Forbidden when grep_live tries to fetch file content from Drive API. Also confirms duplicate banner bug."
severity: blocker

### 5. Re-index Button Appears on Staleness Banner
expected: When a staleness banner is shown, a "Re-index" button appears on the banner. Clicking it shows a spinner on the button and disables it while re-indexing is in progress.
result: skipped
reason: Blocked by 403 error — banners get replaced by error state before re-index can be tested

### 6. Send Button Disabled During Re-index
expected: While a file is being re-indexed (spinner visible on Re-index button), the chat send button is disabled and shows a tooltip like "Re-indexing in progress" when hovered.
result: skipped
reason: Blocked by 403 error

### 7. Success Toast After Re-index
expected: After re-indexing completes, a green "Re-indexed successfully" toast notification appears and auto-dismisses after about 3 seconds. The staleness banner for that file disappears or updates.
result: skipped
reason: Blocked by 403 error — re-index cannot complete

### 8. Staleness Banners Persist After Page Reload
expected: After receiving a response with staleness banners, reload the page. Navigate back to the same chat session. The staleness banners still appear on the same message (persisted via IndexedDB).
result: skipped
reason: Messages disappear on reload (Test 1 issue), so banners can't persist either

## Summary

total: 8
passed: 0
issues: 3
pending: 0
skipped: 5

## Gaps

- truth: "Messages and chat sessions persist across page reload"
  status: failed
  reason: "User reported: when i reloaded the page all the messages disappeared. when i upload the same link, the chat reappears again and the selection of that chat appears in the sidebar"
  severity: major
  test: 1
  root_cause: "indexedFilesMap in AppShell.tsx is ephemeral React state never restored on mount. ChatView gated behind isIndexed which depends on that map — always false after reload despite IndexedDB having data."
  artifacts:
    - path: "frontend/src/components/app-shell/AppShell.tsx"
      issue: "indexedFilesMap (line 39-41) initialized empty, never hydrated from persisted data on mount"
    - path: "frontend/src/lib/db.ts"
      issue: "Chat.indexed_sources only stores string[] (file IDs), not full IndexedFile objects needed for hydration"
  missing:
    - "Persist full IndexedFile objects (file_id, file_name, indexed_at) in IndexedDB"
    - "Hydrate indexedFilesMap and totalChunksMap from persisted data in useEffect on mount"
    - "Or decouple rendering gate from indexedFilesMap — use chat.indexed_sources.length > 0"
  debug_session: ".planning/debug/messages-disappear-on-reload.md"

- truth: "Single staleness banner per stale file, correct indexed file/chunk counts"
  status: failed
  reason: "User reported: two yellow banners with duplicate React key. Shows 4 files/12 chunks instead of 2 files/6 chunks"
  severity: major
  test: 2
  root_cause: "handleIndexComplete in AppShell.tsx appends to indexedFilesMap without dedup. IndexingModal useEffect re-fires due to unstable onComplete callback identity, causing double invocation that doubles both file count and chunk count."
  artifacts:
    - path: "frontend/src/components/app-shell/AppShell.tsx"
      issue: "handleIndexComplete line 236 appends without dedup; line 242 additively accumulates totalChunksMap"
    - path: "frontend/src/components/indexing/IndexingModal.tsx"
      issue: "useEffect dependency on onComplete callback causes re-execution of indexing stream"
  missing:
    - "Deduplicate indexedSources by file_id before merging in handleIndexComplete"
    - "Recompute totalChunksMap from actual data rather than additive accumulation"
    - "Stabilize onComplete callback identity — use ref or remove from useEffect deps"
  debug_session: ".planning/debug/duplicate-banners-double-counts.md"

- truth: "grep_live fetches stale file content from Drive API for hybrid retrieval"
  status: failed
  reason: "User reported: 403 Forbidden when grep_live tries to fetch file content from Drive API"
  severity: blocker
  test: 4
  root_cause: "fetch_and_extract() in backend/grep.py always uses ?alt=media which fails for Google Workspace files (Docs/Sheets/Slides). These require the /export endpoint. drive.py:export_file() already handles this correctly."
  artifacts:
    - path: "backend/grep.py"
      issue: "fetch_and_extract() line 60-68 has no mime-type branching, always uses ?alt=media"
    - path: "backend/drive.py"
      issue: "export_file() lines 107-120 has correct branching logic to reuse"
  missing:
    - "Branch on file mimeType in fetch_and_extract() — use /export for Workspace files"
    - "Pass mimeType into function from file_list metadata, or reuse drive.export_file() directly"
  debug_session: ".planning/debug/grep-live-403-drive-api.md"

- truth: "Users can paste any Google Drive link (files or folders)"
  status: failed
  reason: "User reported: can't directly upload Google Drive files, only folders. Users should be able to paste any link"
  severity: cosmetic
  test: 2
  root_cause: "Not a real bug — full pipeline already supports individual file links. Placeholder text says 'Paste a Google Drive folder link...' which misleads users."
  artifacts:
    - path: "frontend/src/components/app-shell/AppShell.tsx"
      issue: "Line 393 placeholder says 'folder link' — should say 'folder or file link' or just 'link'"
  missing:
    - "Change placeholder text from 'Paste a Google Drive folder link...' to 'Paste a Google Drive link...'"
  debug_session: ""
