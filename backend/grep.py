"""Keyword extraction and grep-based live retrieval for stale files.

NOTE: _grep_text_cache is in-memory and per-container. With multiple Modal
replicas, each container maintains its own cache. Redundant fetches are safe.
"""
from __future__ import annotations

import json
import logging
import re
import time

from backend.config import GREP_MAX_RESULTS, get_llm_client
from backend.drive import EXPORT_MIME_MAP
from backend.drive_client import DRIVE_API_BASE, drive_session

logger = logging.getLogger(__name__)

# Cache: file_id -> (text, fetched_at_epoch)
_grep_text_cache: dict[str, tuple[str, float]] = {}
GREP_TEXT_TTL = 300

STOPWORDS = {
    "what", "is", "the", "a", "an", "of", "in", "for", "and", "or",
    "to", "it", "that", "this", "are", "was", "were", "be", "been",
    "how", "do", "does", "did", "will", "would", "can", "could",
    "should", "shall", "may", "might", "has", "have", "had",
    "who", "which", "where", "when", "why", "with", "from", "by",
    "on", "at", "but", "not", "no", "so", "if", "my", "your",
}


async def extract_keywords(query: str, model_key: str = "deepseek") -> list[str]:
    """Extract 8-12 keyword variants from query via LLM, with stopword fallback."""
    prompt = f"""Extract search keywords from this query for a keyword search over documents.
Return 8-12 keyword variants: synonyms, abbreviations, related terms, and the original terms.
Respond with ONLY a JSON array of strings. No explanation.

Query: {query}

Example output: ["revenue", "sales", "income", "ARR", "MRR", "earnings", "Q3 revenue"]"""

    try:
        client, model_name = get_llm_client()
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        text = response.choices[0].message.content.strip()

        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

        parsed = json.loads(text)
        if isinstance(parsed, list) and all(isinstance(k, str) for k in parsed):
            return parsed
    except (json.JSONDecodeError, Exception):
        pass

    # Fallback: split on spaces, strip stopwords, filter short words
    return [w for w in query.lower().split() if w not in STOPWORDS and len(w) > 1]


async def fetch_and_extract(
    file_id: str, access_token: str, *, mime_type: str = ""
) -> str:
    """Fetch file content from Google Drive and return extracted text.

    For Google Workspace files (Docs/Sheets/Slides), uses the /export endpoint.
    For binary files (PDF, TXT, etc.), uses ?alt=media.
    """
    if mime_type in EXPORT_MIME_MAP:
        export_mime = EXPORT_MIME_MAP[mime_type]
        url = f"{DRIVE_API_BASE}/{file_id}/export?mimeType={export_mime}"
    else:
        url = f"{DRIVE_API_BASE}/{file_id}?alt=media"

    async with drive_session(access_token) as session:
        async with session.get(url) as r:
            r.raise_for_status()
            return await r.text()


async def grep_live(
    file_id: str, keywords: list[str], access_token: str,
    *, mime_type: str = "",
) -> list[dict]:
    """Search file text for keyword matches with context windows.

    Returns up to 15 match dicts with text, matched_keyword, sentence_index, file_id.
    Uses cached text within GREP_TEXT_TTL.
    """
    now = time.time()
    cached = _grep_text_cache.get(file_id)

    if cached and (now - cached[1]) < GREP_TEXT_TTL:
        text = cached[0]
    else:
        text = await fetch_and_extract(file_id, access_token, mime_type=mime_type)
        _grep_text_cache[file_id] = (text, time.time())

    # Split on sentence boundaries, but not after common abbreviations.
    # First protect abbreviations, then split, then restore.
    _ABBREV_RE = re.compile(r"\b(Dr|Mr|Mrs|Ms|Jr|Sr|Inc|Corp|Ltd|Prof|Gen|Gov|Vol|vs|etc|approx)\.")
    _SENTINEL = "\x00"
    protected = _ABBREV_RE.sub(lambda m: m.group(1) + _SENTINEL, text)
    sentences = re.split(r"(?<=[.!?])\s+", protected)
    sentences = [s.replace(_SENTINEL, ".") for s in sentences]
    if not keywords:
        return []

    pattern = "|".join(re.escape(k) for k in keywords)
    results = []

    for i, sentence in enumerate(sentences):
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            window = sentences[max(0, i - 1) : min(len(sentences), i + 2)]
            results.append(
                {
                    "text": " ".join(window),
                    "matched_keyword": match.group(0),
                    "sentence_index": i,
                    "file_id": file_id,
                }
            )
        if len(results) >= GREP_MAX_RESULTS:
            break

    return results
