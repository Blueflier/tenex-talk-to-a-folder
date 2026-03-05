---
phase: 01-foundation-auth
plan: 01
subsystem: infra, auth, api
tags: [modal, fastapi, cors, google-oauth, deepseek, openai, aiohttp, pytest]

# Dependency graph
requires: []
provides:
  - Modal app with FastAPI, Volume mount, and secrets
  - Google userinfo auth verification (get_google_user_id)
  - Model strategy config with DeepSeek default and OpenAI swap
  - Health endpoint at GET /health
  - CORS configured for localhost:5173
affects: [01-02, 01-03, 02-indexing-pipeline, 03-retrieval-chat]

# Tech tracking
tech-stack:
  added: [modal, fastapi, aiohttp, openai, numpy, pytest, pytest-asyncio, httpx]
  patterns: [modal-asgi-app, openai-compatible-client-swap, google-userinfo-verification]

key-files:
  created:
    - backend/app.py
    - backend/auth.py
    - backend/config.py
    - backend/requirements.txt
    - backend/tests/conftest.py
    - backend/tests/test_auth.py
    - backend/tests/test_config.py
    - backend/tests/test_cors.py
  modified: []

key-decisions:
  - "CORS allows only localhost:5173 -- production domain added later via env var"
  - "ACTIVE_MODEL read at module level with env default 'deepseek' -- tests reload module to swap"

patterns-established:
  - "Modal app pattern: modal.App + Volume.from_name + @modal.asgi_app() wrapping FastAPI"
  - "Auth pattern: aiohttp call to Google userinfo endpoint, return sub claim"
  - "Model config: dict-based strategy with OpenAI-compatible AsyncOpenAI client for both providers"
  - "Test pattern: monkeypatch env vars in conftest, httpx ASGITransport for FastAPI tests"

requirements-completed: [INFR-01, INFR-02, INFR-04, AUTH-04]

# Metrics
duration: 2min
completed: 2026-03-05
---

# Phase 1 Plan 01: Backend Scaffold Summary

**Modal + FastAPI backend with Volume mount, CORS, Google userinfo auth, and DeepSeek/OpenAI model strategy config**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-05T21:56:54Z
- **Completed:** 2026-03-05T21:58:25Z
- **Tasks:** 1
- **Files modified:** 10

## Accomplishments
- Backend scaffold with Modal app, Volume at /data, and secrets for OpenAI + DeepSeek
- Google access token verification via userinfo endpoint returning sub claim
- Model strategy config supporting DeepSeek (default) and OpenAI with client swap
- CORS allowing localhost:5173 with credential support
- 7 passing tests covering all behaviors

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: Backend tests** - `9b36960` (test)
2. **Task 1 GREEN: Backend implementation** - `c581cd0` (feat)

## Files Created/Modified
- `backend/app.py` - Modal app + FastAPI with CORS, Volume, secrets, health endpoint
- `backend/auth.py` - Google userinfo verification returning sub claim
- `backend/config.py` - Model strategy config with DeepSeek default
- `backend/requirements.txt` - Python dependencies
- `backend/tests/conftest.py` - Shared test fixtures with env vars
- `backend/tests/test_auth.py` - Auth verification tests
- `backend/tests/test_config.py` - Model config + health endpoint tests
- `backend/tests/test_cors.py` - CORS allow/reject tests

## Decisions Made
- CORS allows only localhost:5173 for now; production domain to be added later
- ACTIVE_MODEL env var read at module level; tests use importlib.reload to swap
- Test mocking pattern: aiohttp.ClientSession patched for auth tests, httpx ASGITransport for CORS/health tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend foundation complete, ready for frontend scaffold (01-02)
- Auth module ready for import by future API endpoints
- Model config ready for LLM calls in retrieval + chat phases

## Self-Check: PASSED

All 8 files verified present. Both commits (9b36960, c581cd0) verified in git log.

---
*Phase: 01-foundation-auth*
*Completed: 2026-03-05*
