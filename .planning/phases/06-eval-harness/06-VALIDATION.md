---
phase: 6
slug: eval-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (already configured) |
| **Config file** | backend/requirements.txt includes pytest, pytest-asyncio |
| **Quick run command** | `python -m pytest eval/tests/ -x -q` |
| **Full suite command** | `python -m pytest eval/tests/ -v` |
| **Estimated runtime** | ~5 seconds (unit tests only, no API calls) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest eval/tests/ -x -q`
- **After every plan wave:** Run `python -m pytest eval/tests/ -v && python -m pytest backend/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | EVAL-03 | unit | `python -m pytest eval/tests/test_scoring.py -x` | No - W0 | pending |
| 06-01-02 | 01 | 0 | EVAL-02 | unit | `python -m pytest eval/tests/test_classify.py -x` | No - W0 | pending |
| 06-01-03 | 01 | 0 | EVAL-01 | unit | `python -m pytest eval/tests/test_dataset.py -x` | No - W0 | pending |
| 06-01-04 | 01 | 0 | EVAL-04 | unit | `python -m pytest eval/tests/test_drive_delta.py -x` | No - W0 | pending |
| 06-02-01 | 02 | 1 | EVAL-01 | integration | `python eval/run_eval.py --dry-run` | No - W1 | pending |
| 06-02-02 | 02 | 1 | EVAL-02 | integration | `python eval/run_eval.py --dry-run` | No - W1 | pending |
| 06-03-01 | 03 | 2 | EVAL-03 | integration | `python eval/run_eval.py` | No - W2 | pending |
| 06-03-02 | 03 | 2 | EVAL-04 | integration | `python eval/run_drive_delta.py` | No - W2 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `eval/tests/test_scoring.py` — unit tests for normalize_answer, token_f1, exact_match, score_answer
- [ ] `eval/tests/test_classify.py` — unit tests for CRAWL_MISS, RETRIEVAL_MISS, SYNTHESIS_FAIL heuristics
- [ ] `eval/tests/test_dataset.py` — unit tests for QASPER paper selection, answer extraction
- [ ] `eval/tests/test_drive_delta.py` — unit tests for delta calculation, threshold check
- [ ] `eval/tests/__init__.py` — package init
- [ ] `eval/tests/conftest.py` — shared fixtures (sample chunks, embeddings, QASPER-like data)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full eval run with real QASPER data | EVAL-01 | Requires QASPER download + OpenAI API | `python eval/run_eval.py` with local uvicorn running |
| Drive delta comparison | EVAL-04 | Requires manual PDF upload to Drive | Upload 5 PDFs to Drive, configure eval/config.json, run `python eval/run_drive_delta.py` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
