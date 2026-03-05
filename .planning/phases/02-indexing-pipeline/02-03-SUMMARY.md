---
phase: 02-indexing-pipeline
plan: 03
subsystem: api
tags: [fastapi, sse, drive, embedding, openai, streaming]

requires:
  - phase: 02-indexing-pipeline-01
    provides: Drive resolution, file listing, export, chunking functions
  - phase: 02-indexing-pipeline-02
    provides: Batch embedding with progress, session storage to Volume
  - phase: 01-foundation-auth
    provides: Google auth token verification, FastAPI app scaffold
provides:
  - POST /index SSE endpoint orchestrating full indexing pipeline
  - Two-phase streaming progress (extraction per-file, embedding per-batch)
  - Error handling for empty folders, unsupported files, large files
affects: [03-retrieval-chat, frontend-indexing-ui]

tech-stack:
  added: [pymupdf (Modal image)]
  patterns: [SSE event streaming with named events, best-effort per-file extraction]

key-files:
  created:
    - backend/index.py
    - backend/tests/test_index_endpoint.py
  modified:
    - backend/app.py

key-decisions:
  - "SSE uses named events (event: extraction, event: embedding_start, etc.) not data-only format"
  - "Embedding progress collected via callback list then yielded after embed_chunks completes"
  - "Pydantic IndexRequest model for request validation instead of raw request.json()"

patterns-established:
  - "Router pattern: separate module with APIRouter, imported and included in app.py"
  - "SSE event helper: _sse_event(event, data) for consistent formatting"

requirements-completed: [INDX-09]

duration: 2min
completed: 2026-03-05
---

# Phase 02 Plan 03: POST /index SSE Endpoint Summary

**POST /index endpoint wiring Drive resolution -> extraction -> chunking -> embedding -> storage with two-phase SSE streaming progress**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T23:10:22Z
- **Completed:** 2026-03-05T23:12:51Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- POST /index SSE endpoint with full pipeline orchestration
- Two-phase streaming: extraction events per-file, then embedding progress per-batch
- Distinct error handling for empty folders, all-unsupported folders, invalid URLs
- Large file (>50MB) warning events that still process the file
- Best-effort extraction: per-file failures don't stop pipeline
- 10 integration tests covering all event shapes and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: POST /index SSE streaming endpoint** - `84049d5` (feat)

## Files Created/Modified
- `backend/index.py` - POST /index SSE endpoint with full pipeline orchestration
- `backend/app.py` - Added index router, pymupdf to Modal image, timeout=600
- `backend/tests/test_index_endpoint.py` - 10 integration tests for /index endpoint

## Decisions Made
- Used named SSE events (event: extraction, event: embedding_start, etc.) for clearer client-side parsing
- Embedding progress events collected via callback list and yielded after embed_chunks completes (generator can't yield from within async callback)
- Used Pydantic IndexRequest model for request body validation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full indexing pipeline operational: Drive URL -> SSE streaming progress -> stored embeddings
- Ready for frontend to connect and display indexing progress
- All 122 backend tests passing

---
*Phase: 02-indexing-pipeline*
*Completed: 2026-03-05*
