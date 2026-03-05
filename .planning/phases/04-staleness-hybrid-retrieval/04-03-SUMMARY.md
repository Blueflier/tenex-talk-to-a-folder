---
phase: 04-staleness-hybrid-retrieval
plan: 03
subsystem: api, ui
tags: [reindex, modal-volume, surgical-chunk-replacement, react, sonner, toast]

requires:
  - phase: 04-staleness-hybrid-retrieval
    provides: "staleness.invalidate_caches, StalenessBanner reindexSlot prop, StalenessBannerList renderReindexButton"
  - phase: 02-indexing-pipeline
    provides: "Volume storage, chunking, embedding pipeline"
provides:
  - "POST /reindex endpoint for surgical per-file chunk replacement"
  - "reindex_file function: drop old chunks, fetch/chunk/embed new, merge, volume.commit, invalidate caches"
  - "ReindexButton component with spinner/disabled states"
  - "useReindex hook with per-file reindexing state tracking"
  - "Send button disabled with tooltip during re-index"
  - "Sonner toast: green success auto-dismiss 3s"
affects: [frontend-chat-flow]

tech-stack:
  added: [sonner]
  patterns: [per-file-state-tracking-with-set, slot-pattern-injection, surgical-chunk-replacement]

key-files:
  created:
    - backend/reindex.py
    - frontend/src/hooks/useReindex.ts
    - frontend/src/components/chat/ReindexButton.tsx
    - tests/test_reindex.py
    - frontend/tests/reindex-button.test.tsx
  modified:
    - backend/app.py
    - frontend/src/components/chat/ChatView.tsx
    - frontend/src/components/chat/ChatInput.tsx
    - frontend/src/components/chat/ChatMessage.tsx
    - frontend/src/components/chat/MessageList.tsx
    - frontend/src/App.tsx

key-decisions:
  - "base_path parameter on reindex_file for testability (same pattern as storage.py)"
  - "fetch_and_chunk_file and embed_new_chunks as separate mockable functions for testing"
  - "useReindex tracks per-file state with Set<string> for independent re-indexing"
  - "disabledTooltip prop on ChatInput for contextual tooltip on disabled send button"

patterns-established:
  - "Slot pattern completion: renderReindexButton callback flows ChatView -> MessageList -> ChatMessage -> StalenessBannerList"
  - "Per-file state tracking: Set<string> pattern for tracking multiple independent async operations"

requirements-completed: [RETR-07]

duration: 5min
completed: 2026-03-05
---

# Phase 04 Plan 03: Per-file Re-indexing Endpoint + ReindexButton Summary

**Surgical per-file chunk replacement via POST /reindex with ReindexButton spinner feedback, send-button disable, and sonner success toast**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T23:05:59Z
- **Completed:** 2026-03-05T23:10:50Z
- **Tasks:** 2 (both TDD: test + feat commits)
- **Files modified:** 12

## Accomplishments
- POST /reindex endpoint surgically replaces one file's chunks while preserving all other files
- volume.commit() called after save, invalidate_caches clears staleness + grep caches
- ReindexButton with spinner/disabled states integrated into staleness banners via slot pattern
- Send button disabled with "Re-indexing in progress" tooltip during any re-index
- Green "Re-indexed successfully" toast via sonner auto-dismisses after 3s
- Each file's re-index operates independently (Set<string> tracks per-file state)
- 5 backend tests + 4 frontend tests = 9 new tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Backend reindex tests** - `d17131e` (test)
2. **Task 1 (GREEN): Backend /reindex endpoint** - `08c7bf3` (feat)
3. **Task 2 (RED): Frontend ReindexButton tests** - `424892d` (test)
4. **Task 2 (GREEN): Frontend implementation** - `69dfa67` (feat)

## Files Created/Modified
- `backend/reindex.py` - reindex_file function + POST /reindex endpoint with auth
- `backend/app.py` - Registered reindex_router
- `frontend/src/hooks/useReindex.ts` - Hook with per-file reindexing state tracking
- `frontend/src/components/chat/ReindexButton.tsx` - Button with spinner/disabled states
- `frontend/src/components/chat/ChatView.tsx` - Wired useReindex, renderReindexButton, send disable, toast
- `frontend/src/components/chat/ChatInput.tsx` - Added disabledTooltip prop
- `frontend/src/components/chat/ChatMessage.tsx` - Pass renderReindexButton to StalenessBannerList
- `frontend/src/components/chat/MessageList.tsx` - Pass renderReindexButton through
- `frontend/src/App.tsx` - Added Sonner Toaster provider
- `tests/test_reindex.py` - 5 backend tests for reindex
- `frontend/tests/reindex-button.test.tsx` - 4 frontend tests for ReindexButton

## Decisions Made
- base_path parameter on reindex_file for testability (consistent with storage.py pattern)
- fetch_and_chunk_file and embed_new_chunks as separate functions, easily mockable for testing
- useReindex tracks per-file state with Set<string> so multiple files can reindex independently
- disabledTooltip prop on ChatInput for contextual tooltip on disabled send button

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full staleness + hybrid retrieval pipeline complete (all 3 plans in Phase 4)
- Re-index flow: click button -> spinner -> surgical replacement -> cache invalidation -> toast
- Ready for Phase 5

## Self-Check: PASSED

All 5 key files verified present. All 4 commits verified (d17131e, 08c7bf3, 424892d, 69dfa67). 9 new tests passing (5 backend + 4 frontend).

---
*Phase: 04-staleness-hybrid-retrieval*
*Completed: 2026-03-05*
