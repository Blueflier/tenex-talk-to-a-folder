# Requirements: talk-to-a-folder

**Defined:** 2025-03-05
**Core Value:** Users get accurate, cited answers from their own Google Drive files — every citation points to the exact file, page, and passage.

## v1 Requirements

### Authentication

- [ ] **AUTH-01**: User can sign in with Google via Token Client flow (drive.readonly scope)
- [ ] **AUTH-02**: Access token stored in sessionStorage, attached as Authorization header to all API calls
- [ ] **AUTH-03**: User sees re-auth banner when token expires (Drive 403), sessionStorage cleared automatically
- [ ] **AUTH-04**: User identity derived from Google sub claim server-side on every request

### Indexing

- [ ] **INDX-01**: User can paste a Google Drive link (folder or single file) to start indexing
- [ ] **INDX-02**: Backend resolves Drive link to file list via Drive API
- [ ] **INDX-03**: Google Docs exported as plain text via Drive export API
- [ ] **INDX-04**: PDFs extracted page-by-page via PyMuPDF with recursive chunking per page
- [ ] **INDX-05**: Google Sheets exported as CSV, chunked row-level with headers prepended
- [ ] **INDX-06**: Google Slides exported as plain text, split per slide on double newline
- [ ] **INDX-07**: TXT/MD files chunked with recursive character splitter (1200 chars, 150 overlap)
- [ ] **INDX-08**: Unsupported files (images, videos, ZIP) detected and skipped with reason
- [ ] **INDX-09**: Two-phase SSE progress streaming (extraction per-file, then embedding per-chunk)
- [ ] **INDX-10**: Chunks embedded in batches of 100 via OpenAI text-embedding-3-small
- [ ] **INDX-11**: Embeddings (.npy) and chunks (.json) saved to Modal Volume namespaced by user_id/session_id
- [ ] **INDX-12**: volume.commit() called after every write to prevent data loss
- [ ] **INDX-13**: Duplicate upload detection by Drive file ID against IndexedDB before indexing
- [ ] **INDX-14**: Multi-link sessions: pasting additional links appends to existing session embeddings

### Retrieval

- [ ] **RETR-01**: Query embedded and compared via cosine similarity against session embeddings
- [ ] **RETR-02**: Top-8 chunks returned for docs, top-5 for sheets
- [ ] **RETR-03**: Staleness detection: Drive metadata modifiedTime compared to indexed_at for all session files on each /chat
- [ ] **RETR-04**: Fresh files use pre-computed embeddings; stale files routed to grep_live
- [ ] **RETR-05**: LLM generates 8-12 keyword variants for grep_live queries
- [ ] **RETR-06**: grep_live fetches stale file content, searches with regex alternation, returns up to 15 matches with context windows
- [ ] **RETR-07**: Per-file re-indexing: user clicks "Re-index this file", only that file's chunks replaced in session

### Chat

- [ ] **CHAT-01**: SSE streaming response via fetch + ReadableStream (POST /chat)
- [ ] **CHAT-02**: Inline [N] citations in LLM responses pointing to source file, page, and passage
- [ ] **CHAT-03**: Citation metadata frozen on message at answer time (survives file changes)
- [ ] **CHAT-04**: System prompt constrains LLM to answer only from provided sources
- [ ] **CHAT-05**: Staleness warning events streamed before answer tokens, yellow banner per stale file
- [ ] **CHAT-06**: Citations event sent after stream completes, stored to IndexedDB on message

### Frontend UI

- [ ] **UI-01**: Landing page with "Sign in with Google" button and privacy messaging
- [ ] **UI-02**: Left sidebar with chat list loaded from IndexedDB, sorted by recency
- [ ] **UI-03**: New Chat button generates UUID session_id, creates IndexedDB record
- [ ] **UI-04**: Chat title defaults to first indexed source name, user can click to rename
- [ ] **UI-05**: Chat input bar with Drive link paste zone
- [ ] **UI-06**: Indexing progress: two-phase progress bars (extraction, embedding)
- [ ] **UI-07**: Citation rendering: PDF as "file.pdf, p.7", Sheet as "file.csv, row 12", Slides as "deck, slide 3"
- [ ] **UI-08**: Error banners for all failure modes (403, 404, empty folder, scanned PDF, connection lost, etc.)
- [ ] **UI-09**: Rate limit feedback: 429 response shown to user
- [ ] **UI-10**: Duplicate upload notice with "Open that chat" / "Re-index here" options

### Backend Infrastructure

- [ ] **INFR-01**: Modal app with FastAPI, Volume mount at /data, OpenAI + DeepSeek secrets
- [ ] **INFR-02**: CORS configured with explicit origins (localhost:5173 + production domain)
- [ ] **INFR-03**: Rate limiting on /chat: 10 requests/minute per session (in-memory)
- [ ] **INFR-04**: Model strategy: DeepSeek default, configurable model key, OpenAI-compatible client swap

### Local Persistence

- [ ] **PERS-01**: IndexedDB "chats" store: session_id, title, created_at, last_message_at, indexed_sources[]
- [ ] **PERS-02**: IndexedDB "messages" store: session_id (indexed), role, content, citations[], created_at
- [ ] **PERS-03**: Chat history and messages load from IndexedDB with no server calls
- [ ] **PERS-04**: Old chats readable without auth; new messages require valid token

### Eval Harness

- [ ] **EVAL-01**: QASPER dataset integration for eval pipeline
- [ ] **EVAL-02**: Diagnostic classification: CRAWL_MISS, RETRIEVAL_MISS, STALE_MISS, SYNTHESIS_FAIL per sample
- [ ] **EVAL-03**: LLM judge for automated correctness scoring
- [ ] **EVAL-04**: Drive delta test: compare local eval scores vs real Drive-via-PyMuPDF scores on 5 papers

## v2 Requirements

### Session Recovery

- **RECV-01**: /sessions endpoint to list user sessions from Modal Volume
- **RECV-02**: Frontend can rebuild IndexedDB from server-side session list

### File Detection UI

- **FDET-01**: File detection card grid (green/red borders) before indexing starts
- **FDET-02**: Unsupported file tooltips explaining why

### Enhanced Retrieval

- **ENHR-01**: BM25 hybrid retrieval alongside cosine similarity
- **ENHR-02**: Reranker for improved precision
- **ENHR-03**: grep_live caching with 5-minute TTL per file_id

## Out of Scope

| Feature | Reason |
|---------|--------|
| Silent token refresh | Takehome simplicity — force re-auth on expiry |
| Persistent user accounts | Google sub claim is identity, no user table |
| Semantic chunking | Recursive is correct default at this scale |
| Scanned PDF / OCR | Out of scope for takehome |
| Mobile app | Web only |
| Sheets deduplication | All versions indexed independently |
| Real-time chat / WebSockets | SSE is sufficient |
| Keep-warm pings on Modal | Cost concern for takehome; handle cold start in UI |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| AUTH-04 | TBD | Pending |
| INDX-01 | TBD | Pending |
| INDX-02 | TBD | Pending |
| INDX-03 | TBD | Pending |
| INDX-04 | TBD | Pending |
| INDX-05 | TBD | Pending |
| INDX-06 | TBD | Pending |
| INDX-07 | TBD | Pending |
| INDX-08 | TBD | Pending |
| INDX-09 | TBD | Pending |
| INDX-10 | TBD | Pending |
| INDX-11 | TBD | Pending |
| INDX-12 | TBD | Pending |
| INDX-13 | TBD | Pending |
| INDX-14 | TBD | Pending |
| RETR-01 | TBD | Pending |
| RETR-02 | TBD | Pending |
| RETR-03 | TBD | Pending |
| RETR-04 | TBD | Pending |
| RETR-05 | TBD | Pending |
| RETR-06 | TBD | Pending |
| RETR-07 | TBD | Pending |
| CHAT-01 | TBD | Pending |
| CHAT-02 | TBD | Pending |
| CHAT-03 | TBD | Pending |
| CHAT-04 | TBD | Pending |
| CHAT-05 | TBD | Pending |
| CHAT-06 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |
| UI-05 | TBD | Pending |
| UI-06 | TBD | Pending |
| UI-07 | TBD | Pending |
| UI-08 | TBD | Pending |
| UI-09 | TBD | Pending |
| UI-10 | TBD | Pending |
| INFR-01 | TBD | Pending |
| INFR-02 | TBD | Pending |
| INFR-03 | TBD | Pending |
| INFR-04 | TBD | Pending |
| PERS-01 | TBD | Pending |
| PERS-02 | TBD | Pending |
| PERS-03 | TBD | Pending |
| PERS-04 | TBD | Pending |
| EVAL-01 | TBD | Pending |
| EVAL-02 | TBD | Pending |
| EVAL-03 | TBD | Pending |
| EVAL-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 46 total
- Mapped to phases: 0
- Unmapped: 46

---
*Requirements defined: 2025-03-05*
*Last updated: 2025-03-05 after initial definition*
