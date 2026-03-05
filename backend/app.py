"""Modal app + FastAPI with CORS, Volume, secrets, health endpoint."""
import modal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = modal.App("talk-to-a-folder")
volume = modal.Volume.from_name("talk-to-a-folder-data", create_if_missing=True)

web_app = FastAPI()

from backend.chat import router as chat_router  # noqa: E402
from backend.index import router as index_router  # noqa: E402
from backend.reindex import router as reindex_router  # noqa: E402

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
    """Health check endpoint."""
    return {"status": "ok"}


@app.function(
    volumes={"/data": volume},
    image=modal.Image.debian_slim().pip_install(
        "fastapi", "aiohttp", "openai", "numpy", "pymupdf"
    ),
    secrets=[
        modal.Secret.from_name("openai-secret"),
        modal.Secret.from_name("deepseek-secret"),
    ],
    timeout=600,
)
@modal.asgi_app()
def fastapi_app():
    """Serve the FastAPI app on Modal."""
    return web_app
