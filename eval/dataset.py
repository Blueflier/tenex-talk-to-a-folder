"""QASPER dataset loading and answer extraction.

Selects papers by question density with seed-based reproducibility.
"""

import random

from datasets import load_dataset


def load_qasper_papers(n: int = 5, seed: int = 42) -> list[dict]:
    """Select n QASPER papers optimized for question density.

    Filters to papers with >= 3 questions and <= 200 total paragraphs,
    sorts by question density (questions / paragraphs), samples n from
    the top 20 candidates using a seeded RNG.

    Args:
        n: Number of papers to select.
        seed: Random seed for reproducible selection.

    Returns:
        List of QASPER paper dicts.
    """
    ds = load_dataset("allenai/qasper", split="test")

    candidates = []
    for paper in ds:
        n_questions = len(paper["qas"]["question"])
        total_paragraphs = sum(
            len(paragraphs) for paragraphs in paper["full_text"]["paragraphs"]
        )
        if n_questions >= 3 and total_paragraphs <= 200:
            candidates.append(
                {
                    "paper": paper,
                    "density": n_questions / max(total_paragraphs, 1),
                }
            )

    # Sort by density descending, take top pool, sample for diversity
    candidates.sort(key=lambda x: x["density"], reverse=True)
    rng = random.Random(seed)
    pool = candidates[:20]
    selected = rng.sample(pool, min(n, len(pool)))
    return [c["paper"] for c in selected]


def extract_gold_answers(qas_entry: dict) -> list[dict]:
    """Extract all annotator answers for a QASPER question.

    Checks answer types in priority order: unanswerable, yes_no,
    extractive_spans, free_form_answer.

    Args:
        qas_entry: A QASPER QAS entry with "answers" -> "answer" list.

    Returns:
        List of {"type": str, "text": str} dicts.
    """
    answers = []
    for answer in qas_entry["answers"]["answer"]:
        if answer["unanswerable"]:
            answers.append({"type": "unanswerable", "text": "Unanswerable"})
        elif answer["yes_no"] is not None:
            answers.append(
                {"type": "yes_no", "text": "Yes" if answer["yes_no"] else "No"}
            )
        elif answer["extractive_spans"]:
            text = ", ".join(answer["extractive_spans"])
            answers.append({"type": "extractive", "text": text})
        elif answer["free_form_answer"]:
            answers.append({"type": "abstractive", "text": answer["free_form_answer"]})
    return answers
