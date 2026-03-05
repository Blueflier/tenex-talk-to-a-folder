"""Tests for retrieval engine: cosine similarity, top-k, threshold, citations."""
import numpy as np
import pytest

from backend.retrieval import (
    SIMILARITY_THRESHOLD,
    check_threshold,
    cosine_sim,
    extract_citations,
    retrieve,
    retrieve_mixed,
)


# --------------- cosine_sim ---------------

def test_cosine_sim_identical_vectors():
    """Identical vectors should have similarity ~1.0."""
    vec = np.array([1.0, 0.0, 0.0])
    embeddings = np.array([vec])
    scores = cosine_sim(vec, embeddings)
    assert scores.shape == (1,)
    assert abs(scores[0] - 1.0) < 1e-6


def test_cosine_sim_orthogonal_vectors():
    """Orthogonal vectors should have similarity ~0.0."""
    query = np.array([1.0, 0.0, 0.0])
    embeddings = np.array([[0.0, 1.0, 0.0]])
    scores = cosine_sim(query, embeddings)
    assert abs(scores[0]) < 1e-6


def test_cosine_sim_opposite_vectors():
    """Opposite vectors should have similarity ~-1.0."""
    query = np.array([1.0, 0.0])
    embeddings = np.array([[-1.0, 0.0]])
    scores = cosine_sim(query, embeddings)
    assert abs(scores[0] - (-1.0)) < 1e-6


def test_cosine_sim_multiple_embeddings():
    """Should return one score per embedding row."""
    query = np.array([1.0, 0.0, 0.0])
    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.5, 0.5, 0.0],
    ])
    scores = cosine_sim(query, embeddings)
    assert scores.shape == (3,)
    assert scores[0] > scores[2] > scores[1]


# --------------- retrieve ---------------

def _make_chunks(n, mime_type="application/pdf"):
    return [
        {
            "file_name": f"file_{i}.pdf",
            "file_id": f"id_{i}",
            "text": f"chunk text {i}",
            "mime_type": mime_type,
        }
        for i in range(n)
    ]


def test_retrieve_returns_top_k():
    """retrieve should return top_k results sorted by score descending."""
    np.random.seed(42)
    query = np.array([1.0, 0.0, 0.0])
    # Create embeddings where first vector is most similar to query
    embeddings = np.array([
        [0.9, 0.1, 0.0],
        [0.1, 0.9, 0.0],
        [0.5, 0.5, 0.0],
        [0.8, 0.2, 0.0],
    ])
    chunks = _make_chunks(4)
    results = retrieve(query, chunks, embeddings, top_k=2)
    assert len(results) == 2
    # First result should be chunk 0 (most similar)
    assert results[0][0]["file_name"] == "file_0.pdf"
    # Scores should be descending
    assert results[0][1] >= results[1][1]


def test_retrieve_top_k_5():
    """retrieve with top_k=5 returns 5 results."""
    query = np.random.randn(8)
    embeddings = np.random.randn(10, 8)
    chunks = _make_chunks(10)
    results = retrieve(query, chunks, embeddings, top_k=5)
    assert len(results) == 5


def test_retrieve_top_k_8_default():
    """Default top_k is 8."""
    query = np.random.randn(8)
    embeddings = np.random.randn(20, 8)
    chunks = _make_chunks(20)
    results = retrieve(query, chunks, embeddings)
    assert len(results) == 8


def test_retrieve_fewer_chunks_than_k():
    """If fewer chunks than top_k, return all."""
    query = np.random.randn(4)
    embeddings = np.random.randn(3, 4)
    chunks = _make_chunks(3)
    results = retrieve(query, chunks, embeddings, top_k=8)
    assert len(results) == 3


# --------------- retrieve_mixed ---------------

SHEET_MIME = "application/vnd.google-apps.spreadsheet"


def test_retrieve_mixed_separates_pools():
    """Mixed retrieval: top-8 docs + top-5 sheets, merged by score, capped at 10."""
    np.random.seed(1)
    dim = 8
    query = np.random.randn(dim)

    doc_chunks = _make_chunks(15, mime_type="application/pdf")
    sheet_chunks = _make_chunks(10, mime_type=SHEET_MIME)
    all_chunks = doc_chunks + sheet_chunks

    embeddings = np.random.randn(25, dim)
    results = retrieve_mixed(query, all_chunks, embeddings)

    assert len(results) <= 10
    # Scores should be descending
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_mixed_docs_only_falls_back():
    """If only docs, use top-8."""
    np.random.seed(2)
    dim = 4
    query = np.random.randn(dim)
    chunks = _make_chunks(15, mime_type="application/pdf")
    embeddings = np.random.randn(15, dim)
    results = retrieve_mixed(query, chunks, embeddings)
    assert len(results) == 8


def test_retrieve_mixed_sheets_only_falls_back():
    """If only sheets, use top-5."""
    np.random.seed(3)
    dim = 4
    query = np.random.randn(dim)
    chunks = _make_chunks(10, mime_type=SHEET_MIME)
    embeddings = np.random.randn(10, dim)
    results = retrieve_mixed(query, chunks, embeddings)
    assert len(results) == 5


# --------------- check_threshold ---------------

def test_check_threshold_all_below():
    """All scores below threshold -> True."""
    results = [({}, 0.1), ({}, 0.2), ({}, 0.29)]
    assert check_threshold(results) is True


def test_check_threshold_one_above():
    """At least one score >= threshold -> False."""
    results = [({}, 0.1), ({}, 0.5), ({}, 0.2)]
    assert check_threshold(results) is False


def test_check_threshold_exact():
    """Score exactly at threshold -> above (not below)."""
    results = [({}, SIMILARITY_THRESHOLD)]
    assert check_threshold(results) is False


# --------------- extract_citations ---------------

def test_extract_citations_basic():
    """extract_citations returns correct citation metadata."""
    chunks = [
        (
            {
                "file_name": "report.pdf",
                "file_id": "abc",
                "text": "Some content",
                "page_number": 3,
            },
            0.8,
        ),
        (
            {
                "file_name": "data.csv",
                "file_id": "def",
                "text": "Row data",
                "row_number": 12,
            },
            0.6,
        ),
    ]
    citations = extract_citations(chunks)
    assert len(citations) == 2

    assert citations[0]["index"] == 1
    assert citations[0]["file_name"] == "report.pdf"
    assert citations[0]["file_id"] == "abc"
    assert citations[0]["page_number"] == 3
    assert citations[0]["chunk_text"] == "Some content"

    assert citations[1]["index"] == 2
    assert citations[1]["row_number"] == 12
    assert citations[1]["chunk_text"] == "Row data"


def test_extract_citations_optional_fields():
    """Optional fields default to None."""
    chunks = [
        (
            {
                "file_name": "doc.txt",
                "file_id": "xyz",
                "text": "hello",
            },
            0.5,
        ),
    ]
    citations = extract_citations(chunks)
    assert citations[0]["page_number"] is None
    assert citations[0]["row_number"] is None
    assert citations[0]["slide_index"] is None
