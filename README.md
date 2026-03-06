# Talk to a Folder

A RAG application that lets you chat with your Google Drive files. Paste a Drive link, and the app indexes your documents (Docs, Sheets, Slides, PDFs, TXT, Markdown) into vector embeddings, then answers questions with inline citations grounded in the source material.

## Architecture

```
┌──────────────┐       SSE        ┌──────────────────────┐
│   React SPA  │◄────────────────►│  FastAPI on Modal    │
│  (Vite + TS) │                  │                      │
│              │                  │  /index  - indexing   │
│  IndexedDB   │                  │  /chat   - streaming  │
│  (messages,  │                  │  /reindex - per-file  │
│   sessions)  │                  │                      │
└──────────────┘                  │  Modal Volume (/data) │
                                  │  (embeddings + chunks)│
                                  └──────────────────────┘
                                          │
                                  ┌───────┴────────┐
                                  │ OpenAI embeddings│
                                  │ DeepSeek LLM     │
                                  │ Google Drive API  │
                                  └──────────────────┘
```

**Backend** (Python, FastAPI, Modal):
- **Indexing pipeline**: Drive link → file export → type-specific chunking → OpenAI embeddings → Modal Volume storage
- **Hybrid retrieval**: Cosine similarity over embeddings + live keyword grep for stale files
- **Staleness detection**: Compares Drive `modifiedTime` against `indexed_at` to detect changed/deleted files
- **Streaming chat**: SSE-based token streaming with DeepSeek (configurable to OpenAI)

**Frontend** (React, TypeScript, Vite, Tailwind, shadcn/ui):
- Google OAuth (GIS implicit flow) for Drive access
- Multi-session chat with IndexedDB persistence
- Real-time SSE streaming with inline citation badges
- Per-file re-index from staleness banners

## Setup

### Prerequisites
- Node.js 18+, pnpm
- Python 3.11+
- [Modal](https://modal.com) account (for deployment) or local dev mode
- Google Cloud project with OAuth 2.0 credentials and Drive API enabled
- OpenAI API key (embeddings)
- DeepSeek API key (LLM) or OpenAI key with `ACTIVE_MODEL=openai`

### Backend (local dev)

```bash
cp .env.example .env.local
# Fill in API keys in .env.local

pip install fastapi aiohttp openai numpy pymupdf uvicorn python-dotenv

# Run locally with auth bypass
EVAL_MODE=1 VOLUME_PATH=./data uvicorn backend.app:web_app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env  # or create with VITE_API_URL and VITE_GOOGLE_CLIENT_ID
pnpm install
pnpm dev
```

### Deploy to Modal

```bash
modal deploy backend/app.py
```

## Key Design Decisions

- **SSE over WebSockets**: Simpler protocol for unidirectional streaming; works through CDNs/proxies without upgrade negotiation.
- **Hybrid retrieval**: Embedding similarity for fresh files + live grep for stale files avoids re-indexing on every query while still returning current data.
- **Per-file re-indexing**: Surgical chunk replacement rather than full session re-index — O(file) instead of O(session).
- **IndexedDB for chat history**: Messages persist client-side, reducing backend storage costs and enabling offline viewing of past conversations.
- **Type-specific chunking**: PDFs chunked page-by-page, sheets row-by-row with header prepended, slides split on boundaries — preserves structural context for retrieval.

## Problems We Encountered

- **IndexedDB on serverless**: We initially wanted to use IndexedDB for server-side storage, but ran into idempotency issues when deploying on a serverless architecture (Modal). Each container instance has its own isolated state, so there's no guarantee that consecutive requests hit the same container. This also meant we couldn't rate-limit users without a shared key-value cache across all containers serving the `/chat` endpoint. **Takeaway**: don't design for serverless constraints unless you actually need to scale that way — it introduces complexity (shared state, distributed caching) that isn't worth it for most use cases.

## Testing

```bash
# Backend
python -m pytest backend/tests/ -q

# Frontend
cd frontend && pnpm test
```
