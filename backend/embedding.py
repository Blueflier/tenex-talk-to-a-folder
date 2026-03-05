"""Batch embedding via OpenAI text-embedding-3-small with progress and retry."""

import asyncio
from typing import Callable, Optional

import numpy as np
from openai import AsyncOpenAI

BATCH_SIZE = 100
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536


async def embed_chunks(
    client: AsyncOpenAI,
    chunks: list[dict],
    on_progress: Optional[Callable] = None,
    max_retries: int = 3,
) -> np.ndarray:
    """Embed chunk texts in batches of BATCH_SIZE. Returns (n, EMBED_DIM) float32 array."""
    if not chunks:
        return np.empty((0, EMBED_DIM), dtype=np.float32)

    all_embeddings: list[list[float]] = []
    total = len(chunks)

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        for attempt in range(max_retries):
            try:
                response = await client.embeddings.create(
                    model=EMBED_MODEL,
                    input=texts,
                )
                batch_embeddings = [e.embedding for e in response.data]
                all_embeddings.extend(batch_embeddings)
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

        if on_progress:
            await on_progress(min(i + BATCH_SIZE, total), total)

    return np.array(all_embeddings, dtype=np.float32)
