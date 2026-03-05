# Phase 4: Staleness + Hybrid Retrieval - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Users always get answers from the latest file content. On each /chat request, backend checks Drive modifiedTime against indexed_at for all session files. Stale files are routed to grep_live (LLM keyword extraction + regex search over re-fetched content). Fresh files use pre-computed cosine similarity. Users see staleness warnings and can per-file re-index. No new indexing flow, no UI chrome changes, no multi-session work -- just staleness detection, hybrid retrieval routing, and per-file re-indexing.

</domain>

<decisions>
## Implementation Decisions

### Re-index feedback flow
- Inline spinner on the "Re-index this file" button -- text changes to "Re-indexing..." with spinner
- Chat input field stays visible but send button disabled with tooltip "Re-indexing in progress"
- User can still scroll and read history during re-index
- On success: yellow staleness banner transitions to green "Re-indexed successfully" toast that auto-dismisses after 3 seconds
- Previous grep-based answer stays visible -- user can re-ask for embedding-based answer
- Each stale file's banner and re-index button are independent -- re-indexing one file doesn't affect others

### Staleness banner behavior
- Yellow banner appears ABOVE the assistant's streaming response (before answer tokens)
- One banner per stale file, each with its own "Re-index this file" button
- Banners re-appear on every response that used grep_live for that file (not just first occurrence)
- All stale banners retain active re-index buttons regardless of message age (scrolling up)
- Banner text: "[warning icon] {filename} was modified after indexing -- showing live search results for this file."

### grep_live edge case messaging
- 0 grep matches: banner gets extra line "No matches found -- re-index for best results" with re-index button
- File deleted (404 on metadata): red banner "This file no longer exists in Google Drive. Old answers from this file may be outdated." No re-index button
- File access revoked (403 on metadata): orange/amber banner "Access to {filename} was revoked. Check your Google Drive permissions." with "Re-authenticate" button
- Deleted files: still use old embeddings for retrieval (data was valid when indexed), citations show "(deleted)" suffix

### Staleness/grep caching
- Implement both caches in Phase 4 (not deferred):
  - Staleness check cache: in-memory dict, 60-second TTL per file_id
  - grep_live text cache: in-memory dict, 5-minute TTL per file_id
- Both caches are in-memory only (per container, lost on cold start) -- acceptable for takehome
- Cache invalidation: when user re-indexes a file, clear both its staleness cache and grep text cache entries immediately

### Parallelism
- Staleness check and query embedding run in parallel via asyncio.gather (both I/O-bound)
- grep_live across multiple stale files runs in parallel via asyncio.gather
- Keyword extraction (single LLM call) runs before grep_live calls (shared keyword list across all stale files, per spec)

### Claude's Discretion
- In-memory cache implementation details (dict structure, cleanup strategy)
- Banner component styling within shadcn/ui conventions
- Exact spinner/loading animation for re-index button
- Error handling for partial grep_live failures in parallel execution

</decisions>

<specifics>
## Specific Ideas

- Spec provides complete code samples for: check_staleness(), grep_live(), extract_keywords(), chat() routing, reindex_file(), and the /reindex endpoint -- follow closely
- Three distinct banner colors for three states: yellow (stale), red (deleted), orange (access revoked)
- The "staleness drives routing, not the LLM" principle is the key differentiator vs Perplexity -- emphasize in implementation

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet -- greenfield project, no code exists (Phase 1 not yet built)

### Established Patterns
- None yet -- Phase 1 establishes patterns, Phases 2-3 build the indexing/retrieval this phase modifies

### Integration Points
- Modifies the /chat endpoint (Phase 3) to add staleness check before retrieval
- Adds /reindex endpoint (new)
- Frontend: new staleness banner component, modifications to chat message rendering, chat input disable logic
- IndexedDB: indexed_sources[].indexed_at field used for staleness comparison
- Modal Volume: reindex_file() loads/saves session embeddings (same as Phase 2 writes)

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-staleness-hybrid-retrieval*
*Context gathered: 2026-03-05*
