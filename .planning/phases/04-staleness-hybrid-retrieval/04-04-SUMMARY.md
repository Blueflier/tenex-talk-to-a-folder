---
phase: 04-staleness-hybrid-retrieval
plan: 04
subsystem: api
tags: [google-drive, grep, mime-type, export, aiohttp]

requires:
  - phase: 04-staleness-hybrid-retrieval
    provides: grep_live keyword search and staleness detection
provides:
  - mime-type-aware fetch_and_extract that uses /export for Workspace files
  - grep_live with mime_type passthrough
  - chat.py call site passes mimeType from file_list
affects: [04-staleness-hybrid-retrieval, chat]

tech-stack:
  added: []
  patterns: [mime-type branching for Drive API export vs download]

key-files:
  created: []
  modified:
    - backend/grep.py
    - backend/chat.py
    - backend/tests/test_grep.py
    - backend/tests/test_chat_endpoint.py

key-decisions:
  - "Imported EXPORT_MIME_MAP and DRIVE_API_BASE from backend.drive rather than duplicating"
  - "mime_type as keyword-only arg with empty string default for backward compatibility"

patterns-established:
  - "Workspace file export: check mime_type against EXPORT_MIME_MAP, use /export endpoint with export mimeType"

requirements-completed: [RETR-06]

duration: 2min
completed: 2026-03-06
---

# Phase 04 Plan 04: Grep Mime-Type Branching Summary

**grep_live fetch_and_extract uses /export for Workspace files (Docs/Sheets/Slides) and ?alt=media for binary files, eliminating 403 errors**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-06T01:14:19Z
- **Completed:** 2026-03-06T01:16:28Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- fetch_and_extract branches on mime_type: Workspace files use /export endpoint, binary files use ?alt=media
- grep_live accepts and passes mime_type to fetch_and_extract
- chat.py builds mime_map from file_list and passes mimeType to each grep_live call
- 3 new tests covering export URL, alt=media URL, and mime_type passthrough

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for mime-type branching** - `5324c4a` (test)
2. **Task 1 (GREEN): Implement mime-type branching** - `fa053a7` (feat)

## Files Created/Modified
- `backend/grep.py` - Added mime_type param to fetch_and_extract with EXPORT_MIME_MAP branching; grep_live passes mime_type through
- `backend/chat.py` - Builds mime_map from file_list, passes mime_type to grep_live calls
- `backend/tests/test_grep.py` - 3 new tests for export URL, alt=media URL, mime_type passthrough
- `backend/tests/test_chat_endpoint.py` - Updated _mock_grep_live to accept mime_type kwarg

## Decisions Made
- Imported EXPORT_MIME_MAP and DRIVE_API_BASE from backend.drive rather than duplicating -- cleaner, single source of truth
- mime_type as keyword-only arg with empty string default for backward compatibility with existing callers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated _mock_grep_live in test_chat_endpoint.py**
- **Found during:** Task 1 (GREEN phase verification)
- **Issue:** Existing mock for grep_live in test_chat_endpoint.py didn't accept the new mime_type kwarg, causing test_hybrid_stale_only to fail
- **Fix:** Added `*, mime_type=""` to the mock's _grep function signature
- **Files modified:** backend/tests/test_chat_endpoint.py
- **Verification:** All 26 grep + chat tests pass
- **Committed in:** fa053a7 (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for test correctness after signature change. No scope creep.

## Issues Encountered
- Pre-existing test ordering issue: test_index_endpoint.py::test_valid_folder_url fails when run with all backend tests but passes in isolation. Not related to our changes -- logged as out-of-scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- grep_live now handles all Google Drive file types without 403 errors
- Ready for remaining gap closure plans in phase 04

---
*Phase: 04-staleness-hybrid-retrieval*
*Completed: 2026-03-06*
