"""Scoring utilities for eval pipeline.

SQuAD-style token F1 with type-aware scoring for QASPER answer types.
"""

import re
import string
from collections import Counter


def normalize_answer(text: str) -> str:
    """Lowercase, remove articles/punctuation, collapse whitespace."""
    text = text.lower()
    # Remove articles
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    # Remove punctuation
    text = "".join(ch for ch in text if ch not in string.punctuation)
    # Collapse whitespace
    text = " ".join(text.split())
    return text


def token_f1(prediction: str, reference: str) -> float:
    """Compute token-level F1 between prediction and reference.

    Both strings are normalized before tokenization.
    Returns 1.0 if both are empty, 0.0 if only one is empty.
    """
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
    """Score prediction against gold answers, max across annotators.

    For yes_no and unanswerable types: exact match on normalized text.
    For extractive and abstractive types: token F1.

    Returns 0.0 if gold_answers is empty.
    """
    if not gold_answers:
        return 0.0

    scores = []
    for gold in gold_answers:
        if gold["type"] in ("yes_no", "unanswerable"):
            score = (
                1.0
                if normalize_answer(prediction) == normalize_answer(gold["text"])
                else 0.0
            )
        else:
            score = token_f1(prediction, gold["text"])
        scores.append(score)

    return max(scores)
