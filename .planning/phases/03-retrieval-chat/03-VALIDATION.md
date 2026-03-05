---
phase: 3
slug: retrieval-chat
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (frontend) + pytest (backend) |
| **Config file** | vitest.config.ts / pytest.ini (from Phase 1 setup) |
| **Quick run command** | `pytest tests/test_retrieval.py tests/test_chat_endpoint.py -x --timeout=10 && pnpm test --run` |
| **Full suite command** | `pytest tests/ && pnpm test` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_retrieval.py tests/test_chat_endpoint.py -x --timeout=10`
- **After every plan wave:** Run `pytest tests/ && pnpm test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | RETR-01 | unit | `pytest tests/test_retrieval.py::test_cosine_sim -x` | W0 | pending |
| 03-01-02 | 01 | 1 | RETR-02 | unit | `pytest tests/test_retrieval.py::test_top_k_by_type -x` | W0 | pending |
| 03-01-03 | 01 | 1 | CHAT-04 | integration | `pytest tests/test_chat_endpoint.py::test_off_topic -x` | W0 | pending |
| 03-01-04 | 01 | 1 | CHAT-01 | integration | `pytest tests/test_chat_endpoint.py::test_sse_stream -x` | W0 | pending |
| 03-01-05 | 01 | 1 | CHAT-02 | integration | `pytest tests/test_chat_endpoint.py::test_citations_in_response -x` | W0 | pending |
| 03-01-06 | 01 | 1 | CHAT-06 | integration | `pytest tests/test_chat_endpoint.py::test_citations_event -x` | W0 | pending |
| 03-02-01 | 02 | 1 | CHAT-03 | unit (frontend) | `pnpm test -- --run tests/citations.test.ts` | W0 | pending |
| 03-02-02 | 02 | 1 | UI-07 | unit (frontend) | `pnpm test -- --run tests/citations.test.ts` | W0 | pending |
| 03-02-03 | 02 | 1 | PERS-04 | unit (frontend) | `pnpm test -- --run tests/db.test.ts` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_retrieval.py` — cosine_sim, retrieve, threshold check, top-k by type
- [ ] `tests/test_chat_endpoint.py` — SSE stream parsing, citations event, no_results event, off-topic handling
- [ ] `frontend/tests/citations.test.ts` — formatCitationLabel, citation badge rendering, IndexedDB message with citations
- [ ] `frontend/tests/db.test.ts` — messages load without auth (PERS-04)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streaming cursor renders token-by-token | CHAT-01 | Visual rendering | 1. Send question 2. Observe blinking cursor during streaming |
| Citation popover appears near badge | CHAT-02 | Popover positioning | 1. Get response with citations 2. Click [N] badge 3. Verify popover position |
| Stop generating button aborts stream | CHAT-01 | UI interaction timing | 1. Send question 2. Click stop mid-stream 3. Verify stream stops |
| Pre-chat suggestions auto-fill input | UI-07 | UX flow | 1. Index files 2. Observe suggestions 3. Click one 4. Verify input filled |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
