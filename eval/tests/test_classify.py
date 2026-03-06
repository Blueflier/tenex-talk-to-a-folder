"""Tests for eval/classify.py — classify_failure heuristic."""

import numpy as np

from eval.classify import classify_failure


class TestClassifyFailure:
    def test_crawl_miss_gold_not_in_any_chunk(self, sample_chunks):
        """Gold text not found in any chunk -> CRAWL_MISS."""
        gold_embedding = np.random.default_rng(1).standard_normal(8)
        retrieved_embeddings = np.random.default_rng(2).standard_normal((2, 8))

        result = classify_failure(
            gold_text="quantum entanglement theory",
            all_chunks=sample_chunks,
            retrieved_chunks=sample_chunks[:2],
            gold_embedding=gold_embedding,
            retrieved_embeddings=retrieved_embeddings,
        )
        assert result == "CRAWL_MISS"

    def test_retrieval_miss_low_similarity(self, sample_chunks):
        """Gold in chunks but retrieved embeddings have low cosine sim -> RETRIEVAL_MISS."""
        rng = np.random.default_rng(42)
        gold_embedding = rng.standard_normal(8)
        gold_embedding = gold_embedding / np.linalg.norm(gold_embedding)
        # Make retrieved embeddings orthogonal (low similarity)
        retrieved_embeddings = -gold_embedding.reshape(1, -1) + rng.standard_normal((2, 8)) * 0.1
        retrieved_embeddings = retrieved_embeddings / np.linalg.norm(
            retrieved_embeddings, axis=1, keepdims=True
        )

        result = classify_failure(
            gold_text="the cat sat",  # exists in sample_chunks[0]
            all_chunks=sample_chunks,
            retrieved_chunks=sample_chunks[:2],
            gold_embedding=gold_embedding,
            retrieved_embeddings=retrieved_embeddings,
            similarity_threshold=0.7,
        )
        assert result == "RETRIEVAL_MISS"

    def test_synthesis_fail_gold_in_chunks_and_similar(self, sample_chunks):
        """Gold in chunks AND retrieved embeddings similar -> SYNTHESIS_FAIL."""
        rng = np.random.default_rng(42)
        gold_embedding = rng.standard_normal(8)
        gold_embedding = gold_embedding / np.linalg.norm(gold_embedding)
        # Make retrieved embeddings very similar to gold
        noise = rng.standard_normal((2, 8)) * 0.05
        retrieved_embeddings = gold_embedding.reshape(1, -1) + noise
        retrieved_embeddings = retrieved_embeddings / np.linalg.norm(
            retrieved_embeddings, axis=1, keepdims=True
        )

        result = classify_failure(
            gold_text="the cat sat",  # exists in sample_chunks[0]
            all_chunks=sample_chunks,
            retrieved_chunks=sample_chunks[:2],
            gold_embedding=gold_embedding,
            retrieved_embeddings=retrieved_embeddings,
            similarity_threshold=0.7,
        )
        assert result == "SYNTHESIS_FAIL"

    def test_retrieval_miss_empty_retrieved(self, sample_chunks):
        """Empty retrieved embeddings -> RETRIEVAL_MISS."""
        gold_embedding = np.random.default_rng(1).standard_normal(8)
        empty_embeddings = np.array([]).reshape(0, 8)

        result = classify_failure(
            gold_text="the cat sat",  # exists in sample_chunks[0]
            all_chunks=sample_chunks,
            retrieved_chunks=[],
            gold_embedding=gold_embedding,
            retrieved_embeddings=empty_embeddings,
        )
        assert result == "RETRIEVAL_MISS"

    def test_crawl_miss_case_insensitive(self, sample_chunks):
        """CRAWL_MISS check is case-insensitive."""
        gold_embedding = np.random.default_rng(1).standard_normal(8)
        retrieved_embeddings = np.random.default_rng(2).standard_normal((1, 8))

        # "The Cat Sat" should be found in "The cat sat on the mat..."
        result = classify_failure(
            gold_text="The Cat Sat",
            all_chunks=sample_chunks,
            retrieved_chunks=sample_chunks[:1],
            gold_embedding=gold_embedding,
            retrieved_embeddings=retrieved_embeddings,
            similarity_threshold=0.0,  # ensure we pass retrieval check
        )
        assert result != "CRAWL_MISS"
