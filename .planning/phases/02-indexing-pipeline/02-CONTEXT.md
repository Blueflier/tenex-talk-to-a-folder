# Phase 2: Indexing Pipeline - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

User can paste a Google Drive link (folder or single file) and watch files get extracted, chunked, and embedded with two-phase progress feedback. Covers Drive link resolution, per-type file extraction, type-specific chunking, batch embedding via OpenAI, Modal Volume storage, and SSE progress streaming. No retrieval, no chat, no staleness detection.

</domain>

<decisions>
## Implementation Decisions

### Progress & file cards
- Minimal list layout during extraction: file icon + name + status badge (extracting/done/skipped/queued)
- Unsupported files collapsed into a summary line at bottom: "3 files skipped (unsupported types)" with expand option
- Single progress bar for embedding phase: "Embedding chunks... 200/312 chunks"
- Indexing progress shown in an overlay/modal, not inline in chat

### Partial failure handling
- Best-effort approach: continue indexing whatever succeeds, warn about failures
- Failed files shown inline in the file list with red status and error reason
- Per-file status granularity when embedding fails after retries (show which files are fully/partially/not indexed)
- Drive link validation happens immediately before opening the modal (inline error near input for invalid/inaccessible links)
- Empty folders vs no-supported-files get distinct error messages (toast + empty chat for both, different wording)
- Cancel button available during indexing; cancellation discards all partial data (clean slate)
- Soft file size limit with warning (e.g., 50MB) but still processes large files
- Embedding failure: retry batch 2-3 times, then save what was embedded and let user chat with partial index

### Indexing completion
- Modal auto-dismisses after brief success state (~1-2s showing "Indexed 8 files (312 chunks)")
- Chat header shows persistent summary: "8 files indexed - 312 chunks"
- Context-aware chat input placeholder: "Ask about Q3-Report.pdf, Budget.xlsx, and 6 more..."
- Chat title deferred to Phase 5 (use generic "New Chat" for now)
- Zero successful files: toast notification with error, land on empty chat explaining what happened

### Claude's Discretion
- Exact modal design and animations within shadcn/ui conventions
- Status badge styling and colors
- Progress bar component choice
- Success state animation/transition timing
- File icon selection by type
- Soft size limit threshold (suggested ~50MB)
- Retry timing and backoff strategy for embedding failures
- Toast notification styling and duration

</decisions>

<specifics>
## Specific Ideas

- The spec is extremely prescriptive with code samples for chunking (recursive 1200/150), embedding (text-embedding-3-small, batches of 100), storage (npy + json on Modal Volume), and SSE event shapes. Follow spec closely.
- File cards render after extraction phase, before embedding starts (user sees what was found before waiting for embeddings)
- Chat input locked until indexing completes

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet - greenfield project. Phase 1 establishes the foundation (Modal + FastAPI, React + Vite shell, shadcn/ui, IndexedDB stores)

### Established Patterns
- Phase 1 establishes: shadcn/ui component conventions, Google Identity Services Token Client flow, Modal Volume mount at /data, IndexedDB schema for chats/messages stores
- Spec provides code samples for: recursive_chunk(), chunk_pdf(), chunk_sheet(), chunk_slides(), embed_chunks(), save_session(), SSE event format

### Integration Points
- POST /index endpoint receives { drive_url, access_token }, streams SSE progress
- IndexedDB chats store: indexed_sources[] array with file_id, file_name, indexed_at per file
- Modal Volume path: /data/{user_id}/{session_id}_embeddings.npy + _chunks.json
- Google Drive API for link resolution and file export (uses access_token from Phase 1 auth)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 02-indexing-pipeline*
*Context gathered: 2026-03-05*
