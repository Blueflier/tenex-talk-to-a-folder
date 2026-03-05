# Roadmap: talk-to-a-folder

## Overview

Deliver a RAG chat app that ingests Google Drive files and answers questions with exact citations. The build progresses from backend/auth foundation, through the indexing pipeline, to core chat with retrieval, then adds staleness-aware hybrid retrieval, multi-session management with polish, and finally the eval harness to make quality claims measurable.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation + Auth** - Backend scaffold, Google OAuth, frontend shell, IndexedDB stores
- [ ] **Phase 2: Indexing Pipeline** - Drive link resolution, file extraction, chunking, embedding, Modal Volume storage
- [ ] **Phase 3: Retrieval + Chat** - Cosine similarity retrieval, streaming LLM responses with inline citations
- [ ] **Phase 4: Staleness + Hybrid Retrieval** - Staleness detection, grep_live for stale files, per-file re-indexing
- [ ] **Phase 5: Multi-session + Polish** - Sidebar chat management, duplicate detection, multi-link, error states, rate limiting
- [ ] **Phase 6: Eval Harness** - QASPER eval pipeline with diagnostic classification and LLM judge

## Phase Details

### Phase 1: Foundation + Auth
**Goal**: User can sign in with Google and land in a working app shell with persistent local storage
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, INFR-01, INFR-02, INFR-04, UI-01, PERS-01, PERS-02, PERS-03
**Success Criteria** (what must be TRUE):
  1. User can click "Sign in with Google" and receive a valid access token with drive.readonly scope
  2. Backend FastAPI app runs on Modal with Volume mounted, CORS configured, and secrets available
  3. API calls from frontend include Authorization header; expired tokens trigger a re-auth banner
  4. IndexedDB "chats" and "messages" stores exist and persist data across page reloads
  5. Model strategy is configured with DeepSeek default and swappable model key
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Indexing Pipeline
**Goal**: User can paste a Drive link and watch their files get extracted, chunked, and embedded with progress feedback
**Depends on**: Phase 1
**Requirements**: INDX-01, INDX-02, INDX-03, INDX-04, INDX-05, INDX-06, INDX-07, INDX-08, INDX-09, INDX-10, INDX-11, INDX-12, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. User pastes a Google Drive folder link and sees each supported file extracted with a progress bar
  2. Google Docs, PDFs, Sheets, Slides, TXT, and MD files are each chunked with their type-specific strategy
  3. Unsupported files (images, videos, ZIP) appear as skipped with a reason shown
  4. Embeddings and chunk metadata are saved to Modal Volume namespaced by user/session, with volume.commit() after every write
  5. Two-phase SSE progress streams: extraction per-file, then embedding per-chunk
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Retrieval + Chat
**Goal**: User can ask questions about indexed files and receive streaming answers with exact file/page/passage citations
**Depends on**: Phase 2
**Requirements**: RETR-01, RETR-02, CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-06, UI-07, PERS-04
**Success Criteria** (what must be TRUE):
  1. User types a question and receives a streaming response via fetch + ReadableStream
  2. Response contains inline [N] citations; clicking a citation shows file name, page number, and passage
  3. LLM only answers from provided sources (system prompt constraint verified by off-topic question)
  4. Citation metadata is frozen on each message and survives file changes (stored to IndexedDB)
  5. Old chat messages are readable without auth; new messages require a valid token
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Staleness + Hybrid Retrieval
**Goal**: Users always get answers from the latest file content, even when Drive files have changed since indexing
**Depends on**: Phase 3
**Requirements**: RETR-03, RETR-04, RETR-05, RETR-06, RETR-07, CHAT-05
**Success Criteria** (what must be TRUE):
  1. On each /chat request, backend checks Drive modifiedTime against indexed_at for all session files
  2. Stale files are routed to grep_live instead of pre-computed embeddings; fresh files use cosine similarity
  3. LLM generates keyword variants for grep_live; grep returns up to 15 matches with context windows
  4. User sees a yellow staleness warning banner per stale file before answer tokens stream
  5. User can click "Re-index this file" to replace only that file's chunks in the session
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Multi-session + Polish
**Goal**: User can manage multiple chat sessions with full error handling and production-quality UX
**Depends on**: Phase 3
**Requirements**: UI-02, UI-03, UI-04, UI-08, UI-09, UI-10, INDX-13, INDX-14, INFR-03
**Success Criteria** (what must be TRUE):
  1. Left sidebar shows chat list sorted by recency; user can create new chats and rename existing ones
  2. Pasting a previously indexed Drive link shows duplicate notice with "Open that chat" / "Re-index here" options
  3. Pasting additional Drive links into an existing session appends embeddings to the session
  4. All failure modes (403, 404, empty folder, scanned PDF, connection lost, rate limit) show descriptive error banners
  5. /chat endpoint enforces 10 req/min per session rate limit; 429 response shown to user
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Eval Harness
**Goal**: Quality claims are measurable with an automated eval pipeline on real academic papers
**Depends on**: Phase 3
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04
**Success Criteria** (what must be TRUE):
  1. QASPER dataset loads and feeds questions through the retrieval + chat pipeline
  2. Each eval sample is classified as CRAWL_MISS, RETRIEVAL_MISS, STALE_MISS, or SYNTHESIS_FAIL
  3. LLM judge scores correctness automatically with reproducible results
  4. Drive delta test compares local eval scores vs real Drive-via-PyMuPDF scores on 5 papers
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6
(Phases 4, 5, and 6 all depend on Phase 3 but not each other)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + Auth | 0/? | Not started | - |
| 2. Indexing Pipeline | 0/? | Not started | - |
| 3. Retrieval + Chat | 0/? | Not started | - |
| 4. Staleness + Hybrid Retrieval | 0/? | Not started | - |
| 5. Multi-session + Polish | 0/? | Not started | - |
| 6. Eval Harness | 0/? | Not started | - |
