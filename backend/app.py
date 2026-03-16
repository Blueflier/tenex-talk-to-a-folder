"""FastAPI app with CORS and health endpoint."""
import logging
from collections import deque
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


# ── In-memory log ring buffer ────────────────────────────────────
class _RingBufferHandler(logging.Handler):
    """Stores recent log records in a fixed-size deque, queryable via /debug/logs."""

    def __init__(self, capacity: int = 2000):
        super().__init__()
        self.buffer: deque[dict] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })


_log_buffer = _RingBufferHandler(capacity=2000)
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), _log_buffer])
# Also attach to uvicorn loggers (they configure their own handlers)
for _name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(_name).addHandler(_log_buffer)

from fastapi import FastAPI, Query
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
    allow_origins=["http://localhost:5173", "https://tenex-talk-to-a-folder.vercel.app", "https://tenex-talk-to-a-folder.fly.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@web_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@web_app.get("/debug/logs")
async def debug_logs(
    level: str = Query(None, description="Filter by log level (INFO, WARNING, ERROR)"),
    search: str = Query(None, description="Case-insensitive text search in message"),
    logger_name: str = Query(None, alias="logger", description="Filter by logger name"),
    limit: int = Query(100, description="Max entries to return"),
):
    """Return recent in-memory logs. No file needed — queryable ring buffer."""
    logs = list(_log_buffer.buffer)
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    if search:
        s = search.lower()
        logs = [l for l in logs if s in l["msg"].lower()]
    if logger_name:
        logs = [l for l in logs if logger_name in l["logger"]]
    return logs[-limit:]
