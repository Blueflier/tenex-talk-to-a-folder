---
status: diagnosed
trigger: "Messages and chat sessions disappear when the page is reloaded"
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: indexedFilesMap is ephemeral React state, never persisted or restored; UI gate requires isIndexed=true to render ChatView
test: trace data flow from reload through rendering
expecting: IndexedDB has data but UI never reaches ChatView to load it
next_action: report diagnosis

## Symptoms

expected: After reload, sidebar shows chats and selecting one shows its messages
actual: Sidebar shows chats (loaded from IndexedDB) but main panel shows "Paste a Google Drive link" instead of ChatView with messages
errors: none
reproduction: 1. Index a Drive folder, send messages. 2. Reload page.
started: likely always broken (architectural gap)

## Eliminated

(none needed -- root cause found on first pass)

## Evidence

- timestamp: 2026-03-05
  checked: AppShell.tsx lines 36-44
  found: indexedFilesMap and totalChunksMap are useState<Map> initialized empty; never hydrated from any persistent store on mount
  implication: after reload these maps are always empty

- timestamp: 2026-03-05
  checked: AppShell.tsx lines 292-298
  found: isIndexed = indexedFiles.length > 0; indexedFiles derived from indexedFilesMap which is empty after reload
  implication: isIndexed is always false after reload

- timestamp: 2026-03-05
  checked: AppShell.tsx lines 354-396
  found: rendering is gated on `selectedSessionId && isIndexed`; when isIndexed=false, renders "Paste a Google Drive link" empty state instead of ChatView
  implication: ChatView (which loads messages from IndexedDB) is never mounted after reload

- timestamp: 2026-03-05
  checked: Chat interface in db.ts
  found: Chat has indexed_sources string[] field, saved to IndexedDB
  implication: indexed source file IDs ARE persisted in IndexedDB but never used to reconstruct indexedFilesMap

- timestamp: 2026-03-05
  checked: AppShell.tsx lines 62-78
  found: useEffect loads chats from IndexedDB on mount (getChats), but only sets chats and selectedSessionId; does NOT populate indexedFilesMap or totalChunksMap
  implication: the hydration step that would bridge persisted data to the rendering gate is completely missing

- timestamp: 2026-03-05
  checked: handleIndexComplete (lines 221-266)
  found: indexedFilesMap entries contain file_id, file_name, indexed_at; Chat.indexed_sources only stores file_id strings
  implication: even if hydration were added, file_name and indexed_at are not persisted -- would need schema change or separate store

- timestamp: 2026-03-05
  checked: App.tsx line 10
  found: token stored in sessionStorage (survives same-tab reload, lost on new tab)
  implication: auth state is a secondary issue for new-tab scenarios but not the primary cause for same-tab reload

## Resolution

root_cause: |
  The `indexedFilesMap` (Map<string, IndexedFile[]>) in AppShell is pure React state,
  populated only by `handleIndexComplete` after indexing finishes. It is NEVER hydrated
  from IndexedDB on page load. The rendering gate at line 354 requires `isIndexed` to
  be true (derived from indexedFilesMap) to mount ChatView. After reload, indexedFilesMap
  is empty, so isIndexed=false, and the app shows the "Paste a Google Drive link" empty
  state instead of ChatView -- even though chats and messages ARE persisted in IndexedDB.

  Secondary issue: Chat.indexed_sources only stores file_id strings. The IndexedFile
  objects (with file_name and indexed_at) needed by indexedFilesMap are never persisted
  anywhere, so even adding hydration would require storing more data.

fix: (not applied -- diagnosis only)
verification: (not applied)
files_changed: []
