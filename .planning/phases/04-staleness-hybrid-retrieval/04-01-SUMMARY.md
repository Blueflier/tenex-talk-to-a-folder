---
phase: 04-staleness-hybrid-retrieval
plan: 01
subsystem: api
tags: [staleness, grep, hybrid-retrieval, sse, aiohttp, drive-api]

requires:
  - phase: 03-retrieval-chat
    provides: "/chat SSE endpoint, retrieve_mixed, extract_citations"
  - phase: 02-indexing-pipeline
    provides: "Volume storage for chunks/embeddings"
provides:
  - "Staleness detection via Drive metadata with 60s cache"
  - "Keyword extraction via LLM with stopword fallback"
  - "grep_live file search with context windows and 5min text cache"
  - "Hybrid /chat routing: fresh->cosine, modified->grep, deleted->cosine with (deleted) suffix"
  - "Staleness SSE event before tokens"
affects: [04-02, 04-03, frontend-staleness-ui]

tech-stack:
  added: [aiohttp]
  patterns: [three-way-partition, parallel-asyncio-gather, sse-staleness-event, in-memory-cache-with-ttl]

key-files:
  created:
    - backend/staleness.py
    - backend/grep.py
    - backend/tests/test_staleness.py
    - backend/tests/test_grep.py
  modified:
    - backend/chat.py
    - backend/tests/test_chat_endpoint.py

key-decisions:
  - "Three-way partition: deleted files (404) stay on cosine path per CONTEXT.md locked decision"
  - "Staleness SSE event emitted before any tokens so frontend can show banner immediately"
  - "extract_keywords uses LLM with stopword-filtered fallback on parse failure"
  - "grep_live context windows include 1 sentence before and after match"

patterns-established:
  - "In-memory cache with TTL pattern: dict[key, tuple[value, timestamp]] checked against monotonic time"
  - "Parallel asyncio.gather for independent async operations (staleness + embedding)"
  - "SSE event ordering: staleness -> tokens -> citations -> DONE"

requirements-completed: [RETR-03, RETR-04, RETR-05, RETR-06, CHAT-05]

duration: 4min
completed: 2026-03-05
---

# Phase 04 Plan 01: Backend Staleness + Hybrid Retrieval Summary

**Staleness detection via Drive metadata, grep_live keyword search for stale files, and hybrid /chat routing with SSE staleness events**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T22:00:00Z
- **Completed:** 2026-03-05T22:04:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Staleness detection comparing Drive modifiedTime against indexed_at with 60s in-memory cache
- Keyword extraction via LLM with JSON parsing and stopword-filtered fallback
- grep_live returning up to 15 keyword matches with context windows and 5min text cache
- Hybrid /chat routing: three-way partition (fresh->cosine, modified->grep, deleted->cosine with "(deleted)" suffix)
- Staleness SSE event emitted before tokens so frontend can render banners immediately
- 26 total tests passing across staleness, grep, and chat endpoint modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Staleness detection + grep_live + keyword extraction modules** - `617b4c7` (test) + `e5286d6` (feat) - TDD
2. **Task 2: Hybrid /chat routing with staleness SSE events** - `e62fbc2` (feat)

## Files Created/Modified
- `backend/staleness.py` - Staleness detection via Drive metadata with cache
- `backend/grep.py` - Keyword extraction and grep-based live retrieval
- `backend/chat.py` - Modified for hybrid retrieval with staleness SSE events
- `backend/tests/test_staleness.py` - 6 tests for staleness detection
- `backend/tests/test_grep.py` - 6 tests for keyword extraction and grep
- `backend/tests/test_chat_endpoint.py` - 14 tests including 7 new hybrid retrieval tests

## Decisions Made
- Three-way partition honors CONTEXT.md locked decision: deleted files (404) stay on cosine path using old embeddings
- Staleness SSE event emitted before any tokens so frontend can show banner immediately
- extract_keywords uses LLM with stopword-filtered fallback on JSON parse failure
- grep_live context windows include 1 sentence before and after each match
- file_name_map built from file_list for attaching names to grep results

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend hybrid retrieval pipeline complete
- Frontend staleness UI (plan 04-02) can consume staleness SSE events
- Cache invalidation ready via invalidate_caches() for re-indexing flows

## Self-Check: PASSED

All 6 files verified present. All 3 commits verified (617b4c7, e5286d6, e62fbc2). 26/26 tests passing.

---
*Phase: 04-staleness-hybrid-retrieval*
*Completed: 2026-03-05*
