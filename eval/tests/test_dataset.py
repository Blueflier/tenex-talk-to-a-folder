"""Tests for eval/dataset.py — load_qasper_papers, extract_gold_answers."""

from unittest.mock import patch, MagicMock

from eval.dataset import load_qasper_papers, extract_gold_answers


def _make_paper(n_questions, n_paragraphs_per_section, n_sections=3):
    """Helper to create a minimal QASPER-like paper dict."""
    return {
        "title": f"Paper with {n_questions}q",
        "full_text": {
            "section_name": [f"Section {i}" for i in range(n_sections)],
            "paragraphs": [
                [f"Paragraph {j}" for j in range(n_paragraphs_per_section)]
                for _ in range(n_sections)
            ],
        },
        "qas": {
            "question": [f"Question {i}?" for i in range(n_questions)],
            "answers": [
                {
                    "answer": [
                        {
                            "unanswerable": False,
                            "yes_no": None,
                            "extractive_spans": [f"span_{i}"],
                            "free_form_answer": "",
                        }
                    ]
                }
                for i in range(n_questions)
            ],
        },
    }


class TestLoadQasperPapers:
    @patch("eval.dataset.load_dataset")
    def test_returns_n_papers(self, mock_load):
        # Create 25 papers: enough candidates for top-20 pool
        papers = [_make_paper(n_questions=5, n_paragraphs_per_section=10) for _ in range(25)]
        mock_load.return_value = papers
        result = load_qasper_papers(n=5, seed=42)
        assert len(result) == 5

    @patch("eval.dataset.load_dataset")
    def test_reproducible_with_seed(self, mock_load):
        papers = [_make_paper(n_questions=5, n_paragraphs_per_section=10) for _ in range(25)]
        # Give each paper a unique title for identity checking
        for i, p in enumerate(papers):
            p["title"] = f"Paper_{i}"
        mock_load.return_value = papers

        result1 = load_qasper_papers(n=5, seed=42)
        result2 = load_qasper_papers(n=5, seed=42)
        assert [p["title"] for p in result1] == [p["title"] for p in result2]

    @patch("eval.dataset.load_dataset")
    def test_filters_min_questions(self, mock_load):
        """Papers with < 3 questions are excluded."""
        papers = [
            _make_paper(n_questions=2, n_paragraphs_per_section=5),  # too few questions
            *[_make_paper(n_questions=5, n_paragraphs_per_section=10) for _ in range(10)],
        ]
        papers[0]["title"] = "TooFewQuestions"
        for i, p in enumerate(papers[1:], 1):
            p["title"] = f"Good_{i}"
        mock_load.return_value = papers

        result = load_qasper_papers(n=5, seed=42)
        titles = [p["title"] for p in result]
        assert "TooFewQuestions" not in titles

    @patch("eval.dataset.load_dataset")
    def test_filters_max_paragraphs(self, mock_load):
        """Papers with > 200 paragraphs are excluded."""
        papers = [
            _make_paper(n_questions=5, n_paragraphs_per_section=100, n_sections=3),  # 300 paras
            *[_make_paper(n_questions=5, n_paragraphs_per_section=10) for _ in range(10)],
        ]
        papers[0]["title"] = "TooLong"
        for i, p in enumerate(papers[1:], 1):
            p["title"] = f"Good_{i}"
        mock_load.return_value = papers

        result = load_qasper_papers(n=5, seed=42)
        titles = [p["title"] for p in result]
        assert "TooLong" not in titles


class TestExtractGoldAnswers:
    def test_extractive_spans(self, sample_qasper_qas):
        answers = extract_gold_answers(sample_qasper_qas)
        # First annotator has extractive spans
        assert answers[0]["type"] == "extractive"
        assert answers[0]["text"] == "gradient descent, backpropagation"

    def test_free_form(self, sample_qasper_qas):
        answers = extract_gold_answers(sample_qasper_qas)
        # Second annotator has free_form
        assert answers[1]["type"] == "abstractive"
        assert "gradient descent" in answers[1]["text"]

    def test_yes_no(self, sample_qasper_yes_no):
        answers = extract_gold_answers(sample_qasper_yes_no)
        assert len(answers) == 1
        assert answers[0]["type"] == "yes_no"
        assert answers[0]["text"] == "Yes"

    def test_unanswerable(self, sample_qasper_unanswerable):
        answers = extract_gold_answers(sample_qasper_unanswerable)
        assert len(answers) == 1
        assert answers[0]["type"] == "unanswerable"
        assert answers[0]["text"] == "Unanswerable"

    def test_empty_answers(self):
        """Empty answer list returns empty."""
        entry = {"answers": {"answer": []}}
        answers = extract_gold_answers(entry)
        assert answers == []
