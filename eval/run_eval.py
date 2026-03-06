"""Main eval CLI entry point.

Runs QASPER papers through the full RAG pipeline (chunking, embedding,
retrieval, chat) and scores responses with token F1. Supports --dry-run
for validation without API calls.

Usage:
    EVAL_MODE=1 python eval/run_eval.py          # full eval
    EVAL_MODE=1 python eval/run_eval.py --dry-run # validate only
"""

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

import httpx
import numpy as np
from openai import AsyncOpenAI

# Ensure project root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.chunking import chunk_pdf, recursive_chunk
from backend.embedding import embed_chunks
from backend.storage import save_session
from eval.cache import load_paper_cache, save_paper_cache
from eval.classify import classify_failure
from eval.client import query_chat
from eval.dataset import extract_gold_answers, load_qasper_papers
from eval.scoring import score_answer


def load_config() -> dict:
    """Load eval configuration from eval/config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


def reconstruct_chunks_from_fulltext(paper: dict) -> list[dict]:
    """Create synthetic chunks from QASPER full_text sections.

    Used as fallback when actual PDF is unavailable.
    """
    title = paper.get("title", "unknown")
    chunks = []
    sections = paper.get("full_text", {})
    section_names = sections.get("section_name", [])
    paragraphs_list = sections.get("paragraphs", [])

    for sec_idx, (sec_name, paragraphs) in enumerate(
        zip(section_names, paragraphs_list)
    ):
        for para_idx, para in enumerate(paragraphs):
            if not para.strip():
                continue
            # Apply recursive chunking for consistency with real PDF path
            sub_chunks = recursive_chunk(para)
            for ci, chunk_text in enumerate(sub_chunks):
                chunks.append(
                    {
                        "text": chunk_text,
                        "source": title,
                        "section": sec_name,
                        "chunk_index": len(chunks),
                    }
                )

    return chunks


def try_download_pdf(paper: dict) -> bytes | None:
    """Try to download the actual PDF for a QASPER paper.

    Attempts Semantic Scholar API to find an open-access PDF URL.
    Returns PDF bytes or None if unavailable.
    """
    paper_id = paper.get("id", paper.get("article_id", ""))
    if not paper_id:
        return None

    try:
        # Try Semantic Scholar API for open access PDF
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=openAccessPdf"
        req = Request(url, headers={"User-Agent": "eval-harness/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            pdf_url = data.get("openAccessPdf", {})
            if pdf_url and pdf_url.get("url"):
                pdf_req = Request(
                    pdf_url["url"],
                    headers={"User-Agent": "eval-harness/1.0"},
                )
                with urlopen(pdf_req, timeout=30) as pdf_resp:
                    return pdf_resp.read()
    except Exception:
        pass

    return None


class FakeVolume:
    """Stub volume for save_session compatibility."""

    def commit(self):
        pass


async def process_paper(
    paper: dict,
    paper_idx: int,
    total_papers: int,
    config: dict,
    openai_client: AsyncOpenAI,
    temp_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Process a single paper: chunk, embed, query, score.

    Returns per-paper result dict with f1, diagnostics, etc.
    """
    title = paper.get("title", "unknown")
    paper_id = paper.get("id", paper.get("article_id", f"paper_{paper_idx}"))
    print(f"\nProcessing paper {paper_idx + 1}/{total_papers}: {title}")

    # Step 1: Get chunks and embeddings (from cache or fresh)
    cached = load_paper_cache(paper_id)
    if cached is not None:
        embeddings, chunks = cached
        print(f"  Loaded from cache ({len(chunks)} chunks)")
    else:
        # Try real PDF first, fall back to full_text reconstruction
        pdf_bytes = try_download_pdf(paper)
        if pdf_bytes is not None:
            chunks = chunk_pdf(pdf_bytes, title)
            print(f"  Downloaded PDF, chunked into {len(chunks)} chunks")
        else:
            chunks = reconstruct_chunks_from_fulltext(paper)
            print(
                f"  PDF unavailable, reconstructed {len(chunks)} chunks from full_text"
            )

        if not chunks:
            print("  WARNING: No chunks extracted, skipping paper")
            return {
                "paper_id": paper_id,
                "title": title,
                "n_questions": 0,
                "f1": 0.0,
                "diagnostics": {},
                "scores": [],
            }

        if dry_run:
            # Create dummy embeddings for dry run
            embeddings = np.zeros((len(chunks), 1536), dtype=np.float32)
        else:
            print(f"  Embedding {len(chunks)} chunks...")
            embeddings = await embed_chunks(openai_client, chunks)
            save_paper_cache(paper_id, embeddings, chunks)
            print("  Cached embeddings")

    # Step 2: Pre-load session for this paper
    session_id = paper_id
    user_id = "eval-user"
    volume = FakeVolume()
    save_session(user_id, session_id, embeddings, chunks, volume, base_path=temp_dir)

    # Step 3: Process questions
    qas = paper.get("qas", {})
    questions = qas.get("question", [])
    answers_list = qas.get("answers", [])

    scores = []
    diagnostics = {"CORRECT": 0, "CRAWL_MISS": 0, "RETRIEVAL_MISS": 0, "SYNTHESIS_FAIL": 0}

    for q_idx, question in enumerate(questions):
        qas_entry = {
            "answers": {"answer": answers_list[q_idx]["answer"]}
            if q_idx < len(answers_list)
            else {"answer": []},
        }
        gold_answers = extract_gold_answers(qas_entry)

        truncated = question[:80] + "..." if len(question) > 80 else question
        print(f"  Question {q_idx + 1}/{len(questions)}: {truncated}")

        if dry_run:
            print(f"    Gold answers: {[a['text'][:60] for a in gold_answers]}")
            scores.append(0.0)
            continue

        # Query the chat endpoint
        try:
            async with httpx.AsyncClient() as http_client:
                result = await query_chat(
                    http_client,
                    config["base_url"],
                    session_id,
                    question,
                    auth_token="eval-bypass",
                )
            response_text = result["text"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print("    Rate limited, waiting 10s...")
                await asyncio.sleep(10)
                try:
                    async with httpx.AsyncClient() as http_client:
                        result = await query_chat(
                            http_client,
                            config["base_url"],
                            session_id,
                            question,
                            auth_token="eval-bypass",
                        )
                    response_text = result["text"]
                except Exception:
                    print("    Retry failed, scoring 0")
                    scores.append(0.0)
                    diagnostics["SYNTHESIS_FAIL"] += 1
                    continue
            else:
                print(f"    HTTP error {e.response.status_code}, scoring 0")
                scores.append(0.0)
                diagnostics["SYNTHESIS_FAIL"] += 1
                continue
        except Exception as e:
            print(f"    Error: {e}, scoring 0")
            scores.append(0.0)
            diagnostics["SYNTHESIS_FAIL"] += 1
            continue

        # Score
        f1 = score_answer(response_text, gold_answers)
        scores.append(f1)

        if f1 >= 1.0:
            diagnostics["CORRECT"] += 1
            print(f"    F1={f1:.2f} CORRECT")
        else:
            # Classify failure
            try:
                # Get best gold answer text for embedding
                best_gold = max(gold_answers, key=lambda a: len(a["text"]))
                gold_emb = await embed_chunks(
                    openai_client,
                    [{"text": best_gold["text"]}],
                )
                gold_emb = gold_emb[0]

                # Use all embeddings as "retrieved" approximation
                category = classify_failure(
                    best_gold["text"],
                    chunks,
                    chunks[:10],  # approximate retrieved set
                    gold_emb,
                    embeddings[:10],
                    similarity_threshold=config.get("similarity_threshold", 0.7),
                )
            except Exception:
                category = "SYNTHESIS_FAIL"

            diagnostics[category] = diagnostics.get(category, 0) + 1
            print(f"    F1={f1:.2f} {category}")

        # Rate limiting delay
        await asyncio.sleep(1)

    paper_f1 = sum(scores) / len(scores) if scores else 0.0

    return {
        "paper_id": paper_id,
        "title": title,
        "n_questions": len(questions),
        "f1": paper_f1,
        "diagnostics": diagnostics,
        "scores": scores,
    }


async def main():
    parser = argparse.ArgumentParser(description="Run QASPER eval pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate dataset loading and paper selection without API calls",
    )
    args = parser.parse_args()

    config = load_config()
    print(f"Eval config: n_papers={config['n_papers']}, seed={config['seed']}")

    # Load QASPER papers
    print("Loading QASPER dataset...")
    papers = load_qasper_papers(n=config["n_papers"], seed=config["seed"])
    print(f"Selected {len(papers)} papers")

    openai_client = AsyncOpenAI() if not args.dry_run else None

    # Create temp directory for session data
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        results = []

        for i, paper in enumerate(papers):
            result = await process_paper(
                paper,
                i,
                len(papers),
                config,
                openai_client,
                temp_path,
                dry_run=args.dry_run,
            )
            results.append(result)

    # Aggregate
    all_scores = [s for r in results for s in r["scores"]]
    overall_f1 = sum(all_scores) / len(all_scores) if all_scores else 0.0

    diagnostics_total = {"CORRECT": 0, "CRAWL_MISS": 0, "RETRIEVAL_MISS": 0, "SYNTHESIS_FAIL": 0}
    for r in results:
        for k, v in r["diagnostics"].items():
            diagnostics_total[k] = diagnostics_total.get(k, 0) + v

    # Build output
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {"n_papers": config["n_papers"], "seed": config["seed"]},
        "overall_f1": round(overall_f1, 4),
        "per_paper": [
            {
                "paper_id": r["paper_id"],
                "title": r["title"],
                "n_questions": r["n_questions"],
                "f1": round(r["f1"], 4),
                "diagnostics": r["diagnostics"],
            }
            for r in results
        ],
        "diagnostics_total": diagnostics_total,
    }

    # Write results JSON
    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {results_path}")

    # Print summary table
    print("\n" + "=" * 60)
    print(f"EVAL SUMMARY  (overall F1: {overall_f1:.4f})")
    print("=" * 60)
    print(f"{'Paper':<35} {'Qs':>4} {'F1':>6}")
    print("-" * 60)
    for r in results:
        title = r["title"][:32] + "..." if len(r["title"]) > 32 else r["title"]
        print(f"{title:<35} {r['n_questions']:>4} {r['f1']:>6.4f}")
    print("-" * 60)
    print(f"\nDiagnostics: {diagnostics_total}")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made. Dataset loading validated.")


if __name__ == "__main__":
    asyncio.run(main())
