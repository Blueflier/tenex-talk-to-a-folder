# Talk to a Folder

A RAG application that lets you chat with your Google Drive files. Paste a Drive link, and the app indexes your documents (Docs, Sheets, Slides, PDFs, TXT, Markdown) into vector embeddings, then answers questions with inline citations grounded in the source material.

## Architecture

```
┌──────────────┐       SSE        ┌──────────────────────┐
│   React SPA  │◄────────────────►│  FastAPI on Fly.io   │
│  (Vite + TS) │                  │                      │
│              │                  │  /index  - indexing   │
│  IndexedDB   │                  │  /chat   - streaming  │
│  (messages,  │                  │  /reindex - per-file  │
│   sessions)  │                  │                      │
└──────────────┘                  │  Fly Volume (/data)   │
                                  │  (embeddings + chunks)│
                                  └──────────────────────┘
                                          │
                                  ┌───────┴────────┐
                                  │ OpenAI embeddings│
                                  │ DeepSeek LLM     │
                                  │ Google Drive API  │
                                  └──────────────────┘
```

**Backend** (Python, FastAPI, Fly.io):
- **Indexing pipeline**: Drive link → file export → type-specific chunking → OpenAI embeddings → Fly Volume storage
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
- Python 3.13+
- [Fly.io](https://fly.io) account (for deployment) or local dev mode
- Google Cloud project with OAuth 2.0 credentials and Drive API enabled
- OpenAI API key (embeddings)
- DeepSeek API key (LLM) or OpenAI key with `ACTIVE_MODEL=openai`

### Backend (local dev)

```bash
cp .env.example .env.local
# Fill in API keys in .env.local

pip install -r requirements.txt

# Run locally with auth bypass
EVAL_MODE=1 DATA_DIR=./data uvicorn backend.app:web_app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env  # set VITE_API_URL and VITE_GOOGLE_CLIENT_ID
pnpm install
pnpm dev
```

### Deploy to Fly.io

```bash
fly deploy
```

## Key Design Decisions

- **SSE over WebSockets**: Simpler protocol for unidirectional streaming; works through CDNs/proxies without upgrade negotiation.
- **Hybrid retrieval**: Embedding similarity for fresh files + live grep for stale files avoids re-indexing on every query while still returning current data.
- **Per-file re-indexing**: Surgical chunk replacement rather than full session re-index — O(file) instead of O(session).
- **IndexedDB for chat history**: Messages persist client-side, reducing backend storage costs and enabling offline viewing of past conversations.
- **Type-specific chunking**: PDFs chunked page-by-page, sheets row-by-row with header prepended, slides split on boundaries — preserves structural context for retrieval.

## Problems We Encountered

- **Serverless → single-machine**: We originally deployed on Modal (serverless), but each container instance had isolated state — no guarantee consecutive requests hit the same container. This made persistent storage and rate-limiting hard without a shared cache. We moved to Fly.io with a persistent volume mount, which gives us a single machine with stable local disk for embeddings/chunks. **Takeaway**: don't design for serverless constraints unless you actually need to scale that way.

## Testing

```bash
# Backend
python -m pytest backend/tests/ -q

# Frontend
cd frontend && pnpm test
```
