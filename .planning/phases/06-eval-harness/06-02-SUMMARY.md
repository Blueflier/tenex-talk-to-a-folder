---
phase: 06-eval-harness
plan: 02
subsystem: testing
tags: [eval, qasper, sse-client, embedding-cache, drive-delta, httpx, tdd]

# Dependency graph
requires:
  - "06-01: eval/scoring.py, eval/classify.py, eval/dataset.py"
provides:
  - "eval/run_eval.py: full eval CLI with --dry-run"
  - "eval/run_drive_delta.py: compute_delta, check_threshold, Drive comparison"
  - "eval/client.py: async SSE client for POST /chat"
  - "eval/cache.py: embedding cache save/load"
  - "eval/config.json: eval configuration defaults"
  - "eval/README.md: setup and usage documentation"
  - "backend/auth.py: EVAL_MODE bypass"
affects: [06-eval-harness]

# Tech tracking
tech-stack:
  added: []
  patterns: [EVAL_MODE auth bypass, SSE stream parsing with httpx, embedding cache mirroring storage.py, TDD for drive delta]

key-files:
  created:
    - eval/run_eval.py
    - eval/run_drive_delta.py
    - eval/client.py
    - eval/cache.py
    - eval/config.json
    - eval/README.md
    - eval/tests/test_drive_delta.py
  modified:
    - backend/auth.py
    - .gitignore
    - eval/dataset.py

key-decisions:
  - "EVAL_MODE env var in auth.py returns 'eval-user' bypassing Google API"
  - "datasets 4.0 compat: use revision='refs/convert/parquet' for allenai/qasper"
  - "httpx.stream() for SSE parsing instead of response.aiter_lines() on non-streamed POST"
  - "Full_text reconstruction fallback when PDF download unavailable"
  - "compute_delta uses key intersection for graceful mismatched-keys handling"

patterns-established:
  - "EVAL_MODE env var pattern for auth bypass in eval contexts"
  - "SSE client pattern: stream POST, parse data: lines, accumulate tokens"

requirements-completed: [EVAL-01, EVAL-04]

# Metrics
duration: 5min
completed: 2026-03-06
---

# Phase 6 Plan 2: Eval Pipeline Wiring Summary

**End-to-end eval pipeline: SSE client, embedding cache, auth bypass, run_eval.py orchestrator with --dry-run, Drive delta comparison with TDD unit tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-06T01:40:08Z
- **Completed:** 2026-03-06T01:44:51Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Full eval pipeline wired: QASPER dataset -> chunk -> embed -> cache -> query /chat -> score -> classify -> results JSON + stdout summary
- Drive delta comparison with unit-tested compute_delta and check_threshold (TDD: 10 tests)
- SSE client parsing POST /chat stream, embedding cache mirroring storage.py pattern
- Auth bypass via EVAL_MODE env var, README with complete setup/usage documentation

## Task Commits

Each task was committed atomically:

1. **Task 1: Auth bypass, cache, client, config** - `93ab9e0` (feat)
2. **Task 2: run_eval.py orchestrator** - `e6d064e` (feat)
3. **Task 3: Drive delta tests RED** - `ab16501` (test)
4. **Task 3: Drive delta + README GREEN** - `5575506` (feat)

_TDD Task 3 has RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `backend/auth.py` - Added EVAL_MODE env var bypass returning "eval-user"
- `eval/cache.py` - Embedding cache save/load with .npy + .json per paper
- `eval/client.py` - Async SSE client for POST /chat with token accumulation
- `eval/config.json` - Eval defaults: base_url, n_papers, seed, drive_delta
- `eval/run_eval.py` - Main eval CLI with --dry-run, PDF download/fallback, cache, scoring
- `eval/run_drive_delta.py` - Drive delta comparison with compute_delta, check_threshold
- `eval/tests/test_drive_delta.py` - 10 unit tests for delta calculation and threshold logic
- `eval/README.md` - Setup, usage, cache, QASPER, and Drive delta documentation
- `eval/dataset.py` - Fixed datasets 4.0 compat with parquet revision
- `.gitignore` - Added eval/cache/ and eval/data/ entries

## Decisions Made
- EVAL_MODE env var in auth.py returns "eval-user" bypassing Google API (cleanest approach per RESEARCH.md)
- datasets 4.0 removed script-based loading; fixed with `revision="refs/convert/parquet"` for allenai/qasper
- httpx.stream() context manager for SSE parsing (proper streaming instead of buffered response)
- Full_text reconstruction as fallback when Semantic Scholar PDF download unavailable
- compute_delta uses key intersection for graceful handling of mismatched paper sets

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed datasets 4.0 incompatibility with QASPER loading**
- **Found during:** Task 2 (run_eval.py verification)
- **Issue:** `datasets` 4.0.0 removed support for script-based datasets; `load_dataset("allenai/qasper")` raised RuntimeError
- **Fix:** Added `revision="refs/convert/parquet"` parameter to use HuggingFace's auto-converted parquet version
- **Files modified:** eval/dataset.py
- **Verification:** --dry-run loads 416 papers, selects 5, prints questions
- **Committed in:** e6d064e (Task 2 commit)

**2. [Rule 1 - Bug] Fixed paper ID field name for parquet revision**
- **Found during:** Task 2 (run_eval.py verification)
- **Issue:** Parquet version uses `id` instead of `article_id` field name
- **Fix:** Updated run_eval.py to check `id` first, fall back to `article_id`
- **Files modified:** eval/run_eval.py
- **Verification:** Paper IDs correctly extracted (e.g., "1911.10742")
- **Committed in:** e6d064e (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for datasets library version compatibility. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required for dry-run. Full eval requires `OPENAI_API_KEY` and running uvicorn.

## Next Phase Readiness
- Complete eval pipeline ready: `python eval/run_eval.py --dry-run` validates end-to-end
- Full eval requires running uvicorn + OpenAI API key
- Drive delta requires Google access token + Drive folder with PDFs
- 44 total eval tests passing

---
*Phase: 06-eval-harness*
*Completed: 2026-03-06*
