---
phase: 04-staleness-hybrid-retrieval
verified: 2026-03-05T14:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
must_haves:
  truths:
    - "On each /chat request, backend checks Drive modifiedTime against indexed_at for all session files"
    - "Stale files are routed to grep_live instead of pre-computed embeddings; fresh files use cosine similarity"
    - "LLM generates keyword variants for grep_live; grep returns up to 15 matches with context windows"
    - "User sees a yellow staleness warning banner per stale file before answer tokens stream"
    - "User can click Re-index this file to replace only that file's chunks in the session"
  artifacts:
    - path: "backend/staleness.py"
      provides: "check_staleness with TTL cache, invalidate_caches"
    - path: "backend/grep.py"
      provides: "extract_keywords via LLM, grep_live with text cache"
    - path: "backend/chat.py"
      provides: "Hybrid /chat with staleness SSE events, three-way partition"
    - path: "backend/reindex.py"
      provides: "POST /reindex with surgical chunk replacement"
    - path: "frontend/src/components/chat/StalenessBanner.tsx"
      provides: "Three-variant banner (yellow/red/amber)"
    - path: "frontend/src/components/chat/StalenessBannerList.tsx"
      provides: "Container rendering banners per stale file"
    - path: "frontend/src/hooks/useStream.ts"
      provides: "SSE staleness event parsing"
    - path: "frontend/src/hooks/useReindex.ts"
      provides: "Per-file reindex hook with Set tracking"
    - path: "frontend/src/components/chat/ReindexButton.tsx"
      provides: "Button with spinner/disabled states"
    - path: "frontend/src/lib/db.ts"
      provides: "stale_files field on Message interface"
  key_links:
    - from: "backend/chat.py"
      to: "backend/staleness.py"
      via: "from backend.staleness import check_staleness"
    - from: "backend/chat.py"
      to: "backend/grep.py"
      via: "from backend.grep import extract_keywords, grep_live"
    - from: "backend/reindex.py"
      to: "backend/staleness.py"
      via: "from backend.staleness import invalidate_caches"
    - from: "frontend/src/hooks/useStream.ts"
      to: "SSE staleness event"
      via: "case staleness in switch"
    - from: "frontend/src/components/chat/ChatMessage.tsx"
      to: "StalenessBannerList"
      via: "renders above assistant content"
    - from: "frontend/src/components/chat/ChatView.tsx"
      to: "useReindex hook"
      via: "import and wire renderReindexButton"
    - from: "backend/app.py"
      to: "backend/reindex.py"
      via: "web_app.include_router(reindex_router)"
---

# Phase 4: Staleness + Hybrid Retrieval Verification Report

**Phase Goal:** Users always get answers from the latest file content, even when Drive files have changed since indexing
**Verified:** 2026-03-05T14:00:00Z
**Status:** passed
**Re-verification:** Yes -- confirming previous pass

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On each /chat request, backend checks Drive modifiedTime against indexed_at for all session files | VERIFIED | `backend/chat.py` L166-167: `asyncio.gather(check_staleness(file_list, access_token), _embed_query(query))`. `backend/staleness.py` L71: `meta["modifiedTime"] > f["indexed_at"]` comparison with 60s TTL cache. 6 staleness tests (180 lines) + 7 hybrid chat tests validate. |
| 2 | Stale files routed to grep_live; fresh files use cosine similarity | VERIFIED | `backend/chat.py` L192-194: Three-way partition (`deleted_ids`, `grep_ids`, `fresh_mask`). Fresh path L198-201 uses `retrieve_mixed()`. Stale path L217-231 calls `extract_keywords` then `asyncio.gather(*grep_live(...))`. Tests validate both paths including mixed scenarios. |
| 3 | LLM generates keyword variants for grep_live; grep returns up to 15 matches with context windows | VERIFIED | `backend/grep.py` L27-58: `extract_keywords` calls LLM with prompt for 8-12 variants, strips markdown fences, parses JSON, falls back to stopword filter. L83-123: `grep_live` splits sentences, builds regex alternation, returns up to 15 matches with 1-sentence context window. 6 grep tests (207 lines). |
| 4 | User sees yellow staleness warning banner per stale file before answer tokens stream | VERIFIED | Backend: `backend/chat.py` L176-186 emits `type: "staleness"` SSE event before any token events. Frontend: `useStream.ts` L118-123 `case "staleness"` handler stores in ref and calls callback. `StalenessBanner.tsx` L63-81 renders yellow variant (`bg-yellow-50`, AlertTriangle icon). `ChatMessage.tsx` L123-124 renders `StalenessBannerList` above assistant content when `staleFiles.length > 0`. 6 frontend banner tests (109 lines). |
| 5 | User can click Re-index this file to replace only that file's chunks in the session | VERIFIED | Backend: `backend/reindex.py` L63-123 `reindex_file` does surgical replacement (keep mask at L94, merge at L103-109, volume.commit at L116, invalidate_caches at L119). Endpoint registered in `app.py` L13+L17. Frontend: `ReindexButton.tsx` renders button with Loader2 spinner + disabled states. `useReindex.ts` POSTs to `/reindex` with per-file Set tracking. `ChatView.tsx` L69-77 wires hook with success toast, L263-276 `renderReindexButton` callback, L281 `isSendDisabled` includes `isReindexing`. 5 backend + 4 frontend tests (256 lines). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/staleness.py` | Staleness detection with cache | VERIFIED | 86 lines. check_staleness, invalidate_caches, aiohttp, asyncio.gather, 60s TTL cache. |
| `backend/grep.py` | Keyword extraction + grep_live | VERIFIED | 124 lines. LLM call, fence stripping, stopword fallback, sentence splitting, context windows, 15-result cap, 5min text cache. |
| `backend/chat.py` | Hybrid /chat with SSE staleness | VERIFIED | 317 lines. Imports check_staleness, extract_keywords, grep_live. Three-way partition, staleness SSE event before tokens, grep citations with source="grep". |
| `backend/reindex.py` | POST /reindex endpoint | VERIFIED | 173 lines. Surgical chunk replacement, volume.commit, invalidate_caches, 401 guard. Router registered in app.py. |
| `frontend/src/components/chat/StalenessBanner.tsx` | Three-variant banner | VERIFIED | 83 lines. Yellow (stale), red (not_found), amber (access_denied). StalenessInfo type exported. reindexSlot prop. |
| `frontend/src/components/chat/StalenessBannerList.tsx` | Banner container | VERIFIED | 29 lines. Renders one StalenessBanner per stale file. renderReindexButton callback prop. |
| `frontend/src/hooks/useStream.ts` | Staleness SSE parsing | VERIFIED | 155 lines. `case "staleness"` at L118-123. currentStaleFilesRef exposed. onStaleness callback in UseStreamCallbacks. |
| `frontend/src/hooks/useReindex.ts` | Reindex hook | VERIFIED | 63 lines. Per-file Set tracking, POST to /reindex, onSuccess/onError, isFileReindexing helper. |
| `frontend/src/components/chat/ReindexButton.tsx` | Button with states | VERIFIED | 37 lines. Default: RefreshCw + "Re-index this file". Loading: Loader2 spinner + "Re-indexing..." + disabled. |
| `frontend/src/lib/db.ts` | stale_files on Message | VERIFIED | stale_files?: { file_name, file_id, error? }[] on Message interface. Persisted by saveMessage, loaded by loadMessages. |
| `backend/tests/test_staleness.py` | Staleness tests | VERIFIED | 180 lines. 6 tests: fresh, stale, error handling (404/403), cache TTL, cache expired, invalidate_caches. |
| `backend/tests/test_grep.py` | Grep tests | VERIFIED | 207 lines. 6 tests: keywords, fallback, strips fences, grep matches, cap at 15, text cache. |
| `backend/tests/test_chat_endpoint.py` | Chat hybrid tests | VERIFIED | 640 lines. 14 tests total, 7 new for hybrid: staleness event, fresh only, stale only, mixed, deleted uses embeddings, deleted+stale, parallel execution. |
| `tests/test_reindex.py` | Reindex tests | VERIFIED | 212 lines. 5 tests: surgical replacement, cache invalidation, indexed_at returned, volume commit, 401. |
| `frontend/src/components/chat/StalenessBanner.test.tsx` | Banner tests | VERIFIED | 109 lines. 6 tests: yellow, red, amber banners, noMatches, banner list, stale_files persistence in IndexedDB. |
| `frontend/tests/reindex-button.test.tsx` | ReindexButton tests | VERIFIED | 44 lines. 4 tests: default state, loading state, click calls handler, disabled prevents click. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/chat.py` | `backend/staleness.py` | `from backend.staleness import check_staleness` | WIRED | L24. Used at L167. |
| `backend/chat.py` | `backend/grep.py` | `from backend.grep import extract_keywords, grep_live` | WIRED | L18. extract_keywords at L218, grep_live at L221. |
| `backend/reindex.py` | `backend/staleness.py` | `from backend.staleness import invalidate_caches` | WIRED | L16. Used at L119. |
| `backend/app.py` | `backend/reindex.py` | `web_app.include_router(reindex_router)` | WIRED | L13 import, L17 registration. |
| `frontend/useStream.ts` | SSE staleness event | `case "staleness"` in switch | WIRED | L118-123. Stores in currentStaleFilesRef, calls onStaleness callback. |
| `frontend/ChatMessage.tsx` | `StalenessBannerList` | Import + conditional render | WIRED | L8 import, L123-124 renders when `!isUser && staleFiles && staleFiles.length > 0 && sessionId`. |
| `frontend/ChatView.tsx` | `useReindex` hook | Import + wire renderReindexButton | WIRED | L8 import, L69 destructure, L263-276 renderReindexButton, L281 isSendDisabled, L300 passed to MessageList. |
| `frontend/ChatView.tsx` | `ReindexButton` | Import + rendered in callback | WIRED | L13 import, L268 rendered inside renderReindexButton. |
| `frontend/useReindex.ts` | POST /reindex | `fetch(API_BASE/reindex)` | WIRED | L20. Full request/response handling. |
| `frontend/StalenessBanner.tsx` | ReindexButton | Via reindexSlot prop | WIRED | L79 renders `{reindexSlot}`. ChatView L268 passes ReindexButton via renderReindexButton -> StalenessBannerList -> StalenessBanner. |
| `frontend/ChatView.tsx` | Sonner toast | `toast.success` and `toast.error` | WIRED | L71 success toast, L75 error toast. |
| `frontend/ChatView.tsx` | Send button disabled | `isSendDisabled = isStreaming OR isReindexing OR rateLimited` | WIRED | L281. Passed as isStreaming to ChatInput L304, with disabledTooltip L308-314. |
| `frontend/db.ts` | IndexedDB stale_files | stale_files on Message interface | WIRED | ChatView L59 loads stale_files from stored messages, L179 saves stale_files on done. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RETR-03 | 04-01 | Staleness detection: Drive modifiedTime compared to indexed_at | SATISFIED | `backend/staleness.py` check_staleness compares modifiedTime > indexed_at with 60s TTL cache. 6 tests validate. |
| RETR-04 | 04-01 | Fresh files use embeddings; stale files routed to grep_live | SATISFIED | `backend/chat.py` three-way partition: fresh_mask -> retrieve_mixed, grep_ids -> grep_live. 7 hybrid tests validate both paths. |
| RETR-05 | 04-01 | LLM generates 8-12 keyword variants for grep_live | SATISFIED | `backend/grep.py` extract_keywords with LLM prompt requesting 8-12 variants, fence stripping, stopword fallback. Tests validate. |
| RETR-06 | 04-01 | grep_live returns up to 15 matches with context windows | SATISFIED | `backend/grep.py` grep_live: regex alternation, 1-sentence context, 15-result cap, 5min text cache. Tests validate cap and context. |
| RETR-07 | 04-03 | Per-file re-indexing replaces only that file's chunks | SATISFIED | `backend/reindex.py` reindex_file: keep mask, merge, volume.commit, invalidate_caches. Frontend ReindexButton wired. 5 tests validate surgical replacement. |
| CHAT-05 | 04-01, 04-02 | Staleness warning events streamed before answer tokens, yellow banner | SATISFIED | Backend emits `type: "staleness"` SSE before tokens. Frontend parses in useStream, renders yellow StalenessBanner. Tests validate SSE order and rendering. |

No orphaned requirements found. All 6 requirement IDs (RETR-03 through RETR-07, CHAT-05) accounted for.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/chat/ChatView.tsx` | 72 | TODO: update IndexedDB indexed_sources entry with new indexed_at | Info | Non-blocking refinement. Re-index flow works end-to-end; this is metadata bookkeeping. |
| `backend/chat.py` | 136-140 | DEBUG print statements in _load_session_data | Info | Should be cleaned up before production but does not affect functionality. |
| `frontend/src/components/chat/ChatView.tsx` | 304 | `isStreaming={isSendDisabled}` disables textarea during re-index | Info | ChatInput receives isSendDisabled as its isStreaming prop, meaning textarea is disabled during re-index too (not just send button). Minor UX deviation but non-blocking. |

### Human Verification Required

### 1. Staleness Banner Visual Appearance

**Test:** Trigger a /chat request with a stale file (modify a Drive file after indexing), observe the banner.
**Expected:** Yellow banner with AlertTriangle icon appears above the assistant message, showing file name and "was modified after indexing" text. Red banner for deleted files. Amber for access revoked.
**Why human:** Visual rendering, color accuracy, icon display, layout positioning cannot be verified programmatically.

### 2. Re-index Flow End-to-End

**Test:** Click "Re-index this file" button on a staleness banner.
**Expected:** Button shows spinner + "Re-indexing..." text. Send button becomes disabled with tooltip "Re-indexing in progress". On completion, green toast "Re-indexed successfully" appears for 3 seconds.
**Why human:** Spinner animation, toast timing, tooltip positioning, and state transitions require visual verification.

### 3. SSE Event Ordering

**Test:** Send a chat message with a stale file in the session.
**Expected:** Staleness banner appears instantly before any answer text streams in.
**Why human:** Timing and perceived ordering of real SSE events requires real browser observation.

### Gaps Summary

No gaps found. All 5 observable truths verified with substantive implementations and complete wiring across backend and frontend. All 6 requirement IDs satisfied. 1,392 lines of tests across 6 test files cover the full surface area. Three INFO-level items found (TODO comment, debug prints, textarea disabled during reindex) -- none are blockers.

---

_Verified: 2026-03-05T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
