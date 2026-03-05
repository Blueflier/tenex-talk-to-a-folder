---
phase: 03-retrieval-chat
plan: 03
subsystem: ui
tags: [indexeddb, citations, auth-guard, suggestions, react, persistence]

requires:
  - phase: 01-foundation-auth
    provides: IndexedDB persistence layer with chats/messages stores
  - phase: 03-retrieval-chat
    provides: useStream hook, Citation interface, ChatView component tree
provides:
  - "loadMessages: sorted IndexedDB message loading without auth"
  - "Citation persistence as frozen snapshots on IndexedDB messages"
  - "Auth guard blocking new sends without google_access_token"
  - "EmptyState component with template-based suggestion cards"
  - "generateSuggestions from indexed file names"
affects: [04-staleness-hybrid-retrieval]

tech-stack:
  added: [fake-indexeddb]
  patterns: [suggestion template generation, prefill prop pattern for input auto-fill, auth guard with re-auth banner]

key-files:
  created:
    - frontend/src/lib/suggestions.ts
    - frontend/src/lib/citations.test.ts
    - frontend/src/components/chat/EmptyState.tsx
  modified:
    - frontend/src/lib/db.ts
    - frontend/src/lib/db.test.ts
    - frontend/src/components/chat/ChatView.tsx
    - frontend/src/components/chat/ChatInput.tsx

key-decisions:
  - "loadMessages sorts client-side after getAll rather than using IDB cursor for simplicity"
  - "ChatInput uses prefill prop pattern instead of controlled value to avoid breaking internal state"
  - "Test files placed alongside source (src/lib/*.test.ts) matching existing project convention"

patterns-established:
  - "Auth guard: check sessionStorage token before send, set needsAuth state on missing"
  - "Message persistence: save user message on send, save assistant message with frozen citations on stream done"
  - "Suggestion generation: template cycling over file names, no LLM call"

requirements-completed: [CHAT-02, CHAT-03, CHAT-06, PERS-04]

duration: 4min
completed: 2026-03-05
---

# Phase 3 Plan 3: Citation Persistence + Auth Guard + Empty State Summary

**IndexedDB citation snapshots with auth-guarded sends, sorted message loading without auth, and template-based suggestion cards**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T22:13:28Z
- **Completed:** 2026-03-05T22:17:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- loadMessages loads sorted messages from IndexedDB without requiring auth token (PERS-04)
- ChatView persists user messages on send and assistant messages with frozen citation arrays on stream completion
- Auth guard blocks new message sends when google_access_token is missing, shows re-auth banner
- EmptyState shows file count header and up to 4 clickable suggestion cards from file names
- 24 frontend tests pass including 9 new tests for citations and message persistence

## Task Commits

Each task was committed atomically:

1. **Task 1: Citation persistence + auth guard (TDD RED)** - `65c8d95` (test)
2. **Task 1: Citation persistence + auth guard (TDD GREEN)** - `70f71fa` (feat)
3. **Task 2: Empty state with suggestion cards** - `ae7ea7e` (feat)

_Note: Task 1 followed TDD with separate RED/GREEN commits_

## Files Created/Modified
- `frontend/src/lib/db.ts` - Added loadMessages with created_at sort, no auth requirement
- `frontend/src/lib/db.test.ts` - Added 3 tests: citation persistence, sorted loading, no-auth loading
- `frontend/src/lib/citations.test.ts` - 6 tests for formatCitationLabel and citation schema
- `frontend/src/lib/suggestions.ts` - generateSuggestions from indexed file names using templates
- `frontend/src/components/chat/EmptyState.tsx` - File count header + suggestion card grid
- `frontend/src/components/chat/ChatView.tsx` - IndexedDB wiring, auth guard, EmptyState integration
- `frontend/src/components/chat/ChatInput.tsx` - Added prefill prop for suggestion auto-fill

## Decisions Made
- loadMessages sorts client-side after getAll rather than using IDB cursor -- simpler, message lists are small
- ChatInput uses a prefill prop with useEffect sync instead of full controlled mode to avoid refactoring internal state
- Test files placed alongside source files (src/lib/*.test.ts) matching existing project convention rather than separate tests/ directory

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test file paths adjusted to match project convention**
- **Found during:** Task 1 (test creation)
- **Issue:** Plan specified `frontend/tests/citations.test.ts` and `frontend/tests/db.test.ts` but project convention places tests alongside source files (`src/lib/*.test.ts`) and tsconfig only includes `src/`
- **Fix:** Created test files at `frontend/src/lib/citations.test.ts` and extended existing `frontend/src/lib/db.test.ts`
- **Files modified:** frontend/src/lib/citations.test.ts, frontend/src/lib/db.test.ts
- **Verification:** All tests discovered and pass with vitest
- **Committed in:** 65c8d95 (Task 1 RED commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Path adjustment only. No scope creep.

## Issues Encountered
None beyond the test path adjustment documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 (Retrieval + Chat) fully complete
- Backend RAG pipeline with SSE streaming, frontend chat UI with streaming/citations, IndexedDB persistence with frozen citations, auth guard, and empty state suggestions all wired
- Ready for Phase 4 (Staleness + Hybrid Retrieval)

## Self-Check: PASSED

All created files verified present. All 3 task commits verified in git log. TypeScript compilation clean. 24 tests pass.

---
*Phase: 03-retrieval-chat*
*Completed: 2026-03-05*
