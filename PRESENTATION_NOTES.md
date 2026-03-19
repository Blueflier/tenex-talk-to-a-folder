# Talk to a Folder — Architecture & Product Overview

## What It Does

- Paste a Google Drive folder link, we index every file, and you can chat with all of them in natural language
- Supports Google Docs, Sheets, Slides, PDFs, TXT, Markdown
- Real-time streaming answers with inline citations back to the exact source

---

## Architecture

### Frontend (React + Vite, hosted on Vercel)
- Google OAuth for Drive read-only access — no file uploads, no storage headaches
- **IndexedDB for full client-side persistence** — chats, messages, citations, and indexed file metadata all stored locally in the browser
  - Two object stores: `chats` (keyed by session_id) and `messages` (indexed by session_id + created_at)
  - Chat history survives page refreshes without any server-side message store
  - Reduces backend complexity — we don't store conversations, the browser does
- SSE (Server-Sent Events) for real-time streaming of both indexing progress and LLM responses
- Tailwind + shadcn/ui components, dark mode, mobile responsive

### Backend (FastAPI + Python, hosted on Fly.io)
- Three core endpoints: `/index` (SSE), `/chat` (SSE), `/reindex` (REST)
- Disk-based storage on Fly.io volume mounts — numpy `.npy` for embeddings, JSON for chunk metadata
  - No database, no pgvector, no Pinecone — just files on disk
  - Simple, fast, zero operational overhead
- In-memory rate limiting: 10 requests per 60s per session

### RAG Pipeline
- **Chunking**: 250-char chunks with 30-char overlap, type-specific strategies per file format
  - PDFs: page-by-page via PyMuPDF
  - Sheets: row-level with headers prepended to every row
  - Slides: split on slide boundaries
  - Docs/text: recursive character splitting
- **Embedding**: OpenAI `text-embedding-3-small` (1536 dimensions), batched 100 at a time with retry + exponential backoff
- **Retrieval**: Cosine similarity with file-type-aware pooling
  - Mixed content: top-8 docs + top-5 sheets, merge by score, cap at 10
  - Similarity threshold of 0.3 — below that, we say "no results" instead of hallucinating

### Hybrid Search (Cosine + Live Grep)
- Three-way partition at query time:
  - **Fresh files** → standard cosine similarity
  - **Stale/modified files** → live keyword grep against current Drive content
  - **Deleted files** → use old embeddings, mark citations as "(deleted)"
- Grep path: LLM extracts 8-12 keywords from the query, searches sentence-by-sentence with context windows
- Result: you always get answers from the latest content, even if files changed since indexing

### Staleness Detection
- On every chat, we check each file's Drive `modifiedTime` vs. our `indexed_at` timestamp
- 10-second TTL cache per file to avoid hammering the Drive API
- UI shows banners: yellow for modified, red for deleted, with one-click re-index buttons

### Surgical Per-File Reindexing
- Re-index a single file without touching the rest of the session
- Removes old chunks for that file, fetches + chunks + embeds the new version, merges back in
- Regenerates summary chunks so broad queries stay accurate

### Folder-Level Summary Chunks (new)
- After indexing, LLM generates a 1-2 sentence summary per file
- Creates synthetic chunks: per-file summary + folder overview
- These embed close to broad queries like "what are these files about?" — solves the empty-results problem for overview questions

### New File Detection
- If you indexed a folder and someone adds a new file later, we detect it at chat time
- Compares current folder contents against the indexed file list
- Toast notification with re-index action

---

## Key Tradeoffs

| Decision | Upside | Downside |
|----------|--------|----------|
| Disk storage over vector DB | Zero ops, no external dependency, fast read/write | No cross-machine sharing, limited to single volume |
| IndexedDB for chat persistence | No server-side message store, instant loads, works offline-ish | Data lives in one browser, no cross-device sync |
| In-memory caching (staleness, grep text) | Fast, simple | Per-process only — redundant API calls across replicas |
| 250-char chunks | Fine-grained retrieval, good for specific questions | May miss broader context; summary chunks compensate |
| Hybrid cosine + grep | Always-fresh answers even for stale files | Grep path is slower, keyword extraction adds LLM call |
| Google OAuth only | No auth infrastructure to maintain | Tied to Google ecosystem |
| LLM-generated summaries at index time | Dramatically improves broad query quality | Adds latency to indexing (one LLM call per file) |
| SSE streaming | Real-time UX for both indexing and chat | More complex frontend parsing than simple REST |

---

## Future Design Opportunities

- **Cross-device sync**: Move chat persistence from IndexedDB to a lightweight server-side store (Supabase, SQLite on Fly)
- **Semantic caching**: Cache frequent query embeddings to skip re-embedding identical questions
- **Multi-folder sessions**: Index multiple Drive folders into a single chat session
- **Collaborative chats**: Share a session link with teammates who have Drive access
- **Scheduled re-indexing**: Background job to keep embeddings fresh without manual re-index clicks
- **Smarter chunking**: Adaptive chunk sizes based on content density (larger for prose, smaller for tables)
- **Hybrid vector DB**: Migrate to pgvector or Qdrant for cross-machine scaling when needed
- **File-type expansion**: Support images (OCR), audio (transcription), video (subtitle extraction)
- **Conversation memory**: Use previous Q&A pairs as context for follow-up questions (currently sends last response only)
- **Analytics dashboard**: Show which files get queried most, which chunks get cited, query patterns

---

## Business Impact

- **Removes friction from knowledge retrieval** — instead of searching through 50 files in a Drive folder, ask a question and get a cited answer in seconds
- **Zero setup for end users** — paste a link, sign in with Google, start chatting. No file uploads, no data migration, no onboarding
- **Client-side persistence via IndexedDB** means we don't store user data on our servers — strong privacy story, simpler compliance (no PII in our database)
- **Real-time staleness detection** means answers are never silently outdated — users trust the system because it tells them when something changed
- **Hybrid retrieval** is a differentiator — most RAG tools fail silently when source data changes. We gracefully degrade to live search
- **Works for any team with a shared Drive folder** — sales teams with proposal docs, eng teams with design docs, legal with contracts, students with course materials
- **Surgical reindexing** means you don't re-process 100 files because one changed — keeps the experience fast and costs low
- **Summary chunks solve the "cold start" problem** — the very first question most people ask is "what's in here?" and now we have an answer
- **Lightweight infrastructure** — single Fly.io machine with a volume mount, Vercel for frontend. Costs near zero at low scale, straightforward to scale up
