"""Tests for eval/scoring.py — normalize_answer, token_f1, score_answer."""

from eval.scoring import normalize_answer, token_f1, score_answer


class TestNormalizeAnswer:
    def test_lowercase_and_strip_articles(self):
        assert normalize_answer("The Cat.") == "cat"

    def test_all_articles_removed(self):
        assert normalize_answer("  a  an  the  ") == ""

    def test_punctuation_removed(self):
        assert normalize_answer("hello, world!") == "hello world"

    def test_whitespace_collapsed(self):
        assert normalize_answer("  hello   world  ") == "hello world"

    def test_empty_string(self):
        assert normalize_answer("") == ""

    def test_mixed(self):
        assert normalize_answer("A Quick Brown Fox!") == "quick brown fox"


class TestTokenF1:
    def test_exact_match(self):
        assert token_f1("the cat sat", "the cat sat") == 1.0

    def test_partial_overlap(self):
        # "cat sat" vs "dog sat" -> normalized: "cat sat" vs "dog sat"
        # common = {"sat": 1}, pred=2, ref=2
        # precision=0.5, recall=0.5, f1=0.5
        result = token_f1("the cat sat", "the dog sat")
        assert abs(result - 0.5) < 0.01

    def test_both_empty(self):
        assert token_f1("", "") == 1.0

    def test_pred_empty(self):
        assert token_f1("", "hello") == 0.0

    def test_ref_empty(self):
        assert token_f1("hello", "") == 0.0

    def test_no_overlap(self):
        assert token_f1("cat dog", "fish bird") == 0.0

    def test_normalized_comparison(self):
        # "The Cat" and "the cat" should be same after normalization
        assert token_f1("The Cat", "the cat") == 1.0


class TestScoreAnswer:
    def test_yes_no_exact_match(self):
        score = score_answer("Yes", [{"type": "yes_no", "text": "Yes"}])
        assert score == 1.0

    def test_yes_no_mismatch(self):
        score = score_answer("No", [{"type": "yes_no", "text": "Yes"}])
        assert score == 0.0

    def test_unanswerable_match(self):
        score = score_answer(
            "Unanswerable", [{"type": "unanswerable", "text": "Unanswerable"}]
        )
        assert score == 1.0

    def test_extractive_f1(self):
        score = score_answer(
            "gradient descent optimization",
            [{"type": "extractive", "text": "gradient descent"}],
        )
        # pred: "gradient descent optimization" (3 tokens)
        # ref: "gradient descent" (2 tokens)
        # common=2, precision=2/3, recall=2/2=1.0, f1=2*(2/3*1)/(2/3+1)=0.8
        assert abs(score - 0.8) < 0.01

    def test_max_across_annotators(self):
        gold = [
            {"type": "extractive", "text": "gradient descent"},
            {"type": "abstractive", "text": "gradient descent optimization"},
        ]
        score = score_answer("gradient descent optimization", gold)
        # Second annotator gives F1=1.0
        assert score == 1.0

    def test_empty_gold_answers(self):
        assert score_answer("some text", []) == 0.0

    def test_mixed_types_picks_best(self):
        gold = [
            {"type": "yes_no", "text": "Yes"},
            {"type": "abstractive", "text": "The answer is yes definitely"},
        ]
        # "yes" as prediction: exact match with yes_no -> 1.0
        score = score_answer("Yes", gold)
        assert score == 1.0
