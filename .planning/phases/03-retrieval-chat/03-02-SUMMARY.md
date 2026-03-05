---
phase: 03-retrieval-chat
plan: 02
subsystem: ui
tags: [react, streaming, sse, citations, radix, react-markdown, shadcn]

requires:
  - phase: 01-foundation-auth
    provides: shadcn/ui setup, IndexedDB persistence layer, api fetch pattern
provides:
  - useStream hook for SSE fetch + ReadableStream parsing
  - Citation interface and formatCitationLabel helper
  - Complete chat component tree (9 components)
  - useAutoResize hook for textarea auto-grow
affects: [03-retrieval-chat, 04-staleness-hybrid-retrieval]

tech-stack:
  added: [react-markdown, @radix-ui/react-popover]
  patterns: [SSE stream parsing with line buffering, citation-aware markdown rendering, streaming vs complete message rendering split]

key-files:
  created:
    - frontend/src/hooks/useStream.ts
    - frontend/src/hooks/useAutoResize.ts
    - frontend/src/lib/citations.ts
    - frontend/src/components/chat/ChatView.tsx
    - frontend/src/components/chat/MessageList.tsx
    - frontend/src/components/chat/ChatMessage.tsx
    - frontend/src/components/chat/CitationBadge.tsx
    - frontend/src/components/chat/CitationPopover.tsx
    - frontend/src/components/chat/CitationFooter.tsx
    - frontend/src/components/chat/ChatInput.tsx
    - frontend/src/components/chat/StreamingCursor.tsx
    - frontend/src/components/chat/NoResultsMessage.tsx
    - frontend/src/components/ui/popover.tsx
    - frontend/src/components/ui/textarea.tsx
    - frontend/src/components/ui/avatar.tsx
  modified:
    - frontend/src/index.css
    - frontend/package.json

key-decisions:
  - "Citation badges render only after streaming completes to avoid flicker from partial [ characters"
  - "CitationPopover uses fixed positioning anchored to badge element for scroll-safe placement"
  - "useStream uses ref-stable callbacks to avoid stale closure issues during streaming"

patterns-established:
  - "SSE parsing: buffer incomplete lines across reads, split on newline, keep last fragment"
  - "Citation rendering: split content on /([N])/g, render badges for complete patterns only"
  - "Streaming state: isStreaming flag on message controls raw text vs citation-aware rendering"

requirements-completed: [CHAT-01, CHAT-02, UI-07]

duration: 3min
completed: 2026-03-05
---

# Phase 3 Plan 2: Chat UI with Streaming + Citations Summary

**ChatGPT-style chat UI with SSE streaming hook, inline citation badges/popovers, and expandable textarea input**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T22:06:53Z
- **Completed:** 2026-03-05T22:09:52Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- useStream hook with proper SSE line buffering, abort support, and all event type handling
- Complete chat component tree: ChatView, MessageList, ChatMessage, CitationBadge, CitationPopover, CitationFooter, ChatInput, StreamingCursor, NoResultsMessage
- Citation badges render as clickable blue pills that open Radix popovers with file/page/passage details
- Chat input with Enter/Shift+Enter handling and stop generating button during streaming

## Task Commits

Each task was committed atomically:

1. **Task 1: useStream hook, citation types, and shadcn setup** - `b3e6082` (feat)
2. **Task 2: Chat component tree** - `0494e8c` (feat)

## Files Created/Modified
- `frontend/src/hooks/useStream.ts` - SSE fetch + ReadableStream parsing with line buffering and abort
- `frontend/src/hooks/useAutoResize.ts` - Textarea auto-grow hook with 200px max height
- `frontend/src/lib/citations.ts` - Citation interface and formatCitationLabel helper
- `frontend/src/components/chat/ChatView.tsx` - Main container integrating useStream with message state
- `frontend/src/components/chat/MessageList.tsx` - Scrollable message area with auto-scroll
- `frontend/src/components/chat/ChatMessage.tsx` - User/assistant message with citation-aware markdown
- `frontend/src/components/chat/CitationBadge.tsx` - Inline clickable blue badge for [N] citations
- `frontend/src/components/chat/CitationPopover.tsx` - Radix popover with file/page/passage and Show more
- `frontend/src/components/chat/CitationFooter.tsx` - Compact source summary below assistant messages
- `frontend/src/components/chat/ChatInput.tsx` - Expandable textarea with send/stop buttons
- `frontend/src/components/chat/StreamingCursor.tsx` - Blinking cursor during active stream
- `frontend/src/components/chat/NoResultsMessage.tsx` - Muted italic no-results fallback
- `frontend/src/components/ui/popover.tsx` - shadcn Popover component
- `frontend/src/components/ui/textarea.tsx` - shadcn Textarea component
- `frontend/src/components/ui/avatar.tsx` - shadcn Avatar component
- `frontend/src/index.css` - Added blink keyframes animation

## Decisions Made
- Citation badges render only after streaming completes to avoid flicker from partial `[` characters (per Research pitfall #2)
- CitationPopover uses fixed positioning anchored to badge element for scroll-safe placement
- useStream callbacks stored in ref to prevent stale closures during streaming
- New AbortController created per request to prevent stale controller issues (per Research pitfall #4)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved misplaced shadcn components from frontend/@ to frontend/src/**
- **Found during:** Task 1 (shadcn setup)
- **Issue:** shadcn CLI resolved `@/` alias literally and placed files in `frontend/@/components/ui/` instead of `frontend/src/components/ui/`
- **Fix:** Manually copied files to correct location and removed the erroneous `@/` directory
- **Files modified:** frontend/src/components/ui/popover.tsx, textarea.tsx, avatar.tsx
- **Verification:** tsc --noEmit passes, imports resolve correctly
- **Committed in:** b3e6082 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor path issue with shadcn CLI. No scope creep.

## Issues Encountered
None beyond the shadcn path issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Chat component tree ready to wire to backend /chat endpoint and IndexedDB persistence
- useStream hook ready for integration with actual SSE backend
- Citation rendering pattern established for reuse in staleness/hybrid retrieval phase

## Self-Check: PASSED

All 15 created files verified present. Both task commits (b3e6082, 0494e8c) verified in git log. TypeScript compilation clean.

---
*Phase: 03-retrieval-chat*
*Completed: 2026-03-05*
