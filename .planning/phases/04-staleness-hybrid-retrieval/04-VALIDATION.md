---
phase: 4
slug: staleness-hybrid-retrieval
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 4 -- Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + Vitest (frontend) |
| **Config file** | pytest.ini / vitest.config.ts (from Phase 1 setup) |
| **Quick run command** | `pytest tests/test_staleness.py tests/test_grep.py tests/test_reindex.py -x --timeout=10` |
| **Full suite command** | `pytest tests/ && pnpm test --run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_staleness.py tests/test_grep.py tests/test_reindex.py -x --timeout=10`
- **After every plan wave:** Run `pytest tests/ && pnpm test --run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | RETR-03 | unit | `pytest tests/test_staleness.py::test_check_staleness -x` | W0 | pending |
| 04-01-02 | 01 | 1 | RETR-03 | unit | `pytest tests/test_staleness.py::test_staleness_error_handling -x` | W0 | pending |
| 04-01-03 | 01 | 1 | RETR-03 | unit | `pytest tests/test_staleness.py::test_staleness_cache_ttl -x` | W0 | pending |
| 04-01-04 | 01 | 1 | RETR-04 | unit | `pytest tests/test_staleness.py::test_hybrid_partition -x` | W0 | pending |
| 04-02-01 | 02 | 1 | RETR-05 | unit | `pytest tests/test_grep.py::test_extract_keywords -x` | W0 | pending |
| 04-02-02 | 02 | 1 | RETR-05 | unit | `pytest tests/test_grep.py::test_extract_keywords_fallback -x` | W0 | pending |
| 04-02-03 | 02 | 1 | RETR-06 | unit | `pytest tests/test_grep.py::test_grep_live_matches -x` | W0 | pending |
| 04-02-04 | 02 | 1 | RETR-06 | unit | `pytest tests/test_grep.py::test_grep_live_cap -x` | W0 | pending |
| 04-02-05 | 02 | 1 | RETR-06 | unit | `pytest tests/test_grep.py::test_grep_text_cache -x` | W0 | pending |
| 04-03-01 | 03 | 2 | RETR-07 | unit | `pytest tests/test_reindex.py::test_surgical_replacement -x` | W0 | pending |
| 04-03-02 | 03 | 2 | RETR-07 | unit | `pytest tests/test_reindex.py::test_cache_invalidation -x` | W0 | pending |
| 04-04-01 | 04 | 2 | CHAT-05 | integration | `pytest tests/test_chat_endpoint.py::test_staleness_event -x` | W0 | pending |
| 04-04-02 | 04 | 2 | CHAT-05 | unit (fe) | `pnpm test -- --run tests/staleness-banner.test.ts` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_staleness.py` -- check_staleness, staleness cache, hybrid partition, error handling stubs
- [ ] `tests/test_grep.py` -- extract_keywords, grep_live, grep text cache, keyword fallback stubs
- [ ] `tests/test_reindex.py` -- surgical replacement, cache invalidation, indexed_at return stubs
- [ ] `tests/test_chat_endpoint.py::test_staleness_event` -- SSE staleness event emission (extend existing)
- [ ] `frontend/tests/staleness-banner.test.ts` -- banner variants (yellow/red/orange), re-index button states

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Yellow banner appears above streaming response | CHAT-05 | Visual layout positioning | Send chat with stale file, verify banner renders above response text |
| Re-index spinner and button disable | RETR-07 | Animation/interaction timing | Click re-index, verify spinner, verify send disabled, verify toast on success |
| Banner color variants (yellow/red/orange) | CHAT-05 | Visual styling verification | Trigger each error state, verify correct color |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
