---
phase: 5
slug: multi-session-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.0.18 + jsdom + @testing-library/react (frontend), pytest + pytest-asyncio + httpx (backend) |
| **Config file** | `frontend/vitest.config.ts` (frontend), `backend/pytest.ini` or inline (backend) |
| **Quick run command** | `cd frontend && pnpm test` / `cd backend && python -m pytest tests/ -x` |
| **Full suite command** | `cd frontend && pnpm test && cd ../backend && python -m pytest tests/` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && pnpm test` or `cd backend && python -m pytest tests/ -x` (whichever is relevant)
- **After every plan wave:** Run `cd frontend && pnpm test && cd ../backend && python -m pytest tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | UI-02 | unit | `cd frontend && pnpm vitest run src/components/app-shell/Sidebar.test.tsx -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | UI-03 | unit | `cd frontend && pnpm vitest run src/components/app-shell/AppShell.test.tsx -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | UI-04 | unit | `cd frontend && pnpm vitest run src/components/app-shell/SidebarItem.test.tsx -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | UI-10, INDX-13 | unit | `cd frontend && pnpm vitest run src/components/app-shell/DuplicateNotice.test.tsx -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | INDX-14 | unit | `cd backend && python -m pytest tests/test_storage.py -x` | ✅ (extend) | ⬜ pending |
| 05-03-01 | 03 | 3 | UI-08 | unit | `cd frontend && pnpm vitest run src/components/app-shell/AppShell.test.tsx -x` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 3 | UI-09, INFR-03 | unit | `cd backend && python -m pytest tests/test_chat_endpoint.py -x` | ✅ (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/app-shell/Sidebar.test.tsx` — stubs for UI-02
- [ ] `frontend/src/components/app-shell/SidebarItem.test.tsx` — stubs for UI-04
- [ ] `frontend/src/components/app-shell/DuplicateNotice.test.tsx` — stubs for UI-10
- [ ] `frontend/src/components/app-shell/AppShell.test.tsx` — stubs for UI-03, UI-08
- [ ] Extend `frontend/src/lib/db.test.ts` — stubs for deleteChat, updateChatTitle (INDX-13)
- [ ] Extend `backend/tests/test_chat_endpoint.py` — stubs for rate limiting (INFR-03)
- [ ] Extend `backend/tests/test_storage.py` — stubs for append logic (INDX-14)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Duplicate notice card renders with correct chat name | UI-10 | Visual styling | Paste a previously indexed Drive link, verify yellow/amber card appears below input |
| Toast color coding (red vs amber) | UI-08 | Visual styling | Trigger 403, 404 (red) and empty folder (amber) errors, verify correct colors |
| Inline rename focus and escape behavior | UI-04 | Focus management | Click rename on sidebar item, verify input focused, press Escape to cancel |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
