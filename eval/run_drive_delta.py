"""Drive delta comparison script.

Compares local PDF eval F1 scores against Drive-fetched eval scores.
Flags papers where the delta exceeds the configured threshold.

Usage:
    EVAL_MODE=1 GOOGLE_ACCESS_TOKEN=... python eval/run_drive_delta.py
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.client import query_chat
from eval.dataset import extract_gold_answers, load_qasper_papers
from eval.scoring import score_answer


def compute_delta(
    local_scores: dict[str, float],
    drive_scores: dict[str, float],
) -> dict[str, float]:
    """Compute per-paper absolute F1 difference.

    Only includes papers present in both dicts (intersection).

    Args:
        local_scores: {paper_id: f1} from local eval.
        drive_scores: {paper_id: f1} from Drive eval.

    Returns:
        {paper_id: abs(local_f1 - drive_f1)} for shared papers.
    """
    common_keys = set(local_scores) & set(drive_scores)
    return {
        pid: abs(local_scores[pid] - drive_scores[pid])
        for pid in common_keys
    }


def check_threshold(
    deltas: dict[str, float],
    threshold: float,
) -> list[str]:
    """Return paper IDs where delta strictly exceeds threshold.

    Args:
        deltas: {paper_id: delta_value} from compute_delta.
        threshold: Maximum acceptable delta.

    Returns:
        List of paper IDs exceeding threshold.
    """
    return [pid for pid, delta in deltas.items() if delta > threshold]


def load_config() -> dict:
    """Load eval configuration from eval/config.json."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


async def run_questions_against_session(
    config: dict,
    papers: list[dict],
    session_prefix: str,
) -> dict[str, float]:
    """Run eval questions against a session and return per-paper F1 scores."""
    scores_by_paper = {}

    async with httpx.AsyncClient() as http_client:
        for paper in papers:
            paper_id = paper.get("id", paper.get("article_id", "unknown"))
            session_id = f"{session_prefix}_{paper_id}"
            qas = paper.get("qas", {})
            questions = qas.get("question", [])
            answers_list = qas.get("answers", [])

            paper_scores = []
            for q_idx, question in enumerate(questions):
                qas_entry = {
                    "answers": {"answer": answers_list[q_idx]["answer"]}
                    if q_idx < len(answers_list)
                    else {"answer": []},
                }
                gold_answers = extract_gold_answers(qas_entry)

                try:
                    result = await query_chat(
                        http_client,
                        config["base_url"],
                        session_id,
                        question,
                        auth_token=os.environ.get("GOOGLE_ACCESS_TOKEN", ""),
                    )
                    f1 = score_answer(result["text"], gold_answers)
                    paper_scores.append(f1)
                except Exception as e:
                    print(f"    Error: {e}")
                    paper_scores.append(0.0)

                await asyncio.sleep(1)  # Rate limiting

            scores_by_paper[paper_id] = (
                sum(paper_scores) / len(paper_scores) if paper_scores else 0.0
            )

    return scores_by_paper


async def main():
    config = load_config()
    drive_config = config.get("drive_delta", {})
    drive_folder_link = drive_config.get("drive_folder_link", "")
    threshold = drive_config.get("f1_delta_threshold", 0.10)

    if not drive_folder_link:
        print("ERROR: drive_delta.drive_folder_link is empty in eval/config.json")
        print("Set it to a Google Drive folder link containing the eval PDFs.")
        sys.exit(1)

    google_token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
    if not google_token:
        print("ERROR: GOOGLE_ACCESS_TOKEN environment variable not set.")
        print("Provide a valid Google access token for Drive API access.")
        sys.exit(1)

    print("Loading QASPER papers...")
    papers = load_qasper_papers(n=config["n_papers"], seed=config["seed"])
    print(f"Selected {len(papers)} papers")

    # Step 1: Load local eval results (or run local eval)
    results_path = Path(__file__).parent / "results.json"
    if results_path.exists():
        with open(results_path) as f:
            local_results = json.load(f)
        local_scores = {
            p["paper_id"]: p["f1"] for p in local_results.get("per_paper", [])
        }
        print(f"Loaded local scores for {len(local_scores)} papers")
    else:
        print("No local results.json found. Run eval/run_eval.py first.")
        sys.exit(1)

    # Step 2: Index Drive folder
    print(f"\nIndexing Drive folder: {drive_folder_link}")
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.post(
                f"{config['base_url']}/index",
                json={
                    "drive_link": drive_folder_link,
                    "session_id": "drive_eval",
                },
                headers={"Authorization": f"Bearer {google_token}"},
                timeout=300.0,
            )
            if response.status_code != 200:
                print(f"ERROR: /index returned {response.status_code}")
                sys.exit(1)
            print("Drive folder indexed successfully")
        except Exception as e:
            print(f"ERROR indexing Drive folder: {e}")
            sys.exit(1)

    # Step 3: Run questions against Drive-indexed session
    print("\nRunning eval against Drive-indexed session...")
    drive_scores = await run_questions_against_session(
        config, papers, session_prefix="drive_eval"
    )

    # Step 4: Compute deltas
    deltas = compute_delta(local_scores, drive_scores)
    flagged = check_threshold(deltas, threshold)

    # Step 5: Print comparison table
    print("\n" + "=" * 70)
    print(f"DRIVE DELTA COMPARISON  (threshold: {threshold})")
    print("=" * 70)
    print(f"{'Paper':<30} {'Local':>7} {'Drive':>7} {'Delta':>7} {'Flag':>6}")
    print("-" * 70)
    for pid in sorted(deltas.keys()):
        local_f1 = local_scores.get(pid, 0.0)
        drive_f1 = drive_scores.get(pid, 0.0)
        delta = deltas[pid]
        flag = " ***" if pid in flagged else ""
        print(f"{pid:<30} {local_f1:>7.4f} {drive_f1:>7.4f} {delta:>7.4f}{flag}")
    print("-" * 70)

    mean_delta = sum(deltas.values()) / len(deltas) if deltas else 0.0
    print(f"\nMean delta: {mean_delta:.4f}")
    if flagged:
        print(f"FLAGGED ({len(flagged)} papers exceed threshold): {flagged}")
    else:
        print("No papers exceed threshold. Local and Drive scores are consistent.")

    # Step 6: Write results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "local_scores": local_scores,
        "drive_scores": drive_scores,
        "deltas": deltas,
        "mean_delta": round(mean_delta, 4),
        "flagged_papers": flagged,
    }
    output_path = Path(__file__).parent / "drive_delta_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
