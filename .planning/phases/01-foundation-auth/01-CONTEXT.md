# Phase 1: Foundation + Auth - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend scaffold (Modal + FastAPI with Volume, CORS, secrets), Google OAuth via Token Client flow (drive.readonly scope), React + Vite frontend shell with shadcn/ui, IndexedDB stores for chats and messages, and model strategy config (DeepSeek default, swappable key). No indexing, no chat, no retrieval — just the foundation.

</domain>

<decisions>
## Implementation Decisions

### Sign-in button
- Use Google Identity Services' `renderButton()` — Google-styled, familiar, handles its own states
- No custom button styling needed

### Permission denied handling
- Inline error on the landing page when user denies drive.readonly scope
- Explain why Drive access is required
- Include a "Try again" button to re-trigger the OAuth flow

### Token expiry / re-auth
- Modal dialog overlay when token expires mid-session (403 from Drive/backend)
- "Your session has expired" with sign-in button
- Old chat history remains visible behind the modal (read-only from IndexedDB)
- sessionStorage cleared automatically on expiry detection

### Post-auth transition
- Brief skeleton/shimmer of the app layout (~500ms) while IndexedDB loads
- Then render the main app shell

### Claude's Discretion
- Landing page layout and visual design (within shadcn/ui conventions)
- App shell structure after sign-in (sidebar placeholder, empty state messaging)
- IndexedDB schema details beyond what PERS-01/02/03 specify
- FastAPI project structure and Modal app configuration
- Exact skeleton shimmer implementation

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The spec is highly prescriptive with code samples for most implementation details (Token Client setup, Volume mount paths, IndexedDB store schemas).

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no code exists yet

### Established Patterns
- None yet — this phase establishes the patterns for all subsequent phases

### Integration Points
- Google OAuth Client ID available in `client_secret_*.json` at project root
- Spec provides detailed code samples for Token Client flow, FastAPI app structure, and IndexedDB schemas

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-auth*
*Context gathered: 2026-03-05*
