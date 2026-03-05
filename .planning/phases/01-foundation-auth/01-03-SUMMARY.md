---
phase: 01-foundation-auth
plan: 03
subsystem: auth, ui
tags: [google-oauth, gis-token-client, react, sessionStorage, drive-readonly]

# Dependency graph
requires:
  - phase: 01-foundation-auth/01
    provides: "Backend with CORS, auth verification, /health endpoint"
  - phase: 01-foundation-auth/02
    provides: "Vite+React scaffold, IndexedDB persistence, shadcn/ui components"
provides:
  - "Google OAuth Token Client flow with drive.readonly scope"
  - "Auth-aware apiFetch wrapper detecting 401/403 for re-auth"
  - "Landing page with sign-in button and privacy messaging"
  - "App shell with skeleton loading and sidebar placeholder"
  - "ReAuthModal for expired token recovery"
affects: [02-indexing-pipeline, 03-retrieval-chat, 05-multi-session-polish]

# Tech tracking
tech-stack:
  added: [google-identity-services]
  patterns: [sessionStorage-token-management, token-client-custom-button, auth-aware-fetch-wrapper]

key-files:
  created:
    - frontend/src/lib/auth.ts
    - frontend/src/lib/api.ts
    - frontend/src/lib/api.test.ts
    - frontend/src/types/google.d.ts
    - frontend/src/components/landing/LandingPage.tsx
    - frontend/src/components/landing/Landing.test.tsx
    - frontend/src/components/app-shell/AppShell.tsx
    - frontend/src/components/app-shell/ReAuthModal.tsx
    - frontend/.env.example
  modified:
    - frontend/index.html
    - frontend/src/App.tsx

key-decisions:
  - "Google Token Client with custom button (not renderButton) per GIS best practices"
  - "sessionStorage for access token (cleared on tab close, no refresh tokens)"
  - "apiFetch clears token and throws TOKEN_EXPIRED on 401/403 responses"

patterns-established:
  - "Token Client pattern: initAuth on mount, requestToken on user click"
  - "Auth-aware fetch: apiFetch wraps fetch with Authorization header and 401/403 detection"
  - "Error inline: auth errors shown in landing page UI, not alerts"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, UI-01]

# Metrics
duration: 12min
completed: 2026-03-05
---

# Phase 1 Plan 3: Google OAuth + Landing Page + Auth-Aware API Client Summary

**Google OAuth Token Client flow with drive.readonly scope, landing page with privacy messaging, auth-aware apiFetch wrapper, and app shell with re-auth modal**

## Performance

- **Duration:** ~12 min (across checkpoint pause)
- **Started:** 2026-03-05
- **Completed:** 2026-03-05
- **Tasks:** 3 (2 TDD + 1 human-verify)
- **Files modified:** 11

## Accomplishments
- Auth module (initAuth/requestToken) wraps Google Identity Services Token Client for drive.readonly scope
- apiFetch wrapper attaches Bearer token from sessionStorage and detects 401/403 for re-auth flow
- Landing page with sign-in button, privacy messaging, and inline error handling for denied scope
- App shell with skeleton shimmer loading and sidebar placeholder for post-auth state
- ReAuthModal overlays on token expiry so old chat history remains visible
- Full TDD coverage: api.test.ts (4 tests) and Landing.test.tsx (4 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for apiFetch** - `82212d8` (test)
2. **Task 1 GREEN: Auth module + API client** - `9c728e6` (feat)
3. **Task 2 RED: Failing tests for LandingPage** - `0abef1b` (test)
4. **Task 2 GREEN: UI components + App.tsx wiring** - `40a7372` (feat)
5. **Task 3: Verify auth flow end-to-end** - human-verify checkpoint (no code commit)

## Files Created/Modified
- `frontend/src/types/google.d.ts` - Type declarations for google.accounts.oauth2 Token Client API
- `frontend/src/lib/auth.ts` - initAuth and requestToken wrapping GIS Token Client
- `frontend/src/lib/api.ts` - apiFetch with Authorization header and 401/403 detection
- `frontend/src/lib/api.test.ts` - Tests for apiFetch token attachment and error handling
- `frontend/src/components/landing/LandingPage.tsx` - Sign-in page with privacy messaging and error states
- `frontend/src/components/landing/Landing.test.tsx` - Render tests for LandingPage component
- `frontend/src/components/app-shell/AppShell.tsx` - Post-auth shell with skeleton loading
- `frontend/src/components/app-shell/ReAuthModal.tsx` - Modal dialog for expired token re-auth
- `frontend/src/App.tsx` - Root component routing between landing and app shell based on token state
- `frontend/index.html` - Added GIS script tag
- `frontend/.env.example` - VITE_GOOGLE_CLIENT_ID and VITE_API_URL placeholders

## Decisions Made
- Google Token Client with custom button (not renderButton) per GIS best practices and RESEARCH.md guidance
- sessionStorage for access token storage (cleared on tab close, no refresh token complexity)
- apiFetch clears token and throws TOKEN_EXPIRED on both 401 and 403 responses to trigger re-auth

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- OAuth app needed to be published to production in Google Cloud Console for sign-in to work (resolved by user during checkpoint verification)

## User Setup Required

Environment variables needed:
- `VITE_GOOGLE_CLIENT_ID` - Extract from client_secret_*.json (web.client_id field)
- `VITE_API_URL` - Set to http://localhost:8000

Dashboard configuration:
- Ensure http://localhost:5173 is in Authorized JavaScript origins in Google Cloud Console

## Next Phase Readiness
- Auth foundation complete: sign-in, token management, re-auth all working
- apiFetch ready for use by indexing pipeline (Phase 2) and chat (Phase 3)
- App shell ready for sidebar (Phase 5) and chat content (Phase 3)

## Self-Check: PASSED

All 4 commits verified (82212d8, 9c728e6, 0abef1b, 40a7372). All 9 created files confirmed on disk.

---
*Phase: 01-foundation-auth*
*Completed: 2026-03-05*
