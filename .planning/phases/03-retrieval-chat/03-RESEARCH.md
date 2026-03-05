# Phase 3: Retrieval + Chat - Research

**Researched:** 2026-03-05
**Domain:** Cosine similarity retrieval, SSE streaming chat, citation rendering, IndexedDB persistence
**Confidence:** HIGH

## Summary

Phase 3 connects the indexing pipeline (Phase 2) to a chat interface. The backend loads embeddings + chunks from Modal Volume, embeds the user query, performs cosine similarity retrieval, builds a prompt with numbered sources, and streams the LLM response token-by-token via SSE. The frontend renders a standard ChatGPT-style chat UI with streaming text, inline [N] citation badges, citation popovers, and persists everything to IndexedDB.

The spec provides complete code samples for every major component: `cosine_sim`, `retrieve`, `build_prompt`, the `/chat` SSE endpoint, and the `useStream` hook. Implementation should follow these samples closely. The main engineering challenges are: (1) correctly parsing SSE events from a POST fetch stream, (2) rendering citation badges inline in markdown-like text, (3) freezing citation metadata on messages for IndexedDB persistence, and (4) handling the no-auth read-only mode for old chats.

**Primary recommendation:** Follow the spec's code samples directly. The `useStream` hook, `/chat` endpoint, and retrieval functions are fully specified. Focus implementation effort on the citation popover UX and the streaming cursor rendering, which are design decisions rather than algorithmic ones.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Citation click behavior: Popover near clicked [N] showing file name, page/row, passage text. Dismiss on click-outside. Colored badge/links (blue, hover underline). Passage truncated ~200 chars with "Show more". Compact citation summary footer below each assistant message.
- Chat message styling: Full-width left-aligned like ChatGPT/Claude. Streaming renders token-by-token with blinking cursor. Citation [N] badges render once citation text fully streamed. Expandable textarea input (starts single-line, grows), Shift+Enter newlines, Enter sends. Input disabled during streaming with "Stop generating" button.
- No-results handling: Cosine similarity threshold at 0.3. If all top-k below threshold, skip LLM call. Backend sends `{ type: "no_results" }` SSE event. Frontend renders muted/italic message.
- Pre-chat empty state: File count header + 3-4 clickable suggestion cards generated from file names (no LLM call). Clicking auto-fills input. Suggestions disappear after first question.

### Claude's Discretion
- Exact chat message visual differentiation (icons, background colors, spacing)
- Popover positioning and animation
- Stop generating button placement and styling
- Streaming cursor implementation details
- Citation badge exact color and size
- Suggestion card styling

### Deferred Ideas (OUT OF SCOPE)
None

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RETR-01 | Query embedded and compared via cosine similarity against session embeddings | Spec provides `cosine_sim` and `retrieve` functions; numpy dot product + argsort |
| RETR-02 | Top-8 chunks returned for docs, top-5 for sheets | `retrieve` function with configurable `top_k`; determine k based on chunk mime_type |
| CHAT-01 | SSE streaming response via fetch + ReadableStream (POST /chat) | Spec provides full `/chat` endpoint with `StreamingResponse` and `useStream` hook |
| CHAT-02 | Inline [N] citations in LLM responses pointing to source file, page, and passage | System prompt instructs model to cite as [1], [2]; citations event sent after stream |
| CHAT-03 | Citation metadata frozen on message at answer time (survives file changes) | Citations stored on IndexedDB message record with chunk_text snapshot |
| CHAT-04 | System prompt constrains LLM to answer only from provided sources | `build_prompt` function with strict "Answer using ONLY the sources below" constraint |
| CHAT-06 | Citations event sent after stream completes, stored to IndexedDB on message | `{ type: "citations", citations: [...] }` SSE event emitted after all tokens |
| UI-07 | Citation rendering: PDF as "file.pdf, p.7", Sheet as "file.csv, row 12", Slides as "deck, slide 3" | Chunk metadata schema includes page_number, row_number, slide_index |
| PERS-04 | Old chats readable without auth; new messages require valid token | IndexedDB loads without server; /chat requires Authorization header |

</phase_requirements>

## Standard Stack

### Core -- Backend (additions to Phase 1/2 stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | latest | Cosine similarity computation | Already installed; `np.dot` + `np.linalg.norm` for vector ops |
| openai | latest | Query embedding + LLM streaming | AsyncOpenAI for both embedding and chat completion streaming |

### Core -- Frontend (additions to Phase 1/2 stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-markdown | 9.x | Render assistant messages as markdown | LLM output contains markdown formatting; need custom renderers for citations |

### Supporting -- Frontend
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @radix-ui/react-popover | latest | Citation click popovers | Accessible popover with click-outside dismiss, already in shadcn ecosystem |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-markdown | dangerouslySetInnerHTML | No XSS protection, no custom component mapping for citations |
| Radix Popover | Custom popover div | Would need manual focus trap, click-outside, positioning logic |
| fetch+ReadableStream | Vercel AI SDK useChat | SDK expects specific format; our custom events (no_results, citations) don't fit |

**Additional shadcn components to add:**
```bash
pnpm dlx shadcn@latest add popover textarea avatar
```

## Architecture Patterns

### Backend: /chat Endpoint Flow
```
POST /chat { session_id, query, file_list }
  1. Verify access_token -> get user_id
  2. Load embeddings.npy + chunks.json from Volume
  3. Embed query via OpenAI text-embedding-3-small
  4. Cosine similarity -> top-k chunks
  5. Check threshold (0.3) -> if all below, emit no_results event
  6. build_prompt(query, retrieved_chunks) -> system prompt
  7. Stream LLM response token-by-token as SSE events
  8. Emit citations event after stream completes
  9. Emit [DONE]
```

### SSE Event Types for /chat
```
{ "type": "token",      "content": "The " }         -> append to message
{ "type": "citations",  "citations": [...] }         -> store to IndexedDB
{ "type": "no_results" }                             -> skip LLM, show muted message
{ "type": "error",      "message": "..." }           -> inline error
[DONE]                                               -> stream complete
```

Note: `staleness` and `staleness warning` events are Phase 4 scope. Phase 3 treats all chunks as fresh.

### Frontend Component Structure
```
src/
  components/
    chat/
      ChatView.tsx          # Main chat container
      MessageList.tsx       # Scrollable message area
      ChatMessage.tsx       # Single message (user or assistant)
      CitationBadge.tsx     # Inline [N] rendered as clickable badge
      CitationPopover.tsx   # Popover with file/page/passage details
      CitationFooter.tsx    # Compact source summary below assistant message
      ChatInput.tsx         # Expandable textarea with send/stop buttons
      EmptyState.tsx        # Pre-chat suggestions
      NoResultsMessage.tsx  # Muted "no relevant info" message
      StreamingCursor.tsx   # Blinking cursor during streaming
  hooks/
    useStream.ts            # SSE fetch + ReadableStream parsing
    useAutoResize.ts        # Textarea auto-grow logic
  lib/
    db.ts                   # IndexedDB operations (from Phase 1)
    citations.ts            # Citation formatting helpers
```

### Pattern 1: SSE Stream Parsing with fetch
**What:** POST to /chat, read response body as stream, parse SSE lines
**When to use:** Every chat message send
**Example:**
```typescript
// Source: spec.md useStream hook
const response = await fetch(`${MODAL_URL}/chat`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${accessToken}`,
  },
  body: JSON.stringify({ session_id: sessionId, query, file_list: fileList }),
  signal: abortController.signal,
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n");
  buffer = lines.pop() || ""; // keep incomplete line in buffer

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const raw = line.slice(6).trim();
    if (raw === "[DONE]") break;
    const event = JSON.parse(raw);
    // handle event.type: "token", "citations", "no_results", "error"
  }
}
```

### Pattern 2: Citation Rendering in Markdown
**What:** Parse [N] patterns in assistant text and render as clickable badges
**When to use:** Rendering every assistant message
**Example:**
```typescript
// Split text on citation patterns, render badges inline
function renderContentWithCitations(
  content: string,
  citations: Citation[],
  onCitationClick: (index: number, anchorEl: HTMLElement) => void
) {
  // Regex to match [1], [2], etc.
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const idx = parseInt(match[1]);
      return <CitationBadge key={i} index={idx} onClick={onCitationClick} />;
    }
    // Render non-citation text as markdown
    return <ReactMarkdown key={i}>{part}</ReactMarkdown>;
  });
}
```

### Pattern 3: Cosine Similarity Retrieval (Backend)
**What:** Embed query, compute similarity, return top-k
**When to use:** Every /chat request
**Example:**
```python
# Source: spec.md
def cosine_sim(query_vec, embeddings):
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
    return np.dot(embeddings, query_vec) / (norms + 1e-9)

def retrieve(query_embedding, chunks, embeddings, top_k=8):
    scores = cosine_sim(query_embedding, embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]

# Threshold check (from CONTEXT.md decision)
SIMILARITY_THRESHOLD = 0.3
results = retrieve(query_vec, chunks, embeddings, top_k=8)
if all(score < SIMILARITY_THRESHOLD for _, score in results):
    # Emit no_results event, skip LLM call
    yield f'data: {json.dumps({"type": "no_results"})}\n\n'
    yield 'data: [DONE]\n\n'
    return
```

### Pattern 4: Top-k Selection by File Type
**What:** Use top_k=8 for docs, top_k=5 for sheets
**When to use:** When session contains mixed file types
**Example:**
```python
# Determine top_k based on chunk composition
sheet_mime = "application/vnd.google-apps.spreadsheet"
has_sheets = any(c["mime_type"] == sheet_mime for c in chunks)
has_docs = any(c["mime_type"] != sheet_mime for c in chunks)

# If mixed: retrieve from both pools separately
if has_sheets and has_docs:
    doc_chunks = [(i, c) for i, c in enumerate(chunks) if c["mime_type"] != sheet_mime]
    sheet_chunks = [(i, c) for i, c in enumerate(chunks) if c["mime_type"] == sheet_mime]
    # Retrieve top-8 from docs, top-5 from sheets, merge by score
else:
    top_k = 5 if has_sheets else 8
    results = retrieve(query_vec, chunks, embeddings, top_k)
```

### Anti-Patterns to Avoid
- **Storing citations by reference, not by value:** Citations must snapshot the chunk_text at answer time. If you store only chunk_index, the citation breaks when files are re-indexed.
- **Parsing SSE without buffering:** ReadableStream chunks may split mid-line. Always buffer incomplete lines across reads.
- **Using EventSource for POST:** EventSource is GET-only. The spec explicitly requires fetch + ReadableStream.
- **Re-deriving citations on render:** Citations are frozen on the message. Never re-fetch or re-compute them from current embeddings.
- **Rendering [N] badges during streaming:** Badge should only appear once the full citation text `[N]` is streamed (all characters received). Partial `[` should render as text.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Popover positioning | Manual absolute positioning + scroll logic | Radix Popover (via shadcn) | Handles viewport overflow, scroll containers, focus management |
| Markdown rendering | Regex-based text formatting | react-markdown | XSS-safe, extensible with custom components for citation injection |
| Click-outside dismiss | Manual document click listeners | Radix Popover built-in | Handles portal rendering, nested click events correctly |
| Textarea auto-resize | Manual scrollHeight measurement | CSS `field-sizing: content` or a small hook | Browser-native approach avoids layout thrash |

**Key insight:** The chat UI looks simple but has many edge cases around streaming state, citation parsing during partial updates, and popover positioning in scrolling containers. Use Radix primitives for all interactive overlays.

## Common Pitfalls

### Pitfall 1: SSE Buffer Splitting
**What goes wrong:** ReadableStream delivers chunks at arbitrary byte boundaries. A single SSE line like `data: {"type":"token","content":"hello"}` may arrive split across two reads.
**Why it happens:** Network/TCP packet boundaries don't align with SSE message boundaries.
**How to avoid:** Buffer incomplete lines: accumulate text until you see `\n`, only process complete lines.
**Warning signs:** Intermittent JSON.parse errors during streaming.

### Pitfall 2: Citation Badge Rendering During Streaming
**What goes wrong:** During streaming, partial text like `[` appears momentarily as a badge or garbled rendering before the full `[1]` arrives.
**Why it happens:** Rendering citations on every token update without waiting for complete pattern.
**How to avoid:** Only render citation badges after streaming completes, or use a regex that only matches complete `[N]` patterns and treats incomplete `[` as plain text.
**Warning signs:** Flickering badges during streaming, or `[` characters appearing and disappearing.

### Pitfall 3: IndexedDB Write Timing
**What goes wrong:** User closes tab during streaming; partial message is lost because IndexedDB write happens only after stream completes.
**Why it happens:** The spec writes the final message to IndexedDB only after `[DONE]`.
**How to avoid:** Accept this tradeoff for Phase 3 -- the spec pattern is correct. A production improvement would periodically flush partial content.
**Warning signs:** None during normal use; only on unexpected tab close.

### Pitfall 4: Abort Controller Cleanup
**What goes wrong:** "Stop generating" button is clicked but stream continues, or subsequent messages get cancelled by a stale abort controller.
**Why it happens:** AbortController is not properly reset between requests.
**How to avoid:** Create a new AbortController per request. On stop: call `abort()`, then set `isLoading = false`. On new request: create fresh controller.
**Warning signs:** Messages after stop are immediately cancelled; or stop button has no effect.

### Pitfall 5: Message State Race Condition
**What goes wrong:** Multiple rapid sends create interleaved assistant messages.
**Why it happens:** The spec's `setMessages` approach uses functional updates, but if the user can send before the previous stream completes, messages interleave.
**How to avoid:** Disable input during streaming (already a locked decision). The "Stop generating" button must abort the previous stream before enabling input.
**Warning signs:** Two assistant messages appearing simultaneously.

### Pitfall 6: Popover in Scroll Container
**What goes wrong:** Citation popover appears at wrong position or gets clipped by the chat scroll container.
**Why it happens:** Absolute positioning relative to a scrolling parent.
**How to avoid:** Use Radix Popover which handles portal rendering and scroll-aware positioning automatically.
**Warning signs:** Popovers appear off-screen or behind other elements when chat is scrolled.

## Code Examples

### System Prompt (build_prompt)
```python
# Source: spec.md
def build_prompt(query, retrieved_chunks):
    sources = "\n\n".join(
        f"[{i+1}] {c['file_name']}"
        + (f", p.{c['page_number']}" if c.get('page_number') else "")
        + (f", row {c['row_number']}" if c.get('row_number') else "")
        + (f", slide {c['slide_index']}" if c.get('slide_index') else "")
        + f"\n{c['text']}"
        for i, (c, _) in enumerate(retrieved_chunks)
    )

    return f"""You are an assistant answering questions about a user's Google Drive files.
Answer using ONLY the sources below. Cite inline as [1], [2], etc.
If the answer is not in the sources, say "I couldn't find that in the provided files."
Do not guess or use outside knowledge.

SOURCES:
{sources}

QUESTION: {query}"""
```

### LLM Streaming (Backend)
```python
# Source: spec.md patterns + DeepSeek config
async def stream_llm(query: str, retrieved_chunks: list, model_key: str = "deepseek"):
    client = get_client(model_key)
    model_config = MODELS[model_key]
    prompt = build_prompt(query, retrieved_chunks)

    response = await client.chat.completions.create(
        model=model_config["model"],
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=2000,
        temperature=0.1,  # Low temp for factual grounding
    )

    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
```

### Citation Extraction (Backend)
```python
# Build citations list from retrieved chunks to emit after stream
def extract_citations(retrieved_chunks):
    return [
        {
            "index": i + 1,
            "file_name": c["file_name"],
            "file_id": c["file_id"],
            "page_number": c.get("page_number"),
            "row_number": c.get("row_number"),
            "slide_index": c.get("slide_index"),
            "chunk_text": c["text"],  # frozen at answer time
        }
        for i, (c, score) in enumerate(retrieved_chunks)
    ]
```

### Citation Format Helper (Frontend)
```typescript
// Source: UI-07 requirement + spec citation format
interface Citation {
  index: number;
  file_name: string;
  file_id: string;
  page_number?: number;
  row_number?: number;
  slide_index?: number;
  chunk_text: string;
}

function formatCitationLabel(c: Citation): string {
  if (c.page_number) return `${c.file_name}, p.${c.page_number}`;
  if (c.row_number) return `${c.file_name}, row ${c.row_number}`;
  if (c.slide_index) return `${c.file_name}, slide ${c.slide_index}`;
  return c.file_name;
}
```

### Suggestion Generation (Frontend, no LLM)
```typescript
// Source: CONTEXT.md locked decision
function generateSuggestions(indexedSources: IndexedSource[]): string[] {
  const fileNames = indexedSources
    .flatMap(s => s.file_list)
    .filter(f => f.status === "indexed")
    .map(f => f.name);

  const templates = [
    (name: string) => `Summarize ${name}`,
    (name: string) => `What are the key points in ${name}?`,
    (name: string) => `What does ${name} say about...`,
  ];

  // Pick up to 4 suggestions from different files
  return fileNames.slice(0, 4).map((name, i) =>
    templates[i % templates.length](name)
  );
}
```

### Auth Guard for New Messages
```typescript
// Source: PERS-04 requirement
// Old messages load from IndexedDB (no auth needed)
// New message send requires valid token
async function handleSend(query: string) {
  const token = sessionStorage.getItem("google_access_token");
  if (!token) {
    // Show re-auth modal (from Phase 1 pattern)
    setShowAuthModal(true);
    return;
  }
  await sendMessage(query);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| EventSource for SSE | fetch + ReadableStream | Broadly adopted ~2022+ | EventSource is GET-only; fetch allows POST with body |
| Full page re-renders on stream | Functional state updates | React 18+ | Batched updates prevent flicker during rapid token streaming |
| Store citations as chunk indices | Store full citation snapshot | Design decision | Citations survive re-indexing; slight storage overhead |

## Open Questions

1. **Mixed file type top-k strategy**
   - What we know: Spec says top-8 for docs, top-5 for sheets
   - What's unclear: When a session has both docs and sheets, do we retrieve from separate pools (8+5=13 sources) or a single pool with hybrid k?
   - Recommendation: Retrieve from separate pools, merge by score, cap at 10 total sources to keep prompt size manageable

2. **react-markdown vs custom rendering**
   - What we know: LLM output will contain markdown (headers, lists, bold). Citations are `[N]` patterns inline.
   - What's unclear: Whether to use react-markdown with custom component overrides or a simpler text-splitting approach
   - Recommendation: Use react-markdown for the prose, but split on `[N]` patterns first and render badges separately. This avoids react-markdown eating the bracket patterns.

3. **Textarea auto-resize approach**
   - What we know: CSS `field-sizing: content` is the modern approach but has limited browser support
   - What's unclear: Browser support requirements for this project
   - Recommendation: Use a small `useAutoResize` hook that sets `textarea.style.height = textarea.scrollHeight + 'px'` on input change -- universally supported

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (frontend) + pytest (backend) |
| Config file | vitest.config.ts / pytest.ini (from Phase 1 setup) |
| Quick run command | `pnpm test --run` / `pytest tests/ -x --timeout=10` |
| Full suite command | `pnpm test` / `pytest tests/` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETR-01 | Cosine similarity retrieval returns ranked chunks | unit | `pytest tests/test_retrieval.py::test_cosine_sim -x` | Wave 0 |
| RETR-02 | Top-8 for docs, top-5 for sheets | unit | `pytest tests/test_retrieval.py::test_top_k_by_type -x` | Wave 0 |
| CHAT-01 | /chat returns SSE stream with token events | integration | `pytest tests/test_chat_endpoint.py::test_sse_stream -x` | Wave 0 |
| CHAT-02 | LLM output contains [N] citations | integration | `pytest tests/test_chat_endpoint.py::test_citations_in_response -x` | Wave 0 |
| CHAT-03 | Citation metadata frozen on IndexedDB message | unit (frontend) | `pnpm test -- --run tests/citations.test.ts` | Wave 0 |
| CHAT-04 | Off-topic question returns "not in sources" | integration | `pytest tests/test_chat_endpoint.py::test_off_topic -x` | Wave 0 |
| CHAT-06 | Citations event emitted after token stream | integration | `pytest tests/test_chat_endpoint.py::test_citations_event -x` | Wave 0 |
| UI-07 | Citation labels formatted correctly per type | unit (frontend) | `pnpm test -- --run tests/citations.test.ts` | Wave 0 |
| PERS-04 | Old chats load without auth | unit (frontend) | `pnpm test -- --run tests/db.test.ts` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_retrieval.py tests/test_chat_endpoint.py -x --timeout=10`
- **Per wave merge:** Full suite `pytest tests/ && pnpm test --run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_retrieval.py` -- cosine_sim, retrieve, threshold check, top-k by type
- [ ] `tests/test_chat_endpoint.py` -- SSE stream parsing, citations event, no_results event, off-topic handling
- [ ] `frontend/tests/citations.test.ts` -- formatCitationLabel, citation badge rendering, IndexedDB message with citations
- [ ] `frontend/tests/db.test.ts` -- messages load without auth (PERS-04)

## Sources

### Primary (HIGH confidence)
- spec.md -- Complete code samples for cosine_sim, retrieve, build_prompt, /chat endpoint, useStream hook, SSE event format, citation schema, IndexedDB operations
- Phase 1 RESEARCH.md -- Established patterns for shadcn/ui, IndexedDB, Modal/FastAPI, OAuth flow
- Phase 3 CONTEXT.md -- Locked decisions for citation UX, chat styling, no-results handling, empty state

### Secondary (MEDIUM confidence)
- react-markdown custom component rendering -- standard documented pattern for injecting custom elements
- Radix Popover -- standard shadcn component, well-documented API

### Tertiary (LOW confidence)
- CSS field-sizing: content -- newer spec, browser support may be limited; fallback hook recommended

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- spec provides exact libraries and code samples
- Architecture: HIGH -- spec provides full endpoint structure, hook implementation, SSE format
- Pitfalls: HIGH -- SSE buffering and citation rendering are well-known challenges with documented solutions
- Citation UX: MEDIUM -- popover positioning in scroll containers needs careful implementation with Radix

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, no fast-moving dependencies)
