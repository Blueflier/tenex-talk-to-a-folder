# Phase 6: Eval Harness - Research

**Researched:** 2026-03-05
**Domain:** RAG evaluation pipeline, QASPER dataset, token F1 scoring
**Confidence:** HIGH

## Summary

This phase builds a standalone Python eval pipeline that ingests QASPER academic papers locally (bypassing Drive), runs questions through the existing retrieval + chat pipeline via HTTP, scores responses with token-level F1, and classifies failures diagnostically. A separate Drive delta script compares local vs Drive-fetched scores.

The QASPER dataset from AllenAI contains 1,585 NLP papers with 5,049 questions. Each question has multiple annotator answers categorized as yes/no, extractive, abstractive, or unanswerable. The standard evaluation approach is max-F1-across-annotators with SQuAD-style token normalization. The eval harness reuses existing `chunking.py` and `embedding.py` directly for local PDF processing, then hits `POST /chat` via HTTP for end-to-end testing.

**Primary recommendation:** Use HuggingFace `datasets` library to load QASPER, select 5 papers by question density, process PDFs locally with existing `chunk_pdf` + `embed_chunks`, hit local uvicorn `/chat` endpoint via `httpx`, score with SQuAD-style token F1, and classify failures with heuristic checks on chunk coverage and retrieval similarity.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Local PDF ingestion -- bypass Drive API entirely, no Google auth needed for eval
- 5 papers auto-selected from QASPER (optimized for question density and manageable size, reproducible via seed)
- Eval runs against HTTP endpoints (POST /chat via local uvicorn), testing the full stack including SSE parsing
- QASPER data downloaded locally, gitignored, README documents download link for others
- Results output as JSON file with summary printed to stdout (overall F1, per-paper breakdown, diagnostic counts)
- First run hits OpenAI API for embeddings, caches to eval/cache/ (gitignored)
- Per-paper cache files: {paper_id}_embeddings.npy + _chunks.json (mirrors storage.py pattern)
- Manual invalidation -- delete eval/cache/ to force re-embedding, documented in README
- Automated heuristics for diagnostic classification (no LLM classifier)
- CRAWL_MISS: passage-level check -- search for gold answer text in all extracted chunks
- RETRIEVAL_MISS: semantic similarity -- embed gold answer, compare cosine similarity to retrieved chunks
- STALE_MISS: N/A for local eval runs -- only applies in Drive delta test (EVAL-04)
- SYNTHESIS_FAIL: answer existed in retrieved chunks but LLM generated wrong response
- Token-level F1 as sole metric (no LLM judge needed)
- All QASPER question types included: yes/no, extractive, abstractive, unanswerable
- Multiple annotator answers: max F1 across annotators (standard QASPER approach)
- Separate script: eval/run_drive_delta.py from main eval eval/run_eval.py
- Drive folder link read from config file (eval/config.json)
- Delta threshold: 0.10 absolute F1 difference
- Single Python script: python eval/run_eval.py
- Simple print statements for progress (no tqdm dependency)

### Claude's Discretion
- Answer type-aware scoring (exact match for yes/no/unanswerable vs token F1 for extractive/abstractive)
- Auto-selection criteria for the 5 QASPER papers
- SSE response parsing approach in eval client
- eval/config.json schema and defaults
- Exact F1 tokenization/normalization approach

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EVAL-01 | QASPER dataset integration for eval pipeline | HuggingFace `datasets` library loads allenai/qasper; full_text contains section paragraphs; qas contains questions with annotator answers; chunk_pdf processes paper PDFs locally |
| EVAL-02 | Diagnostic classification: CRAWL_MISS, RETRIEVAL_MISS, STALE_MISS, SYNTHESIS_FAIL | Heuristic classification using substring search (CRAWL_MISS), cosine similarity of gold answer embedding vs retrieved chunks (RETRIEVAL_MISS), STALE_MISS only in Drive delta, SYNTHESIS_FAIL as fallback |
| EVAL-03 | LLM judge for automated correctness scoring | User decided: token-level F1 replaces LLM judge. SQuAD-style normalize_answer + token overlap F1. Exact match for yes/no/unanswerable. Max F1 across annotators. |
| EVAL-04 | Drive delta test: compare local vs Drive-via-PyMuPDF on 5 papers | Separate script eval/run_drive_delta.py; user uploads PDFs to Drive manually; config.json holds Drive folder link; delta = abs(local_f1 - drive_f1); threshold 0.10 |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| datasets | latest | Load QASPER from HuggingFace | Official distribution channel for allenai/qasper |
| httpx | latest | Async HTTP client for POST /chat | Already in requirements.txt; async SSE streaming support |
| numpy | latest | Embedding cache, cosine similarity | Already used throughout backend |
| pymupdf | latest | PDF text extraction for QASPER papers | Already used in chunking.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openai | latest | Embed queries and gold answers | Already in requirements.txt; needed for embedding cache |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| datasets library | Direct JSON download | datasets handles caching, versioning, splits automatically |
| httpx for SSE | aiohttp | httpx already in deps and simpler for streaming line parsing |

**Installation:**
```bash
pip install datasets
```

Only `datasets` is new. All others (`httpx`, `numpy`, `pymupdf`, `openai`) are already in requirements.txt.

## Architecture Patterns

### Recommended Project Structure
```
eval/
├── run_eval.py           # Main eval CLI entry point
├── run_drive_delta.py    # Drive delta comparison script
├── config.json           # Drive folder link + defaults
├── scoring.py            # normalize_answer, token_f1, exact_match
├── classify.py           # CRAWL_MISS, RETRIEVAL_MISS, SYNTHESIS_FAIL
├── dataset.py            # QASPER loading, paper selection, answer extraction
├── client.py             # HTTP client for POST /chat with SSE parsing
├── cache.py              # Embedding cache load/save (mirrors storage.py)
├── README.md             # Setup instructions, QASPER download link
└── cache/                # gitignored: {paper_id}_embeddings.npy + _chunks.json
```

### Pattern 1: QASPER Dataset Loading and Paper Selection
**What:** Load QASPER via HuggingFace datasets, select 5 papers by question density
**When to use:** Initial dataset setup
**Example:**
```python
# Source: HuggingFace datasets docs + QASPER dataset card
from datasets import load_dataset
import random

def load_qasper_papers(n=5, seed=42):
    """Select n papers optimized for question density and manageable size."""
    ds = load_dataset("allenai/qasper", split="test")

    # Score papers by question count / full_text length ratio
    candidates = []
    for paper in ds:
        n_questions = len(paper["qas"]["question"])
        # Count paragraphs across all sections
        total_paragraphs = sum(
            len(paragraphs)
            for paragraphs in paper["full_text"]["paragraphs"]
        )
        if n_questions >= 3 and total_paragraphs <= 200:  # manageable size
            candidates.append({
                "paper": paper,
                "density": n_questions / max(total_paragraphs, 1),
                "n_questions": n_questions,
            })

    # Sort by density, take top pool, then sample for diversity
    candidates.sort(key=lambda x: x["density"], reverse=True)
    rng = random.Random(seed)
    selected = rng.sample(candidates[:20], min(n, len(candidates)))
    return [c["paper"] for c in selected]
```

### Pattern 2: QASPER Answer Extraction
**What:** Extract gold answers from QASPER's nested annotator structure
**When to use:** Building eval samples from QASPER questions
**Example:**
```python
# Source: QASPER dataset card (HuggingFace)
def extract_gold_answers(qas_entry):
    """Extract all annotator answers for a question.

    Returns list of dicts: {type, text} where type is
    'yes_no', 'extractive', 'abstractive', or 'unanswerable'.
    """
    answers = []
    for answer in qas_entry["answers"]["answer"]:
        if answer["unanswerable"]:
            answers.append({"type": "unanswerable", "text": "Unanswerable"})
        elif answer["yes_no"] is not None:
            answers.append({"type": "yes_no", "text": "Yes" if answer["yes_no"] else "No"})
        elif answer["extractive_spans"]:
            # Join multiple spans with comma (standard approach)
            text = ", ".join(answer["extractive_spans"])
            answers.append({"type": "extractive", "text": text})
        elif answer["free_form_answer"]:
            answers.append({"type": "abstractive", "text": answer["free_form_answer"]})
    return answers
```

### Pattern 3: SQuAD-style Token F1 Scoring
**What:** Normalize and compute token-level F1 between prediction and reference
**When to use:** Scoring every eval sample
**Example:**
```python
# Source: SQuAD evaluation script / QASPER baseline (allenai/qasper-led-baseline)
import re
import string
from collections import Counter

def normalize_answer(text: str) -> str:
    """Lowercase, remove articles/punctuation, collapse whitespace."""
    text = text.lower()
    # Remove articles
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    # Remove punctuation
    text = ''.join(ch for ch in text if ch not in string.punctuation)
    # Collapse whitespace
    text = ' '.join(text.split())
    return text

def token_f1(prediction: str, reference: str) -> float:
    """Compute token-level F1 between prediction and reference."""
    pred_tokens = normalize_answer(prediction).split()
    ref_tokens = normalize_answer(reference).split()

    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0

    common = Counter(pred_tokens) & Counter(ref_tokens)
    num_common = sum(common.values())

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)

def score_answer(prediction: str, gold_answers: list[dict]) -> float:
    """Max F1 across annotators, type-aware scoring."""
    scores = []
    for gold in gold_answers:
        if gold["type"] in ("yes_no", "unanswerable"):
            # Exact match for categorical answers
            score = 1.0 if normalize_answer(prediction) == normalize_answer(gold["text"]) else 0.0
        else:
            # Token F1 for extractive/abstractive
            score = token_f1(prediction, gold["text"])
        scores.append(score)
    return max(scores) if scores else 0.0
```

### Pattern 4: SSE Response Parsing in Eval Client
**What:** Parse SSE stream from POST /chat to extract full response text
**When to use:** Eval client calling the chat endpoint
**Example:**
```python
# Source: Existing SSE format from chat.py: data: {json} with types token, citations, etc.
import httpx
import json

async def query_chat(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    query: str,
    auth_token: str = "",
) -> dict:
    """Send query to /chat and parse SSE response into text + citations."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    response = await client.post(
        f"{base_url}/chat",
        json={"session_id": session_id, "query": query},
        headers=headers,
        timeout=120.0,
    )

    full_text = ""
    citations = []

    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]  # strip "data: "
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "token":
            full_text += event.get("content", "")
        elif event.get("type") == "citations":
            citations = event.get("citations", [])
        elif event.get("type") == "no_results":
            full_text = "I couldn't find that in the provided files."

    return {"text": full_text, "citations": citations}
```

### Pattern 5: Diagnostic Classification
**What:** Classify why an answer was wrong
**When to use:** Post-scoring analysis of each sample
**Example:**
```python
# Heuristic-based classification per CONTEXT.md decisions
import numpy as np

def classify_failure(
    gold_text: str,
    all_chunks: list[dict],
    retrieved_chunks: list[dict],
    gold_embedding: np.ndarray,
    retrieved_embeddings: np.ndarray,
    similarity_threshold: float = 0.7,
) -> str:
    """Classify why retrieval/generation failed.

    Returns: CRAWL_MISS, RETRIEVAL_MISS, or SYNTHESIS_FAIL
    """
    # CRAWL_MISS: gold answer text not found in ANY chunk
    gold_normalized = gold_text.lower().strip()
    found_in_chunks = any(
        gold_normalized in chunk["text"].lower()
        for chunk in all_chunks
    )
    if not found_in_chunks:
        return "CRAWL_MISS"

    # RETRIEVAL_MISS: gold answer similar to some chunk but not in retrieved set
    # Compare gold_embedding to retrieved_embeddings via cosine sim
    if retrieved_embeddings.size > 0:
        sims = np.dot(retrieved_embeddings, gold_embedding) / (
            np.linalg.norm(retrieved_embeddings, axis=1) * np.linalg.norm(gold_embedding) + 1e-9
        )
        if np.max(sims) < similarity_threshold:
            return "RETRIEVAL_MISS"
    else:
        return "RETRIEVAL_MISS"

    # If answer was in retrieved chunks but LLM still got it wrong
    return "SYNTHESIS_FAIL"
```

### Anti-Patterns to Avoid
- **Using LLM as judge when token F1 suffices:** User explicitly decided token F1 only. Do not add LLM-based evaluation.
- **Hitting Drive API from eval:** Local PDF ingestion only. The eval must work without Google auth.
- **Re-embedding on every run:** Cache embeddings after first run. The cache pattern mirrors storage.py.
- **Hardcoding paper IDs:** Use seed-based selection for reproducibility, not hardcoded IDs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| QASPER data loading | Custom JSON parser | `datasets.load_dataset("allenai/qasper")` | Handles download, caching, schema validation, splits |
| Token F1 normalization | Custom normalizer | SQuAD normalize_answer pattern | Battle-tested, standard in QA eval community |
| PDF text extraction | Custom extractor | Existing `chunk_pdf` from chunking.py | Already handles page-by-page extraction with PyMuPDF |
| Embedding batches | Custom batching | Existing `embed_chunks` from embedding.py | Already handles batching, retries, progress |
| Cosine similarity | Manual dot product | Existing `cosine_sim` from retrieval.py | Already handles norms correctly |

**Key insight:** Most of the eval pipeline is wiring -- the heavy lifting (chunking, embedding, retrieval, chat) already exists in the backend. The eval scripts are thin orchestration layers.

## Common Pitfalls

### Pitfall 1: QASPER full_text vs actual PDF
**What goes wrong:** QASPER provides `full_text` as structured sections, but the eval needs to process actual PDFs to test the real chunking pipeline.
**Why it happens:** The dataset includes parsed text, tempting shortcuts.
**How to avoid:** Download actual paper PDFs from Semantic Scholar/ArXiv using the paper IDs. Use `chunk_pdf` on real PDFs, not the pre-parsed text. The QASPER `full_text` is only useful as a reference for CRAWL_MISS checks.
**Warning signs:** If chunks look suspiciously clean with perfect section boundaries.

### Pitfall 2: Auth bypass for local eval
**What goes wrong:** POST /chat requires Authorization header with Google token.
**Why it happens:** The chat endpoint calls `get_google_user_id(token)` which hits Google's API.
**How to avoid:** Either (a) mock auth in a test mode, (b) run uvicorn with an env flag that skips auth, or (c) use synthetic user_id and pre-load session data directly. Option (c) is cleanest -- bypass the HTTP endpoint for data loading and only use it for chat queries with a test auth bypass.
**Warning signs:** 401 errors when running eval.

### Pitfall 3: SSE parsing edge cases
**What goes wrong:** Incomplete lines, buffering issues, or unexpected event formats.
**Why it happens:** SSE can split across TCP frames. The chat endpoint uses `data: {json}` format.
**How to avoid:** Use `httpx` async line iteration which handles buffering. Skip lines that don't start with `data: `. Handle `[DONE]` sentinel.
**Warning signs:** Truncated JSON, missing tokens in reassembled response.

### Pitfall 4: Embedding dimension mismatch
**What goes wrong:** Cached embeddings have different dimensions than query embeddings.
**Why it happens:** Model change or cache corruption.
**How to avoid:** Store embedding model name in cache metadata. Validate dimensions on load (should be 1536 for text-embedding-3-small).
**Warning signs:** Cosine similarity returns NaN or unexpected values.

### Pitfall 5: Rate limiting during eval
**What goes wrong:** The /chat endpoint has a 10 req/min rate limit per session.
**Why it happens:** Eval sends many queries rapidly.
**How to avoid:** Use a unique session_id per paper or per batch. Add small delays between requests. Or temporarily disable rate limiting for eval sessions.
**Warning signs:** 429 responses from the server.

### Pitfall 6: QASPER answer structure is nested
**What goes wrong:** Accessing answers incorrectly due to the nested annotator structure.
**Why it happens:** Each question has multiple annotators, each providing different answer types.
**How to avoid:** Always iterate `qas["answers"]["answer"]` (list of annotator responses). Check `unanswerable` first, then `yes_no`, then `extractive_spans`, then `free_form_answer`.
**Warning signs:** Empty gold answers, type errors on None values.

## Code Examples

### Embedding Cache (mirrors storage.py pattern)
```python
# Source: Existing storage.py base_path pattern
import json
from pathlib import Path
import numpy as np

CACHE_DIR = Path("eval/cache")

def save_paper_cache(paper_id: str, embeddings: np.ndarray, chunks: list[dict]):
    """Cache embeddings and chunks for a paper."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(CACHE_DIR / f"{paper_id}_embeddings.npy"), embeddings)
    with open(CACHE_DIR / f"{paper_id}_chunks.json", "w") as f:
        json.dump(chunks, f)

def load_paper_cache(paper_id: str) -> tuple[np.ndarray, list[dict]] | None:
    """Load cached embeddings and chunks. Returns None if not cached."""
    emb_path = CACHE_DIR / f"{paper_id}_embeddings.npy"
    chunks_path = CACHE_DIR / f"{paper_id}_chunks.json"
    if not emb_path.exists() or not chunks_path.exists():
        return None
    embeddings = np.load(str(emb_path))
    with open(chunks_path) as f:
        chunks = json.load(f)
    return embeddings, chunks
```

### eval/config.json Schema
```json
{
  "base_url": "http://localhost:8000",
  "n_papers": 5,
  "seed": 42,
  "similarity_threshold": 0.7,
  "drive_delta": {
    "drive_folder_link": "",
    "f1_delta_threshold": 0.10
  }
}
```

### Results JSON Output Format
```json
{
  "timestamp": "2026-03-05T12:00:00Z",
  "config": { "n_papers": 5, "seed": 42 },
  "overall_f1": 0.42,
  "per_paper": [
    {
      "paper_id": "abc123",
      "title": "Paper Title",
      "n_questions": 12,
      "f1": 0.45,
      "diagnostics": {
        "CRAWL_MISS": 2,
        "RETRIEVAL_MISS": 3,
        "SYNTHESIS_FAIL": 1,
        "CORRECT": 6
      }
    }
  ],
  "diagnostics_total": {
    "CRAWL_MISS": 5,
    "RETRIEVAL_MISS": 8,
    "SYNTHESIS_FAIL": 3,
    "CORRECT": 14
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BLEU/ROUGE for QA | Token F1 (SQuAD-style) | Standard since SQuAD 2016 | Token F1 better captures partial matches |
| LLM judge scoring | Token F1 + exact match | User decision | Simpler, reproducible, no extra LLM cost |
| Full dataset eval | 5-paper subset | User decision | Fast iteration, minutes not hours |

## Open Questions

1. **How to get actual PDF files for QASPER papers?**
   - What we know: QASPER provides paper IDs and parsed full_text. The actual PDFs need to come from ArXiv or Semantic Scholar.
   - What's unclear: Whether QASPER paper IDs map directly to ArXiv IDs. Some papers may not have freely available PDFs.
   - Recommendation: Use Semantic Scholar API (`GET /paper/{paper_id}`) to find ArXiv links. Fall back to reconstructing PDF-like text from QASPER `full_text` sections if PDF unavailable. Document the approach in README.

2. **Auth bypass strategy for local eval**
   - What we know: POST /chat requires Authorization header -> calls get_google_user_id
   - What's unclear: Best way to bypass auth without modifying production code
   - Recommendation: Add an `EVAL_MODE=true` env var check in auth.py that returns a synthetic user_id. Or pre-load session data into a local directory and patch VOLUME_PATH. The eval already needs uvicorn running locally, so a test mode flag is cleanest.

3. **QASPER `full_text` vs real PDF round-trip fidelity**
   - What we know: The eval tests the REAL chunking pipeline (PyMuPDF extraction). QASPER's pre-parsed text serves as ground truth for CRAWL_MISS checks.
   - What's unclear: How much extraction quality differs between PyMuPDF on the actual PDF vs QASPER's clean parsed text
   - Recommendation: This difference is exactly what the eval measures. CRAWL_MISS classification captures extraction losses.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already configured) |
| Config file | backend/requirements.txt includes pytest, pytest-asyncio |
| Quick run command | `python -m pytest eval/tests/ -x -q` |
| Full suite command | `python -m pytest eval/tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | QASPER loads and feeds questions through pipeline | integration | `python eval/run_eval.py --dry-run` (validate dataset loading without API calls) | No - Wave 0 |
| EVAL-02 | Each sample classified as CRAWL_MISS/RETRIEVAL_MISS/STALE_MISS/SYNTHESIS_FAIL | unit | `python -m pytest eval/tests/test_classify.py -x` | No - Wave 0 |
| EVAL-03 | Token F1 scoring produces correct results | unit | `python -m pytest eval/tests/test_scoring.py -x` | No - Wave 0 |
| EVAL-04 | Drive delta compares local vs Drive scores | unit | `python -m pytest eval/tests/test_drive_delta.py -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest eval/tests/ -x -q`
- **Per wave merge:** `python -m pytest eval/tests/ -v && python -m pytest backend/tests/ -v`
- **Phase gate:** Full suite green + one successful `python eval/run_eval.py --dry-run`

### Wave 0 Gaps
- [ ] `eval/tests/test_scoring.py` -- covers EVAL-03: normalize_answer, token_f1, exact_match, score_answer with all answer types
- [ ] `eval/tests/test_classify.py` -- covers EVAL-02: CRAWL_MISS, RETRIEVAL_MISS, SYNTHESIS_FAIL heuristics
- [ ] `eval/tests/test_dataset.py` -- covers EVAL-01: QASPER paper selection, answer extraction
- [ ] `eval/tests/test_drive_delta.py` -- covers EVAL-04: delta calculation, threshold check
- [ ] `eval/tests/__init__.py` -- package init
- [ ] `eval/tests/conftest.py` -- shared fixtures (sample chunks, embeddings, QASPER-like data)

## Sources

### Primary (HIGH confidence)
- QASPER dataset card: https://huggingface.co/datasets/allenai/qasper -- dataset structure, fields, splits
- QASPER evaluator implementation: https://github.com/Saiyam26/openai_ft/blob/main/qasper_evaluator.py -- normalize_answer, token F1, answer type handling
- Existing codebase: backend/chat.py, retrieval.py, chunking.py, embedding.py, storage.py -- SSE format, chunking API, embedding API, storage patterns

### Secondary (MEDIUM confidence)
- SQuAD evaluation methodology (via QASPER evaluator reference) -- normalize_answer standard approach
- AllenAI QASPER baseline: https://github.com/allenai/qasper-led-baseline -- baseline F1 scores (33.63)

### Tertiary (LOW confidence)
- Paper selection criteria (question density heuristic) -- reasonable but unvalidated approach

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - only new dep is `datasets`, all others already in project
- Architecture: HIGH - mirrors existing storage.py patterns, reuses chunking/embedding modules
- Pitfalls: HIGH - auth bypass and SSE parsing are known challenges from existing codebase
- Scoring: HIGH - SQuAD-style token F1 is well-documented standard

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, QASPER dataset unlikely to change)
