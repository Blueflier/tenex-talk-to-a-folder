# Phase 5: Multi-session + Polish - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

User can manage multiple chat sessions with full error handling and production-quality UX. Covers sidebar chat management (list, create, rename, delete), duplicate Drive link detection, multi-link sessions (append embeddings), comprehensive error states for all failure modes, and rate limiting on /chat. No new indexing strategies, no retrieval changes, no cross-session embedding sharing.

</domain>

<decisions>
## Implementation Decisions

### Session switching
- State-based session management (selectedSessionId in AppShell state) -- no client-side router
- Clicking a sidebar chat swaps the ChatView component via state change
- Abort active stream immediately when user clicks a different chat; partial response already saved to IndexedDB
- Fixed sidebar (w-64), no collapsible/hamburger behavior -- desktop-focused takehome
- "+" button in sidebar creates empty session: generates UUID, creates IndexedDB record, switches to empty ChatView with Drive link input

### Duplicate detection
- Duplicate check triggers on paste, before indexing starts -- resolve Drive link to file IDs, check against all sessions in IndexedDB
- Duplicate notice: inline card below the Drive link input (yellow/amber) showing which chat has these files
- "Open that chat" switches selectedSessionId to the existing session (same as sidebar click)
- "Re-index here" indexes the entire pasted link into the current session (all files, not just overlapping ones)
- Same-session re-paste: skip with notice ("These files are already indexed in this chat")
- Partial overlap across sessions: show informational notice, index all files anyway
- Multi-link input: ChatInput detects Drive URLs vs questions -- if input looks like a Drive URL, trigger indexing flow; otherwise send as chat question

### Error states
- All errors use sonner toasts (already wired up) -- no inline error banners
- Color-coded: red for fatal errors (403, 404, network failure), yellow/amber for warnings (scanned PDF, empty folder)
- Auto-dismiss after 5-8 seconds for non-critical errors
- Connection loss detected on failed requests only (no proactive navigator.onLine listener)
- Rate limit (429): red toast "Too many requests. Please wait a moment." + chat input disabled for ~10 seconds with cooldown

### Rate limiting
- Backend: 10 req/min per session, in-memory counter on /chat endpoint
- Frontend: on 429 response, disable chat input briefly and show red toast

### Chat title & rename
- Default title: first indexed source name (file name or folder name from first Drive link)
- Three-dot menu on sidebar items with "Rename" and "Delete" options
- Rename: inline text field in sidebar on menu click, Enter to save, Escape to cancel
- Delete: confirmation dialog, removes chat + messages from IndexedDB; server-side embeddings left to expire naturally
- Title editable from sidebar only (not from chat header)
- Sidebar items show title only -- no file count, no message preview

### Claude's Discretion
- Three-dot menu component styling and positioning
- Confirmation dialog design for delete
- Drive URL detection regex/heuristic in ChatInput
- Rate limit cooldown timer implementation
- Toast auto-dismiss durations within 5-8s range
- Empty state design when no chats exist after deleting all

</decisions>

<specifics>
## Specific Ideas

- Follow standard AI chat app conventions (ChatGPT/Claude) for sidebar behavior -- established in Phase 3
- AppShell.tsx already has sidebar placeholder at w-64 with chat list rendering and shimmer loading -- extend rather than rebuild
- Phase 2 decision: indexing progress shown in modal overlay, chat header shows "8 files indexed - 312 chunks" -- keep this pattern when adding multi-link support

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AppShell.tsx`: Sidebar placeholder with `getChats()` loading and chat list rendering (needs session switching + new chat + menu)
- `ChatView.tsx`: Full chat component with streaming, citations, staleness banners, re-indexing -- receives sessionId as prop (ready for state-based switching)
- `db.ts`: `getChats()` returns chats sorted by recency, `Chat` type with `indexed_sources[]` for duplicate detection
- `sonner` toast system already wired in `App.tsx` (`<Toaster position="top-center" richColors />`)
- shadcn/ui: button, card, dialog, popover, avatar, textarea, progress components available
- `useStream` hook: has `abort()` method for canceling streams on session switch
- `ChatInput.tsx`: Has prefill prop pattern and disabledTooltip -- extend for Drive URL detection and rate limit cooldown

### Established Patterns
- IndexedDB Promise-wrapped CRUD pattern in `db.ts`
- SSE streaming with abort via `useStream` hook
- Per-file independent state tracking (useReindex with `Set<string>`)
- Color-coded banners: yellow (stale), red (deleted), orange (access revoked) from Phase 4

### Integration Points
- `AppShell.tsx` renders `ChatView` -- needs to pass selectedSessionId and provide switching mechanism
- `db.ts` needs: `deleteChat()`, `deleteMessages(sessionId)`, `updateChatTitle()` functions
- `ChatInput.tsx` needs Drive URL detection to route between indexing flow and chat question
- Backend `app.py` needs rate limiting middleware on /chat endpoint
- `IndexingModal` needs duplicate detection check before opening

</code_context>

<deferred>
## Deferred Ideas

- Cross-session embedding sharing (user-level embedding store) -- would allow new sessions to reference files indexed in other sessions without re-indexing. Requires storage architecture change (per-user vs per-session embeddings). Future phase or v2.

</deferred>

---

*Phase: 05-multi-session-polish*
*Context gathered: 2026-03-05*
