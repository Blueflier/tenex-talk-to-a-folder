"""Unit tests for drive delta calculation and threshold logic."""

import pytest

from eval.run_drive_delta import check_threshold, compute_delta


class TestComputeDelta:
    """Tests for compute_delta function."""

    def test_basic_delta(self):
        local = {"paper1": 0.8, "paper2": 0.6}
        drive = {"paper1": 0.7, "paper2": 0.9}
        result = compute_delta(local, drive)
        assert result == pytest.approx({"paper1": 0.1, "paper2": 0.3}, abs=1e-9)

    def test_identical_scores(self):
        local = {"paper1": 0.5}
        drive = {"paper1": 0.5}
        result = compute_delta(local, drive)
        assert result == {"paper1": pytest.approx(0.0)}

    def test_empty_dicts(self):
        result = compute_delta({}, {})
        assert result == {}

    def test_mismatched_keys_uses_intersection(self):
        """Papers only in one dict are skipped gracefully."""
        local = {"paper1": 0.8, "paper2": 0.6}
        drive = {"paper1": 0.7, "paper3": 0.9}
        result = compute_delta(local, drive)
        # Only paper1 is in both
        assert "paper1" in result
        assert "paper2" not in result
        assert "paper3" not in result

    def test_absolute_difference(self):
        """Delta is always absolute (positive)."""
        local = {"p1": 0.3}
        drive = {"p1": 0.8}
        result = compute_delta(local, drive)
        assert result["p1"] == pytest.approx(0.5)


class TestCheckThreshold:
    """Tests for check_threshold function."""

    def test_flags_papers_above_threshold(self):
        deltas = {"p1": 0.05, "p2": 0.12, "p3": 0.10}
        flagged = check_threshold(deltas, threshold=0.10)
        assert flagged == ["p2"]

    def test_all_below_threshold(self):
        deltas = {"p1": 0.01, "p2": 0.05}
        flagged = check_threshold(deltas, threshold=0.10)
        assert flagged == []

    def test_zero_threshold_flags_nonzero(self):
        deltas = {"p1": 0.05, "p2": 0.0, "p3": 0.001}
        flagged = check_threshold(deltas, threshold=0.0)
        assert sorted(flagged) == ["p1", "p3"]

    def test_empty_deltas(self):
        flagged = check_threshold({}, threshold=0.10)
        assert flagged == []

    def test_multiple_flagged_sorted(self):
        deltas = {"a": 0.5, "b": 0.3, "c": 0.01}
        flagged = check_threshold(deltas, threshold=0.10)
        assert sorted(flagged) == ["a", "b"]
