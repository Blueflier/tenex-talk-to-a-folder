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
    allow_origins=["http://localhost:5173", "https://tenex-talk-to-a-folder.fly.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@web_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
