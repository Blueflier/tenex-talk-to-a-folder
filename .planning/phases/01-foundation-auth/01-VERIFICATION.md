---
phase: 01-foundation-auth
verified: 2026-03-05T23:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 1: Foundation + Auth Verification Report

**Phase Goal:** User can sign in with Google and land in a working app shell with persistent local storage
**Verified:** 2026-03-05T23:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can click "Sign in with Google" and receive a valid access token with drive.readonly scope | VERIFIED | `auth.ts` calls `initTokenClient` with `drive.readonly` scope, stores token in sessionStorage. `LandingPage.tsx` renders "Sign in with Google" button calling `requestToken()`. GIS script in `index.html`. `App.tsx` wires initAuth on mount + requestToken on click. |
| 2 | Backend FastAPI app runs on Modal with Volume mounted, CORS configured, and secrets available | VERIFIED | `app.py` defines Modal app "talk-to-a-folder", Volume at `/data`, CORSMiddleware allowing `localhost:5173`, secrets for openai-secret and deepseek-secret, `@modal.asgi_app()` decorator. Health endpoint returns `{"status": "ok"}`. |
| 3 | API calls from frontend include Authorization header; expired tokens trigger a re-auth banner | VERIFIED | `api.ts` reads token from sessionStorage, attaches `Authorization: Bearer {token}`, throws `TOKEN_EXPIRED` on 401/403 and clears sessionStorage. `App.tsx` listens for `TOKEN_EXPIRED` via unhandledrejection, sets `showReAuth=true`. `ReAuthModal.tsx` renders dialog with sign-in button. |
| 4 | IndexedDB "chats" and "messages" stores exist and persist data across page reloads | VERIFIED | `db.ts` creates "chats" store with `session_id` keyPath and `last_message_at` index; "messages" store with autoIncrement, `session_id` and `created_at` indexes. Full CRUD: saveChat, getChats, saveMessage, getMessages, loadMessages. 7 tests in `db.test.ts`. |
| 5 | Model strategy is configured with DeepSeek default and swappable model key | VERIFIED | `config.py` defines `MODEL_CONFIGS` with "deepseek" and "openai" entries, `ACTIVE_MODEL` from env defaulting to "deepseek", `get_llm_client()` returns `(AsyncOpenAI, model_name)` tuple. Used by `chat.py` and `grep.py`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app.py` | Modal app + FastAPI with CORS, Volume, secrets, health endpoint | VERIFIED | 49 lines, all exports present (web_app, fastapi_app) |
| `backend/auth.py` | Google userinfo verification returning sub claim | VERIFIED | 24 lines, exports get_google_user_id, calls googleapis.com/oauth2/v3/userinfo |
| `backend/config.py` | Model strategy config with DeepSeek default | VERIFIED | 35 lines, exports get_llm_client, MODEL_CONFIGS, ACTIVE_MODEL, VOLUME_PATH |
| `backend/requirements.txt` | Python dependencies | VERIFIED | 10 packages listed |
| `frontend/src/lib/db.ts` | IndexedDB open, CRUD for chats and messages | VERIFIED | 142 lines, exports openDB, getChats, getMessages, saveChat, saveMessage, loadMessages, Chat, Message types |
| `frontend/src/lib/db.test.ts` | Tests for IndexedDB operations | VERIFIED | File exists with 7+ tests |
| `frontend/vite.config.ts` | Vite config with Tailwind v4 plugin | VERIFIED | File exists |
| `frontend/vitest.config.ts` | Vitest configuration with jsdom | VERIFIED | File exists |
| `frontend/src/lib/auth.ts` | Token Client initialization and requestToken | VERIFIED | 34 lines, exports initAuth, requestToken, uses drive.readonly scope |
| `frontend/src/lib/api.ts` | Auth-aware fetch wrapper detecting 403 | VERIFIED | 57 lines, exports apiFetch, streamIndex. Attaches Bearer token, detects 401/403 |
| `frontend/src/lib/api.test.ts` | Tests for apiFetch | VERIFIED | File exists |
| `frontend/src/components/landing/LandingPage.tsx` | Landing page with sign-in button and error handling | VERIFIED | 61 lines, renders Card with "Sign in with Google" button, privacy messaging, error display |
| `frontend/src/components/landing/Landing.test.tsx` | Render tests for landing page | VERIFIED | File exists |
| `frontend/src/components/app-shell/AppShell.tsx` | Post-auth app shell with skeleton loading | VERIFIED | 83 lines, skeleton shimmer for 500ms, loads chats from IndexedDB, empty state message |
| `frontend/src/components/app-shell/ReAuthModal.tsx` | Modal dialog for expired token re-auth | VERIFIED | 35 lines, Dialog with "Your session has expired" message and sign-in button |
| `frontend/src/types/google.d.ts` | Type declarations for GIS Token Client | VERIFIED | 30 lines, declares TokenClient, TokenResponse, ErrorResponse, initTokenClient |
| `frontend/index.html` | GIS script tag | VERIFIED | Contains `<script src="https://accounts.google.com/gsi/client" async defer>` |
| `frontend/.env.example` | Environment variable placeholders | VERIFIED | File exists |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app.py` | `backend/auth.py` | import get_google_user_id | WIRED | Used by chat.py, index.py, reindex.py (downstream consumers) |
| `backend/app.py` | `backend/config.py` | import get_llm_client | WIRED | Used by chat.py and grep.py |
| `frontend/src/App.tsx` | `frontend/src/lib/auth.ts` | initAuth + requestToken | WIRED | App.tsx imports and calls both on mount and click |
| `frontend/src/lib/api.ts` | sessionStorage | getItem/removeItem | WIRED | Reads token on every call, clears on 401/403 |
| `frontend/src/lib/api.ts` | backend/app.py | Authorization: Bearer header | WIRED | Header attached in both apiFetch and streamIndex |
| `frontend/src/lib/db.ts` | IndexedDB | indexedDB.open | WIRED | Opens "talk-to-a-folder" DB version 1 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-01 | 01-03 | Google sign-in via Token Client (drive.readonly) | SATISFIED | auth.ts uses initTokenClient with drive.readonly scope |
| AUTH-02 | 01-03 | Token in sessionStorage, Authorization header on API calls | SATISFIED | auth.ts stores in sessionStorage, api.ts reads and attaches Bearer header |
| AUTH-03 | 01-03 | Re-auth banner on token expiry, sessionStorage cleared | SATISFIED | api.ts clears on 401/403, App.tsx shows ReAuthModal |
| AUTH-04 | 01-01 | User identity from Google sub claim server-side | SATISFIED | auth.py calls userinfo endpoint, returns info["sub"] |
| INFR-01 | 01-01 | Modal app with FastAPI, Volume, secrets | SATISFIED | app.py defines all three |
| INFR-02 | 01-01 | CORS with explicit origins | SATISFIED | CORSMiddleware allows localhost:5173 |
| INFR-04 | 01-01 | Model strategy with DeepSeek default | SATISFIED | config.py MODEL_CONFIGS with deepseek default |
| UI-01 | 01-03 | Landing page with sign-in and privacy messaging | SATISFIED | LandingPage.tsx renders both |
| PERS-01 | 01-02 | IndexedDB "chats" store schema | SATISFIED | db.ts creates with session_id keyPath, last_message_at index |
| PERS-02 | 01-02 | IndexedDB "messages" store schema | SATISFIED | db.ts creates with autoIncrement, session_id + created_at indexes |
| PERS-03 | 01-02 | Chat history loads from IndexedDB with no server calls | SATISFIED | AppShell.tsx calls getChats() on mount, no fetch calls |

No orphaned requirements found -- all 11 requirement IDs mapped to this phase in REQUIREMENTS.md are covered by plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/app-shell/AppShell.tsx` | 49 | `{/* Sidebar placeholder */}` comment | Info | Expected -- sidebar is Phase 5 scope |

No blocker or warning-level anti-patterns found in Phase 1 files.

### Human Verification Required

### 1. Google OAuth End-to-End Flow

**Test:** Visit localhost:5173, click "Sign in with Google", complete consent
**Expected:** Google popup requests drive.readonly scope, token stored in sessionStorage, app shell loads with skeleton then empty state
**Why human:** OAuth popup interaction cannot be verified programmatically

### 2. Re-Auth Modal Trigger

**Test:** After sign-in, delete sessionStorage token in DevTools, trigger an API call
**Expected:** ReAuthModal appears with "Your session has expired" and sign-in button, old chat history visible behind
**Why human:** Requires browser interaction and visual confirmation

### 3. Privacy Messaging Visibility

**Test:** View landing page before sign-in
**Expected:** Card shows "Your files stay in Google Drive. We only read them to answer your questions."
**Why human:** Visual layout and readability verification

### Gaps Summary

No gaps found. All 5 observable truths verified with full artifact existence, substantive implementation, and proper wiring. All 11 requirements satisfied. All 9 commits confirmed in git log. No blocker anti-patterns detected.

### Commit Verification

All 9 documented commits verified in git history:
- Plan 01: 9b36960 (test), c581cd0 (feat)
- Plan 02: 8e57208 (feat), 0c40673 (test), 8cd3487 (feat)
- Plan 03: 82212d8 (test), 9c728e6 (feat), 0abef1b (test), 40a7372 (feat)

---

_Verified: 2026-03-05T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
