# Tech Choices & Tradeoffs

## Stack Overview

| Layer | Choice | Alternatives Considered |
|-------|--------|------------------------|
| Frontend | React 19 + TypeScript + Vite 7 | Next.js, plain HTML |
| Styling | Tailwind CSS 4 + shadcn/ui (Radix primitives) | MUI, Chakra |
| Backend | Python + FastAPI | Node/Express, Django |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) | Cohere, local models |
| LLM | DeepSeek Chat (default), OpenAI GPT-4o-mini (configurable) | Anthropic, Llama |
| Vector storage | Raw `.npy` files on disk | Pinecone, Chroma, pgvector |
| Chat persistence | IndexedDB (client-side) | Server-side DB, localStorage |
| Deployment | Fly.io single machine + persistent volume | Modal (serverless), AWS, Vercel |
| Auth | Google OAuth (GIS implicit flow) | Firebase Auth, Auth0 |
| Package manager | pnpm | npm, yarn |

---

## Key Decisions & Tradeoffs

### 1. SSE over WebSockets

**Chose**: Server-Sent Events for streaming LLM tokens and indexing progress.

**Why**: Simpler unidirectional protocol. Works through CDNs and reverse proxies without upgrade negotiation. FastAPI's `StreamingResponse` makes SSE trivial. We don't need client-to-server streaming — all client messages go through regular POST requests.

**Tradeoff**: No bidirectional communication. If we ever need server-initiated push outside of an active request (e.g., background reindex notifications), we'd need to add WebSockets or polling.

### 2. Flat `.npy` + `.json` files instead of a vector database

**Chose**: NumPy arrays saved to disk with `np.save`/`np.load`, chunk metadata in plain JSON.

**Why**: Zero infrastructure. No database to provision, no connection pool to manage. Cosine similarity over a few thousand vectors in NumPy is sub-millisecond. The data is namespaced by `{user_id}/{session_id}`, so there's no cross-session contamination.

**Tradeoff**: No built-in ANN indexing — we do brute-force cosine sim. This is fine for typical Drive folder sizes (hundreds to low thousands of chunks) but wouldn't scale to millions of vectors. Migration to a real vector DB would require rewriting `storage.py` and `retrieval.py`.

### 3. Single machine (Fly.io) instead of serverless (Modal)

**Chose**: Fly.io with a persistent volume mount at `/data`.

**Why**: We originally deployed on Modal (serverless), but each container instance had isolated state. Consecutive requests weren't guaranteed to hit the same container, which broke our file-based storage model. We would have needed a shared cache (Redis/S3) just to read embeddings, adding latency and complexity.

**Tradeoff**: Single point of failure — no horizontal scaling. The 1 GB shared-CPU VM is cheap but constrains concurrent users. Fly's `auto_stop_machines` helps with cost (scales to zero), but a traffic spike could overwhelm one machine. Good enough for the current use case.

### 4. Hybrid retrieval: cosine similarity + live grep

**Chose**: Fresh files use embedding-based retrieval; stale/modified files fall back to keyword grep against live Drive content.

**Why**: Avoids re-indexing the entire session every time a file changes. The grep path uses an LLM call to expand the user's query into 8-12 keyword variants, then does regex matching with sentence-window context. This keeps answers current without the latency of re-embedding.

**Tradeoff**: Grep results are lower quality than embedding retrieval — no semantic understanding, just keyword hits with context windows. The LLM keyword expansion adds one extra API call per chat when stale files exist. The grep text cache (5 min TTL, in-memory) doesn't survive restarts.

### 5. Per-file surgical re-indexing

**Chose**: `/reindex` endpoint replaces only one file's chunks and embeddings in the session, leaving everything else intact.

**Why**: O(file) instead of O(session). A user updating one Google Doc shouldn't have to wait for the entire folder to re-embed. The implementation builds a keep-mask over chunk indices, splices out the old file's data, and merges in the new.

**Tradeoff**: More complex merge logic in `reindex.py`. If the session data format changes, this code needs to stay in sync with the indexing pipeline.

### 6. IndexedDB for chat history (client-side)

**Chose**: All messages, sessions, and citations persist in the browser's IndexedDB.

**Why**: No server-side database needed for chat. Users can view past conversations offline. Reduces backend storage costs to just embeddings + chunks. The server is stateless with respect to conversation history.

**Tradeoff**: Chat history is device-local — no cross-device sync. Clearing browser data loses all history. If we add multi-device support, we'd need a server-side message store.

### 7. DeepSeek as default LLM (with OpenAI fallback)

**Chose**: DeepSeek Chat as the primary LLM, configurable via `ACTIVE_MODEL` env var.

**Why**: Cost. DeepSeek is significantly cheaper per token than GPT-4o while producing comparable quality for grounded Q&A with provided sources. The `config.py` abstraction makes switching models a one-line env change.

**Tradeoff**: DeepSeek has higher latency than OpenAI for first-token time. Less mature API with occasional availability issues. The OpenAI fallback is there for reliability.

### 8. Google OAuth implicit flow (no backend token storage)

**Chose**: GIS (Google Identity Services) implicit flow. Token lives in `sessionStorage`, passed as `Authorization: Bearer` header on every request, discarded server-side after use.

**Why**: Simplest possible auth. No refresh token management, no token database, no session cookies. The backend just calls Google's userinfo endpoint to get the `sub` claim for user namespacing.

**Tradeoff**: Token expires after ~1 hour. Users must re-authenticate when it expires (we show a `ReAuthModal`). No offline access — can't do background re-indexing without the user present.

### 9. Type-specific chunking strategies

**Chose**: Different chunking logic per file type — PDFs page-by-page, sheets row-by-row with header prepended, slides on double-newline boundaries, text/docs with recursive character splitting.

**Why**: Preserves structural context that matters for retrieval. A spreadsheet row with its header is a self-contained fact. A PDF page boundary is a natural semantic unit. Generic fixed-size chunking would split across these boundaries and lose context.

**Tradeoff**: More code to maintain (four chunking paths). Each new file type needs its own chunker. The sheet chunker produces one chunk per row, which can be many chunks for large spreadsheets.

### 10. In-memory rate limiting and caching

**Chose**: Per-process dictionaries for rate limits (`_rate_limits`), staleness cache (`_staleness_cache`), and grep text cache (`_grep_text_cache`).

**Why**: Zero-dependency simplicity. With a single Fly.io machine, there's only one process, so in-memory state is effectively global.

**Tradeoff**: Doesn't survive process restarts. Won't work correctly with multiple replicas (each would enforce limits independently). Noted in code comments as a known limitation — Redis would be the fix if we scale out.

---

## Production Quality

**Modular architecture.** The backend is split into focused modules — `index.py` (embedding pipeline), `chat.py` (retrieval + generation), `grep.py` (live keyword search), `staleness.py` (freshness detection), `config.py` (centralized model/key config). Each module owns one responsibility and can be modified independently.

**Edge-case handling.** Rate limiting is enforced per-user in-memory to prevent abuse. The staleness system gracefully degrades: if a file has been modified since indexing, it falls back to grep-based retrieval rather than serving stale embeddings. SSE streams handle client disconnects without leaking resources. The auth layer validates Google tokens on every request and namespaces all data by `user_id/session_id` to prevent cross-session contamination.

**Error boundaries.** File type extraction handles malformed PDFs, empty sheets, and unsupported MIME types with clear error messages rather than silent failures. The frontend uses IndexedDB with schema migrations so chat history survives app updates.

## AI-Native Speed

**Built with Claude Code throughout.** Every module was scaffolded, iterated, and debugged with AI assistance — from the FastAPI route handlers to the React component tree to the Fly.io deployment config. The workflow: describe intent, generate code, read and verify the output, then refine. This let a small team ship a full-stack RAG app with auth, streaming, hybrid retrieval, and real-time staleness detection in a compressed timeline.

**Verification loop.** AI-generated code was never shipped blindly. Each module was read through, tested against real Google Drive folders, and refined based on actual behavior — especially the chunking pipeline, cosine similarity ranking, and SSE streaming logic.

## Chunking: Simple by Design

We use **simple fixed-size character chunking** with overlap — not sentence-aware, paragraph-aware, or recursive splitting (like LangChain's `RecursiveCharacterTextSplitter`). This was a deliberate choice to keep the pipeline minimal and predictable.

**Why not recursive/semantic chunking?** More sophisticated splitting adds complexity without proportional gain for our use case. The documents being queried are typically well-structured Google Docs, Sheets, and Slides — the structure comes from the file type, not from parsing prose boundaries. We get structural awareness from **type-specific extraction** (page-by-page for PDFs, row-by-row for sheets) rather than from a generic text splitter.

**Where the wow factor lives: real-time interactivity.** Instead of investing in chunking sophistication, we invested in **live staleness detection and hybrid retrieval**. For a business that constantly updates documents with new information, the ability to query that information immediately matters more than marginally better chunk boundaries. Our staleness checker polls Google Drive metadata to detect modified or newly added files, then seamlessly falls back to live grep search — so answers stay current without waiting for a full re-index. This is the differentiator: not how we split text, but how fast the system adapts when that text changes.

---

## What We'd Change with More Time

- **Vector DB** (Chroma or pgvector) for ANN search at scale
- **Redis** for shared rate limits, caching, and session state across replicas
- **Refresh token flow** for persistent auth and background re-indexing
- **Server-side message store** for cross-device chat history
- **Streaming progress during embedding** (currently batched after completion)
- **Incremental folder watching** instead of manual re-index triggers
