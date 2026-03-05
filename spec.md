# talk-to-a-folder — Technical Spec

---

## What It Is

A React frontend + Modal Python backend. User authenticates with Google, pastes any Google Drive link (folder, doc, PDF, sheet, slide, txt, md), and gets a chat agent that answers questions about those files with citations that point to the exact file, page, and passage.

---

## Architecture

```
BROWSER (React + Vite)
    │
    ├── Google OAuth flow → access_token (never leaves browser except as request header)
    ├── User pastes Drive link
    ├── POST /index { drive_url, access_token } → streams indexing progress
    ├── POST /chat  { query, session_id, access_token } → SSE streams answer
    └── Renders citations as inline [1] footnotes with file + page metadata

MODAL BACKEND (FastAPI + Python)
    │
    ├── POST /index
    │     1. Verify access_token → extract Google user_id (sub claim)
    │     2. Resolve link → file or folder via Drive API
    │     3. List files if folder, single file if not
    │     4. Export/download each file to raw text
    │     5. Chunk by file type (details below)
    │     6. Embed all chunks in batches of 100 (OpenAI text-embedding-3-small)
    │     7. Save to Modal Volume:
    │          {user_id}/{session_id}_embeddings.npy
    │          {user_id}/{session_id}_chunks.json
    │     8. Stream progress events back to browser
    │     Returns: session_id
    │
    ├── POST /chat
    │     1. Verify access_token → extract Google user_id (sub claim)
    │     2. Load {user_id}/{session_id}_embeddings.npy + _chunks.json from Volume
    │     3. Ping Drive metadata for all session files → identify stale file_ids
    │     4. Partition: fresh files → embed query + cosine sim → top-8 chunks
    │                   stale files → LLM generates keyword variants → grep_live
    │     5. Combine fresh retrieval + grep results into numbered sources
    │     6. Stream LLM response (SSE) — DeepSeek by default
    │     Returns: streamed answer + citation metadata + staleness warnings
    │
    └── Modal Volume
          Keys: {user_id}/{session_id}_embeddings.npy
                {user_id}/{session_id}_chunks.json
          Namespaced by Google user ID (sub claim) — no cross-user access
          TTL: none for now (manual cleanup)
```

---

## Data Storage: What Lives Where

```
BROWSER                              MODAL VOLUME (server)
─────────────────────────────        ──────────────────────────────────────────
sessionStorage                       /data/
  google_access_token                  {user_id}/
                                         {session_id}_embeddings.npy  ← float32 vectors
IndexedDB                                {session_id}_chunks.json     ← chunk text + metadata
  chats store                            {session_id2}_embeddings.npy
    session_id                           {session_id2}_chunks.json
    title
    created_at                       Never stored anywhere:
    indexed_sources[]                  raw file content
      file_id                          google_access_token
      file_name                        user PII beyond Google sub claim
      indexed_at
  messages store
    session_id (FK)
    role
    content
    citations[]
```

The browser has enough to render the full UI and chat history with no server calls.
The server has everything needed to answer questions.
They join on session_id. Embeddings never touch the browser.

---

## Google OAuth

Scope: `https://www.googleapis.com/auth/drive.readonly`

Never request more than readonly. The access token lives in React state — it is passed as a request header to Modal on each call and discarded server-side after use. We never store it.

Flow:
```
Landing page
  → "Sign in with Google" (Google Identity Services JS SDK)
  → consent screen
  → access_token returned to browser
  → token stored in sessionStorage (survives refresh, gone on tab close)
  → token attached to every /index and /chat request as Authorization header
```

GIS has two flows — use Flow A (Token Client) only:

```js
// ✅ Flow A: Token Client — returns access_token directly, valid 1 hour
// This is what we use. Works entirely client-side, no backend exchange needed.
const client = google.accounts.oauth2.initTokenClient({
  client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
  scope: "https://www.googleapis.com/auth/drive.readonly",
  callback: (response) => {
    if (response.access_token) {
      sessionStorage.setItem("google_access_token", response.access_token);
      setAccessToken(response.access_token);
    }
  },
});
client.requestAccessToken();

// ❌ Flow B: Code Client — returns authorization_code, requires backend exchange
// Do NOT use this. It requires a server endpoint to exchange the code for a token,
// which adds backend infrastructure we explicitly cut.
```

Token expiry (1 hour): if a /chat call returns 403 from Drive, the frontend clears sessionStorage and shows an inline banner: "Google session expired — click to re-authenticate." We do not implement silent refresh for the takehome.

---

## User Identity

No user database. Google's `sub` claim (a stable unique ID tied to the Google account, does not change if email changes) is the user identity. It is extracted server-side on every `/index` and `/chat` call by verifying the access token against Google's userinfo endpoint.

```python
async def get_google_user_id(access_token: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        ) as r:
            if r.status != 200:
                raise HTTPException(status_code=401, detail="Invalid access token")
            info = await r.json()
            return info["sub"]  # e.g. "107834521098765432101"
```

All Modal Volume files are namespaced by user_id:

```
/data/
  107834521098765432101/
    abc123_embeddings.npy
    abc123_chunks.json
    def456_embeddings.npy
    def456_chunks.json
```

This means:
- No one can access another user's embeddings without their Google token
- If IndexedDB is cleared, the user re-authenticates and the backend can list their existing sessions from the Volume directory
- No extra infrastructure — the Volume directory IS the user record

```python
def session_path(user_id: str, session_id: str, suffix: str) -> Path:
    return VOLUME_PATH / user_id / f"{session_id}_{suffix}"

def list_user_sessions(user_id: str) -> list[str]:
    user_dir = VOLUME_PATH / user_id
    if not user_dir.exists():
        return []
    # Each session has two files — deduplicate by session_id
    files = user_dir.glob("*_chunks.json")
    return [f.stem.replace("_chunks", "") for f in files]
```

The `/sessions` endpoint lets the frontend recover sessions after IndexedDB is cleared:

```python
@app.get("/sessions")
async def get_sessions(authorization: str = Header(...)):
    access_token = authorization.replace("Bearer ", "")
    user_id = await get_google_user_id(access_token)
    session_ids = list_user_sessions(user_id)
    # Return session_ids — frontend can rebuild IndexedDB from these
    # For now: just return the list. Full metadata recovery is a production concern.
    return {"session_ids": session_ids}
```

---

## Supported File Types

| Type | MIME | Extraction method | Chunk strategy | Citation granularity |
|---|---|---|---|---|
| Google Doc | application/vnd.google-apps.document | Drive export → text/plain | Recursive | Paragraph |
| PDF | application/pdf | PyMuPDF (fitz) | Recursive per page | File + page number |
| Google Sheet | application/vnd.google-apps.spreadsheet | Drive export → text/csv | Row-level | File + row number |
| Google Slides | application/vnd.google-apps.presentation | Drive export → text/plain | Per slide | File + slide index |
| TXT / MD | text/plain, text/markdown | Raw read | Recursive | File |

Red border (unsupported, shown but not indexed):
- Images (jpg, png, etc.)
- Videos
- ZIP files
- Any MIME not in the table above

### Drive Export Routing

Two different Drive API endpoints depending on file type. Using the wrong one returns a 400.

```python
GOOGLE_NATIVE_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
    # Note: Sheets uses CSV export specifically — handled separately
}

async def fetch_file_content(file_id: str, mime_type: str, access_token: str) -> bytes:
    headers = {"Authorization": f"Bearer {access_token}"}

    if mime_type == "application/vnd.google-apps.spreadsheet":
        # Sheets → CSV (not plain text — plain text loses column structure)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
        params = {"mimeType": "text/csv"}

    elif mime_type in GOOGLE_NATIVE_MIME_TYPES:
        # Google Docs, Slides → plain text
        # Tradeoff: tables and formatting are lost. A Doc table becomes
        # flat text with no delimiters. Acceptable for Q&A over prose.
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
        params = {"mimeType": "text/plain"}

    else:
        # PDF, TXT, MD — binary download
        # Cannot call /export on these — returns 400
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        params = {"alt": "media"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as r:
            if r.status == 403:
                raise PermissionError(f"Access denied: {file_id}")
            if r.status != 200:
                raise ValueError(f"Drive export failed: {r.status} for {file_id}")
            return await r.read()
```

Slides exported as plain text: Drive inserts `\n\n` between slides, which our per-slide chunking splits on. This is fragile — if Drive changes its export format, slide boundary detection breaks silently. Acceptable for takehome; production fix would use the Slides API to fetch slides individually.

---

## File Detection UI

When the user pastes a Drive link and we resolve the file list, show a card grid before indexing starts:

- Green border: supported type, will be indexed
- Red border: unsupported type, tooltip says why ("Images cannot be indexed — no text content")
- Each card shows: file icon, filename, file type badge, file size
- "Start indexing" button only appears after cards render
- User can see exactly what will and won't be included before committing

---

## Chunking — Per Type

### Google Docs, TXT, MD — Recursive

Mirrors LangChain RecursiveCharacterTextSplitter. Tries separators in order: `\n\n`, `\n`, `. `, ` `. Stops when chunk fits within maxChars. Carries 150 char overlap between chunks.

```python
def recursive_chunk(text, max_chars=1200, overlap=150):
    separators = ["\n\n", "\n", ". ", " "]

    def split(t, sep_idx):
        if len(t) <= max_chars or sep_idx >= len(separators):
            return [t]
        sep = separators[sep_idx]
        parts = t.split(sep)
        results = []
        current = ""
        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) > max_chars and current:
                results.append(current)
                current = current[-overlap:] + sep + part
            else:
                current = candidate
        if current:
            results.append(current)
        return [r for chunk in results
                for r in (split(chunk, sep_idx + 1) if len(chunk) > max_chars else [chunk])]

    return split(text, 0)
```

### PDF — Recursive per page

Extract text page by page with PyMuPDF. Run recursive chunking on each page's text independently. This means chunk boundaries never cross page boundaries — page number is always unambiguous.

```python
import fitz  # PyMuPDF

def extract_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        chunks = recursive_chunk(text)
        for j, chunk in enumerate(chunks):
            pages.append({
                "text": chunk,
                "page_number": i + 1,
                "chunk_index": j
            })
    return pages
```

### Google Sheets — Row-level

Each row becomes one chunk. Column headers are prepended to every row so the embedding captures structure. A row without headers is meaningless to an embedding model.

```python
import csv, io

def chunk_sheet(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return []
    headers = rows[0]
    chunks = []
    for i, row in enumerate(rows[1:], start=2):
        text = ", ".join(f"{h}: {v}" for h, v in zip(headers, row) if v.strip())
        chunks.append({"text": text, "row_number": i})
    return chunks
```

### Google Slides — Per slide

Export to plain text gives all slides concatenated. Split on slide boundaries (Drive export inserts `\n\n` between slides). Each slide = one chunk regardless of length.

---

## Chunk Metadata Schema

Every chunk, regardless of file type, gets this shape before embedding:

```python
{
    "text": "...",
    "file_id": "1aBcDeFg",
    "file_name": "Q3_report.pdf",
    "mime_type": "application/pdf",
    "drive_url": "https://drive.google.com/file/d/1aBcDeFg",
    # type-specific (None if not applicable):
    "page_number": 7,       # PDF
    "row_number": 12,       # Sheets
    "slide_index": 3,       # Slides
    "chunk_index": 2,       # position within page/slide/doc
}
```

Citation renders as:
- PDF: `Q3_report.pdf, p.7`
- Sheet: `budget.csv, row 12`
- Slides: `deck.pptx, slide 3`
- Doc/TXT/MD: `notes.md`

---

## Embedding + Storage

```python
import openai
import numpy as np
from typing import Callable, Awaitable

BATCH_SIZE = 100

# embed_chunks cannot both yield progress and return an array —
# an async generator cannot return a value in Python.
# Solution: progress callback instead of yield.

async def embed_chunks(
    chunks: list[dict],
    on_progress: Callable[[int, int], Awaitable[None]] = None
) -> np.ndarray:
    all_embeddings = []
    client = openai.AsyncOpenAI()

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=[c["text"] for c in batch]
        )
        vecs = [r.embedding for r in response.data]
        all_embeddings.extend(vecs)

        if on_progress:
            await on_progress(i + len(batch), len(chunks))

    return np.array(all_embeddings, dtype=np.float32)

# In the /index endpoint, wire progress to SSE:
async def index_with_progress(chunks, vol, event_queue):
    async def on_progress(completed, total):
        await event_queue.put({"phase": "embedding", "completed": completed, "total": total})

    return await embed_chunks(chunks, on_progress=on_progress)
```

### Modal App Definition

The Volume must be explicitly mounted in the Modal app definition. Without this, `/data` doesn't exist and all reads/writes fail silently.

```python
import modal
from fastapi import FastAPI

app = modal.App("talk-to-a-folder")

# Create volume once, reuse across deployments
volume = modal.Volume.from_name("talk-to-a-folder-data", create_if_missing=True)

web_app = FastAPI()

@app.function(
    volumes={"/data": volume},
    image=modal.Image.debian_slim().pip_install(
        "fastapi", "pymupdf", "numpy", "aiohttp", "openai"
    ),
    secrets=[
        modal.Secret.from_name("openai-secret"),
        modal.Secret.from_name("deepseek-secret"),
    ]
)
@modal.asgi_app()
def fastapi_app():
    return web_app
```

`volume.commit()` must be called after every write. It is a network call (~100-200ms) but guarantees the write persists before the function returns. Omitting it risks silent data loss on container crashes. Only needed after writes — `/chat` reads only, no commit needed there.

### Storage on Modal Volume

```python
import json, numpy as np
from pathlib import Path

VOLUME_PATH = Path("/data")

def session_dir(user_id: str) -> Path:
    d = VOLUME_PATH / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def save_session(user_id, session_id, chunks, embeddings, vol: modal.Volume):
    d = session_dir(user_id)
    np.save(d / f"{session_id}_embeddings.npy", embeddings)
    (d / f"{session_id}_chunks.json").write_text(json.dumps(chunks))
    vol.commit()  # required — without this, writes may not persist between calls

def load_session(user_id, session_id):
    d = session_dir(user_id)
    embeddings = np.load(d / f"{session_id}_embeddings.npy")
    chunks = json.loads((d / f"{session_id}_chunks.json").read_text())
    return chunks, embeddings

def session_exists(user_id, session_id):
    d = VOLUME_PATH / user_id
    return (d / f"{session_id}_chunks.json").exists()
```

---

## Retrieval

```python
def cosine_sim(query_vec, embeddings):
    # embeddings: (N, 1536), query_vec: (1536,)
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
    return np.dot(embeddings, query_vec) / (norms + 1e-9)

def retrieve(query_embedding, chunks, embeddings, top_k=8):
    scores = cosine_sim(query_embedding, embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]
```

top_k = 8 for docs. top_k = 5 for sheets (rows are denser, less context needed per chunk).

---

## Chat Prompt

```python
def build_prompt(query, retrieved_chunks):
    sources = "\n\n".join(
        f"[{i+1}] {c['file_name']}"
        + (f", p.{c['page_number']}" if c.get('page_number') else "")
        + (f", row {c['row_number']}" if c.get('row_number') else "")
        + f"\n{c['text']}"
        for i, (c, _) in enumerate(retrieved_chunks)
    )

    return f"""You are an assistant answering questions about a user's Google Drive files.
Answer using ONLY the sources below. Cite inline as [1], [2], etc.
If the answer is not in the sources, say "I couldn't find that in the provided files."
Do not guess or use outside knowledge.

SOURCES:
{sources}

QUESTION: {query}"""
```

---

## Indexing Progress — Two Phases

Phase 1 (extraction): fast, synchronous, per-file
```
Extracting text... [===>      ] 3 / 8 files
```

Phase 2 (embedding): batched, per-chunk
```
Embedding chunks... [======>   ] 200 / 312 chunks
```

Progress is streamed via SSE from Modal to the browser. The chat input is locked until both phases complete. The file cards render after Phase 1 and before Phase 2 — user sees what was found before waiting for embedding.

SSE event shape:
```json
{ "phase": "extraction", "completed": 3, "total": 8, "file_name": "report.pdf" }
{ "phase": "embedding",  "completed": 200, "total": 312 }
{ "phase": "done", "session_id": "abc123" }
```

---

## Failure Modes and How We Handle Each

### OAuth token expiry (1 hour)
Drive API returns 403. Backend returns `{ "error": "drive_auth_expired" }`.
Frontend shows: "Your Google session expired. Please sign in again." Clears session state. User re-authenticates — embeddings are still on the Volume so we skip re-indexing if session_id is preserved.

### File permissions (403 on specific file)
Skip the file. Add it to a `failed_files` list returned with the session. Frontend shows it as a grey card with "Access denied" tooltip.

### Large folder (100+ files)
No hard cap. Progress bar handles it. If a single file is >50MB we skip it and add to `failed_files` with "File too large." Note this in the card UI.

### PDF extraction failure (scanned/image PDF)
PyMuPDF returns empty text. Detect: if `page.get_text()` returns < 50 chars for every page, flag as "Scanned PDF — no extractable text." Skip and show in red card with that message.

### Duplicate files (v1, v2, final)
We do not deduplicate. All versions are indexed. Citations include filename so the user can tell which version the answer came from. Call this out explicitly: "All file versions are indexed independently."

### Sheet with 5000 rows
5000 chunks is fine for embedding (50 batches, ~15 seconds). Retrieval is still fast (cosine sim over 5000 vectors in numpy is ~2ms). No special handling needed.

### Empty folder
Resolve file list → 0 supported files → show message "No supported files found in this folder" before indexing starts. Do not proceed.

---

## Eval Harness

Dataset: **QASPER** (allenai/qasper on Hugging Face)
- Full research papers as documents
- Questions with gold answers + evidence sentences + section locations
- Maps directly: paper = file, section = page, evidence sentence = chunk

### Local eval vs Drive pipeline eval

The eval script runs against clean pre-extracted text from HuggingFace. This tests chunking and retrieval logic in isolation but is optimistic — it bypasses PyMuPDF extraction entirely.

Real Drive-via-PyMuPDF introduces noise that the local eval won't catch:
- Headers and footers bleeding into paragraph text
- Hyphenated line breaks mid-word
- Two-column layouts merged in the wrong order
- Footnote numbers appearing mid-sentence

**How to measure the delta:**
1. Download 5 QASPER papers as PDFs (use their arXiv IDs to find them)
2. Upload to a real Drive folder
3. Run the same questions through the live app
4. Compare correctness scores against local eval scores

If delta is small (<10%): extraction is clean, local eval is a reliable proxy.
If delta is large (>20%): PyMuPDF is losing information — add a post-processing step to strip headers/footers before chunking.

For the takehome, state this explicitly in the write-up: *"Eval was run against clean pre-extracted text. Real-world PDF extraction may introduce additional noise not captured in these scores."*

### Diagnostic pipeline per sample

```python
async def eval_sample(sample, user_id, session_id):
    # sample = { query, gold_answer, evidence_sentence, section }
    # Note: eval runs locally — pass a test user_id like "eval_user"

    chunks, embeddings = load_session(user_id, session_id)
    query_vec = embed_query(sample["query"])
    retrieved = retrieve(query_vec, chunks, embeddings, top_k=8)

    # Step 1: was the evidence sentence even in the indexed chunks?
    evidence_in_index = any(
        sample["evidence_sentence"].lower() in c["text"].lower()
        for c, _ in [(ch, s) for ch, s in zip(chunks, [0]*len(chunks))]
    )

    # Step 2: did retrieval surface the right chunk in top-8?
    evidence_retrieved = any(
        sample["evidence_sentence"].lower() in c["text"].lower()
        for c, _ in retrieved
    )

    # Step 3: did the LLM answer correctly?
    answer = await chat(sample["query"], retrieved)
    correct = await llm_judge(sample["query"], sample["gold_answer"], answer)

    # Classify
    if not evidence_in_index:
        failure = "CRAWL_MISS"      # chunking destroyed the evidence sentence
    elif not evidence_retrieved:
        failure = "RETRIEVAL_MISS"  # embedding similarity failed to rank it top-8
    elif not correct:
        failure = "SYNTHESIS_FAIL"  # LLM had the chunk, got it wrong anyway
    else:
        failure = None

    return {
        "query": sample["query"],
        "failure": failure,
        "evidence_in_index": evidence_in_index,
        "evidence_retrieved": evidence_retrieved,
        "correct": correct,
        "top_chunk_score": retrieved[0][1] if retrieved else 0,
    }
```

### What the failure distribution tells you

| Dominant failure | What to fix |
|---|---|
| CRAWL_MISS | Chunk size too small, evidence sentence split across chunks → increase overlap or chunk size |
| RETRIEVAL_MISS | Embedding similarity not capturing the right passage → try larger model (text-embedding-3-large), or add BM25 hybrid retrieval |
| SYNTHESIS_FAIL | LLM ignoring or misreading the context → tighten system prompt, reduce top_k to remove noise |

---

## Chat History + IndexedDB

### What a "chat" is

One chat = one session. A session starts when the user creates a new chat. They can paste multiple Drive links into the same session — each link triggers a new indexing job that appends to the session's embedding store on Modal Volume. The agent answers across all indexed links in the session.

```
Session abc123
  ├── Indexed: /drive/folders/Q3-Reports    (8 files, 312 chunks)
  ├── Indexed: /drive/file/d/budget.pdf     (1 file, 47 chunks)
  └── Messages: [user, assistant, user, assistant, ...]
```

On each new `/index` call for an existing session, load both files, append, and save back:

```python
# On each new /index call for an existing session:
# Load existing embeddings + chunks, concatenate, save back
def append_to_session(user_id, session_id, new_chunks, new_embeddings):
    if session_exists(user_id, session_id):
        old_chunks, old_embeddings = load_session(user_id, session_id)
        chunks = old_chunks + new_chunks
        embeddings = np.vstack([old_embeddings, new_embeddings])
    else:
        chunks, embeddings = new_chunks, new_embeddings
    save_session(user_id, session_id, chunks, embeddings)
```

### IndexedDB Schema

Two object stores. Nothing sensitive — no tokens, no file content.

```js
// Object store: "chats"
// Primary key: session_id
{
  session_id: "abc123",
  title: "New chat",              // user-editable, defaults to first Drive link name
  created_at: 1234567890,
  last_message_at: 1234567890,
  // model intentionally not stored — internal config only
  indexed_sources: [              // appended to on each /index call
    {
      drive_url: "https://drive.google.com/...",
      label: "Q3 Reports",        // folder/file name from Drive API
      file_list: [
        { name: "report.pdf", mime_type: "application/pdf", status: "indexed" | "failed" | "unsupported" }
      ],
      indexed_at: 1234567890,
    }
  ]
}

// Object store: "messages"
// Primary key: auto-increment id
// Index: session_id (for fast per-chat queries)
// Index: created_at (for ordering)
{
  id: 1,
  session_id: "abc123",
  role: "user" | "assistant",
  content: "...",
  created_at: 1234567890,
  citations: [                    // null on user messages
    {
      index: 1,
      file_name: "report.pdf",
      page_number: 7,
      chunk_text: "..."           // exact text the model saw — frozen at answer time
    }
  ]
}
```

`citations` stored on the message, not re-derived. If the folder is re-indexed later, old answers still show what the model actually saw.

### IndexedDB Initialization

```js
const DB_NAME = "talk-to-a-folder";
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;

      const chats = db.createObjectStore("chats", { keyPath: "session_id" });
      chats.createIndex("last_message_at", "last_message_at");

      const messages = db.createObjectStore("messages", { autoIncrement: true });
      messages.createIndex("session_id", "session_id");
      messages.createIndex("created_at", "created_at");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
```

### Key IndexedDB Operations

```js
// Load all chats for sidebar (sorted by recency)
async function getChats(db) {
  return new Promise((resolve) => {
    const tx = db.transaction("chats", "readonly");
    const index = tx.objectStore("chats").index("last_message_at");
    const req = index.getAll();
    req.onsuccess = () => resolve(req.result.reverse()); // newest first
  });
}

// Load messages for a chat
async function getMessages(db, session_id) {
  return new Promise((resolve) => {
    const tx = db.transaction("messages", "readonly");
    const index = tx.objectStore("messages").index("session_id");
    const req = index.getAll(session_id);
    req.onsuccess = () => resolve(req.result.sort((a, b) => a.created_at - b.created_at));
  });
}

// Append a message
async function addMessage(db, message) {
  return new Promise((resolve) => {
    const tx = db.transaction(["messages", "chats"], "readwrite");
    tx.objectStore("messages").add(message);
    // Update last_message_at on parent chat
    const chatsStore = tx.objectStore("chats");
    const req = chatsStore.get(message.session_id);
    req.onsuccess = () => {
      const chat = req.result;
      chat.last_message_at = message.created_at;
      chatsStore.put(chat);
    };
    tx.oncomplete = resolve;
  });
}
```

### UI: Left Sidebar

```
┌─────────────────┬──────────────────────────────────────────┐
│  + New Chat     │                                          │
│─────────────────│   [file cards when indexing]             │
│  Q3 Reports     │                                          │
│  2h ago         │   Chat messages...                       │
│                 │                                          │
│  Budget review  │                                          │
│  Yesterday      │                                          │
│                 │                                          │
│  onboarding     │   [input bar + Drive link paste zone]    │
│  3 days ago     │                                          │
└─────────────────┴──────────────────────────────────────────┘
```

- Sidebar loads from IndexedDB on mount — no server call
- Clicking a chat loads messages from IndexedDB instantly
- Chat title defaults to the first indexed source name, user can click to rename (stored in IndexedDB)
- New Chat button generates a new session_id (uuid), creates IndexedDB record, clears the main panel

### Re-authentication Flow

Access token lives in React state only. On app reload it's gone.

```
User opens app
  → IndexedDB loads chat list (instant, no server)
  → If no access_token in state: show "Sign in to continue" banner
  → User signs in → token back in state
  → Old chats still load from IndexedDB (read-only, no token needed)
  → Typing a new message in an old chat:
      → token exists → /chat call works normally
      → Drive 403 mid-chat → show inline error on that message:
        "Could not verify access to [filename]. The file may have moved or permissions changed."
      → other chunks in the same response still render normally
```

---

## Duplicate Upload Detection

When a user pastes a Drive link, before indexing starts, compare against `indexed_sources` in IndexedDB. Use Drive file ID as the canonical key — not the URL, which can have formatting variations.

```js
async function checkBeforeIndexing(driveUrl, resolvedFileId, db) {
  const chats = await getChats(db);
  for (const chat of chats) {
    for (const source of chat.indexed_sources) {
      const alreadyIndexed = source.file_list.find(f => f.file_id === resolvedFileId);
      if (alreadyIndexed) {
        return {
          duplicate: true,
          chat_id: chat.session_id,
          chat_title: chat.title,
          indexed_at: source.indexed_at,
        };
      }
    }
  }
  return { duplicate: false };
}
```

UI behavior: before the file cards render, show an inline notice:
- "You indexed this folder 3 days ago in 'Q3 Reports' chat. Re-index anyway?"
- Two buttons: "Open that chat" | "Re-index here"
- If they re-index, append to current session as normal — old session keeps its own embeddings

---

## Staleness Detection

Every file in `indexed_sources` in IndexedDB stores `indexed_at` (ISO timestamp) and `file_id`. On each `/chat` call, the backend pings the Drive API metadata endpoint for every file in the session — metadata only, no content fetch. All parallelized.

```python
import asyncio, aiohttp

async def get_file_metadata(session, file_id, access_token):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,modifiedTime"
    async with session.get(url, headers={"Authorization": f"Bearer {access_token}"}) as r:
        if r.status == 403:
            return {"file_id": file_id, "error": "access_denied"}
        return await r.json()

async def check_staleness(file_list, access_token):
    # file_list entries have: file_id, name, indexed_at (ISO string)
    async with aiohttp.ClientSession() as session:
        tasks = [get_file_metadata(session, f["file_id"], access_token) for f in file_list]
        results = await asyncio.gather(*tasks)

    stale_ids = set()
    for f, meta in zip(file_list, results):
        if "error" in meta:
            stale_ids.add(f["file_id"])  # treat inaccessible as stale
        elif meta["modifiedTime"] > f["indexed_at"]:
            stale_ids.add(f["file_id"])
    return stale_ids
```

Staleness = `modifiedTime > indexed_at`. Two timestamps. No content fetch. Cheap.

---

## Hybrid Retrieval: Staleness-Driven Routing

The LLM does not decide which retrieval method to use. Staleness decides.

```
File is fresh  →  use pre-computed embeddings  (fast, semantic)
File is stale  →  use live grep                (slow, exact, always current)
```

This removes an entire class of routing errors. The model never has to guess whether a file might have changed — we know, because we checked.

```python
async def chat(query, user_id, session_id, file_list, access_token):
    chunks, embeddings = load_session(user_id, session_id)
    stale_ids = await check_staleness(file_list, access_token)

    # Partition chunks by staleness
    fresh_mask = [i for i, c in enumerate(chunks) if c["file_id"] not in stale_ids]
    fresh_chunks = [chunks[i] for i in fresh_mask]
    fresh_embeddings = embeddings[fresh_mask] if fresh_mask else np.array([])

    # 1. Semantic retrieval over fresh chunks
    retrieved = []
    if fresh_chunks:
        query_vec = await embed_query(query)
        retrieved = retrieve(query_vec, fresh_chunks, fresh_embeddings, top_k=8)

    # 2. Live grep over stale files only
    grep_results = []
    stale_files = [f for f in file_list if f["file_id"] in stale_ids]
    keywords = extract_keywords(query)  # strip stopwords, keep nouns
    for f in stale_files:
        results = await grep_live(f["file_id"], keywords, access_token)
        grep_results.extend(results)

    # 3. Combine and synthesize
    context = format_chunks(retrieved) + format_grep_results(grep_results)
    return await synthesize(query, context, stale_files)
```

### grep_live Implementation

```python
import re

async def grep_live(file_id, keywords, access_token):
    content = await fetch_file_content(file_id, access_token)
    text = extract_text(content)  # PyMuPDF for PDF, plain text for Docs
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Join all keyword variants into one regex alternation pattern.
    # One pass over the document catches any variant in any sentence.
    # e.g. ["revenue", "sales", "ARR"] → "revenue|sales|ARR"
    pattern = "|".join(re.escape(k) for k in keywords)
    results = []

    for i, sentence in enumerate(sentences):
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            # Expand: one sentence before + one after for context
            window = sentences[max(0, i-1):min(len(sentences), i+2)]
            results.append({
                "text": " ".join(window),
                "matched_keyword": match.group(0),  # which variant actually matched
                "sentence_index": i,
                "file_id": file_id,
            })
        if len(results) >= 15:
            break

    return results
```

The 15-match cap is tunable. If eval shows grep missing answers, raise it or broaden keywords. If the model gets confused by too many matches, lower it.

### Staleness UI

Frontend renders a yellow banner per stale file above the assistant message:

```
⚠ report.pdf was modified after indexing — showing live search results for this file.
[Re-index this file]
```

---

## Per-File Re-indexing

When a user clicks "Re-index this file", only that file's chunks are replaced in the Modal Volume. Everything else in the session is untouched.

```python

@app.post("/reindex")
async def reindex_endpoint(
    session_id: str,
    file_id: str,
    authorization: str = Header(...)
):
    access_token = authorization.replace("Bearer ", "")
    user_id = await get_google_user_id(access_token)
    result = await reindex_file(user_id, session_id, file_id, access_token)
    return result
    # Returns: { "file_id": "...", "indexed_at": "2025-..." }
    # Frontend uses indexed_at to update IndexedDB entry for this file

async def reindex_file(user_id, session_id, file_id, access_token):
    # 1. Fetch and re-process the file
    file_content = await fetch_file_content(file_id, access_token)
    new_chunks = chunk_file(file_content)
    new_embeddings = await embed_chunks(new_chunks)  # batched, streams progress

    # 2. Load current session (both files)
    old_chunks, old_embeddings = load_session(user_id, session_id)

    # 3. Drop old chunks for this file only — surgical, nothing else touched
    keep = [i for i, c in enumerate(old_chunks) if c["file_id"] != file_id]
    kept_chunks = [old_chunks[i] for i in keep]
    kept_embeddings = old_embeddings[keep] if keep else np.array([])

    # 4. Append new chunks
    merged_chunks = kept_chunks + new_chunks
    merged_embeddings = np.vstack([kept_embeddings, new_embeddings]) if keep else new_embeddings

    # 5. Save back — two files, same as initial index
    save_session(user_id, session_id, merged_chunks, merged_embeddings)

    # 6. Return new indexed_at so frontend updates IndexedDB
    return {"file_id": file_id, "indexed_at": datetime.utcnow().isoformat()}
```

Frontend updates `indexed_at` in IndexedDB on success — next `/chat` call sees the file as fresh.

---

## Eval: Failure Modes

Four measurable failure categories:

```
CRAWL_MISS
  → Evidence sentence not found in any indexed chunk
  → Chunk size too small, sentence split across chunk boundary
  → Fix: increase overlap, increase chunk size

RETRIEVAL_MISS (fresh files only)
  → Evidence was indexed but not in top-8 cosine sim results
  → Embedding similarity didn't rank it highly enough
  → Fix: increase top_k, try larger embedding model, add BM25 hybrid

STALE_MISS (stale files only)
  → File was stale, grep_live ran, but answer wasn't in grep results
  → Keywords too specific, answer requires inference not extraction,
    answer spans non-adjacent sentences
  → Fix: broader keywords, larger context window, or surface "re-index needed" to user

SYNTHESIS_FAIL
  → Right chunk was retrieved, LLM got the answer wrong anyway
  → Too many distracting chunks, ambiguous phrasing, or model ignored the source constraint
  → Fix: reduce top_k, tighten system prompt, test across model variants

ROUTING_ACCURACY (cross-cutting)
  → Fresh files: did embeddings find the answer? (RETRIEVAL_MISS rate)
  → Stale files: did grep find the answer? (STALE_MISS rate)
  → Compare rates: if STALE_MISS >> RETRIEVAL_MISS, grep is a worse fallback
    than embeddings — consider re-indexing on staleness instead of grepping
```

Running eval across both fresh and stale conditions tells you whether grep is actually a useful fallback or just a different failure mode.

---

## Model Strategy

Users never see model selection. Default is DeepSeek. After running evals against QASPER, swap to whichever model has the lowest SYNTHESIS_FAIL rate.

```python
# backend/models.py
MODELS = {
    "deepseek": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
}

ACTIVE_MODEL = "deepseek"  # change this after evals
```

DeepSeek uses an OpenAI-compatible API — the client swap is one line:

```python
from openai import AsyncOpenAI

def get_client(model_key):
    m = MODELS[model_key]
    if m["provider"] == "deepseek":
        return AsyncOpenAI(base_url=m["base_url"], api_key=os.environ[m["api_key_env"]])
    elif m["provider"] == "openai":
        return AsyncOpenAI(api_key=os.environ[m["api_key_env"]])
    elif m["provider"] == "anthropic":
        # Use Anthropic SDK separately
        import anthropic
        return anthropic.AsyncAnthropic(api_key=os.environ[m["api_key_env"]])
```

The model key is stored in the Modal backend config only — never sent to the frontend. The chat response includes no model metadata. IndexedDB does not store which model was used.

---

## Keyword Extraction for grep_live

One LLM call before grepping. The model generates keyword variants — synonyms, abbreviations, related terms — that a keyword search would miss if it only used the user's exact phrasing.

```python
async def extract_keywords(query: str, model_key: str) -> list[str]:
    prompt = f"""Extract search keywords from this query for a keyword search over documents.
Return 8-12 keyword variants: synonyms, abbreviations, related terms, and the original terms.
Respond with ONLY a JSON array of strings. No explanation.

Query: {query}

Example output: ["revenue", "sales", "income", "ARR", "MRR", "earnings", "Q3 revenue"]"""

    client = get_client(model_key)
    response = await client.chat.completions.create(
        model=MODELS[model_key]["model"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: split query on spaces, strip stopwords
        stopwords = {"what", "is", "the", "a", "an", "of", "in", "for", "and", "or"}
        return [w for w in query.lower().split() if w not in stopwords]
```

This runs once per `/chat` call where stale files exist, before any grep calls. The same keyword list is used across all stale files in the session.

---

## Auth: Token Persistence

Access token stored in `sessionStorage` — survives page refresh, gone when tab closes.

```js
// On successful OAuth:
sessionStorage.setItem("google_access_token", token);

// On app load:
const token = sessionStorage.getItem("google_access_token");
// If token exists, skip sign-in screen
// If null, show sign-in

// On sign-out or 403:
sessionStorage.removeItem("google_access_token");
```

Token is never written to `localStorage` or IndexedDB. If the tab closes, the user re-authenticates on next open — IndexedDB still has their chat history and the Modal Volume still has their embeddings, so nothing is lost except the token.

**Token expiry during a session (1 hour):** Drive API returns 403. Backend returns `{"error": "drive_auth_expired"}`. Frontend clears sessionStorage, shows inline banner: "Google session expired — click to re-authenticate." After re-auth, the failed request is not automatically retried — user re-sends their message.

---

## Data Storage: What Lives Where

```
BROWSER                              MODAL VOLUME (server)
─────────────────────────────        ──────────────────────────────────────────
sessionStorage                       /data/
  google_access_token                  {user_id}/
                                         {session_id}_embeddings.npy  ← float32 vectors
IndexedDB                                {session_id}_chunks.json     ← chunk text + metadata
  chats store                            {session_id2}_embeddings.npy
    session_id                           {session_id2}_chunks.json
    title
    created_at                       Never stored anywhere:
    indexed_sources[]                  raw file content
      file_id                          google_access_token
      file_name                        user PII beyond Google sub claim
      indexed_at
  messages store
    session_id (FK)
    role
    content
    citations[]
```

The browser has enough to render the full UI and chat history with no server calls.
The server has everything needed to answer questions.
They join on session_id. Embeddings never touch the browser.

---

## Google OAuth Setup

Two environments, two redirect URIs registered in Google Cloud Console.

```
Development:  http://localhost:5173/auth/callback
Production:   https://your-modal-app.modal.run/auth/callback
```

Scopes requested: `https://www.googleapis.com/auth/drive.readonly`

Frontend uses Google Identity Services (GIS) SDK — no backend involvement in the OAuth flow:

```js
// index.html — load GIS
<script src="https://accounts.google.com/gsi/client" async></script>

// useGoogleAuth.js
function initGoogleAuth(onSuccess) {
    const client = google.accounts.oauth2.initTokenClient({
        client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
        scope: "https://www.googleapis.com/auth/drive.readonly",
        callback: (response) => {
            if (response.access_token) {
                sessionStorage.setItem("google_access_token", response.access_token);
                onSuccess(response.access_token);
            }
        },
    });
    return client;
}
```

`VITE_GOOGLE_CLIENT_ID` lives in `.env.local` — never committed. For production, set as a Vite env variable in your deployment config.

---

## Error States

Every external call has a defined failure state. Nothing fails silently.

| Error | Cause | UI Behavior |
|---|---|---|
| Drive 403 on file fetch | Permission removed or token expired | Yellow banner per affected file: "Could not access [filename]" |
| Drive 403 on token expiry | Token >1 hour old | Red banner: "Google session expired — re-authenticate" + clears sessionStorage |
| Drive 404 | File deleted after indexing | Grey card: "This file no longer exists in Drive" |
| OpenAI embedding API down | Service outage | Indexing fails with: "Embedding service unavailable — try again shortly" |
| Modal cold start timeout | First request after idle | Frontend shows spinner with "Starting up..." after 3s with no response |
| SSE connection drops mid-stream | Network blip | Message renders with "⚠ Connection lost" appended. Retry button re-sends the last user message |
| Empty folder | No supported files | Show message before indexing starts: "No supported files found" — do not proceed |
| LLM returns no tool call | Model answered from training data | Detected by checking if retrieved_chunks is empty in response. Append disclaimer: "This answer was not grounded in your files." |

---

## Rate Limiting

Per-session throttle on Modal to prevent embedding bill runup.

```python
from collections import defaultdict
import time

# In-memory throttle — good enough for takehome
request_times = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 10

def check_rate_limit(session_id: str):
    now = time.time()
    window = [t for t in request_times[session_id] if now - t < 60]
    if len(window) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many requests — wait a moment")
    window.append(now)
    request_times[session_id] = window
```

Applied to `/chat` only — `/index` is naturally throttled by its own latency.

---

## Empty State + Onboarding

What a new user sees before authenticating:

```
┌─────────────────────────────────────────────────┐
│                                                 │
│         talk-to-a-folder                        │
│                                                 │
│   Ask questions about any Google Drive          │
│   folder or file. Answers cite the exact        │
│   page and passage they came from.              │
│                                                 │
│         [ Sign in with Google ]                 │
│                                                 │
│   Requires read-only Drive access.              │
│   Your files are never stored.                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

"Your files are never stored" is accurate — we store embeddings (numerical vectors) and chunk text, not raw files. Worth being precise about this in the UI if reviewers ask.

After auth, before any chat:

```
┌──────────────┬──────────────────────────────────┐
│ + New Chat   │                                  │
│──────────────│   Paste a Google Drive link      │
│              │   to get started.                │
│   No chats   │                                  │
│   yet        │   Folders, Docs, PDFs, Sheets,   │
│              │   Slides, and text files         │
│              │   are supported.                 │
│              │                                  │
└──────────────┴──────────────────────────────────┘
```

---

## "Better Than Perplexity" — The Answer

This section exists for the write-up and any verbal explanation to reviewers.

Perplexity retrieves web pages and answers with URL-level citations. You cannot verify which sentence in the page the answer came from. You cannot ask it about your private documents. It has no memory of previous searches.

This project is better in three specific ways:

**1. Citation granularity.** Every answer cites the exact file, page number, and passage the model used. Not a URL — a chunk. The chunk text is stored on the message so the citation is frozen and verifiable even if the file changes later.

**2. Private document retrieval.** The agent operates on the user's own Drive files, not the public web. The retrieval pipeline (embed → cosine sim → top-k) is the same mechanism, applied to private data.

**3. Staleness-aware retrieval.** When a source file is modified after indexing, the system detects it, routes queries about that file to live grep instead of stale embeddings, and tells the user. Perplexity has no equivalent concept — it re-crawls on demand but gives no signal about whether its index is current.

The eval harness makes claim 1 and 3 measurable, not just asserted.

---

## What We Are Not Building (Explicit Scope Cuts)

- No silent token refresh (force re-auth on expiry)
- No persistent user accounts — sessions are anonymous and local to the browser. session_ids persist in IndexedDB and are namespaced by Google user_id on the Volume, but there is no user table or login state server-side
- No reranker (pure cosine sim is sufficient to demonstrate the pipeline)
- No semantic chunking (recursive is the right default; semantic requires embedding at chunk time which adds latency with marginal gain at this scale)
- No Sheets deduplication across versions
- No support for scanned PDFs (OCR is out of scope)

Each of these is a real production concern and worth noting in the write-up.

---

## Consolidated Failure Modes, Fallbacks, and Tradeoffs

Every decision in this spec has a failure mode. This section collects them in one place so you know what to look for during testing and what lever to pull when something breaks.

---

### Indexing Pipeline

| Failure | Cause | Fallback / Fix |
|---|---|---|
| PDF extraction returns empty text | Scanned/image PDF — no text layer | Detect: if `page.get_text()` < 50 chars across all pages, mark as unsupported. Show red card: "Scanned PDF — no extractable text" |
| PDF extraction garbled | Two-column layout, headers bleeding into body | Post-process: strip lines that match header/footer patterns (page numbers, repeated title text). Measure via local vs Drive delta test |
| Google Doc export incomplete | Very large Doc hits Drive export size limit | Chunk the export request by section using the Docs API instead of full export |
| Sheet with merged cells | Drive CSV export flattens merged cells unpredictably | No fix — document as known limitation. Row-level chunking will produce malformed rows |
| Zero chunks after extraction | File has content but chunker returns empty | Fallback: return the raw text as one chunk rather than failing silently |

---

### Chunking

| Failure | Cause | Fallback / Fix |
|---|---|---|
| Evidence sentence split across chunk boundary | Overlap too small relative to sentence length | Increase overlap from 150 to 300 chars. Measure via CRAWL_MISS rate in eval |
| Chunk too large for embedding model token limit | Single paragraph > 8191 tokens | Recursive chunker handles this by falling back to finer separators — verify the fallback path is hit in tests |
| Chunk too small, loses surrounding context | max_chars too low | Increase max_chars. Watch for RETRIEVAL_MISS rate going down vs SYNTHESIS_FAIL going up (more context = more noise) |
| Sheet row chunks missing context | Headers not prepended to every row | Fix: always prepend headers. Without this, "45000" is meaningless to an embedding model |

---

### Embedding

| Failure | Cause | Fallback / Fix |
|---|---|---|
| OpenAI embedding API down | Service outage | Catch HTTP 5xx, return `{"error": "embedding_unavailable"}` to frontend. Do not partially index |
| Batch exceeds token limit | Chunks averaging > 80 tokens each with batch size 100 | Reduce BATCH_SIZE to 50. At 8191 token limit per input, 100 chunks of 1200 chars each is ~30k tokens total — well within batch limits |
| Embedding cost runup | User indexes huge folder repeatedly | Rate limit `/index` endpoint: max 3 index calls per session per hour |

---

### Retrieval

| Failure | Cause | Fallback / Fix |
|---|---|---|
| RETRIEVAL_MISS — right chunk not in top-k | Cosine sim ranked it below position k | Increase top_k from 8 to 12. Watch SYNTHESIS_FAIL — more chunks = more noise for the LLM |
| All retrieved chunks score below 0.3 | Query is about something not in the files | Return early with: "I couldn't find relevant information in the provided files." Don't call the LLM |
| Stale file — embeddings outdated | File modified after indexing | Route to grep_live instead of embeddings. Show yellow banner. Offer per-file re-index |
| numpy vstack OOM on large session | Many files appended to same session | For takehome: not a concern. Production fix: migrate to a proper vector DB |

---

### grep_live

| Failure | Cause | Fallback / Fix |
|---|---|---|
| STALE_MISS — grep finds nothing | Keywords don't match document vocabulary | LLM generates 8-12 variants using regex alternation (`revenue\|sales\|ARR`). One pass catches any variant. If still no match, tell the user the file may need re-indexing |
| grep_live fetches huge file on every query | 50-page PDF downloaded per chat message | Cache raw extracted text server-side with 5-minute TTL keyed by file_id. Repeated queries on same stale file reuse cached text |
| Answer requires inference, not extraction | "What is the trend in Q3 revenue?" — answer not in any single sentence | grep fundamentally can't help here. Surface to user: "This file has been modified — for analytical questions, re-index it for best results" |
| grep hits 15-match cap before finding answer | Dense document with many keyword matches | Increase cap, or narrow keywords. The `matched_keyword` field in results tells you which variant is over-matching |

The regex alternation pattern is key here — instead of N sequential keyword searches, one pass covers all variants:
```python
# All keyword variants in one regex pass
pattern = "|".join(re.escape(k) for k in keywords)
# e.g. ["revenue", "sales", "ARR", "income"] → "revenue|sales|ARR|income"
matches = re.search(pattern, sentence, re.IGNORECASE)
# match.group(0) tells you which variant fired
```

---

### Synthesis

| Failure | Cause | Fallback / Fix |
|---|---|---|
| SYNTHESIS_FAIL — answer wrong despite right chunk | Too many distracting chunks, model didn't focus | Reduce top_k. Check if RETRIEVAL_MISS goes up — find the right tradeoff for your eval data |
| Model answers from training data, ignores sources | System prompt not strict enough | Add: "If you use any knowledge not present in the numbered sources, your answer is wrong." Measure: check if system answer contains NOT FOUND on adversarial queries |
| Citation index wrong | Model cites [3] but only 2 sources exist | Add validation: parse citation indices from answer, flag any out of range |
| Model refuses to answer | Safety filter on document content | Log refusals separately. Not a retrieval or synthesis failure — different category |

---

### Staleness Detection

| Failure | Cause | Fallback / Fix |
|---|---|---|
| modifiedTime check adds latency | Many files in session, all pinged on each /chat | Parallelize with asyncio.gather (already in spec). Cache staleness result for 60 seconds per file_id |
| File deleted after indexing | Drive returns 404 on metadata call | Treat as stale, route to grep_live. grep_live will 404 on fetch — catch it, tell user: "This file no longer exists in Drive" |
| False positive stale — file modified but content unchanged | Formatting change triggers modifiedTime update | No fix without content hashing. Accept false positives — grep fallback is safe even when unnecessary |

---

### Auth + Session

| Failure | Cause | Fallback / Fix |
|---|---|---|
| Token expired mid-session | Google tokens expire after 1 hour | Drive API returns 403. Backend returns `{"error": "drive_auth_expired"}`. Frontend clears sessionStorage, shows re-auth banner. Failed message not auto-retried |
| sessionStorage cleared | User opens incognito, or browser clears storage | User re-authenticates. IndexedDB chat history still intact. Modal Volume embeddings still intact. Only the token is lost |
| session_id collision | Two sessions get same UUID | Use `crypto.randomUUID()` — collision probability is negligible |
| Modal Volume fills up | Many users, no TTL on session files | Out of scope for takehome. Production fix: TTL of 30 days, cron cleanup job |

---

### Integration Points

| Decision | Tradeoff |
|---|---|
| GIS Token Client (Flow A) over Code Client (Flow B) | Flow A returns access_token directly — no backend needed. Flow B requires a server token exchange endpoint we explicitly cut. No meaningful downside to Flow A for this use case |
| `/export?mimeType=text/plain` for Google-native files | Tables and formatting are lost — a Doc table becomes undelimited flat text. Acceptable for prose Q&A. Production fix: use Docs API to preserve structure |
| Sheets uses CSV export, not plain text | Plain text export of a Sheet loses column alignment. CSV preserves it for row-level chunking. Slight extra complexity in the routing logic |
| Slides plain text export split on `\n\n` | Fragile — depends on Drive's export format inserting double newlines between slides. If Drive changes this, slide boundary detection breaks silently. No alternative without the Slides API |
| `volume.commit()` after every write | Adds ~100-200ms to `/index` and `/reindex`. Omitting risks silent data loss on container crash. Worth the latency |
| Explicit CORS origins over wildcard | Wildcard `allow_origins=["*"]` lets any website call your Modal endpoint and burn your API credits. Explicit origins only, updated before production deploy |
| `fetch` + `ReadableStream` over `EventSource` | `EventSource` is GET-only. Our `/chat` is POST — query in URL params would appear in server logs and break on long messages. `fetch` adds ~50 lines of boilerplate but keeps the request body secure |
| `fetch` + `ReadableStream` over Vercel AI SDK | AI SDK expects its own stream format — adapting FastAPI to emit it adds complexity. Our custom event types (`staleness`, `citations`) don't map cleanly to SDK conventions. Native `fetch` gives full control |
| Progress callback over async generator in `embed_chunks` | Python async generators cannot return a value. Callback pattern separates progress reporting from the return value cleanly. Slight readability cost vs generator syntax |
| Modal cold starts accepted, no keep-warm ping | Keep-warm pings cost money on Modal. For a takehome demo, handling cold start in the UI ("Starting up...") is sufficient. Production: add a scheduled ping or use Modal's keep-warm config |

---

### Eval-Specific

| Failure | Cause | What it means |
|---|---|---|
| CRAWL_MISS | Evidence sentence not in any chunk | Chunking destroyed it — increase overlap |
| RETRIEVAL_MISS | Evidence indexed but not in top-k | Embedding similarity failed — increase top_k or try larger embedding model |
| STALE_MISS | Stale file, grep didn't find answer | Keywords too narrow, or answer requires inference — grep can't help |
| SYNTHESIS_FAIL | Right chunk retrieved, wrong answer | Too much noise in context, or model ignoring source constraint |
| Judge bias | LLM judge scores its own outputs leniently | Spot-check 10 samples manually. If judge score > your intuition consistently, add stricter judge prompt |
| Local vs Drive delta > 20% | PyMuPDF extraction losing information | Add header/footer stripping post-process before chunking |

---

## SSE Streaming: Backend to Frontend

### FastAPI backend — StreamingResponse

```python
from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse
import json, asyncio

# CORS — must be added before any route definitions
# Wildcard allow_origins is NOT used — any site could call your endpoint
# and burn your API credits. Explicit origins only.
from fastapi.middleware.cors import CORSMiddleware

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",       # Vite dev server
        "https://your-production-domain.com",  # set before deploying
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.post("/chat")
async def chat_endpoint(
    body: ChatRequest,  # { session_id, query, file_list }
    authorization: str = Header(...)
):
    access_token = authorization.replace("Bearer ", "")
    user_id = await get_google_user_id(access_token)

    async def event_stream():
        # 1. Staleness check — emit warning events before any text
        stale_ids = await check_staleness(body.file_list, access_token)
        if stale_ids:
            stale_names = [f["file_name"] for f in body.file_list if f["file_id"] in stale_ids]
            yield f"data: {json.dumps({'type': 'staleness', 'files': stale_names})}

"

        # 2. Retrieve
        chunks, embeddings = load_session(user_id, body.session_id)
        retrieved, grep_results = await hybrid_retrieve(
            body.query, chunks, embeddings, body.file_list, stale_ids, access_token
        )

        # 3. Stream LLM response token by token
        citations = []
        async for token in stream_llm(body.query, retrieved, grep_results):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}

"

        # 4. After stream completes, emit citations as final event
        citations = extract_citations(retrieved, grep_results)
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}

"

        yield "data: [DONE]

"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

SSE event types:
```
{ "type": "staleness", "files": ["report.pdf"] }   → show yellow banner
{ "type": "token",     "content": "The " }          → append to message in UI
{ "type": "citations", "citations": [...] }          → store to IndexedDB on message
{ "type": "error",     "message": "..." }            → show inline error
[DONE]                                               → stream complete
```

### Frontend — fetch + ReadableStream (not EventSource, not Vercel AI SDK)

`EventSource` only supports GET requests. Our `/chat` endpoint is POST (needs session_id, query, file_list in the body). Putting these in URL params is bad — queries appear in server logs and break on long messages.

The Vercel AI SDK (`useChat`) expects a specific stream format incompatible with our custom event types (`staleness`, `citations`). Adapting it adds more complexity than it saves.

Solution: `fetch` with `response.body.getReader()`. Same streaming behavior, full control over event parsing, ~50 lines of boilerplate.

```js
// hooks/useStream.js
import { useState, useRef, useCallback } from "react";
import { addMessage, updateChat } from "../lib/db";

export function useStream({ sessionId, accessToken, fileList, db }) {
  const [messages, setMessages]   = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [staleFiles, setStaleFiles] = useState([]);
  const abortRef = useRef(null);

  const sendMessage = useCallback(async (query) => {
    // 1. Append user message immediately
    const userMsg = { role: "user", content: query, created_at: Date.now(), session_id: sessionId };
    setMessages(prev => [...prev, userMsg]);
    await addMessage(db, userMsg);
    setIsLoading(true);

    // 2. Start POST request
    abortRef.current = new AbortController();
    const response = await fetch(`${import.meta.env.VITE_MODAL_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ session_id: sessionId, query, file_list: fileList }),
      signal: abortRef.current.signal,
    });

    if (!response.ok) {
      const err = await response.json();
      if (err.error === "drive_auth_expired") {
        sessionStorage.removeItem("google_access_token");
        // trigger re-auth banner via state
      }
      setIsLoading(false);
      return;
    }

    // 3. Read SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let assistantContent = "";
    let citations = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split("
").filter(l => l.startsWith("data: "));

      for (const line of lines) {
        const raw = line.replace("data: ", "").trim();
        if (raw === "[DONE]") break;

        const event = JSON.parse(raw);

        if (event.type === "staleness") {
          setStaleFiles(event.files);  // show yellow banner
        }
        if (event.type === "token") {
          assistantContent += event.content;
          // Update message in place as tokens arrive
          setMessages(prev => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: assistantContent };
            } else {
              next.push({ role: "assistant", content: assistantContent, citations: [] });
            }
            return next;
          });
        }
        if (event.type === "citations") {
          citations = event.citations;
        }
        if (event.type === "error") {
          // surface inline error
        }
      }
    }

    // 4. Stream complete — write final message with citations to IndexedDB
    const assistantMsg = {
      role: "assistant",
      content: assistantContent,
      citations,
      created_at: Date.now(),
      session_id: sessionId,
    };
    await addMessage(db, assistantMsg);
    setMessages(prev => {
      const next = [...prev];
      next[next.length - 1] = assistantMsg;
      return next;
    });
    setIsLoading(false);
  }, [sessionId, accessToken, fileList, db]);

  return { messages, setMessages, isLoading, staleFiles, sendMessage };
}
```

---

## Frontend Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | React + Vite | Specified |
| Styling | Tailwind CSS | Utility-first, consistent with shadcn |
| Components | shadcn/ui | Built on Radix primitives, accessible by default, copy-paste into your codebase |
| Primitives | Radix UI | Unstyled accessible components shadcn is built on — use directly for anything shadcn doesn't cover |
| Chat streaming | Vercel AI SDK (useChat) | Handles SSE, message state, loading, stream completion in ~5 lines |
| Local persistence | IndexedDB (native) | No library needed — the operations we need are simple enough |
| Icons | lucide-react | Ships with shadcn |

**Key shadcn components used:**
- `Sheet` — left sidebar (slides in on mobile)
- `Card` — file detection cards with green/red borders
- `Badge` — file type label on each card
- `Tooltip` — unsupported file reason on red cards
- `Dialog` — re-auth prompt
- `Progress` — two-phase indexing progress bar
- `ScrollArea` — chat message container
- `Separator` — sidebar dividers
- `Button`, `Input` — chat input bar

**Tailwind config additions needed:**
```js
// tailwind.config.js
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // shadcn uses CSS variables — these are set in index.css
        // no custom colors needed unless you're overriding the theme
      }
    }
  },
  plugins: [require("tailwindcss-animate")] // required by shadcn
}
```

**Setup commands:**
```bash
npm create vite@latest talk-to-a-folder -- --template react
cd talk-to-a-folder
npm install
npx shadcn@latest init        # sets up tailwind, CSS variables, components.json
npx shadcn@latest add card badge tooltip dialog progress scroll-area separator button input sheet
npm install ai                # Vercel AI SDK
npm install lucide-react      # icons (likely already installed by shadcn)
```

---

## Stack Summary

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | React + Vite | Specified |
| UI components | shadcn/ui + Radix UI + Tailwind CSS | Accessible, composable, consistent |
| Chat streaming | Vercel AI SDK (useChat) | SSE plumbing, message state, stream completion callback |
| Icons | lucide-react | Ships with shadcn |
| Auth | Google Identity Services JS SDK | OAuth without a backend |
| Backend | Modal + FastAPI | Persistent volume, Python PDF ecosystem |
| PDF extraction | PyMuPDF (fitz) | Best real-world PDF text quality |
| Embeddings | OpenAI text-embedding-3-small | Cheap, fast, good enough |
| LLM | DeepSeek (default) — swappable to Claude/GPT-4o-mini after evals | OpenAI-compatible, model is internal config only |
| Vector storage | Modal Volume + numpy (.npy + .json) | No external dependency, free, fast enough |
| Local persistence | IndexedDB (native browser API) | Chat history, sessions, citations |
| Eval dataset | QASPER (allenai/qasper) | Maps directly: paper=file, evidence sentence=chunk |