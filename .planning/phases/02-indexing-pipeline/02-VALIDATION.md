---
phase: 2
slug: indexing-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + Vitest (frontend) |
| **Config file** | pytest.ini / vitest.config.ts (from Phase 1) |
| **Quick run command** | `pytest tests/ -x` / `pnpm vitest run` |
| **Full suite command** | `pytest tests/` / `pnpm vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x` (backend) / `pnpm vitest run` (frontend)
- **After every plan wave:** Run full suite both frontend and backend
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | INDX-01 | unit | `pytest tests/test_drive.py::test_extract_drive_id -x` | W0 | pending |
| 02-01-02 | 01 | 1 | INDX-02 | unit (mock) | `pytest tests/test_drive.py::test_list_folder -x` | W0 | pending |
| 02-01-03 | 01 | 1 | INDX-03 | unit (mock) | `pytest tests/test_drive.py::test_export_doc -x` | W0 | pending |
| 02-01-04 | 01 | 1 | INDX-08 | unit | `pytest tests/test_drive.py::test_unsupported_mime -x` | W0 | pending |
| 02-01-05 | 01 | 1 | INDX-04 | unit | `pytest tests/test_chunking.py::test_chunk_pdf -x` | W0 | pending |
| 02-01-06 | 01 | 1 | INDX-05 | unit | `pytest tests/test_chunking.py::test_chunk_sheet -x` | W0 | pending |
| 02-01-07 | 01 | 1 | INDX-06 | unit | `pytest tests/test_chunking.py::test_chunk_slides -x` | W0 | pending |
| 02-01-08 | 01 | 1 | INDX-07 | unit | `pytest tests/test_chunking.py::test_recursive_chunk -x` | W0 | pending |
| 02-01-09 | 01 | 1 | INDX-10 | unit (mock) | `pytest tests/test_embedding.py::test_batch_embed -x` | W0 | pending |
| 02-01-10 | 01 | 1 | INDX-11 | unit | `pytest tests/test_storage.py::test_save_session -x` | W0 | pending |
| 02-01-11 | 01 | 1 | INDX-12 | unit (mock) | `pytest tests/test_storage.py::test_commit_called -x` | W0 | pending |
| 02-01-12 | 01 | 1 | INDX-09 | integration | `pytest tests/test_index_endpoint.py -x` | W0 | pending |
| 02-02-01 | 02 | 2 | UI-05 | unit | `pnpm vitest run src/components/chat/ChatInput.test.tsx` | W0 | pending |
| 02-02-02 | 02 | 2 | UI-06 | unit | `pnpm vitest run src/components/indexing/IndexingModal.test.tsx` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_drive.py` — stubs for INDX-01, INDX-02, INDX-03, INDX-08
- [ ] `backend/tests/test_chunking.py` — stubs for INDX-04, INDX-05, INDX-06, INDX-07
- [ ] `backend/tests/test_embedding.py` — stubs for INDX-10
- [ ] `backend/tests/test_storage.py` — stubs for INDX-11, INDX-12
- [ ] `backend/tests/test_index_endpoint.py` — stubs for INDX-09
- [ ] `frontend/src/components/chat/ChatInput.test.tsx` — stubs for UI-05
- [ ] `frontend/src/components/indexing/IndexingModal.test.tsx` — stubs for UI-06
- [ ] `pip install pymupdf` — new backend dependency
- [ ] `pnpm dlx shadcn@latest add progress` — new frontend component
- [ ] `backend/tests/fixtures/sample.pdf` — test fixture for PyMuPDF tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Modal auto-dismisses after success | UI-06 | Animation timing | Verify modal shows "Indexed N files" then auto-closes after ~1-2s |
| Cancel discards partial data | UI-06 | State cleanup across systems | Start indexing, cancel mid-stream, verify no orphaned data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
