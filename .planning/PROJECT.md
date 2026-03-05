# talk-to-a-folder

## What This Is

A RAG-powered chat app that lets users paste Google Drive links and ask questions about their files. React frontend + Modal/FastAPI Python backend. Answers cite the exact file, page, and passage they came from. Built as a take-home assignment demonstrating retrieval engineering, citation granularity, and staleness-aware hybrid retrieval.

## Core Value

Users get accurate, cited answers from their own Google Drive files — every citation points to the exact file, page, and passage the model used.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Google OAuth (Token Client flow, drive.readonly scope)
- [ ] Drive link resolution (folder or single file)
- [ ] File type support: Google Docs, PDFs, Sheets, Slides, TXT, MD
- [ ] File detection UI with green/red cards before indexing
- [ ] Per-type chunking (recursive, per-page PDF, row-level sheets, per-slide)
- [ ] OpenAI text-embedding-3-small batch embedding with progress streaming
- [ ] Modal Volume storage (embeddings.npy + chunks.json per session)
- [ ] Cosine similarity retrieval (top-8 docs, top-5 sheets)
- [ ] Staleness detection via Drive metadata modifiedTime check
- [ ] Hybrid retrieval: embeddings for fresh files, grep_live for stale files
- [ ] LLM-powered keyword extraction for grep_live
- [ ] SSE streaming chat responses with inline [N] citations
- [ ] Citation metadata frozen on message (file, page, passage)
- [ ] IndexedDB for chat history, messages, and citations (browser-side)
- [ ] Left sidebar with chat list, new chat, rename
- [ ] Duplicate upload detection (by Drive file ID)
- [ ] Per-file re-indexing
- [ ] Multi-link sessions (append embeddings to existing session)
- [ ] Token expiry handling (re-auth banner on 403)
- [ ] Error states for all failure modes (permissions, empty folder, scanned PDF, etc.)
- [ ] Rate limiting on /chat (10 req/min per session)
- [ ] QASPER eval harness with CRAWL_MISS / RETRIEVAL_MISS / STALE_MISS / SYNTHESIS_FAIL classification
- [ ] Model strategy: DeepSeek default, swappable after eval

### Out of Scope

- Silent token refresh — force re-auth on expiry (takehome simplicity)
- Persistent user accounts / user database — Google sub claim is identity
- Reranker — pure cosine sim sufficient for demo
- Semantic chunking — recursive is correct default at this scale
- Sheets deduplication across versions
- OCR for scanned PDFs
- Mobile app — web only
- Real-time chat / WebSockets

## Context

- Take-home assignment for a job application — optimize for demonstrating engineering skills to reviewers
- Frontend deployed separately (Vercel/Netlify), backend on Modal
- All API keys (Google, OpenAI, DeepSeek) already configured
- Spec is highly detailed with code samples — implementation should follow spec closely
- The "better than Perplexity" angle: citation granularity, private docs, staleness awareness
- Eval harness (QASPER) included in v1 to make claims measurable

## Constraints

- **Stack**: React + Vite frontend, Modal + FastAPI backend (specified)
- **UI**: shadcn/ui + Radix + Tailwind CSS
- **Auth**: Google Identity Services Token Client (Flow A only, no backend exchange)
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: DeepSeek default (OpenAI-compatible API), swappable
- **Storage**: Modal Volume (numpy .npy + JSON), no external vector DB
- **Local state**: IndexedDB (native), sessionStorage for token
- **Streaming**: fetch + ReadableStream (not EventSource, not Vercel AI SDK for chat)
- **CORS**: Explicit origins only, no wildcard

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Token Client over Code Client | No backend token exchange needed, simpler | -- Pending |
| fetch+ReadableStream over EventSource | /chat is POST, EventSource is GET-only | -- Pending |
| fetch+ReadableStream over Vercel AI SDK | Custom event types (staleness, citations) don't fit SDK format | -- Pending |
| Modal Volume over vector DB | No external dependency, free, fast enough for takehome | -- Pending |
| Staleness drives retrieval routing | Removes LLM routing errors entirely — binary check, not model judgment | -- Pending |
| Row-level sheet chunking with headers | Headers prepended to every row so embeddings capture structure | -- Pending |
| volume.commit() after every write | Adds ~100-200ms but prevents silent data loss | -- Pending |

---
*Last updated: 2025-03-05 after initialization*
