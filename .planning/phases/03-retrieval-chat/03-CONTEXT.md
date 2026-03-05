# Phase 3: Retrieval + Chat - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

User asks questions about indexed files and receives streaming answers with exact file/page/passage citations. Covers cosine similarity retrieval, streaming LLM responses via fetch + ReadableStream, inline [N] citations with clickable popovers, citation metadata frozen on each message (stored to IndexedDB), and read-only access to old chats without auth. Staleness detection, hybrid retrieval, multi-session sidebar, and duplicate detection are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Citation click behavior
- Popover appears near the clicked [N] citation showing file name, page/row, and passage text
- Popover dismisses on click-outside
- Citation numbers rendered as colored badge/links (blue, hover underline) — clear clickable affordance
- Passage text truncated to ~200 chars with a "Show more" link to expand full chunk
- Compact citation summary footer below each assistant message listing all sources used (e.g., "Sources: report.pdf p.7, data.csv row 12")

### Chat message styling
- Full-width, left-aligned layout like ChatGPT/Claude — standard AI chat app conventions
- Streaming renders token-by-token with a blinking cursor at the end
- Citation [N] badges render once the citation text is fully streamed
- Expandable textarea for input: starts single-line, grows as user types, Shift+Enter for newlines, Enter to send
- Input disabled during streaming with a "Stop generating" button

### No-results handling
- Cosine similarity threshold at 0.3 — if all top-k chunks score below, skip LLM call entirely
- Backend sends a special `{ type: "no_results" }` SSE event (not regular tokens)
- Frontend renders in muted/italic style with message: "I couldn't find relevant information in the provided files. Try rephrasing your question or check if the right files were indexed."

### Pre-chat empty state
- After indexing completes, show file count header ("3 files indexed") + 3-4 clickable question suggestions
- Suggestions generated from file names using simple templates (e.g., "Summarize [filename]", "What are the key points in [filename]?") — no LLM call
- Clicking a suggestion auto-fills the input
- Suggestions disappear after user sends their first question

### Claude's Discretion
- Exact chat message visual differentiation (icons, background colors, spacing)
- Popover positioning and animation
- Stop generating button placement and styling
- Streaming cursor implementation details
- Citation badge exact color and size
- Suggestion card styling

</decisions>

<specifics>
## Specific Ideas

- "It should be like any other chatbot app like ChatGPT or Claude" — standard AI chat conventions, nothing exotic
- The spec is highly prescriptive with code samples for retrieval (cosine_sim, retrieve functions), chat prompt (build_prompt), SSE event format, and useStream hook — implementation should follow spec closely

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, Phase 1 and 2 code will be built first

### Established Patterns
- shadcn/ui + Radix + Tailwind CSS (decided in Phase 1)
- IndexedDB for local persistence with chats and messages stores (Phase 1)
- Google Identity Services Token Client flow (Phase 1)
- Modal + FastAPI backend with Volume storage (Phase 1)
- SSE streaming pattern established in Phase 2 (indexing progress)

### Integration Points
- Embeddings (.npy) and chunks (.json) from Phase 2's indexing pipeline on Modal Volume
- IndexedDB messages store (PERS-02) for storing citations on messages
- Token from sessionStorage for auth header on /chat requests
- SSE streaming infrastructure from Phase 2 can be reused/adapted for chat streaming

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-retrieval-chat*
*Context gathered: 2026-03-05*
