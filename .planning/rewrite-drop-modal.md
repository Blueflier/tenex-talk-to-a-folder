# Rewrite: Drop Modal, Pure FastAPI + Local Disk

Branch: `rewrite/drop-modal-fastapi`
Goal: Remove all Modal dependencies. Run as a plain FastAPI app with uvicorn and local disk storage. All existing tests must pass after changes.

---

## Context

The app is a RAG chat tool: React frontend + Python backend. The backend is FastAPI wrapped in Modal. Modal provides:
1. **`modal.App` / `@modal.asgi_app()`** — container orchestration (app.py)
2. **`modal.Volume`** — persistent disk at `/data` with `.commit()` / `.reload()` semantics
3. **`modal.Image`** — dependency declaration (pip_install)
4. **`modal.Secret`** — env var injection (OPENAI_API_KEY, DEEPSEEK_API_KEY)

The storage layer is simple: numpy `.npy` files + `.json` files written to `VOLUME_PATH`. No vector DB. Removing Modal means replacing these 4 things with standard equivalents.

---

## Files to Change (in order)

### 1. `backend/app.py` — REWRITE (the core change)

**Current:** Defines `modal.App`, `modal.Volume`, wraps FastAPI with `@modal.asgi_app()` and `@app.function()`.

**Target:** Plain FastAPI app served by uvicorn. No modal imports.

```python
"""FastAPI app with CORS and health endpoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.chat import router as chat_router
from backend.index import router as index_router
from backend.reindex import router as reindex_router

web_app = FastAPI()

web_app.include_router(chat_router)
web_app.include_router(index_router)
web_app.include_router(reindex_router)

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@web_app.get("/health")
async def health():
    return {"status": "ok"}
```

- DELETE: `modal.App`, `modal.Volume.from_name`, `modal.Image`, `modal.Secret`, `@app.function()`, `@modal.asgi_app()`, the `volume` export, the `fastapi_app()` function.
- KEEP: `web_app` (the FastAPI instance), all routers, CORS config, health endpoint.
- DO NOT add a `if __name__` block here — that goes in a new file.

### 2. `backend/config.py` — EDIT

**Change `VOLUME_PATH`** from `/data` to a local path:
```python
VOLUME_PATH = Path(os.environ.get("DATA_DIR", "./data"))
```
This lets the path be configured via env var, defaulting to `./data` relative to CWD.

### 3. `backend/storage.py` — EDIT

**Remove the `volume` parameter** from all three functions (`save_session`, `load_session`, `append_session`). Remove all `volume.commit()` calls. The functions should just read/write to disk — no commit step needed for local filesystem.

Specific changes:
- `save_session`: Remove `volume` param, remove `volume.commit()` call (line 41)
- `load_session`: No `volume` param currently — no change needed
- `append_session`: Remove `volume` param, update internal `save_session` call to not pass `volume`

### 4. `backend/index.py` — EDIT

- **Line 237**: Remove `from backend.app import volume as app_volume`
- **Line 208**: Change `append_session(user_id, session_id, embeddings, all_chunks, volume)` → `append_session(user_id, session_id, embeddings, all_chunks)`
- **Line 62**: Remove `volume` param from `_index_event_stream` signature
- **Line 240**: Update the call to `_index_event_stream` — remove `app_volume` argument

### 5. `backend/chat.py` — EDIT

- **Line 136-138**: Remove these three lines entirely:
  ```python
  from backend.app import volume as app_volume
  app_volume.reload()
  ```
  The `_load_session_data` function just reads files from disk — no volume reload needed.

### 6. `backend/reindex.py` — EDIT

- **Line 109**: Remove `volume.commit()`
- **Lines 56-61**: Remove `volume` param from `reindex_file` signature
- **Line 151**: Remove `from backend.app import volume as app_volume`
- **Lines 153-159**: Remove `volume=app_volume` from the `reindex_file(...)` call

### 7. `backend/tests/test_storage.py` — EDIT

- Remove `mock_volume` fixture and all `mock_volume` params from test functions
- Remove `test_volume_commit_called_once` test entirely (no volume to commit)
- Update all `save_session(...)` and `append_session(...)` calls: remove the `mock_volume` argument

### 8. `backend/tests/test_index_endpoint.py` — EDIT

- **Lines 13-21**: DELETE the entire Modal mock block (`_modal_mock = MagicMock()` ... `sys.modules["modal"] = _modal_mock`)
- The import `from backend.app import web_app` should now work without mocking since app.py no longer imports modal
- Remove `_mock_volume()` helper (line 98-99) if it exists

### 9. `backend/tests/test_chat_endpoint.py` — EDIT

- **Lines 12-24**: DELETE the entire Modal mock block (same pattern as test_index_endpoint.py)
- The import `from backend.app import web_app` should now work without mocking

### 10. New file: `backend/run.py` — CREATE

Entry point for local development:
```python
"""Local development server entry point."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app:web_app", host="0.0.0.0", port=8000, reload=True)
```

### 11. New file: `requirements.txt` — CREATE

Extract from Modal's `pip_install` plus existing imports:
```
fastapi
uvicorn[standard]
aiohttp
openai
numpy
pymupdf
httpx
pytest
pytest-asyncio
```

### 12. New file: `.env.example` — CREATE

```
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
DATA_DIR=./data
ACTIVE_MODEL=deepseek
```

### 13. `backend/storage.py` line 8 — EDIT

Change `VOLUME_PATH = Path("/data")` to import from config:
```python
from backend.config import VOLUME_PATH
```
Remove the local `VOLUME_PATH = Path("/data")` definition. (config.py is the single source of truth.)

---

## What NOT to change

- `backend/drive.py` — no Modal references
- `backend/drive_client.py` — no Modal references
- `backend/auth.py` — no Modal references
- `backend/chunking.py` — no Modal references
- `backend/embedding.py` — no Modal references
- `backend/grep.py` — no Modal references
- `backend/staleness.py` — no Modal references
- `backend/retrieval.py` — no Modal references
- `frontend/` — no changes needed
- `.planning/` — no changes needed

---

## Verification

After all changes, run:
```bash
cd /Users/josephhartono/src/tenex-talk-to-a-folder
python -m pytest backend/tests/ -v
```

All existing tests must pass. No new tests are needed — this is a pure infrastructure swap with identical behavior.

Also verify:
```bash
python -c "from backend.app import web_app; print('import ok')"
```
This should succeed without any `ModuleNotFoundError: No module named 'modal'`.

---

## Summary of Modal touchpoints being removed

| Symbol | File(s) | Replacement |
|--------|---------|-------------|
| `import modal` | app.py | delete |
| `modal.App(...)` | app.py | delete |
| `modal.Volume.from_name(...)` | app.py | delete (local disk) |
| `modal.Image.debian_slim().pip_install(...)` | app.py | requirements.txt |
| `modal.Secret.from_name(...)` | app.py | .env / env vars |
| `@modal.asgi_app()` | app.py | uvicorn CLI |
| `@app.function(...)` | app.py | delete |
| `volume.commit()` | storage.py, reindex.py | delete (no-op on local disk) |
| `volume.reload()` | chat.py | delete (no-op on local disk) |
| `from backend.app import volume` | index.py, chat.py, reindex.py | delete |
| `volume` param | storage.py, index.py, reindex.py | remove from signatures |
| `sys.modules["modal"] = mock` | test_index_endpoint.py, test_chat_endpoint.py | delete |
