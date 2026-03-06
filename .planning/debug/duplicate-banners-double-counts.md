---
status: diagnosed
trigger: "Two identical yellow staleness banners for same file. React key collision in StalenessBannerList.tsx:19. UI shows 4 files indexed 12 chunks when only 2 files and 6 chunks."
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: Two separate bugs with the same root pattern -- accumulation instead of replacement
test: Code reading and tracing data flow
expecting: Confirm both issues stem from append-style state updates
next_action: Report diagnosis

## Symptoms

expected: One staleness banner per stale file; correct file/chunk counts matching actual indexed data
actual: Two identical yellow banners for same file; "4 files indexed -- 12 chunks" when only 2 files and 6 chunks
errors: React key collision warning at StalenessBannerList.tsx:19 (duplicate key from duplicate file_id)
reproduction: Index files, trigger staleness, observe duplicate banners and doubled counts
started: Phase 04 staleness + hybrid retrieval

## Eliminated

(none)

## Evidence

- timestamp: 2026-03-05T00:01:00Z
  checked: StalenessBannerList.tsx key prop
  found: Uses `key={info.file_id}` which is correct IF the array has unique file_ids; React key collision means the staleFiles array contains duplicate entries with the same file_id
  implication: The problem is upstream -- the staleFiles array itself has duplicates

- timestamp: 2026-03-05T00:02:00Z
  checked: useStream.ts staleness handling (line 118-123)
  found: On "staleness" SSE event, it does `currentStaleFilesRef.current = event.files` (full replacement) and calls `onStaleness?.(event.files)` -- this is a clean replace, NOT accumulation
  implication: useStream itself does not accumulate duplicates; the SSE event would need to contain duplicates, OR the problem is in how ChatView wires it

- timestamp: 2026-03-05T00:03:00Z
  checked: ChatView.tsx onStaleness callback (line 102-111)
  found: `onStaleness(files)` replaces `pendingStaleFilesRef.current = files` and does `{ ...last, staleFiles: files }` -- this is also a clean replace
  implication: The staleness SSE event from the backend contains duplicate entries, OR the backend sends multiple staleness events per chat request and the last one is the one that sticks (which would be fine). Need to check backend.

- timestamp: 2026-03-05T00:04:00Z
  checked: backend/chat.py _chat_event_stream staleness emission (lines 176-186)
  found: Iterates `file_list` and includes any file whose `file_id in stale_ids`. The `file_list` comes directly from the frontend request body (`body.get("file_list")`). If `file_list` itself has duplicate entries, the staleness event will too.
  implication: Root cause for banners is likely that `file_list` sent from frontend contains duplicate file entries

- timestamp: 2026-03-05T00:05:00Z
  checked: AppShell.tsx handleIndexComplete (lines 221-266) -- how indexedFilesMap is built
  found: "SMOKING GUN" -- Line 233-237: `const existing = next.get(selectedSessionId) || []; next.set(selectedSessionId, [...existing, ...result.indexedSources]);` This APPENDS new indexed sources to existing ones. If the user indexes the same Drive link twice (or the effect re-runs), the indexedFilesMap will contain duplicate file entries.
  implication: This is the root cause of BOTH bugs. The append pattern means re-indexing the same files doubles the entries.

- timestamp: 2026-03-05T00:06:00Z
  checked: AppShell.tsx totalChunksMap update (lines 239-244)
  found: Same pattern: `const existing = next.get(selectedSessionId) || 0; next.set(selectedSessionId, existing + result.totalChunks);` This ADDS chunk counts. Re-indexing same files doubles the count.
  implication: Confirms both bugs share the same root cause -- accumulative state updates in handleIndexComplete

- timestamp: 2026-03-05T00:07:00Z
  checked: AppShell.tsx line 300 -- how fileList is derived and sent to ChatView
  found: `const fileList = indexedFiles.map(...)` -- if indexedFiles has duplicates, fileList has duplicates, which gets passed to ChatView, which sends it in the /chat request body, which causes backend to emit staleness events with duplicates
  implication: Confirms the full chain: duplicate indexedFiles -> duplicate fileList -> duplicate staleness SSE -> duplicate banners + React key collision

- timestamp: 2026-03-05T00:08:00Z
  checked: IndexingModal.tsx useEffect dependency array (line 209)
  found: Dependencies include `[open, driveUrl, sessionId, token, onComplete, onError, reset]`. If `onComplete` or `onError` change identity between renders (they are useCallbacks but onComplete depends on selectedSessionId), the effect could re-run, causing a second indexing stream and thus a second onComplete call. This is a likely trigger for the double-append.
  implication: The useEffect re-firing is a plausible trigger, but even without it, the append-without-dedup pattern is fundamentally broken for any re-index scenario.

## Resolution

root_cause: |
  TWO related bugs, ONE root cause in AppShell.tsx `handleIndexComplete`:

  1. **DUPLICATE BANNERS (React key collision):** `handleIndexComplete` appends to `indexedFilesMap` without deduplication (line 236: `[...existing, ...result.indexedSources]`). When indexing completes (potentially called twice due to useEffect re-firing in IndexingModal), the same files are appended again. This doubled `indexedFiles` array flows to `fileList` prop -> ChatView -> /chat request body -> backend staleness check -> staleness SSE event with duplicate file entries -> StalenessBannerList renders two banners with the same `file_id` key -> React key collision warning.

  2. **DOUBLED COUNTS ("4 files indexed -- 12 chunks"):** Same function additively accumulates `totalChunksMap` (line 242: `existing + result.totalChunks`). A second call doubles the count from 6 to 12 chunks, and `indexedFiles.length` goes from 2 to 4.

  **Trigger:** The IndexingModal useEffect has `onComplete` in its dependency array. Since `onComplete` is `handleIndexComplete` wrapped in useCallback with `[selectedSessionId]` dependency, if selectedSessionId changes or the component re-renders with a new callback identity, the effect re-runs, re-streams the indexing endpoint, and calls onComplete a second time -- doubling everything.

fix: (not applied -- diagnosis only)
verification: (not applicable)
files_changed: []
