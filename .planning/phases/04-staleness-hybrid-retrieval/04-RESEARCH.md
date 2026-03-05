# Phase 4: Staleness + Hybrid Retrieval - Research

**Researched:** 2026-03-05
**Domain:** Drive metadata staleness detection, hybrid retrieval routing, regex-based live grep, per-file re-indexing, in-memory caching
**Confidence:** HIGH

## Summary

Phase 4 adds staleness awareness to the Phase 3 chat pipeline. On every `/chat` request, the backend checks Google Drive `modifiedTime` against each file's `indexed_at` timestamp. Files that have changed since indexing are routed to `grep_live` (LLM-extracted keywords + regex search over re-fetched content) instead of pre-computed embeddings. The frontend shows yellow staleness banners before answer tokens stream and offers per-file re-indexing.

The spec provides complete code samples for all six core functions: `check_staleness()`, `grep_live()`, `extract_keywords()`, the modified `chat()` routing, `reindex_file()`, and the `/reindex` endpoint. The CONTEXT.md decisions lock in caching strategy (in-memory, 60s staleness / 5min grep text), parallelism approach (asyncio.gather), and detailed UI behavior for banners/re-index flow. Implementation should follow spec code closely.

The main engineering challenges are: (1) correctly partitioning chunks by staleness and merging retrieval results from two different sources (embeddings vs grep), (2) parallel I/O coordination (staleness check + query embedding, then parallel grep across stale files), (3) the re-index endpoint that surgically replaces one file's chunks without touching others, and (4) frontend state management for per-file banners with independent re-index buttons.

**Primary recommendation:** Follow spec code samples directly. Focus implementation effort on the parallelism (asyncio.gather patterns), cache invalidation on re-index, and the frontend banner component with its three distinct states (stale/deleted/revoked).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Re-index feedback flow: Inline spinner on button, text changes to "Re-indexing...", chat send button disabled with tooltip, success transitions to green toast (auto-dismiss 3s), previous grep answer stays visible, each file's banner/button independent
- Staleness banner behavior: Yellow banner ABOVE assistant's streaming response, one per stale file with own re-index button, re-appears on every response using grep_live, all stale banners retain active re-index buttons regardless of message age, specific banner text format
- grep_live edge case messaging: 0 matches gets extra "No matches found" line with re-index button, deleted file (404) gets red banner with no re-index button, access revoked (403) gets orange banner with "Re-authenticate" button, deleted files still use old embeddings with "(deleted)" suffix on citations
- Staleness/grep caching: Both caches in Phase 4 (not deferred), staleness check cache 60s TTL, grep text cache 5min TTL, both in-memory dict per container, cache invalidation on re-index clears both entries immediately
- Parallelism: Staleness check and query embedding run in parallel (asyncio.gather), grep_live across multiple stale files in parallel, keyword extraction runs before grep calls (shared keyword list)

### Claude's Discretion
- In-memory cache implementation details (dict structure, cleanup strategy)
- Banner component styling within shadcn/ui conventions
- Exact spinner/loading animation for re-index button
- Error handling for partial grep_live failures in parallel execution

### Deferred Ideas (OUT OF SCOPE)
None

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RETR-03 | Staleness detection: Drive metadata modifiedTime compared to indexed_at for all session files on each /chat | Spec provides complete `check_staleness()` with `get_file_metadata()` + asyncio.gather; string comparison of ISO timestamps |
| RETR-04 | Fresh files use pre-computed embeddings; stale files routed to grep_live | Spec provides `hybrid_retrieve()` with fresh_mask/stale partition; Phase 3 cosine sim for fresh, grep for stale |
| RETR-05 | LLM generates 8-12 keyword variants for grep_live queries | Spec provides `extract_keywords()` with JSON-array prompt, fallback stopword splitting on parse failure |
| RETR-06 | grep_live fetches stale file content, searches with regex alternation, returns up to 15 matches with context windows | Spec provides complete `grep_live()` with sentence splitting, regex alternation pattern, context window expansion |
| RETR-07 | Per-file re-indexing: user clicks "Re-index this file", only that file's chunks replaced in session | Spec provides `reindex_file()` and `/reindex` endpoint; surgical chunk replacement via keep-mask + append |
| CHAT-05 | Staleness warning events streamed before answer tokens, yellow banner per stale file | Spec provides SSE `{ type: "staleness", files: [...] }` event; CONTEXT.md locks banner text/behavior/colors |

</phase_requirements>

## Standard Stack

### Core -- Backend (additions to Phase 3 stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | latest | Drive metadata API calls for staleness check | Already used in Phase 1 for auth; reuse for parallel Drive API calls |
| re (stdlib) | -- | Regex alternation for grep_live | Standard library; `re.search` with `re.IGNORECASE` for case-insensitive keyword matching |
| json (stdlib) | -- | Parse LLM keyword extraction response | Standard library; `json.loads` for LLM JSON array output |
| asyncio (stdlib) | -- | Parallel I/O coordination | `asyncio.gather` for staleness+embedding, parallel grep across files |

### Core -- Frontend (additions to Phase 3 stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lucide-react | latest | Warning/spinner icons for banners | Already in project via shadcn; AlertTriangle, Loader2, XCircle icons |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn Alert | -- | Staleness banner component | Yellow/red/orange variants for stale/deleted/revoked states |
| shadcn Button | -- | Re-index button with spinner state | Already available; loading prop pattern |
| shadcn Sonner/Toast | -- | "Re-indexed successfully" toast | Success notification on re-index completion |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory dict cache | Redis/Memcached | Overkill for takehome; in-memory is correct per CONTEXT.md decision |
| Regex grep | Full-text search (whoosh, sqlite FTS) | Spec explicitly uses regex; grep is simple and sufficient |
| LLM keyword extraction | Static NLP (spaCy, NLTK) | LLM generates synonyms/abbreviations that static NLP cannot |

**No new installations needed.** All libraries already in the project from Phases 1-3.

## Architecture Patterns

### Backend: Modified /chat Flow (Phase 4 additions in bold)
```
POST /chat { session_id, query, file_list }
  1. Verify access_token -> get user_id
  2. Load embeddings.npy + chunks.json from Volume
  **3. asyncio.gather: check_staleness(file_list) + embed_query(query)**
  **4. If stale_ids: emit SSE { type: "staleness", files: [...] }**
  **5. Partition chunks: fresh_mask vs stale file_ids**
  6. Fresh chunks -> cosine similarity -> top-k (same as Phase 3)
  **7. If stale: extract_keywords(query) -> keywords**
  **8. asyncio.gather: grep_live(file_id, keywords) for each stale file**
  **9. Merge: format_chunks(retrieved) + format_grep_results(grep_results)**
  10. Stream LLM response token-by-token
  11. Emit citations event (now includes grep-sourced citations)
  12. Emit [DONE]
```

### New Endpoint: POST /reindex
```
POST /reindex { session_id, file_id }
  1. Verify access_token -> get user_id
  2. Fetch file content from Drive
  3. Chunk + embed (same pipeline as Phase 2)
  4. Load existing session chunks/embeddings
  5. Drop old chunks for this file_id only
  6. Append new chunks + embeddings
  7. Save merged session, volume.commit()
  8. Clear staleness + grep caches for this file_id
  9. Return { file_id, indexed_at }
```

### In-Memory Cache Structure
```python
# Staleness cache: avoid re-checking Drive metadata every request
# Key: file_id, Value: (is_stale: bool, checked_at: float)
_staleness_cache: dict[str, tuple[bool, float]] = {}
STALENESS_TTL = 60  # seconds

# Grep text cache: avoid re-fetching file content for repeated queries
# Key: file_id, Value: (extracted_text: str, fetched_at: float)
_grep_text_cache: dict[str, tuple[str, float]] = {}
GREP_TEXT_TTL = 300  # 5 minutes
```

### Frontend: Banner Component Hierarchy
```
src/
  components/
    chat/
      StalenessBanner.tsx        # Single stale file banner (yellow/red/orange)
      StalenessBannerList.tsx     # Container for multiple banners above message
      ReindexButton.tsx           # Button with spinner/disabled/success states
  hooks/
    useReindex.ts                # POST /reindex, update IndexedDB, clear stale state
```

### Pattern 1: Parallel Staleness Check + Query Embedding
**What:** Run staleness check and query embedding concurrently since both are I/O-bound
**When to use:** Every /chat request
**Example:**
```python
# Source: spec.md + CONTEXT.md parallelism decision
async def hybrid_chat(query, user_id, session_id, file_list, access_token):
    chunks, embeddings = load_session(user_id, session_id)

    # Parallel: staleness check + query embedding (both I/O bound)
    stale_ids, query_vec = await asyncio.gather(
        check_staleness(file_list, access_token),
        embed_query(query),
    )

    # Fresh retrieval
    fresh_mask = [i for i, c in enumerate(chunks) if c["file_id"] not in stale_ids]
    retrieved = []
    if fresh_mask:
        fresh_chunks = [chunks[i] for i in fresh_mask]
        fresh_embeddings = embeddings[fresh_mask]
        retrieved = retrieve(query_vec, fresh_chunks, fresh_embeddings, top_k=8)

    # Stale retrieval: keyword extraction THEN parallel grep
    grep_results = []
    if stale_ids:
        stale_files = [f for f in file_list if f["file_id"] in stale_ids]
        keywords = await extract_keywords(query)  # single LLM call
        grep_tasks = [grep_live(f["file_id"], keywords, access_token) for f in stale_files]
        all_grep = await asyncio.gather(*grep_tasks)
        for results in all_grep:
            grep_results.extend(results)

    return retrieved, grep_results
```

### Pattern 2: Cache with TTL Check
**What:** Simple in-memory cache with timestamp-based expiry
**When to use:** Staleness checks (60s) and grep text (5min)
**Example:**
```python
import time

_staleness_cache: dict[str, tuple[bool, float]] = {}
STALENESS_TTL = 60

async def check_staleness_cached(file_list, access_token):
    now = time.time()
    uncached = []
    cached_stale = set()

    for f in file_list:
        fid = f["file_id"]
        if fid in _staleness_cache:
            is_stale, checked_at = _staleness_cache[fid]
            if now - checked_at < STALENESS_TTL:
                if is_stale:
                    cached_stale.add(fid)
                continue
        uncached.append(f)

    # Only check uncached files
    if uncached:
        fresh_stale = await check_staleness(uncached, access_token)
        for f in uncached:
            is_stale = f["file_id"] in fresh_stale
            _staleness_cache[f["file_id"]] = (is_stale, now)
            if is_stale:
                cached_stale.add(f["file_id"])

    return cached_stale

def invalidate_caches(file_id: str):
    """Called after successful re-index."""
    _staleness_cache.pop(file_id, None)
    _grep_text_cache.pop(file_id, None)
```

### Pattern 3: Surgical Chunk Replacement for Re-index
**What:** Remove all chunks for one file_id, append new chunks, save merged session
**When to use:** /reindex endpoint
**Example:**
```python
# Source: spec.md reindex_file
async def reindex_file(user_id, session_id, file_id, access_token):
    # Fetch + re-process
    file_content = await fetch_file_content(file_id, access_token)
    new_chunks = chunk_file(file_content)
    new_embeddings = await embed_chunks(new_chunks)

    # Load existing session
    old_chunks, old_embeddings = load_session(user_id, session_id)

    # Keep everything except this file's chunks
    keep = [i for i, c in enumerate(old_chunks) if c["file_id"] != file_id]
    kept_chunks = [old_chunks[i] for i in keep]
    kept_embeddings = old_embeddings[keep] if keep else np.array([])

    # Merge
    merged_chunks = kept_chunks + new_chunks
    merged_embeddings = (
        np.vstack([kept_embeddings, new_embeddings]) if keep else new_embeddings
    )

    save_session(user_id, session_id, merged_chunks, merged_embeddings)
    invalidate_caches(file_id)

    return {"file_id": file_id, "indexed_at": datetime.utcnow().isoformat()}
```

### Pattern 4: Frontend Staleness Banner State
**What:** Per-message stale files tracked, banner renders above assistant message
**When to use:** Every chat message that was answered with grep_live
**Example:**
```typescript
// Source: spec.md useStream + CONTEXT.md decisions
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  stale_files?: string[];  // file names that were stale for THIS message
  created_at: number;
  session_id: string;
}

// In useStream hook, when staleness event arrives:
if (event.type === "staleness") {
  // Store on the message being built, not just component state
  currentStaleFiles = event.files;
}

// When message finalized:
const assistantMsg = {
  role: "assistant",
  content: assistantContent,
  citations,
  stale_files: currentStaleFiles,  // persisted per message
  created_at: Date.now(),
  session_id: sessionId,
};
```

### Anti-Patterns to Avoid
- **LLM-based routing:** The staleness check is deterministic (timestamp comparison). Never let the LLM decide whether to use embeddings or grep. The spec is explicit: "The LLM does not decide which retrieval method to use. Staleness decides."
- **Sequential staleness checks:** Don't check files one-at-a-time. Use asyncio.gather for all Drive metadata calls.
- **Re-fetching file for every grep:** Cache extracted text for 5 minutes. Repeated queries against the same stale file should reuse cached text.
- **Global stale state:** Stale files are per-message, not global. Each assistant message should record which files were stale when it was generated. Don't mutate previous messages' stale state.
- **Blocking chat input during re-index of unrelated file:** Each file's re-index is independent. Only disable the send button, not the entire UI.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyword extraction | Regex/NLP-based keyword extraction | LLM call with JSON-array prompt | LLM generates synonyms, abbreviations, and related terms that static extraction cannot |
| File content extraction | New extraction code for re-index | Reuse Phase 2 `chunk_file()` and `embed_chunks()` | Re-index is the same pipeline, just for one file |
| Toast notifications | Custom toast implementation | shadcn Sonner/Toast | Already in ecosystem, handles auto-dismiss, stacking |
| Cache expiry cleanup | Background cleanup thread | Lazy eviction on read | Check TTL on access; stale entries are cheap (small dict) |

**Key insight:** Phase 4 is primarily about routing logic and UI state management, not new algorithmic work. The retrieval methods (cosine sim, regex grep) are straightforward. The complexity is in orchestrating them correctly and presenting clear feedback to the user.

## Common Pitfalls

### Pitfall 1: ISO Timestamp String Comparison
**What goes wrong:** `modifiedTime > indexed_at` fails silently if timestamp formats don't match (e.g., one has timezone offset, other doesn't).
**Why it happens:** Google Drive returns RFC 3339 timestamps (e.g., `2025-03-05T12:00:00.000Z`). If `indexed_at` is stored differently (e.g., without trailing Z, or with different precision), string comparison breaks.
**How to avoid:** Store `indexed_at` using `datetime.utcnow().isoformat() + "Z"` to match Drive's format. Or parse both to datetime objects for comparison.
**Warning signs:** Files reported as stale when they haven't changed, or never reported as stale.

### Pitfall 2: Empty fresh_mask with numpy indexing
**What goes wrong:** `embeddings[fresh_mask]` crashes when `fresh_mask` is empty (all files stale).
**Why it happens:** numpy fancy indexing with an empty list returns empty array, but `np.vstack` with empty array can fail.
**How to avoid:** Guard with `if fresh_mask:` before indexing. The spec code already does this.
**Warning signs:** TypeError or IndexError when all session files are stale.

### Pitfall 3: extract_keywords JSON Parse Failure
**What goes wrong:** LLM returns keywords with markdown formatting (e.g., ```json\n[...]```) instead of raw JSON array.
**Why it happens:** LLMs sometimes wrap JSON in code blocks despite "Respond with ONLY a JSON array" instruction.
**How to avoid:** Strip markdown code fences before parsing. The spec provides a stopword-based fallback for parse failures.
**Warning signs:** Fallback fires frequently, grep results degrade.

### Pitfall 4: grep_live Sentence Splitting on Non-prose Content
**What goes wrong:** `re.split(r'(?<=[.!?])\s+', text)` produces poor results for structured content (tables, code, CSVs, slides).
**Why it happens:** Sentence-boundary regex assumes prose. CSV rows, code, and slide text don't end with periods.
**How to avoid:** For sheets/CSV, split on newlines instead. For slides, split on double-newline (already the slide delimiter). Add a content-type check before choosing split strategy.
**Warning signs:** grep returns no matches or returns entire document as one "sentence".

### Pitfall 5: Re-index Race Condition
**What goes wrong:** User sends a /chat request while /reindex is in progress. The chat loads the old session data, then re-index overwrites it, creating inconsistency.
**Why it happens:** No locking between /chat reads and /reindex writes on Modal Volume.
**How to avoid:** Accept this for takehome scope. The frontend disables send during re-index (CONTEXT.md decision), which mitigates the window. If both requests happen, the stale answer is still valid -- user can re-ask after re-index completes.
**Warning signs:** None in practice due to frontend guard.

### Pitfall 6: Stale Files Array Not Persisted Per Message
**What goes wrong:** After scrolling up to an old message, the staleness banner is gone because `staleFiles` was stored as component state, not on the message.
**Why it happens:** The spec's `setStaleFiles(event.files)` stores it in component state which is shared/overwritten by new messages.
**How to avoid:** Store `stale_files` on each assistant message in IndexedDB (as shown in Pattern 4 above). Render banner from message data, not component state.
**Warning signs:** Banners disappear when new messages arrive or on page reload.

## Code Examples

### check_staleness with Cache
```python
# Source: spec.md check_staleness + CONTEXT.md caching decision
import asyncio, aiohttp, time

_staleness_cache: dict[str, tuple[bool, float]] = {}
STALENESS_TTL = 60

async def get_file_metadata(session, file_id, access_token):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,modifiedTime"
    async with session.get(url, headers={"Authorization": f"Bearer {access_token}"}) as r:
        if r.status == 404:
            return {"file_id": file_id, "error": "not_found"}
        if r.status == 403:
            return {"file_id": file_id, "error": "access_denied"}
        return await r.json()

async def check_staleness(file_list, access_token):
    now = time.time()
    to_check = []
    stale_ids = set()
    file_errors = {}  # file_id -> error type

    # Check cache first
    for f in file_list:
        fid = f["file_id"]
        if fid in _staleness_cache:
            is_stale, error, checked_at = _staleness_cache[fid]
            if now - checked_at < STALENESS_TTL:
                if is_stale:
                    stale_ids.add(fid)
                if error:
                    file_errors[fid] = error
                continue
        to_check.append(f)

    if not to_check:
        return stale_ids, file_errors

    async with aiohttp.ClientSession() as session:
        tasks = [get_file_metadata(session, f["file_id"], access_token) for f in to_check]
        results = await asyncio.gather(*tasks)

    for f, meta in zip(to_check, results):
        fid = f["file_id"]
        if "error" in meta:
            stale_ids.add(fid)
            file_errors[fid] = meta["error"]
            _staleness_cache[fid] = (True, meta["error"], now)
        elif meta["modifiedTime"] > f["indexed_at"]:
            stale_ids.add(fid)
            _staleness_cache[fid] = (True, None, now)
        else:
            _staleness_cache[fid] = (False, None, now)

    return stale_ids, file_errors
```

### extract_keywords with Fallback
```python
# Source: spec.md extract_keywords
import json

async def extract_keywords(query: str, model_key: str = "deepseek") -> list[str]:
    prompt = f"""Extract search keywords from this query for a keyword search over documents.
Return 8-12 keyword variants: synonyms, abbreviations, related terms, and the original terms.
Respond with ONLY a JSON array of strings. No explanation.

Query: {query}

Example output: ["revenue", "sales", "income", "ARR", "MRR", "earnings", "Q3 revenue"]"""

    client, model = get_llm_client(model_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,
    )
    text = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        keywords = json.loads(text)
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            return keywords
    except json.JSONDecodeError:
        pass

    # Fallback: split query on spaces, strip stopwords
    stopwords = {"what", "is", "the", "a", "an", "of", "in", "for", "and", "or",
                 "to", "how", "does", "do", "are", "was", "were", "been", "be"}
    return [w for w in query.lower().split() if w not in stopwords and len(w) > 1]
```

### grep_live with Text Cache
```python
# Source: spec.md grep_live + CONTEXT.md caching decision
import re, time

_grep_text_cache: dict[str, tuple[str, float]] = {}
GREP_TEXT_TTL = 300  # 5 minutes

async def grep_live(file_id, keywords, access_token):
    now = time.time()

    # Check text cache
    if file_id in _grep_text_cache:
        text, fetched_at = _grep_text_cache[file_id]
        if now - fetched_at < GREP_TEXT_TTL:
            pass  # use cached text
        else:
            text = await fetch_and_extract(file_id, access_token)
            _grep_text_cache[file_id] = (text, now)
    else:
        text = await fetch_and_extract(file_id, access_token)
        _grep_text_cache[file_id] = (text, now)

    sentences = re.split(r'(?<=[.!?])\s+', text)
    pattern = "|".join(re.escape(k) for k in keywords)
    results = []

    for i, sentence in enumerate(sentences):
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            window = sentences[max(0, i-1):min(len(sentences), i+2)]
            results.append({
                "text": " ".join(window),
                "matched_keyword": match.group(0),
                "sentence_index": i,
                "file_id": file_id,
            })
        if len(results) >= 15:
            break

    return results
```

### SSE Staleness Event Emission (Modified /chat)
```python
# Source: spec.md /chat endpoint with staleness
async def event_stream():
    # 1. Parallel: staleness + embedding
    stale_ids_task = check_staleness(body.file_list, access_token)
    embed_task = embed_query(body.query)
    (stale_ids, file_errors), query_vec = await asyncio.gather(
        stale_ids_task, embed_task
    )

    # 2. Emit staleness warnings BEFORE any tokens
    if stale_ids:
        stale_info = []
        for f in body.file_list:
            if f["file_id"] in stale_ids:
                error = file_errors.get(f["file_id"])
                stale_info.append({
                    "file_name": f["file_name"],
                    "file_id": f["file_id"],
                    "error": error,  # None, "not_found", or "access_denied"
                })
        yield f'data: {json.dumps({"type": "staleness", "files": stale_info})}\n\n'

    # 3. Hybrid retrieval
    retrieved, grep_results = await hybrid_retrieve(
        body.query, chunks, embeddings, body.file_list,
        stale_ids, query_vec, access_token
    )

    # 4-6. Stream LLM, citations, [DONE] -- same as Phase 3
```

### Frontend StalenessBanner Component
```typescript
// Source: CONTEXT.md locked decisions
interface StalenessInfo {
  file_name: string;
  file_id: string;
  error?: "not_found" | "access_denied" | null;
}

function StalenessBanner({
  info,
  sessionId,
  onReindexComplete,
}: {
  info: StalenessInfo;
  sessionId: string;
  onReindexComplete: (fileId: string, indexedAt: string) => void;
}) {
  const [isReindexing, setIsReindexing] = useState(false);

  // Deleted file: red banner, no re-index button
  if (info.error === "not_found") {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded-md text-sm">
        This file no longer exists in Google Drive. Old answers may be outdated.
      </div>
    );
  }

  // Access revoked: orange banner, re-authenticate button
  if (info.error === "access_denied") {
    return (
      <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded-md text-sm flex justify-between">
        <span>Access to {info.file_name} was revoked. Check your Google Drive permissions.</span>
        <Button variant="outline" size="sm">Re-authenticate</Button>
      </div>
    );
  }

  // Stale file: yellow banner with re-index button
  return (
    <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-2 rounded-md text-sm flex justify-between items-center">
      <span>
        <AlertTriangle className="inline h-4 w-4 mr-1" />
        {info.file_name} was modified after indexing -- showing live search results.
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={isReindexing}
        onClick={handleReindex}
      >
        {isReindexing ? (
          <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Re-indexing...</>
        ) : (
          "Re-index this file"
        )}
      </Button>
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM decides retrieval method | Deterministic staleness routing | This spec's design | Removes routing errors entirely; binary check, not model judgment |
| Re-crawl entire session on change | Per-file surgical re-index | This spec's design | Faster re-index, other files untouched |
| No staleness signal to user | Explicit banners with re-index action | This spec's design | User understands answer quality and can act on it |

## Open Questions

1. **Staleness event data structure**
   - What we know: Spec shows `{ type: "staleness", files: ["report.pdf"] }` (just names). CONTEXT.md requires three banner types (stale/deleted/revoked).
   - What's unclear: Whether to send error type per file in the SSE event, or make a separate check on the frontend.
   - Recommendation: Extend the event to include error type per file: `{ type: "staleness", files: [{ file_name, file_id, error }] }`. Backend already knows the error from metadata check.

2. **Stale files stored on IndexedDB message**
   - What we know: CONTEXT.md says banners re-appear on scroll-up. Spec stores staleFiles in component state only.
   - What's unclear: Whether to add stale_files to the IndexedDB message schema.
   - Recommendation: Add `stale_files` field to the message record in IndexedDB. This ensures banners survive page reload and scroll.

3. **grep_live for Sheets/CSV content**
   - What we know: Sentence splitting regex (`(?<=[.!?])\s+`) assumes prose text.
   - What's unclear: How to handle CSV/tabular content where rows don't end with periods.
   - Recommendation: Split on newlines for CSV content. Check the file's mime_type and use appropriate split strategy.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (frontend) + pytest (backend) |
| Config file | vitest.config.ts / pytest.ini (from Phase 1 setup) |
| Quick run command | `pytest tests/test_staleness.py tests/test_grep.py tests/test_reindex.py -x --timeout=10` |
| Full suite command | `pytest tests/ && pnpm test --run` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETR-03 | check_staleness returns stale file_ids when modifiedTime > indexed_at | unit | `pytest tests/test_staleness.py::test_check_staleness -x` | Wave 0 |
| RETR-03 | check_staleness treats 403/404 as stale | unit | `pytest tests/test_staleness.py::test_staleness_error_handling -x` | Wave 0 |
| RETR-03 | Staleness cache respects 60s TTL | unit | `pytest tests/test_staleness.py::test_staleness_cache_ttl -x` | Wave 0 |
| RETR-04 | hybrid_retrieve partitions fresh/stale chunks correctly | unit | `pytest tests/test_staleness.py::test_hybrid_partition -x` | Wave 0 |
| RETR-05 | extract_keywords returns 8-12 keyword variants | unit | `pytest tests/test_grep.py::test_extract_keywords -x` | Wave 0 |
| RETR-05 | extract_keywords fallback on JSON parse failure | unit | `pytest tests/test_grep.py::test_extract_keywords_fallback -x` | Wave 0 |
| RETR-06 | grep_live returns matches with context windows | unit | `pytest tests/test_grep.py::test_grep_live_matches -x` | Wave 0 |
| RETR-06 | grep_live caps at 15 results | unit | `pytest tests/test_grep.py::test_grep_live_cap -x` | Wave 0 |
| RETR-06 | grep text cache respects 5min TTL | unit | `pytest tests/test_grep.py::test_grep_text_cache -x` | Wave 0 |
| RETR-07 | reindex_file replaces only target file's chunks | unit | `pytest tests/test_reindex.py::test_surgical_replacement -x` | Wave 0 |
| RETR-07 | reindex_file invalidates caches | unit | `pytest tests/test_reindex.py::test_cache_invalidation -x` | Wave 0 |
| CHAT-05 | /chat emits staleness SSE event before tokens | integration | `pytest tests/test_chat_endpoint.py::test_staleness_event -x` | Wave 0 |
| CHAT-05 | Staleness banner renders for stale files | unit (frontend) | `pnpm test -- --run tests/staleness-banner.test.ts` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_staleness.py tests/test_grep.py tests/test_reindex.py -x --timeout=10`
- **Per wave merge:** `pytest tests/ && pnpm test --run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_staleness.py` -- check_staleness, staleness cache, hybrid partition, error handling
- [ ] `tests/test_grep.py` -- extract_keywords, grep_live, grep text cache, keyword fallback
- [ ] `tests/test_reindex.py` -- surgical replacement, cache invalidation, indexed_at return
- [ ] `tests/test_chat_endpoint.py::test_staleness_event` -- SSE staleness event emission (extend existing file)
- [ ] `frontend/tests/staleness-banner.test.ts` -- banner variants (yellow/red/orange), re-index button states

## Sources

### Primary (HIGH confidence)
- spec.md lines 870-1030 -- Complete code for check_staleness, grep_live, extract_keywords, hybrid_retrieve, reindex_file, /reindex endpoint
- spec.md lines 1119-1149 -- extract_keywords with LLM prompt and fallback
- spec.md lines 1505-1677 -- Modified /chat endpoint with staleness events, useStream hook with staleFiles handling
- spec.md lines 1395-1470 -- Edge cases for staleness (deleted files, false positives, latency)
- 04-CONTEXT.md -- All locked decisions for caching, parallelism, UI behavior, edge cases

### Secondary (MEDIUM confidence)
- Phase 3 03-RESEARCH.md -- Established /chat endpoint pattern, SSE event format, useStream hook structure
- Phase 1 01-01-PLAN.md -- Backend scaffold patterns (auth, config, Modal app structure)

### Tertiary (LOW confidence)
- None -- all Phase 4 patterns are fully specified in spec.md and CONTEXT.md

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries needed; all functions specified in spec
- Architecture: HIGH -- spec provides complete code for every function; CONTEXT.md locks parallelism/caching decisions
- Pitfalls: HIGH -- edge cases explicitly documented in spec (timestamp format, empty arrays, JSON parse failures, race conditions)
- Frontend banners: MEDIUM -- three banner variants and re-index flow are specified but component composition is discretionary

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, spec-driven implementation)
