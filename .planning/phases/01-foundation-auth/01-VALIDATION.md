---
phase: 1
slug: foundation-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (frontend) + pytest (backend) |
| **Config file** | None — Wave 0 installs |
| **Quick run command** | `pnpm test -- --run` (frontend), `pytest tests/ -x` (backend) |
| **Full suite command** | `pnpm test -- --run && pytest tests/` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pnpm test -- --run` (frontend) or `pytest tests/ -x` (backend)
- **After every plan wave:** Run `pnpm test -- --run && pytest tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | INFR-01 | smoke | `modal run backend/app.py` | No | pending |
| 01-02-01 | 02 | 1 | AUTH-01 | manual-only | N/A — requires Google consent screen | No | pending |
| 01-02-02 | 02 | 1 | AUTH-02 | unit | `pnpm test src/lib/api.test.ts` | Wave 0 | pending |
| 01-02-03 | 02 | 1 | AUTH-03 | unit | `pnpm test src/lib/api.test.ts` | Wave 0 | pending |
| 01-02-04 | 02 | 1 | AUTH-04 | unit | `pytest tests/test_auth.py -x` | Wave 0 | pending |
| 01-03-01 | 03 | 1 | UI-01 | unit | `pnpm test src/components/landing/Landing.test.tsx` | Wave 0 | pending |
| 01-03-02 | 03 | 1 | PERS-01 | unit | `pnpm test src/lib/db.test.ts` | Wave 0 | pending |
| 01-03-03 | 03 | 1 | PERS-02 | unit | `pnpm test src/lib/db.test.ts` | Wave 0 | pending |
| 01-03-04 | 03 | 1 | PERS-03 | unit | `pnpm test src/lib/db.test.ts` | Wave 0 | pending |
| 01-04-01 | 04 | 1 | INFR-02 | unit | `pytest tests/test_cors.py -x` | Wave 0 | pending |
| 01-04-02 | 04 | 1 | INFR-04 | unit | `pytest tests/test_config.py -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — Vitest configuration with jsdom
- [ ] `frontend/src/lib/api.test.ts` — stubs for AUTH-02, AUTH-03
- [ ] `frontend/src/lib/db.test.ts` — stubs for PERS-01, PERS-02, PERS-03 (needs fake-indexeddb)
- [ ] `frontend/src/components/landing/Landing.test.tsx` — stubs for UI-01
- [ ] `backend/tests/test_auth.py` — stubs for AUTH-04
- [ ] `backend/tests/test_config.py` — stubs for INFR-04
- [ ] `backend/tests/test_cors.py` — stubs for INFR-02
- [ ] `pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom fake-indexeddb` — frontend test deps
- [ ] `pip install pytest pytest-asyncio httpx` — backend test deps

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Google OAuth consent flow completes and returns access token | AUTH-01 | Requires real Google consent screen interaction | 1. Click "Sign in with Google" 2. Complete OAuth consent 3. Verify sessionStorage has access_token |
| Modal app deploys and serves /health | INFR-01 | Requires Modal deployment | 1. Run `modal deploy backend/app.py` 2. Hit /health endpoint 3. Verify 200 response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
