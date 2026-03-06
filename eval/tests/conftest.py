"""Shared fixtures for eval tests."""

import numpy as np
import pytest


@pytest.fixture
def sample_chunks():
    """Sample chunk dicts mimicking chunked document output."""
    return [
        {"text": "The cat sat on the mat in the living room.", "page": 1},
        {"text": "Quantum computing uses qubits for parallel processing.", "page": 2},
        {"text": "Machine learning models require training data.", "page": 3},
        {"text": "Natural language processing handles text analysis.", "page": 4},
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors (4 chunks x 8 dims for testing)."""
    rng = np.random.default_rng(42)
    emb = rng.standard_normal((4, 8))
    # Normalize rows
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    return emb / norms


@pytest.fixture
def sample_qasper_qas():
    """Sample QASPER-like question-answer structure."""
    return {
        "question": "What method was used?",
        "answers": {
            "answer": [
                {
                    "unanswerable": False,
                    "yes_no": None,
                    "extractive_spans": ["gradient descent", "backpropagation"],
                    "free_form_answer": "",
                },
                {
                    "unanswerable": False,
                    "yes_no": None,
                    "extractive_spans": [],
                    "free_form_answer": "They used gradient descent optimization.",
                },
            ]
        },
    }


@pytest.fixture
def sample_qasper_yes_no():
    """QASPER entry with yes/no answer."""
    return {
        "question": "Did the model outperform the baseline?",
        "answers": {
            "answer": [
                {
                    "unanswerable": False,
                    "yes_no": True,
                    "extractive_spans": [],
                    "free_form_answer": "",
                },
            ]
        },
    }


@pytest.fixture
def sample_qasper_unanswerable():
    """QASPER entry with unanswerable answer."""
    return {
        "question": "What is the runtime complexity?",
        "answers": {
            "answer": [
                {
                    "unanswerable": True,
                    "yes_no": None,
                    "extractive_spans": [],
                    "free_form_answer": "",
                },
            ]
        },
    }


@pytest.fixture
def sample_qasper_paper():
    """A minimal QASPER paper structure for testing."""
    return {
        "title": "Test Paper on NLP Methods",
        "abstract": "We present a novel approach.",
        "full_text": {
            "section_name": ["Introduction", "Methods", "Results"],
            "paragraphs": [
                ["This paper introduces a new method."],
                ["We use gradient descent.", "Training takes 10 epochs."],
                ["Results show improvement."],
            ],
        },
        "qas": {
            "question": ["What method?", "Did it work?", "How long?"],
            "answers": [
                {
                    "answer": [
                        {
                            "unanswerable": False,
                            "yes_no": None,
                            "extractive_spans": ["gradient descent"],
                            "free_form_answer": "",
                        }
                    ]
                },
                {
                    "answer": [
                        {
                            "unanswerable": False,
                            "yes_no": True,
                            "extractive_spans": [],
                            "free_form_answer": "",
                        }
                    ]
                },
                {
                    "answer": [
                        {
                            "unanswerable": False,
                            "yes_no": None,
                            "extractive_spans": [],
                            "free_form_answer": "Training takes 10 epochs.",
                        }
                    ]
                },
            ],
        },
    }
