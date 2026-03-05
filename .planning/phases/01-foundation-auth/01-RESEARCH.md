# Phase 1: Foundation + Auth - Research

**Researched:** 2026-03-05
**Domain:** Google OAuth Token Client, Modal/FastAPI backend, React/Vite frontend, IndexedDB persistence
**Confidence:** HIGH

## Summary

Phase 1 is a greenfield scaffold with four pillars: (1) Google OAuth via Token Client flow returning access tokens with drive.readonly scope, (2) Modal + FastAPI backend with Volume mount and secrets, (3) React + Vite + shadcn/ui frontend shell with landing page and app shell, (4) IndexedDB stores for chats and messages. The spec provides detailed code samples for almost every component, so implementation should follow the spec closely rather than inventing patterns.

One important correction from the CONTEXT.md discussion: the mention of `renderButton()` refers to the `google.accounts.id` API (Sign In with Google), which returns **ID tokens**. The spec requires the `google.accounts.oauth2.initTokenClient` flow (Token Client), which returns **access tokens** for Drive API access. These are two different GIS APIs loaded from the same script. The Token Client flow requires a custom-styled button that calls `client.requestAccessToken()` on click -- there is no pre-rendered button for this flow.

**Primary recommendation:** Follow the spec's code samples directly. This phase is mostly wiring -- use the exact patterns the spec provides for OAuth, Modal app definition, and IndexedDB schemas.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Sign-in button: Use Google Identity Services (custom button calling Token Client's `requestAccessToken()`) -- Google-styled, familiar
- Permission denied handling: Inline error on landing page when user denies drive.readonly scope, explain why needed, include "Try again" button
- Token expiry / re-auth: Modal dialog overlay when token expires (403 from Drive/backend), "Your session has expired" with sign-in button, old chat history visible behind modal (read-only from IndexedDB), sessionStorage cleared on expiry detection
- Post-auth transition: Brief skeleton/shimmer of app layout (~500ms) while IndexedDB loads, then render main app shell

### Claude's Discretion
- Landing page layout and visual design (within shadcn/ui conventions)
- App shell structure after sign-in (sidebar placeholder, empty state messaging)
- IndexedDB schema details beyond what PERS-01/02/03 specify
- FastAPI project structure and Modal app configuration
- Exact skeleton shimmer implementation

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | User can sign in with Google via Token Client flow (drive.readonly scope) | GIS Token Client API verified; initTokenClient + requestAccessToken pattern confirmed |
| AUTH-02 | Access token stored in sessionStorage, attached as Authorization header to all API calls | Standard pattern from spec; sessionStorage survives refresh, gone on tab close |
| AUTH-03 | User sees re-auth banner when token expires (Drive 403), sessionStorage cleared automatically | Modal dialog overlay per CONTEXT.md decision; detect 403 from any API call |
| AUTH-04 | User identity derived from Google sub claim server-side on every request | Backend calls Google userinfo endpoint with access token to get sub claim |
| INFR-01 | Modal app with FastAPI, Volume mount at /data, OpenAI + DeepSeek secrets | Modal.App + @modal.asgi_app() + Volume.from_name() + Secret.from_name() verified |
| INFR-02 | CORS configured with explicit origins (localhost:5173 + production domain) | FastAPI CORSMiddleware with explicit allow_origins list |
| INFR-04 | Model strategy: DeepSeek default, configurable model key, OpenAI-compatible client swap | Config dict with model name + base_url; both DeepSeek and OpenAI use openai SDK |
| UI-01 | Landing page with "Sign in with Google" button and privacy messaging | Custom button triggering Token Client flow; shadcn/ui Card for layout |
| PERS-01 | IndexedDB "chats" store: session_id, title, created_at, last_message_at, indexed_sources[] | Spec provides exact schema and openDB code |
| PERS-02 | IndexedDB "messages" store: session_id (indexed), role, content, citations[], created_at | Spec provides exact schema with auto-increment PK and session_id index |
| PERS-03 | Chat history and messages load from IndexedDB with no server calls | Spec provides getChats() and getMessages() patterns |

</phase_requirements>

## Standard Stack

### Core -- Frontend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | UI framework | Specified in constraints |
| Vite | 6.x | Build tool | Specified in constraints |
| TypeScript | 5.x | Type safety | Standard for React projects |
| Tailwind CSS | 4.x | Utility CSS | Required by shadcn/ui |
| @tailwindcss/vite | latest | Tailwind Vite plugin | New Tailwind v4 integration |
| shadcn/ui | latest (CLI) | Component library | Specified in constraints |

### Core -- Backend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| modal | latest | Serverless platform | Specified in constraints |
| fastapi | latest | API framework | Specified in constraints |
| aiohttp | latest | Async HTTP client | Used for Google userinfo verification |
| openai | latest | LLM/embedding client | OpenAI-compatible API for both OpenAI and DeepSeek |
| numpy | latest | Embedding storage | .npy format for embeddings |

### Supporting -- Frontend
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | Icons | shadcn/ui uses Lucide icons |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw IndexedDB | `idb` (jakearchibald) ~1.2kB | Cleaner async/await API, but spec provides raw IndexedDB samples -- follow spec |
| Custom OAuth button | Google renderButton() | renderButton() is for ID token flow (google.accounts.id), NOT Token Client flow -- cannot use |

**Installation -- Frontend:**
```bash
pnpm create vite@latest frontend -- --template react-ts
cd frontend
pnpm add tailwindcss @tailwindcss/vite
pnpm add -D @types/node
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button card dialog
```

**Installation -- Backend:**
```bash
pip install modal fastapi aiohttp openai numpy
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/
  src/
    components/
      ui/              # shadcn/ui generated components
      landing/         # Landing page + sign-in
      app-shell/       # Post-auth app shell
    lib/
      auth.ts          # Token Client init, token management
      db.ts            # IndexedDB open, CRUD operations
      api.ts           # Fetch wrapper with auth header
      model-config.ts  # Model strategy config (frontend reference only)
    App.tsx
    main.tsx
  index.html
  vite.config.ts

backend/
  app.py               # Modal app + FastAPI routes
  auth.py              # Google userinfo verification
  config.py            # Model strategy, constants
```

### Pattern 1: Google OAuth Token Client Flow
**What:** Client-side OAuth returning access tokens (not ID tokens)
**When to use:** When you need Drive API access without a backend token exchange

**CRITICAL DISTINCTION:** The GIS library (`accounts.google.com/gsi/client`) exposes TWO separate APIs:
- `google.accounts.id` -- Sign In with Google (ID tokens, JWT, `renderButton()`)
- `google.accounts.oauth2` -- Token Client (access tokens, `initTokenClient()`)

We need the Token Client for drive.readonly scope. There is NO pre-rendered button for this flow. We must create a custom button that calls `client.requestAccessToken()`.

```html
<!-- Load GIS library in index.html -->
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

```typescript
// src/lib/auth.ts
let tokenClient: google.accounts.oauth2.TokenClient;

export function initAuth(onSuccess: (token: string) => void, onError: (err: string) => void) {
  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
    scope: "https://www.googleapis.com/auth/drive.readonly",
    callback: (response) => {
      if (response.error) {
        onError(response.error);
        return;
      }
      if (response.access_token) {
        sessionStorage.setItem("google_access_token", response.access_token);
        onSuccess(response.access_token);
      }
    },
    error_callback: (err) => {
      // User closed popup or denied consent
      onError(err.type); // "popup_closed" or "popup_failed_to_open"
    },
  });
}

export function requestToken() {
  tokenClient.requestAccessToken();
}
```

### Pattern 2: Auth-Aware Fetch Wrapper
**What:** Centralized API client that attaches Authorization header and detects 403 for re-auth
**When to use:** Every API call from frontend to backend

```typescript
// src/lib/api.ts
const API_BASE = import.meta.env.VITE_API_URL;

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem("google_access_token");
  if (!token) throw new Error("NO_TOKEN");

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (res.status === 401 || res.status === 403) {
    sessionStorage.removeItem("google_access_token");
    throw new Error("TOKEN_EXPIRED");
  }

  return res;
}
```

### Pattern 3: Modal App with FastAPI
**What:** Serverless FastAPI deployment on Modal with Volume and secrets
**When to use:** Backend definition

```python
# backend/app.py
import modal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = modal.App("talk-to-a-folder")
volume = modal.Volume.from_name("talk-to-a-folder-data", create_if_missing=True)

web_app = FastAPI()

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://your-production-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.function(
    volumes={"/data": volume},
    image=modal.Image.debian_slim().pip_install(
        "fastapi", "aiohttp", "openai", "numpy"
    ),
    secrets=[
        modal.Secret.from_name("openai-secret"),
        modal.Secret.from_name("deepseek-secret"),
    ],
)
@modal.asgi_app()
def fastapi_app():
    return web_app
```

### Pattern 4: Model Strategy Config
**What:** Swappable LLM config using OpenAI-compatible client
**When to use:** All LLM calls

```python
# backend/config.py
import os

MODEL_CONFIGS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
}

ACTIVE_MODEL = os.environ.get("ACTIVE_MODEL", "deepseek")

def get_llm_client():
    cfg = MODEL_CONFIGS[ACTIVE_MODEL]
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=os.environ[cfg["api_key_env"]],
        base_url=cfg["base_url"],
    ), cfg["model"]
```

### Anti-Patterns to Avoid
- **Using `google.accounts.id.renderButton()` for Token Client flow:** This is the wrong API. `renderButton()` returns ID tokens (JWT), not access tokens. You cannot use it to get drive.readonly scope.
- **Storing access token in localStorage:** Spec says sessionStorage. localStorage persists across tab close and is a security risk for access tokens.
- **Forgetting `volume.commit()` after writes:** Writes to Modal Volume may not persist without explicit commit. Not relevant in Phase 1 (no writes yet), but set the pattern now.
- **Wildcard CORS origins:** Spec explicitly says explicit origins only, no `*`.
- **Making IndexedDB calls inside render:** Always in useEffect or event handlers. IndexedDB is async and must not block rendering.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UI components (buttons, cards, dialogs) | Custom components | shadcn/ui | Consistent styling, accessible, copy-paste ownership |
| CSS utility classes | Custom CSS | Tailwind CSS | Specified in constraints |
| Google OAuth flow | Custom OAuth | Google Identity Services SDK | Security, compliance, maintained by Google |
| HTTP client (backend) | requests/urllib | aiohttp | Async required for Modal/FastAPI |
| LLM API calls | Raw HTTP | openai SDK | Handles streaming, retries, both OpenAI and DeepSeek compatible |

## Common Pitfalls

### Pitfall 1: Wrong GIS API for OAuth
**What goes wrong:** Using `google.accounts.id` (Sign In) instead of `google.accounts.oauth2` (Token Client), resulting in ID tokens that cannot access Drive API
**Why it happens:** Both APIs load from the same `gsi/client` script; names are confusingly similar
**How to avoid:** Always use `google.accounts.oauth2.initTokenClient()`. The callback receives `response.access_token`, not a JWT credential.
**Warning signs:** Getting a JWT back instead of an opaque access token; Drive API returning 401

### Pitfall 2: GIS Script Not Loaded Yet
**What goes wrong:** `google.accounts.oauth2` is undefined when React component mounts
**Why it happens:** The GIS script loads async; React may mount before it is ready
**How to avoid:** Check for `window.google?.accounts?.oauth2` before initializing. Use a loading state or onload callback on the script tag.
**Warning signs:** TypeError: Cannot read properties of undefined

### Pitfall 3: Modal Volume Path Confusion
**What goes wrong:** Writing to `/xyz.txt` instead of `/data/xyz.txt` -- file goes to ephemeral local disk
**Why it happens:** Volume is mounted at `/data`, but code uses paths without the mount prefix
**How to avoid:** Use `VOLUME_PATH = Path("/data")` constant; always construct paths from it
**Warning signs:** Files disappear between function invocations

### Pitfall 4: CORS Preflight Missing Headers
**What goes wrong:** Browser blocks requests with "CORS error" despite allow_origins being set
**Why it happens:** Authorization header triggers preflight; `allow_headers` must include it
**How to avoid:** Set `allow_headers=["*"]` or explicitly list `["Authorization", "Content-Type"]`
**Warning signs:** OPTIONS request returns 405; POST never fires

### Pitfall 5: IndexedDB onupgradeneeded Only Fires on Version Change
**What goes wrong:** Adding a new object store or index doesn't take effect
**Why it happens:** `onupgradeneeded` only fires when DB_VERSION changes
**How to avoid:** Increment DB_VERSION when schema changes; handle migrations in onupgradeneeded
**Warning signs:** "store not found" errors in existing browsers

### Pitfall 6: Token Client error_callback vs callback error
**What goes wrong:** Permission denied / popup closed not handled
**Why it happens:** Two different error paths: `error_callback` (popup issues) and `callback` with `response.error` (OAuth errors like access_denied)
**How to avoid:** Handle BOTH error paths. `error_callback` for popup_closed/popup_failed_to_open. `callback` error for access_denied/invalid_scope.
**Warning signs:** Unhandled rejection when user closes consent popup

## Code Examples

### IndexedDB Initialization (from spec)
```typescript
// src/lib/db.ts
const DB_NAME = "talk-to-a-folder";
const DB_VERSION = 1;

export function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result;

      const chats = db.createObjectStore("chats", { keyPath: "session_id" });
      chats.createIndex("last_message_at", "last_message_at");

      const messages = db.createObjectStore("messages", { autoIncrement: true });
      messages.createIndex("session_id", "session_id");
      messages.createIndex("created_at", "created_at");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
```

### Google User ID Verification (from spec)
```python
# backend/auth.py
import aiohttp
from fastapi import HTTPException

async def get_google_user_id(access_token: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as r:
            if r.status != 200:
                raise HTTPException(status_code=401, detail="Invalid access token")
            info = await r.json()
            return info["sub"]
```

### Health Check Endpoint (for verifying backend deployment)
```python
@web_app.get("/health")
async def health():
    return {"status": "ok"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Sign-In Platform Library (gapi.auth2) | Google Identity Services (gsi/client) | 2023 (deprecated) | Must use GIS; old library no longer works for new apps |
| Tailwind CSS config file (tailwind.config.js) | @tailwindcss/vite plugin + CSS @import | Tailwind v4 (2025) | No config file needed; CSS-first configuration |
| shadcn/ui init with npx | pnpm dlx shadcn@latest init | 2024 | CLI changed from shadcn-ui to shadcn |

**Deprecated/outdated:**
- `gapi.auth2`: Fully deprecated, replaced by GIS. Do not use.
- `tailwind.config.js`: Not needed with Tailwind v4 + Vite plugin
- `create-react-app`: Use Vite instead

## Open Questions

1. **GIS TypeScript Types**
   - What we know: The GIS library loads globally via script tag, types available via `@types/google.accounts` or declared manually
   - What's unclear: Whether `@types/google.accounts` is current and complete
   - Recommendation: Add `@types/google.accounts` if available; otherwise declare minimal types in a `.d.ts` file

2. **Production Domain for CORS**
   - What we know: localhost:5173 is the dev origin; production domain TBD
   - What's unclear: Where frontend will be deployed (Vercel, Netlify, etc.)
   - Recommendation: Use environment variable for CORS origins; hardcode localhost:5173 for dev

3. **Modal Secret Names**
   - What we know: Secrets referenced as "openai-secret" and "deepseek-secret" in spec
   - What's unclear: Whether these exact names are already created in the user's Modal account
   - Recommendation: Document the `modal secret create` commands needed; verify during setup

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (frontend) + pytest (backend) |
| Config file | None -- Wave 0 will create |
| Quick run command | `pnpm test` (frontend), `pytest tests/ -x` (backend) |
| Full suite command | `pnpm test -- --run` (frontend), `pytest tests/` (backend) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Token Client initializes and returns access_token | manual-only | N/A -- requires Google consent screen | No |
| AUTH-02 | Token stored in sessionStorage, attached to API calls | unit | `pnpm test src/lib/api.test.ts` | Wave 0 |
| AUTH-03 | 403 response triggers re-auth flow, clears sessionStorage | unit | `pnpm test src/lib/api.test.ts` | Wave 0 |
| AUTH-04 | Server extracts Google sub from access token | unit | `pytest tests/test_auth.py -x` | Wave 0 |
| INFR-01 | FastAPI app runs on Modal with Volume and secrets | smoke | `modal run backend/app.py` (manual deploy check) | No |
| INFR-02 | CORS allows configured origins | unit | `pytest tests/test_cors.py -x` | Wave 0 |
| INFR-04 | Model config returns correct client for active model | unit | `pytest tests/test_config.py -x` | Wave 0 |
| UI-01 | Landing page renders sign-in button | unit | `pnpm test src/components/landing/Landing.test.tsx` | Wave 0 |
| PERS-01 | IndexedDB "chats" store schema correct | unit | `pnpm test src/lib/db.test.ts` | Wave 0 |
| PERS-02 | IndexedDB "messages" store schema correct | unit | `pnpm test src/lib/db.test.ts` | Wave 0 |
| PERS-03 | Data loads from IndexedDB with no server calls | unit | `pnpm test src/lib/db.test.ts` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pnpm test -- --run` (frontend) / `pytest tests/ -x` (backend)
- **Per wave merge:** Full suite both frontend and backend
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- [ ] `frontend/vitest.config.ts` -- Vitest configuration
- [ ] `frontend/src/lib/api.test.ts` -- covers AUTH-02, AUTH-03
- [ ] `frontend/src/lib/db.test.ts` -- covers PERS-01, PERS-02, PERS-03 (needs fake-indexeddb)
- [ ] `frontend/src/components/landing/Landing.test.tsx` -- covers UI-01
- [ ] `backend/tests/test_auth.py` -- covers AUTH-04
- [ ] `backend/tests/test_config.py` -- covers INFR-04
- [ ] `backend/tests/test_cors.py` -- covers INFR-02
- [ ] Framework installs: `pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom fake-indexeddb` (frontend), `pip install pytest pytest-asyncio httpx` (backend)

## Sources

### Primary (HIGH confidence)
- [Google Identity Services Token Client docs](https://developers.google.com/identity/oauth2/web/guides/use-token-model) -- Token Client flow, initTokenClient, requestAccessToken
- [Google Identity Services JS Reference](https://developers.google.com/identity/gsi/web/reference/js-reference) -- renderButton() is for google.accounts.id (ID tokens), NOT Token Client
- [Modal Volumes docs](https://modal.com/docs/guide/volumes) -- Volume creation, mounting, commit behavior
- [Modal Webhooks/ASGI docs](https://modal.com/docs/guide/webhooks) -- FastAPI deployment on Modal
- [Modal Secrets docs](https://modal.com/docs/guide/secrets) -- Secret creation and usage
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) -- Current setup procedure with Tailwind v4

### Secondary (MEDIUM confidence)
- [idb npm library](https://github.com/jakearchibald/idb) -- IndexedDB wrapper alternative (not recommended per spec alignment)

### Tertiary (LOW confidence)
- GIS TypeScript types availability -- needs verification during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries specified in constraints/spec
- Architecture: HIGH -- spec provides detailed code samples
- Pitfalls: HIGH -- verified against official docs (GIS API distinction, Modal Volume behavior)
- OAuth flow: HIGH -- critical renderButton() vs Token Client distinction verified

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable technologies, spec-driven implementation)
