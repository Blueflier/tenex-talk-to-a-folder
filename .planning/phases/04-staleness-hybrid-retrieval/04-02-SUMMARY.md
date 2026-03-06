---
phase: 04-staleness-hybrid-retrieval
plan: 02
subsystem: ui
tags: [react, tailwind, sse, indexeddb, staleness]

requires:
  - phase: 03-retrieval-chat
    provides: ChatMessage, useStream, db.ts, ChatView with SSE streaming
provides:
  - Three-variant StalenessBanner component (yellow/red/amber)
  - StalenessBannerList container for multiple banners
  - useStream staleness SSE event parsing
  - stale_files field on IndexedDB message records
affects: [04-staleness-hybrid-retrieval]

tech-stack:
  added: [lucide-react icons for banners]
  patterns: [SSE event extension pattern, optional field persistence in IndexedDB]

key-files:
  created:
    - frontend/src/components/chat/StalenessBanner.tsx
    - frontend/src/components/chat/StalenessBannerList.tsx
    - frontend/src/components/chat/StalenessBanner.test.tsx
  modified:
    - frontend/src/hooks/useStream.ts
    - frontend/src/lib/db.ts
    - frontend/src/components/chat/ChatMessage.tsx
    - frontend/src/components/chat/MessageList.tsx
    - frontend/src/components/chat/ChatView.tsx

key-decisions:
  - "StalenessInfo type exported from StalenessBanner.tsx as canonical type"
  - "reindexSlot prop pattern for Plan 03 to inject ReindexButton without modifying StalenessBanner"
  - "stale_files stored as optional field on existing Message type (no DB version bump needed)"

patterns-established:
  - "SSE event extension: add new event type to switch, update callback interface"
  - "Slot pattern: reindexSlot prop allows parent to inject button without banner coupling"

requirements-completed: [CHAT-05]

duration: 3min
completed: 2026-03-05
---

# Phase 04 Plan 02: Frontend Staleness Banners Summary

**Three-variant staleness banners (yellow/red/amber) with SSE parsing and IndexedDB persistence per message**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T22:24:52Z
- **Completed:** 2026-03-05T22:27:39Z
- **Tasks:** 1 (TDD: test + feat commits)
- **Files modified:** 8

## Accomplishments
- Three distinct banner variants: yellow (stale), red (deleted/404), amber (access revoked/403)
- useStream parses type=staleness SSE events and exposes stale files to ChatView
- stale_files persisted on IndexedDB message records, banners survive page reload
- ChatMessage renders StalenessBannerList above assistant content only

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Staleness banner tests** - `91ec9a5` (test)
2. **Task 1 (GREEN): Implementation** - `f5b95ba` (feat)

## Files Created/Modified
- `frontend/src/components/chat/StalenessBanner.tsx` - Three-variant banner with StalenessInfo type
- `frontend/src/components/chat/StalenessBannerList.tsx` - Container rendering one banner per stale file
- `frontend/src/components/chat/StalenessBanner.test.tsx` - 6 tests covering all variants and persistence
- `frontend/src/hooks/useStream.ts` - Added staleness SSE event handling
- `frontend/src/lib/db.ts` - Added stale_files field to Message interface
- `frontend/src/components/chat/ChatMessage.tsx` - Renders banners above assistant messages
- `frontend/src/components/chat/MessageList.tsx` - Passes sessionId and staleFiles through
- `frontend/src/components/chat/ChatView.tsx` - Wires onStaleness callback, persists stale_files

## Decisions Made
- StalenessInfo type exported from StalenessBanner.tsx as the canonical type used everywhere
- reindexSlot prop pattern lets Plan 03 inject ReindexButton without modifying banner internals
- stale_files stored as optional field on existing Message type (no IndexedDB version bump needed)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Banner components ready for Plan 03 to wire ReindexButton via reindexSlot prop
- Backend staleness SSE events (Plan 01) will flow through useStream into banners

---
*Phase: 04-staleness-hybrid-retrieval*
*Completed: 2026-03-05*
