# Phase 2: Indexing Pipeline - Research

**Researched:** 2026-03-05
**Domain:** Google Drive API file resolution/export, PDF/text extraction, chunking strategies, OpenAI embeddings, SSE streaming, Modal Volume storage
**Confidence:** HIGH

## Summary

Phase 2 builds the full indexing pipeline: user pastes a Drive link, backend resolves it to files, extracts content per type, chunks with type-specific strategies, embeds via OpenAI, stores to Modal Volume, and streams progress via SSE. The CONTEXT.md provides very specific UI decisions (modal overlay, file list with status badges, single embedding progress bar, cancel support, partial failure handling). The spec provides code samples for chunking, embedding, and storage that should be followed closely.

Key technical areas: (1) Google Drive API v3 for link resolution and file export using aiohttp with the user's access token, (2) PyMuPDF for PDF page-by-page extraction, (3) recursive character splitting for text chunking, (4) OpenAI text-embedding-3-small batch embedding, (5) FastAPI native SSE (EventSourceResponse added in 0.135.0) for two-phase progress streaming, (6) numpy .npy + JSON storage on Modal Volume with volume.commit().

**Primary recommendation:** Follow the spec's code samples directly for chunking and embedding. Use FastAPI's native EventSourceResponse for SSE (no sse-starlette dependency needed). Use aiohttp for all Drive API calls (already in Phase 1 deps). Parse Drive URLs with a regex to extract file/folder IDs.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Minimal list layout during extraction: file icon + name + status badge (extracting/done/skipped/queued)
- Unsupported files collapsed into a summary line at bottom: "3 files skipped (unsupported types)" with expand option
- Single progress bar for embedding phase: "Embedding chunks... 200/312 chunks"
- Indexing progress shown in an overlay/modal, not inline in chat
- Best-effort approach: continue indexing whatever succeeds, warn about failures
- Failed files shown inline in the file list with red status and error reason
- Per-file status granularity when embedding fails after retries (show which files are fully/partially/not indexed)
- Drive link validation happens immediately before opening the modal (inline error near input for invalid/inaccessible links)
- Empty folders vs no-supported-files get distinct error messages (toast + empty chat for both, different wording)
- Cancel button available during indexing; cancellation discards all partial data (clean slate)
- Soft file size limit with warning (e.g., 50MB) but still processes large files
- Embedding failure: retry batch 2-3 times, then save what was embedded and let user chat with partial index
- Modal auto-dismisses after brief success state (~1-2s showing "Indexed 8 files (312 chunks)")
- Chat header shows persistent summary: "8 files indexed - 312 chunks"
- Context-aware chat input placeholder: "Ask about Q3-Report.pdf, Budget.xlsx, and 6 more..."
- Chat title deferred to Phase 5 (use generic "New Chat" for now)
- Zero successful files: toast notification with error, land on empty chat explaining what happened
- Chat input locked until indexing completes

### Claude's Discretion
- Exact modal design and animations within shadcn/ui conventions
- Status badge styling and colors
- Progress bar component choice
- Success state animation/transition timing
- File icon selection by type
- Soft size limit threshold (suggested ~50MB)
- Retry timing and backoff strategy for embedding failures
- Toast notification styling and duration

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INDX-01 | User can paste a Google Drive link (folder or single file) to start indexing | Drive URL regex parsing + validation via Drive API files.get |
| INDX-02 | Backend resolves Drive link to file list via Drive API | files.list with `'{folder_id}' in parents` query, fields=id,name,mimeType,size |
| INDX-03 | Google Docs exported as plain text via Drive export API | files.export with mimeType=text/plain |
| INDX-04 | PDFs extracted page-by-page via PyMuPDF with recursive chunking per page | pymupdf.open() + page.get_text("text") per page |
| INDX-05 | Google Sheets exported as CSV, chunked row-level with headers prepended | files.export with mimeType=text/csv, split rows, prepend header row to each chunk |
| INDX-06 | Google Slides exported as plain text, split per slide on double newline | files.export with mimeType=text/plain, split on \n\n |
| INDX-07 | TXT/MD files chunked with recursive character splitter (1200 chars, 150 overlap) | recursive_chunk() function with configurable params |
| INDX-08 | Unsupported files detected and skipped with reason | mimeType check against supported set |
| INDX-09 | Two-phase SSE progress streaming (extraction per-file, then embedding per-chunk) | FastAPI EventSourceResponse with typed SSE events |
| INDX-10 | Chunks embedded in batches of 100 via OpenAI text-embedding-3-small | openai.embeddings.create with input list of up to 100 texts |
| INDX-11 | Embeddings (.npy) and chunks (.json) saved to Modal Volume namespaced by user_id/session_id | np.save() + json.dump() at /data/{user_id}/{session_id}_*.npy/json |
| INDX-12 | volume.commit() called after every write | volume.commit() after np.save and json.dump |
| UI-05 | Chat input bar with Drive link paste zone | Frontend input component with URL detection and paste handling |
| UI-06 | Indexing progress: two-phase progress bars (extraction, embedding) | Modal overlay with file list (phase 1) and single progress bar (phase 2) |

</phase_requirements>

## Standard Stack

### Core -- Backend (new deps for Phase 2)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pymupdf | latest (1.25.x) | PDF text extraction | Fast, pure-python wheel, page-by-page API, specified in INDX-04 |
| openai | latest (already from Phase 1) | Embeddings API client | text-embedding-3-small batch embedding |
| numpy | latest (already from Phase 1) | Embedding storage | .npy format for dense vectors |
| aiohttp | latest (already from Phase 1) | Google Drive API calls | Async HTTP for Drive file listing/export |

### Core -- Frontend (new deps for Phase 2)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| shadcn/ui progress | latest | Progress bar component | Consistent with existing UI library |
| shadcn/ui dialog | latest (already from Phase 1) | Indexing modal overlay | Already installed |
| lucide-react | latest (already from Phase 1) | File type icons | Already installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyMuPDF | pdfplumber | pdfplumber is slower, heavier; PyMuPDF specified in requirements |
| FastAPI native SSE | sse-starlette | Native EventSourceResponse added in FastAPI 0.135.0, no extra dep needed |
| aiohttp for Drive | google-api-python-client | google-api-python-client is sync; aiohttp already in deps and works async |
| Raw fetch SSE parsing | @microsoft/fetch-event-source | Spec says "fetch + ReadableStream", not a library; raw parsing is simpler for our event shapes |

**Installation -- Backend (additions to requirements.txt):**
```bash
pip install pymupdf
```

**Installation -- Frontend:**
```bash
pnpm dlx shadcn@latest add progress
```

## Architecture Patterns

### Recommended Project Structure (additions to Phase 1)
```
backend/
  app.py               # Add POST /index endpoint
  auth.py              # Existing (from Phase 1)
  config.py            # Existing (from Phase 1)
  drive.py             # Drive link resolution + file export
  chunking.py          # Type-specific chunking strategies
  embedding.py         # OpenAI batch embedding
  storage.py           # Modal Volume save/load

frontend/
  src/
    components/
      indexing/
        IndexingModal.tsx     # Overlay modal for indexing progress
        FileList.tsx          # File cards with status badges
        EmbeddingProgress.tsx # Single progress bar for embedding phase
      chat/
        ChatInput.tsx         # Drive link paste zone + message input
        ChatHeader.tsx        # "8 files indexed - 312 chunks" summary
    lib/
      api.ts           # Existing -- add streamIndex() for SSE
      sse.ts           # SSE parsing utilities for fetch ReadableStream
```

### Pattern 1: Drive Link Resolution
**What:** Parse Drive URL to extract file/folder ID, then resolve via Drive API
**When to use:** When user pastes a Drive link

```python
# backend/drive.py
import re
from typing import Optional

DRIVE_URL_PATTERN = re.compile(r"[-\w]{25,}")
DRIVE_FOLDER_PATTERN = re.compile(r"/folders/([-\w]+)")
DRIVE_FILE_PATTERN = re.compile(r"/d/([-\w]+)")

SUPPORTED_MIME_TYPES = {
    "application/vnd.google-apps.document",    # Google Docs
    "application/vnd.google-apps.spreadsheet", # Google Sheets
    "application/vnd.google-apps.presentation",# Google Slides
    "application/pdf",
    "text/plain",
    "text/markdown",
}

SKIP_REASONS = {
    "image/": "Image files are not supported",
    "video/": "Video files are not supported",
    "application/zip": "ZIP archives are not supported",
    "application/x-zip": "ZIP archives are not supported",
}

def extract_drive_id(url: str) -> Optional[str]:
    """Extract file or folder ID from a Google Drive URL."""
    # Try specific patterns first
    m = DRIVE_FOLDER_PATTERN.search(url)
    if m:
        return m.group(1)
    m = DRIVE_FILE_PATTERN.search(url)
    if m:
        return m.group(1)
    # Fallback: any 25+ char alphanumeric string
    m = DRIVE_URL_PATTERN.search(url)
    if m:
        return m.group(0)
    return None

async def resolve_drive_link(access_token: str, drive_id: str) -> dict:
    """Get metadata for a file/folder. Returns {id, name, mimeType}."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://www.googleapis.com/drive/v3/files/{drive_id}",
            params={"fields": "id,name,mimeType,size"},
            headers={"Authorization": f"Bearer {access_token}"},
        ) as r:
            if r.status == 404:
                raise ValueError("File or folder not found")
            if r.status == 403:
                raise PermissionError("No access to this file/folder")
            r.raise_for_status()
            return await r.json()

async def list_folder_files(access_token: str, folder_id: str) -> list[dict]:
    """List all files in a folder (non-recursive)."""
    files = []
    page_token = None
    async with aiohttp.ClientSession() as session:
        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, size)",
                "pageSize": 100,
            }
            if page_token:
                params["pageToken"] = page_token
            async with session.get(
                "https://www.googleapis.com/drive/v3/files",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as r:
                r.raise_for_status()
                data = await r.json()
                files.extend(data.get("files", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
    return files
```

### Pattern 2: Type-Specific File Export
**What:** Export Google Workspace files to processable formats via Drive API
**When to use:** During extraction phase

```python
# backend/drive.py (continued)

EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

async def export_file(access_token: str, file_id: str, mime_type: str) -> bytes:
    """Export a Google Workspace file or download a binary file."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        if mime_type in EXPORT_MIME_MAP:
            # Google Workspace file -- use export endpoint
            export_mime = EXPORT_MIME_MAP[mime_type]
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            params = {"mimeType": export_mime}
        else:
            # Binary file (PDF, TXT, MD) -- use download endpoint
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {"alt": "media"}

        async with session.get(url, params=params, headers=headers) as r:
            r.raise_for_status()
            return await r.read()
```

### Pattern 3: Type-Specific Chunking
**What:** Different chunking strategies per file type as specified in requirements
**When to use:** After file content is extracted

```python
# backend/chunking.py

def recursive_chunk(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Recursive character splitter. Used for Docs, TXT, MD, and per-page PDF text."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks

def chunk_pdf(pdf_bytes: bytes, file_name: str) -> list[dict]:
    """Extract PDF page-by-page, chunk each page with recursive splitter."""
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    chunks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if not text.strip():
            continue
        page_chunks = recursive_chunk(text)
        for i, chunk_text in enumerate(page_chunks):
            chunks.append({
                "text": chunk_text,
                "source": file_name,
                "page": page_num + 1,
                "chunk_index": i,
            })
    doc.close()
    return chunks

def chunk_sheet(csv_text: str, file_name: str) -> list[dict]:
    """Row-level chunking with headers prepended to every row."""
    lines = csv_text.strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0]
    chunks = []
    for row_num, row in enumerate(lines[1:], start=2):
        chunk_text = f"{header}\n{row}"
        chunks.append({
            "text": chunk_text,
            "source": file_name,
            "row": row_num,
            "chunk_index": 0,
        })
    return chunks

def chunk_slides(text: str, file_name: str) -> list[dict]:
    """Split slides on double newline boundary."""
    slides = text.split("\n\n")
    chunks = []
    for slide_num, slide_text in enumerate(slides, start=1):
        if not slide_text.strip():
            continue
        chunks.append({
            "text": slide_text.strip(),
            "source": file_name,
            "slide": slide_num,
            "chunk_index": 0,
        })
    return chunks

def chunk_text(text: str, file_name: str) -> list[dict]:
    """Recursive chunking for plain text / markdown files."""
    raw_chunks = recursive_chunk(text)
    return [
        {"text": c, "source": file_name, "chunk_index": i}
        for i, c in enumerate(raw_chunks)
    ]
```

### Pattern 4: Batch Embedding
**What:** Embed chunks in batches of 100 using OpenAI text-embedding-3-small
**When to use:** After all chunks are produced

```python
# backend/embedding.py
import numpy as np
from openai import AsyncOpenAI

BATCH_SIZE = 100
EMBED_MODEL = "text-embedding-3-small"

async def embed_chunks(
    client: AsyncOpenAI,
    chunks: list[dict],
    on_progress: callable = None,
    max_retries: int = 3,
) -> np.ndarray:
    """Embed chunk texts in batches of 100. Returns (n, 1536) numpy array."""
    all_embeddings = []
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
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                import asyncio
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        if on_progress:
            await on_progress(min(i + BATCH_SIZE, total), total)

    return np.array(all_embeddings, dtype=np.float32)
```

### Pattern 5: Modal Volume Storage
**What:** Save embeddings and chunk metadata to Modal Volume
**When to use:** After embedding completes

```python
# backend/storage.py
import json
import numpy as np
from pathlib import Path

VOLUME_PATH = Path("/data")

def save_session(
    user_id: str,
    session_id: str,
    embeddings: np.ndarray,
    chunks: list[dict],
    volume,  # modal.Volume instance
):
    """Save embeddings and chunks to Modal Volume."""
    session_dir = VOLUME_PATH / user_id
    session_dir.mkdir(parents=True, exist_ok=True)

    emb_path = session_dir / f"{session_id}_embeddings.npy"
    chunks_path = session_dir / f"{session_id}_chunks.json"

    np.save(str(emb_path), embeddings)
    volume.commit()

    with open(chunks_path, "w") as f:
        json.dump(chunks, f)
    volume.commit()
```

### Pattern 6: SSE Progress Streaming (Backend)
**What:** Two-phase SSE events: extraction per-file, then embedding per-chunk
**When to use:** POST /index endpoint

```python
# In backend/app.py
from fastapi.sse import EventSourceResponse, ServerSentEvent
import json

@web_app.post("/index", response_class=EventSourceResponse)
async def index_drive(request: IndexRequest):
    async def event_stream():
        # Phase 1: Extraction
        for file in files:
            yield ServerSentEvent(
                data=json.dumps({
                    "file_id": file["id"],
                    "file_name": file["name"],
                    "status": "extracting",
                }),
                event="extraction",
            )
            # ... extract and chunk ...
            yield ServerSentEvent(
                data=json.dumps({
                    "file_id": file["id"],
                    "status": "done",  # or "skipped" or "failed"
                    "chunk_count": len(file_chunks),
                }),
                event="extraction",
            )

        # Phase 2: Embedding
        yield ServerSentEvent(
            data=json.dumps({"total_chunks": total_chunks}),
            event="embedding_start",
        )
        # ... embed in batches, yield progress ...
        yield ServerSentEvent(
            data=json.dumps({
                "embedded": current_count,
                "total": total_chunks,
            }),
            event="embedding_progress",
        )

        # Done
        yield ServerSentEvent(
            data=json.dumps({
                "files_indexed": files_indexed,
                "total_chunks": total_chunks,
            }),
            event="complete",
        )

    return event_stream()
```

### Pattern 7: SSE Consumption (Frontend)
**What:** Parse SSE events from POST /index response using fetch + ReadableStream
**When to use:** Frontend indexing flow

```typescript
// frontend/src/lib/sse.ts
export interface SSEEvent {
  event: string;
  data: string;
}

export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    let currentData = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7);
      } else if (line.startsWith("data: ")) {
        currentData = line.slice(6);
      } else if (line === "") {
        if (currentData) {
          yield { event: currentEvent, data: currentData };
          currentEvent = "";
          currentData = "";
        }
      }
    }
  }
}
```

### Anti-Patterns to Avoid
- **Using google-api-python-client in async context:** It is synchronous and will block the event loop. Use aiohttp for all Drive API calls.
- **Loading entire PDF into memory at once:** Use pymupdf.open(stream=bytes) to open from bytes; process page-by-page, don't concatenate all text first.
- **Embedding all chunks in one API call:** Batches of 100 avoid token limits and allow progress tracking. The API accepts arrays but has total token limits (~300K tokens per request).
- **Forgetting volume.commit() after writes:** Modal Volume writes are not durable without explicit commit.
- **Using EventSource API on frontend:** EventSource only supports GET. Since /index is POST, must use fetch + ReadableStream parsing.
- **Chunking CSV by character count:** Sheet chunks should be row-level with headers prepended, not character-split.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | PyMuPDF (pymupdf) | Handles encoding, fonts, layout; page-by-page API built in |
| Embedding computation | Custom embedding model | OpenAI text-embedding-3-small | Production quality, 1536 dims, fast, normalized vectors |
| SSE response formatting | Manual `text/event-stream` strings | FastAPI EventSourceResponse | Handles escaping, formatting, connection management |
| Drive API auth | Manual OAuth header management | aiohttp with Bearer token | Already established in Phase 1 |
| Progress bar UI | Custom progress component | shadcn/ui Progress | Accessible, styled consistently |

## Common Pitfalls

### Pitfall 1: Google Workspace Export Limits
**What goes wrong:** Export fails silently or returns truncated content for very large Google Docs/Sheets
**Why it happens:** Google Drive export API has a 10MB limit for exported content
**How to avoid:** Check file size before export. For large files, warn user but still attempt. Handle export errors gracefully with per-file failure status.
**Warning signs:** Empty or truncated text returned from export endpoint

### Pitfall 2: PDF with No Extractable Text (Scanned PDFs)
**What goes wrong:** page.get_text() returns empty string for scanned PDFs
**Why it happens:** Scanned PDFs contain images, not text layers
**How to avoid:** Check if extracted text is empty/near-empty after processing. Mark file as "skipped" with reason "Scanned PDF - no extractable text". This is explicitly out of scope per requirements (no OCR).
**Warning signs:** Zero chunks produced from a multi-page PDF

### Pitfall 3: CSV with Only Headers
**What goes wrong:** chunk_sheet produces zero chunks for single-row (header-only) CSV
**Why it happens:** Row-level chunking skips the header row itself
**How to avoid:** Return empty chunks list; mark file as having "no data rows"
**Warning signs:** Empty chunks from a file that exists and was exported

### Pitfall 4: SSE Connection Drops Mid-Stream
**What goes wrong:** Frontend stops receiving events but thinks stream is still active
**Why it happens:** Network interruption, Modal cold start timeout, long embedding phase
**How to avoid:** Implement heartbeat events during long operations. Frontend should set a timeout and show error if no event received within N seconds. Handle ReadableStream errors.
**Warning signs:** UI freezes on progress bar with no updates

### Pitfall 5: Race Condition on Cancel
**What goes wrong:** User cancels but backend has already written partial data to Volume
**Why it happens:** Cancel signal from frontend may not reach backend before write completes
**How to avoid:** Track session as "indexing" state. On cancel, clean up any partial files from Volume. Frontend discards all state on cancel (per CONTEXT.md: "clean slate").
**Warning signs:** Orphaned files on Volume after cancelled indexing

### Pitfall 6: Slides Export Double-Newline Ambiguity
**What goes wrong:** Splitting on "\n\n" produces too many or too few chunks depending on slide content
**Why it happens:** Google Slides plain text export format may use double newlines within slide content too
**How to avoid:** Filter out empty chunks after splitting. Accept that slide boundaries may not be perfectly detected -- this is a known limitation of plain text export.
**Warning signs:** Slide chunks with very short or empty content

### Pitfall 7: Modal Function Timeout During Large Indexing
**What goes wrong:** Modal function times out before indexing completes
**Why it happens:** Default Modal function timeout may be too short for large folders with many files
**How to avoid:** Set `timeout=600` (10 minutes) on the Modal function. Stream progress so user knows it's working.
**Warning signs:** Sudden connection drop with no error event

## Code Examples

### POST /index Request/Response Contract
```typescript
// Frontend request
const response = await fetch(`${API_BASE}/index`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    drive_url: "https://drive.google.com/drive/folders/abc123",
    session_id: "uuid-here",
  }),
});

// Parse SSE stream
for await (const event of parseSSE(response)) {
  switch (event.event) {
    case "extraction":
      const file = JSON.parse(event.data);
      // Update file list: { file_id, file_name, status, chunk_count?, error? }
      break;
    case "embedding_start":
      const { total_chunks } = JSON.parse(event.data);
      // Switch to embedding progress bar
      break;
    case "embedding_progress":
      const { embedded, total } = JSON.parse(event.data);
      // Update progress bar
      break;
    case "complete":
      const result = JSON.parse(event.data);
      // { files_indexed, total_chunks, skipped_files }
      break;
    case "error":
      // Handle fatal error
      break;
  }
}
```

### Drive URL Validation (Frontend)
```typescript
// frontend/src/lib/drive.ts
const DRIVE_URL_REGEX = /drive\.google\.com\/(drive\/folders\/|file\/d\/|open\?id=)([-\w]+)/;

export function isValidDriveUrl(url: string): boolean {
  return DRIVE_URL_REGEX.test(url);
}

export function extractDriveId(url: string): string | null {
  const match = url.match(DRIVE_URL_REGEX);
  return match ? match[2] : null;
}
```

### IndexedDB Update After Indexing
```typescript
// After successful indexing, update the chat record
import { openDB, type Chat } from "@/lib/db";

async function updateChatWithSources(
  sessionId: string,
  indexedSources: Array<{ file_id: string; file_name: string; indexed_at: string }>
) {
  const db = await openDB();
  const tx = db.transaction("chats", "readwrite");
  const store = tx.objectStore("chats");
  const chat = await new Promise<Chat>((resolve) => {
    const req = store.get(sessionId);
    req.onsuccess = () => resolve(req.result);
  });
  chat.indexed_sources = indexedSources;
  store.put(chat);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| sse-starlette package | FastAPI native EventSourceResponse | FastAPI 0.135.0 (late 2024) | No extra dependency needed |
| fitz (PyMuPDF old import) | pymupdf (new import name) | PyMuPDF 1.24+ (2024) | `import pymupdf` instead of `import fitz` |
| OpenAI text-embedding-ada-002 | text-embedding-3-small | Jan 2024 | Better quality, adjustable dimensions, cheaper |

**Deprecated/outdated:**
- `import fitz`: Use `import pymupdf` (fitz still works but pymupdf is the canonical import)
- `text-embedding-ada-002`: Replaced by text-embedding-3-small (better, cheaper)
- sse-starlette: Still works but FastAPI 0.135.0+ has native SSE support

## Open Questions

1. **FastAPI version on Modal**
   - What we know: FastAPI 0.135.0+ has native EventSourceResponse. Modal installs whatever version is in pip_install.
   - What's unclear: Whether pinning `fastapi>=0.135.0` in requirements is needed or if latest is fine
   - Recommendation: Pin `fastapi>=0.135.0` in requirements.txt to ensure native SSE support. If issues arise, fall back to sse-starlette.

2. **Google Slides Plain Text Export Format**
   - What we know: Export as text/plain is supported. Slides are separated somehow in the output.
   - What's unclear: Exact separator format (is it truly double-newline between slides?)
   - Recommendation: Implement with double-newline split per spec; filter empty chunks; test with real Slides files.

3. **Modal Function Timeout for Large Folders**
   - What we know: Default Modal timeout may be 300s. Large folders with many PDFs could take longer.
   - What's unclear: Exact default timeout; whether SSE stream survives timeout
   - Recommendation: Set `timeout=600` on the Modal function definition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (frontend) + pytest (backend) |
| Config file | frontend/vitest.config.ts + pytest (backend, from Phase 1) |
| Quick run command | `pnpm test` (frontend), `pytest tests/ -x` (backend) |
| Full suite command | `pnpm test -- --run` (frontend), `pytest tests/` (backend) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INDX-01 | Drive URL parsed to file/folder ID | unit | `pytest tests/test_drive.py::test_extract_drive_id -x` | Wave 0 |
| INDX-02 | Folder resolved to file list via Drive API | unit (mock aiohttp) | `pytest tests/test_drive.py::test_list_folder -x` | Wave 0 |
| INDX-03 | Google Docs exported as plain text | unit (mock) | `pytest tests/test_drive.py::test_export_doc -x` | Wave 0 |
| INDX-04 | PDF extracted page-by-page, chunked | unit | `pytest tests/test_chunking.py::test_chunk_pdf -x` | Wave 0 |
| INDX-05 | CSV chunked row-level with headers | unit | `pytest tests/test_chunking.py::test_chunk_sheet -x` | Wave 0 |
| INDX-06 | Slides split per slide on double newline | unit | `pytest tests/test_chunking.py::test_chunk_slides -x` | Wave 0 |
| INDX-07 | TXT/MD recursive chunked (1200/150) | unit | `pytest tests/test_chunking.py::test_recursive_chunk -x` | Wave 0 |
| INDX-08 | Unsupported mime types detected and skipped | unit | `pytest tests/test_drive.py::test_unsupported_mime -x` | Wave 0 |
| INDX-09 | SSE events stream in two phases | integration | `pytest tests/test_index_endpoint.py -x` | Wave 0 |
| INDX-10 | Chunks embedded in batches of 100 | unit (mock openai) | `pytest tests/test_embedding.py::test_batch_embed -x` | Wave 0 |
| INDX-11 | Embeddings + chunks saved to volume path | unit | `pytest tests/test_storage.py::test_save_session -x` | Wave 0 |
| INDX-12 | volume.commit() called after writes | unit (mock volume) | `pytest tests/test_storage.py::test_commit_called -x` | Wave 0 |
| UI-05 | Drive link input validates and triggers indexing | unit | `pnpm vitest run src/components/chat/ChatInput.test.tsx` | Wave 0 |
| UI-06 | Progress modal shows file list then embedding bar | unit | `pnpm vitest run src/components/indexing/IndexingModal.test.tsx` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x` (backend) / `pnpm vitest run` (frontend)
- **Per wave merge:** Full suite both frontend and backend
- **Phase gate:** Full suite green before /gsd:verify-work

### Wave 0 Gaps
- [ ] `backend/tests/test_drive.py` -- covers INDX-01, INDX-02, INDX-03, INDX-08
- [ ] `backend/tests/test_chunking.py` -- covers INDX-04, INDX-05, INDX-06, INDX-07
- [ ] `backend/tests/test_embedding.py` -- covers INDX-10
- [ ] `backend/tests/test_storage.py` -- covers INDX-11, INDX-12
- [ ] `backend/tests/test_index_endpoint.py` -- covers INDX-09 (integration test with TestClient)
- [ ] `frontend/src/components/chat/ChatInput.test.tsx` -- covers UI-05
- [ ] `frontend/src/components/indexing/IndexingModal.test.tsx` -- covers UI-06
- [ ] Framework install: `pip install pymupdf` (backend addition)
- [ ] Framework install: `pnpm dlx shadcn@latest add progress` (frontend addition)
- [ ] Test fixture: sample PDF file for PyMuPDF tests (`backend/tests/fixtures/sample.pdf`)

## Sources

### Primary (HIGH confidence)
- [Google Drive API v3 - Search files](https://developers.google.com/drive/api/guides/search-files) -- folder listing with `in parents` query
- [Google Drive API v3 - Export formats](https://developers.google.com/drive/api/guides/ref-export-formats) -- confirmed text/plain for Docs+Slides, text/csv for Sheets
- [Google Drive API v3 - Download/Export](https://developers.google.com/drive/api/guides/manage-downloads) -- files.get?alt=media for binary, files/export for Workspace
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings) -- text-embedding-3-small, 1536 dims, 8192 token limit, batch input
- [PyMuPDF docs](https://pymupdf.readthedocs.io/en/latest/page.html) -- page.get_text("text"), open from stream
- [FastAPI SSE docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/) -- EventSourceResponse, ServerSentEvent, added in 0.135.0

### Secondary (MEDIUM confidence)
- [OpenAI community - batch size limits](https://community.openai.com/t/embeddings-api-max-batch-size/655329) -- ~300K token limit per batch request, batches of 100 are safe
- [Google Drive URL patterns](https://github.com/dandyraka/GDriveRegex) -- regex patterns for extracting file/folder IDs

### Tertiary (LOW confidence)
- Google Slides plain text export format -- double-newline as slide separator is spec-assumed, needs validation with real files

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries specified in constraints/spec, APIs verified
- Architecture: HIGH -- spec provides code samples; Drive API, PyMuPDF, OpenAI APIs verified
- Chunking strategies: HIGH -- all from spec, straightforward implementations
- SSE streaming: HIGH -- FastAPI native support verified, POST with fetch+ReadableStream is standard pattern
- Pitfalls: MEDIUM -- common issues identified, but edge cases around Drive export limits and Slides format need runtime validation

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable technologies, spec-driven implementation)
