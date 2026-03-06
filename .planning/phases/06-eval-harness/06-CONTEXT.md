# Phase 6: Eval Harness - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated eval pipeline that measures RAG quality using QASPER academic papers. Produces F1 scores, diagnostic failure classifications, and a Drive delta comparison. This is a backend-only measurement tool — no UI changes.

</domain>

<decisions>
## Implementation Decisions

### Dataset & pipeline wiring
- Local PDF ingestion — bypass Drive API entirely, no Google auth needed for eval
- 5 papers auto-selected from QASPER (optimized for question density and manageable size, reproducible via seed)
- Eval runs against HTTP endpoints (POST /chat via local uvicorn), testing the full stack including SSE parsing
- QASPER data downloaded locally, gitignored, README documents download link for others
- Results output as JSON file with summary printed to stdout (overall F1, per-paper breakdown, diagnostic counts)

### Embedding cache
- First run hits OpenAI API for embeddings, caches to eval/cache/ (gitignored)
- Per-paper cache files: {paper_id}_embeddings.npy + _chunks.json (mirrors storage.py pattern)
- Manual invalidation — delete eval/cache/ to force re-embedding, documented in README
- Subsequent runs load from cache — fast, cheap, deterministic on retrieval side

### Diagnostic classification
- Automated heuristics (no LLM classifier)
- CRAWL_MISS: passage-level check — search for gold answer text in all extracted chunks; if not found in any chunk, extraction/chunking lost it
- RETRIEVAL_MISS: semantic similarity — embed gold answer, compare cosine similarity to retrieved chunks; catches paraphrased matches
- STALE_MISS: N/A for local eval runs — only applies in Drive delta test (EVAL-04)
- SYNTHESIS_FAIL: answer existed in retrieved chunks but LLM generated wrong response

### Scoring
- Token-level F1 as sole metric (no LLM judge needed)
- All QASPER question types included: yes/no, extractive, abstractive, unanswerable
- Unanswerable questions included — tests system prompt constraint (CHAT-04: "I couldn't find that")
- Multiple annotator answers: max F1 across annotators (standard QASPER approach)

### Drive delta test
- Separate script (eval/run_drive_delta.py) from main eval (eval/run_eval.py)
- User manually uploads PDFs to Drive, provides folder link
- Drive folder link read from config file (eval/config.json)
- Delta = absolute F1 score difference between local PDF eval and Drive-fetched eval
- Threshold: 0.10 — flags a problem if local vs Drive scores differ by more than this

### Eval CLI interface
- Single Python script: python eval/run_eval.py
- Simple print statements for progress (no tqdm dependency)
- Prints compact summary table to stdout after writing JSON results

### Claude's Discretion
- Answer type-aware scoring (exact match for yes/no/unanswerable vs token F1 for extractive/abstractive)
- Auto-selection criteria for the 5 QASPER papers
- SSE response parsing approach in eval client
- eval/config.json schema and defaults
- Exact F1 tokenization/normalization approach

</decisions>

<specifics>
## Specific Ideas

- "We can download locally and put in gitignore, not to push that, but in the README we can say to download from ____ link to run evals"
- "I'll manually upload the PDFs so you can just hit the link. That way I can also add more PDFs if needed"
- Cache embeddings locally so eval runs are repeatable without re-embedding — first run hits OpenAI, subsequent runs load from cache

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/retrieval.py`: retrieve_mixed, cosine_sim, extract_citations — core retrieval logic eval will exercise
- `backend/chat.py`: _chat_event_stream, build_prompt, stream_llm — full chat pipeline via POST /chat
- `backend/storage.py`: save_session/load_session with base_path parameter — pattern for eval cache
- `backend/chunking.py`: Type-specific chunking (PDF via PyMuPDF, recursive char splitter)
- `backend/embedding.py`: Batch embedding via OpenAI text-embedding-3-small

### Established Patterns
- `base_path` parameter on storage functions for testability — eval cache can reuse this pattern
- SSE format: `data: {json}` with types token, citations, no_results, error
- Modal Volume namespacing by user_id/session_id — eval can use synthetic IDs

### Integration Points
- Eval hits POST /chat endpoint (requires running uvicorn locally)
- Eval reuses chunking.py and embedding.py directly for local PDF processing
- Eval cache mirrors storage.py file layout (per-paper .npy + .json)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-eval-harness*
*Context gathered: 2026-03-05*
