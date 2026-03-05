# Phase 5: Multi-session + Polish - Research

**Researched:** 2026-03-05
**Domain:** Multi-session management, error handling, rate limiting
**Confidence:** HIGH

## Summary

Phase 5 transforms the single-session prototype into a multi-session app with sidebar navigation, duplicate detection, multi-link appending, comprehensive error toasts, and rate limiting. The existing codebase already has strong foundations: `AppShell.tsx` has a sidebar placeholder with `getChats()` loading, `ChatView` accepts `sessionId` as a prop, `db.ts` has Promise-wrapped IndexedDB CRUD, `sonner` toasts are wired, and `ChatInput` already detects Drive URLs. The work is primarily state management in `AppShell`, new IndexedDB functions (`deleteChat`, `deleteMessages`, `updateChatTitle`), duplicate detection logic against `indexed_sources[]` across all sessions, storage append logic on the backend, and a simple in-memory rate limiter on `/chat`.

No new libraries are needed. All required UI components (dialog, popover, button) are already installed via shadcn/ui + Radix. The backend rate limiter is trivial in-memory dict keyed by session_id. The biggest complexity is the state orchestration in AppShell (session switching, stream abort, indexing flow per session) and ensuring IndexedDB stays consistent when creating/deleting/renaming chats.

**Primary recommendation:** Structure work as 4 waves: (1) session management + sidebar, (2) duplicate detection + multi-link, (3) error toasts + rate limiting, (4) polish + edge cases.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- State-based session management (selectedSessionId in AppShell state) -- no client-side router
- Clicking a sidebar chat swaps the ChatView component via state change
- Abort active stream immediately when user clicks a different chat; partial response already saved to IndexedDB
- Fixed sidebar (w-64), no collapsible/hamburger behavior -- desktop-focused takehome
- "+" button in sidebar creates empty session: generates UUID, creates IndexedDB record, switches to empty ChatView with Drive link input
- Duplicate check triggers on paste, before indexing starts -- resolve Drive link to file IDs, check against all sessions in IndexedDB
- Duplicate notice: inline card below the Drive link input (yellow/amber) showing which chat has these files
- "Open that chat" switches selectedSessionId to the existing session (same as sidebar click)
- "Re-index here" indexes the entire pasted link into the current session (all files, not just overlapping ones)
- Same-session re-paste: skip with notice ("These files are already indexed in this chat")
- Partial overlap across sessions: show informational notice, index all files anyway
- Multi-link input: ChatInput detects Drive URLs vs questions -- if input looks like a Drive URL, trigger indexing flow; otherwise send as chat question
- All errors use sonner toasts (already wired up) -- no inline error banners
- Color-coded: red for fatal errors (403, 404, network failure), yellow/amber for warnings (scanned PDF, empty folder)
- Auto-dismiss after 5-8 seconds for non-critical errors
- Connection loss detected on failed requests only (no proactive navigator.onLine listener)
- Rate limit (429): red toast "Too many requests. Please wait a moment." + chat input disabled for ~10 seconds with cooldown
- Backend: 10 req/min per session, in-memory counter on /chat endpoint
- Frontend: on 429 response, disable chat input briefly and show red toast
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

### Deferred Ideas (OUT OF SCOPE)
- Cross-session embedding sharing (user-level embedding store) -- would allow new sessions to reference files indexed in other sessions without re-indexing. Requires storage architecture change (per-user vs per-session embeddings). Future phase or v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-02 | Left sidebar with chat list loaded from IndexedDB, sorted by recency | AppShell.tsx already has sidebar placeholder + getChats(). Extend with selectedSessionId state, click handlers, active highlight |
| UI-03 | New Chat button generates UUID session_id, creates IndexedDB record | Add saveChat() call with empty title, switch selectedSessionId, show Drive link input |
| UI-04 | Chat title defaults to first indexed source name, user can click to rename | Need updateChatTitle() in db.ts. Default title set on indexing complete. Inline edit in sidebar |
| UI-08 | Error banners for all failure modes (403, 404, empty, scanned PDF, connection, etc.) | sonner toasts already wired. Map each error type to toast.error/toast.warning with appropriate messages |
| UI-09 | Rate limit feedback: 429 response shown to user | useStream handles response status; add 429 check, toast.error, disable input with setTimeout |
| UI-10 | Duplicate upload notice with "Open that chat" / "Re-index here" options | Pre-indexing check: resolve Drive URL to file IDs, scan all chats' indexed_sources in IndexedDB |
| INDX-13 | Duplicate upload detection by Drive file ID against IndexedDB before indexing | getChats() returns all sessions with indexed_sources[]. Compare file IDs from Drive resolve against all sessions |
| INDX-14 | Multi-link sessions: pasting additional links appends to existing session embeddings | Backend: load existing .npy + .json, concatenate new embeddings/chunks, save. Frontend: update IndexedDB chat.indexed_sources |
| INFR-03 | Rate limiting on /chat: 10 requests/minute per session (in-memory) | Simple dict[session_id] -> list[timestamps] in chat.py. Check len in window, return 429 if exceeded |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Already in use |
| sonner | 2.0.7 | Toast notifications | Already wired in App.tsx with `<Toaster richColors />` |
| lucide-react | 0.577.0 | Icons (Plus, MoreVertical, Pencil, Trash2, etc.) | Already in use |
| @radix-ui/react-dialog | 1.1.15 | Delete confirmation dialog | Already installed, shadcn Dialog component available |
| FastAPI | >=0.135.0 | Backend framework | Already in use |

### Supporting (Already Available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui dialog | - | Delete confirmation | Already have Dialog component at `ui/dialog.tsx` |
| shadcn/ui popover | - | Three-dot menu dropdown | Already have Popover component at `ui/popover.tsx` |
| fake-indexeddb | 6.2.5 | Testing IndexedDB operations | Already installed as devDependency |

### No New Dependencies Needed
This phase requires zero new npm or pip packages. Everything is already installed.

## Architecture Patterns

### AppShell State Management
```
AppShell state:
├── selectedSessionId: string | null    // null = no chat selected (empty state)
├── chats: Chat[]                       // loaded from IndexedDB, kept in sync
├── indexedFiles: Map<string, IndexedFile[]>  // per-session indexed files cache
└── indexing state (driveUrl, indexingOpen)   // shared, operates on selectedSessionId
```

**Key change:** Current `AppShell` has a single `sessionId` created via `useState(() => crypto.randomUUID())`. This must become `selectedSessionId` state that changes when user clicks sidebar items or creates new chats.

### Session Switching Flow
```
User clicks sidebar chat ->
  1. abort() current stream (useStream.abort)
  2. setSelectedSessionId(newId)
  3. ChatView unmounts/remounts with new sessionId
  4. ChatView's useEffect loads messages from IndexedDB
  5. ChatHeader updates from chat's indexed files
```

**Critical:** ChatView already has `useEffect([sessionId])` that loads messages. Changing the sessionId prop triggers a fresh load. No extra work needed for message loading.

### Duplicate Detection Flow
```
User pastes Drive URL ->
  1. ChatInput.onDriveLink fires
  2. AppShell calls Drive API to resolve URL -> get file IDs
  3. Scan all chats from IndexedDB for matching file IDs in indexed_sources
  4. Match found in DIFFERENT session -> show DuplicateNotice card
     - "Open that chat" -> setSelectedSessionId(matchingSessionId)
     - "Re-index here" -> proceed with indexing flow
  5. Match found in SAME session -> toast.warning("These files are already indexed")
  6. No match -> proceed with indexing flow
```

**Note:** The Drive URL resolution needs a lightweight API call. The existing `resolve_drive_link` and `list_folder_files` are backend-only. For duplicate detection, we need a frontend call to resolve the Drive URL to file IDs before checking IndexedDB. Options:
- Add a `/resolve` endpoint that returns file IDs without indexing
- Or use the Google Drive API directly from frontend (we have the access token + drive.readonly scope)

**Recommendation:** Use Google Drive API directly from frontend via `fetch` with the access token. This avoids adding a new backend endpoint and is fast (just metadata, no file content).

### Multi-Link Append (Backend)
```python
# In index.py or storage.py:
def append_session(user_id, session_id, new_embeddings, new_chunks, volume):
    existing_emb, existing_chunks = load_session(user_id, session_id)
    combined_emb = np.concatenate([existing_emb, new_embeddings])
    combined_chunks = existing_chunks + new_chunks
    save_session(user_id, session_id, combined_emb, combined_chunks, volume)
```

The current `save_session` overwrites. For multi-link, the `/index` endpoint needs to detect if session data already exists and append rather than overwrite.

### Rate Limiter Pattern (Backend)
```python
import time
from collections import defaultdict

# In-memory rate limit store
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 10  # requests per minute
RATE_WINDOW = 60  # seconds

def check_rate_limit(session_id: str) -> bool:
    """Returns True if rate limited (should block)."""
    now = time.time()
    timestamps = _rate_limits[session_id]
    # Prune old entries
    _rate_limits[session_id] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_limits[session_id]) >= RATE_LIMIT:
        return True
    _rate_limits[session_id].append(now)
    return False
```

### New db.ts Functions Needed
```typescript
// Delete a chat and all its messages
export async function deleteChat(sessionId: string): Promise<void>

// Delete all messages for a session
export async function deleteMessages(sessionId: string): Promise<void>

// Update chat title
export async function updateChatTitle(sessionId: string, title: string): Promise<void>

// Get a single chat by session_id
export async function getChat(sessionId: string): Promise<Chat | undefined>
```

### Recommended Component Structure
```
src/
├── components/
│   ├── app-shell/
│   │   ├── AppShell.tsx          # Major refactor: session management
│   │   ├── Sidebar.tsx           # NEW: extracted sidebar component
│   │   ├── SidebarItem.tsx       # NEW: chat item with three-dot menu
│   │   ├── DuplicateNotice.tsx   # NEW: inline card for duplicate detection
│   │   └── ReAuthModal.tsx       # existing
│   ├── chat/                     # existing, minimal changes
│   └── indexing/                 # existing, minimal changes
├── lib/
│   ├── db.ts                     # Add deleteChat, deleteMessages, updateChatTitle
│   ├── drive.ts                  # Add resolveDriveFiles() for frontend-side resolution
│   └── api.ts                    # existing
```

### Anti-Patterns to Avoid
- **Lifting all state to App.tsx:** Keep session management in AppShell. App.tsx should only handle auth.
- **Re-rendering entire chat list on every message:** Messages are per-session; chat list only needs `last_message_at` updates.
- **Synchronous IndexedDB checks in render:** Always use async effects or callbacks for IndexedDB operations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast notifications | Custom toast component | sonner (already wired) | Rich colors, auto-dismiss, stacking already configured |
| Dropdown menu | Custom positioned dropdown | Radix Popover (already installed) | Handles positioning, focus trap, outside click, keyboard nav |
| Confirmation dialog | Custom modal | shadcn Dialog (already installed) | Accessible, animated, handles escape/overlay click |
| Rate limiting | Custom middleware framework | Simple dict + timestamps in endpoint | In-memory is fine for takehome; no need for Redis/sliding window library |

## Common Pitfalls

### Pitfall 1: Stale Closures in Session Switching
**What goes wrong:** Stream callbacks reference old sessionId after user switches sessions
**Why it happens:** React closures capture state at creation time
**How to avoid:** Already mitigated -- useStream uses `callbacksRef` pattern. Ensure AppShell's abort() is called before switching sessionId
**Warning signs:** Messages appearing in wrong chat after rapid switching

### Pitfall 2: IndexedDB Race Conditions on Delete
**What goes wrong:** Deleting a chat while messages are still being saved from a stream
**Why it happens:** Concurrent IndexedDB transactions on same session
**How to avoid:** Abort stream first, then delete. Use single transaction for chat + messages delete
**Warning signs:** Orphaned messages remaining after chat deletion

### Pitfall 3: Drive API Resolution for Duplicate Detection
**What goes wrong:** Drive API returns folder metadata but not individual file IDs
**Why it happens:** Folder resolution requires listing files (separate API call)
**How to avoid:** For folders, call `https://www.googleapis.com/drive/v3/files?q='${folderId}'+in+parents` from frontend. For single files, the URL itself contains the file ID
**Warning signs:** Duplicate detection only working for single files, not folders

### Pitfall 4: Backend Append vs Overwrite for Multi-Link
**What goes wrong:** Second Drive link overwrites first link's embeddings
**Why it happens:** `save_session` uses `np.save` which overwrites
**How to avoid:** Check if session data exists; if so, load + concatenate before saving
**Warning signs:** Chat losing previously indexed files after pasting a second link

### Pitfall 5: Rate Limit Memory Leak
**What goes wrong:** `_rate_limits` dict grows unbounded over time
**Why it happens:** Old session IDs never cleaned up
**How to avoid:** Prune entries older than RATE_WINDOW on each check, or use a TTL-based approach. For a takehome this is acceptable -- Modal containers restart frequently
**Warning signs:** Memory growth over very long uptimes (unlikely for Modal)

### Pitfall 6: Chat Title Not Set Before Indexing Completes
**What goes wrong:** Sidebar shows "Untitled" or empty title for new chat
**Why it happens:** Chat created with empty title, title only set on indexing complete callback
**How to avoid:** Set initial title to "New Chat" on creation, update to first source name on indexing complete via `updateChatTitle`

## Code Examples

### Three-Dot Menu with Radix Popover
```typescript
// Using existing Popover component from ui/popover.tsx
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MoreVertical, Pencil, Trash2 } from "lucide-react";

function SidebarItemMenu({ onRename, onDelete }: { onRename: () => void; onDelete: () => void }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-muted">
          <MoreVertical className="w-4 h-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-36 p-1" align="start">
        <button onClick={onRename} className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded hover:bg-muted">
          <Pencil className="w-3.5 h-3.5" /> Rename
        </button>
        <button onClick={onDelete} className="flex items-center gap-2 w-full px-2 py-1.5 text-sm rounded hover:bg-muted text-red-600">
          <Trash2 className="w-3.5 h-3.5" /> Delete
        </button>
      </PopoverContent>
    </Popover>
  );
}
```

### Inline Rename in Sidebar
```typescript
function SidebarItem({ chat, isActive, onSelect, onRename }: Props) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(chat.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== chat.title) onRename(trimmed);
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setEditing(false); }}
        onBlur={handleSave}
        className="w-full text-sm px-2 py-1 rounded border"
      />
    );
  }

  return (
    <li onClick={onSelect} className={cn("group flex items-center ...", isActive && "bg-muted")}>
      <span className="truncate flex-1">{chat.title}</span>
      <SidebarItemMenu onRename={() => setEditing(true)} onDelete={...} />
    </li>
  );
}
```

### Delete Confirmation Dialog
```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

function DeleteConfirmDialog({ open, chatTitle, onConfirm, onCancel }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete chat?</DialogTitle>
          <DialogDescription>
            "{chatTitle}" and all its messages will be permanently deleted.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Delete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### Frontend Drive Resolution for Duplicate Detection
```typescript
// lib/drive.ts - add this
export async function resolveDriveFileIds(driveUrl: string, accessToken: string): Promise<string[]> {
  const driveId = extractDriveId(driveUrl);
  if (!driveId) return [];

  // Check if folder or file
  const metaRes = await fetch(
    `https://www.googleapis.com/drive/v3/files/${driveId}?fields=id,mimeType`,
    { headers: { Authorization: `Bearer ${accessToken}` } }
  );
  if (!metaRes.ok) return [];
  const meta = await metaRes.json();

  if (meta.mimeType === "application/vnd.google-apps.folder") {
    // List folder contents
    const listRes = await fetch(
      `https://www.googleapis.com/drive/v3/files?q='${driveId}'+in+parents&fields=files(id)&pageSize=1000`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!listRes.ok) return [];
    const data = await listRes.json();
    return (data.files || []).map((f: { id: string }) => f.id);
  }

  return [driveId];
}
```

### Rate Limiter on Backend
```python
# backend/chat.py - add at module level
import time
from collections import defaultdict

_rate_limits: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(session_id: str) -> bool:
    now = time.time()
    window = [t for t in _rate_limits[session_id] if now - t < 60]
    _rate_limits[session_id] = window
    if len(window) >= 10:
        return True
    _rate_limits[session_id].append(now)
    return False

# In chat_endpoint, before processing:
# if _check_rate_limit(session_id):
#     raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### 429 Handling in useStream
```typescript
// In useStream.ts sendMessage, after fetch:
if (response.status === 429) {
  callbacksRef.current.onError("rate_limited");
  setIsStreaming(false);
  return;
}
```

### Frontend Rate Limit Cooldown in ChatView/AppShell
```typescript
const [rateLimited, setRateLimited] = useState(false);

// In onError callback:
if (message === "rate_limited") {
  toast.error("Too many requests. Please wait a moment.", { duration: 6000 });
  setRateLimited(true);
  setTimeout(() => setRateLimited(false), 10_000);
}

// Pass to ChatInput:
<ChatInput disabled={rateLimited} disabledTooltip="Rate limited — please wait" ... />
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single session per page load | selectedSessionId state | This phase | Major AppShell refactor |
| save_session overwrites | append_session detects + concatenates | This phase | Backend storage change |
| No error differentiation | Color-coded sonner toasts | This phase | All error paths need classification |

## Open Questions

1. **Drive API quota for frontend duplicate resolution**
   - What we know: drive.readonly scope is sufficient, metadata calls are lightweight
   - What's unclear: Whether Google rate-limits metadata queries heavily
   - Recommendation: Proceed -- metadata queries are fast and low-cost; unlikely to hit limits for a takehome

2. **IndexedDB indexed_sources schema**
   - What we know: `Chat.indexed_sources` is currently `string[]` (file IDs)
   - What's unclear: Whether we need file names in indexed_sources for duplicate notice display
   - Recommendation: Consider changing to `Array<{ file_id: string; file_name: string }>` to show "This file is already in chat X" with the file name. This may require an IndexedDB migration (version bump to 2).

3. **Empty state after all chats deleted**
   - What we know: Need some UI when chats list is empty
   - What's unclear: Exact design
   - Recommendation: Show the same Drive link input empty state as a new session, with a "Paste a Drive link to start" prompt. Claude's discretion per CONTEXT.md.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (frontend) | Vitest 4.0.18 + jsdom + @testing-library/react |
| Framework (backend) | pytest + pytest-asyncio + httpx |
| Config file (frontend) | `frontend/vitest.config.ts` |
| Quick run command (frontend) | `cd frontend && pnpm test` |
| Quick run command (backend) | `cd backend && python -m pytest tests/ -x` |
| Full suite command | `cd frontend && pnpm test && cd ../backend && python -m pytest tests/` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-02 | Sidebar loads chats sorted by recency | unit | `cd frontend && pnpm vitest run src/components/app-shell/Sidebar.test.tsx -x` | Wave 0 |
| UI-03 | New Chat button creates IndexedDB record | unit | `cd frontend && pnpm vitest run src/components/app-shell/AppShell.test.tsx -x` | Wave 0 |
| UI-04 | Chat title rename in sidebar | unit | `cd frontend && pnpm vitest run src/components/app-shell/SidebarItem.test.tsx -x` | Wave 0 |
| UI-08 | Error toasts for failure modes | unit | `cd frontend && pnpm vitest run src/components/app-shell/AppShell.test.tsx -x` | Wave 0 |
| UI-09 | 429 response shows toast + disables input | unit | `cd frontend && pnpm vitest run src/hooks/useStream.test.ts -x` | Wave 0 |
| UI-10 | Duplicate notice with actions | unit | `cd frontend && pnpm vitest run src/components/app-shell/DuplicateNotice.test.tsx -x` | Wave 0 |
| INDX-13 | Duplicate detection by file ID | unit | `cd frontend && pnpm vitest run src/lib/db.test.ts -x` | Exists (extend) |
| INDX-14 | Multi-link appends embeddings | unit | `cd backend && python -m pytest tests/test_storage.py -x` | Exists (extend) |
| INFR-03 | Rate limit 10 req/min per session | unit | `cd backend && python -m pytest tests/test_chat_endpoint.py -x` | Exists (extend) |

### Sampling Rate
- **Per task commit:** `cd frontend && pnpm test` or `cd backend && python -m pytest tests/ -x`
- **Per wave merge:** Full suite (both frontend + backend)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/components/app-shell/Sidebar.test.tsx` -- covers UI-02
- [ ] `frontend/src/components/app-shell/SidebarItem.test.tsx` -- covers UI-04
- [ ] `frontend/src/components/app-shell/DuplicateNotice.test.tsx` -- covers UI-10
- [ ] `frontend/src/components/app-shell/AppShell.test.tsx` -- covers UI-03, UI-08
- [ ] Extend `frontend/src/lib/db.test.ts` -- covers deleteChat, updateChatTitle for INDX-13
- [ ] Extend `backend/tests/test_chat_endpoint.py` -- covers rate limiting for INFR-03
- [ ] Extend `backend/tests/test_storage.py` -- covers append logic for INDX-14

## Sources

### Primary (HIGH confidence)
- Codebase analysis: AppShell.tsx, ChatView.tsx, db.ts, ChatInput.tsx, chat.py, index.py, storage.py
- CONTEXT.md: All implementation decisions locked by user

### Secondary (MEDIUM confidence)
- sonner API: `toast.error()`, `toast.warning()` with `duration` option -- verified from existing usage in codebase
- Radix Popover: Already installed and used in CitationPopover.tsx -- same pattern for three-dot menu
- Google Drive REST API v3: `files.get` and `files.list` endpoints for frontend duplicate resolution

### Tertiary (LOW confidence)
- None -- all patterns are verified from existing codebase or locked decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, everything already installed
- Architecture: HIGH - clear from existing code structure and CONTEXT.md decisions
- Pitfalls: HIGH - based on direct codebase analysis of existing patterns

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- no external dependency changes)
