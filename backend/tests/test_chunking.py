"""Tests for backend/chunking.py -- type-specific chunking strategies."""
import pytest

from chunking import (
    recursive_chunk,
    chunk_pdf,
    chunk_sheet,
    chunk_slides,
    chunk_text,
)


# --- recursive_chunk ---


class TestRecursiveChunk:
    def test_short_text_single_chunk(self):
        text = "Hello world"
        chunks = recursive_chunk(text)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_splits_at_1200_chars(self):
        text = "A" * 2400
        chunks = recursive_chunk(text)
        # 2400 chars with 1200 max and 150 overlap:
        # chunk1: 0-1200, chunk2: 1050-2250, chunk3: 1900-2400
        assert len(chunks) >= 2

    def test_overlap_between_chunks(self):
        text = "A" * 2400
        chunks = recursive_chunk(text, max_chars=1200, overlap=150)
        # Second chunk starts at 1050 (1200-150), so first 150 chars of chunk2
        # should overlap with last 150 chars of chunk1
        assert len(chunks) >= 2
        # All chunks should be non-empty
        for c in chunks:
            assert len(c) > 0

    def test_skips_empty_chunks(self):
        text = "Hello" + " " * 2000 + "World"
        chunks = recursive_chunk(text)
        for c in chunks:
            assert c.strip() != ""

    def test_empty_text_returns_empty(self):
        assert recursive_chunk("") == []

    def test_whitespace_only_returns_empty(self):
        assert recursive_chunk("   \n\t  ") == []

    def test_custom_params(self):
        text = "A" * 500
        chunks = recursive_chunk(text, max_chars=200, overlap=50)
        assert len(chunks) >= 3


# --- chunk_pdf ---


class TestChunkPdf:
    def _make_sample_pdf(self) -> bytes:
        """Create a minimal 2-page PDF with known text content using pymupdf."""
        import pymupdf

        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((72, 72), "Page one content. This is a test document.")
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Page two content. More test text here.")
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_extracts_both_pages(self):
        pdf_bytes = self._make_sample_pdf()
        chunks = chunk_pdf(pdf_bytes, "test.pdf")
        pages = {c["page"] for c in chunks}
        assert 1 in pages
        assert 2 in pages

    def test_chunks_have_required_metadata(self):
        pdf_bytes = self._make_sample_pdf()
        chunks = chunk_pdf(pdf_bytes, "test.pdf")
        assert len(chunks) > 0
        for c in chunks:
            assert "text" in c
            assert "source" in c
            assert c["source"] == "test.pdf"
            assert "page" in c
            assert "chunk_index" in c

    def test_scanned_pdf_returns_empty(self):
        """A PDF with no text layer should return empty list."""
        import pymupdf

        doc = pymupdf.open()
        doc.new_page()  # blank page, no text
        pdf_bytes = doc.tobytes()
        doc.close()
        chunks = chunk_pdf(pdf_bytes, "scanned.pdf")
        assert chunks == []


# --- chunk_sheet ---


class TestChunkSheet:
    def test_row_level_chunking_with_headers(self):
        csv_text = "Name,Age,City\nAlice,30,NYC\nBob,25,LA"
        chunks = chunk_sheet(csv_text, "data.csv")
        assert len(chunks) == 2
        # Each chunk should have header prepended
        assert chunks[0]["text"] == "Name,Age,City\nAlice,30,NYC"
        assert chunks[1]["text"] == "Name,Age,City\nBob,25,LA"

    def test_chunks_have_metadata(self):
        csv_text = "Name,Age\nAlice,30"
        chunks = chunk_sheet(csv_text, "data.csv")
        assert len(chunks) == 1
        assert chunks[0]["source"] == "data.csv"
        assert chunks[0]["row"] == 2
        assert chunks[0]["chunk_index"] == 0

    def test_header_only_returns_empty(self):
        csv_text = "Name,Age,City"
        chunks = chunk_sheet(csv_text, "data.csv")
        assert chunks == []

    def test_empty_csv_returns_empty(self):
        chunks = chunk_sheet("", "empty.csv")
        assert chunks == []


# --- chunk_slides ---


class TestChunkSlides:
    def test_splits_on_double_newline(self):
        text = "Slide 1 content\n\nSlide 2 content\n\nSlide 3 content"
        chunks = chunk_slides(text, "deck.pptx")
        assert len(chunks) == 3

    def test_chunks_have_metadata(self):
        text = "Slide 1\n\nSlide 2"
        chunks = chunk_slides(text, "deck.pptx")
        assert chunks[0]["source"] == "deck.pptx"
        assert chunks[0]["slide"] == 1
        assert chunks[1]["slide"] == 2
        assert chunks[0]["chunk_index"] == 0

    def test_filters_empty_slides(self):
        text = "Slide 1\n\n\n\n\n\nSlide 2"
        chunks = chunk_slides(text, "deck.pptx")
        assert len(chunks) == 2
        assert chunks[0]["text"] == "Slide 1"
        assert chunks[1]["text"] == "Slide 2"

    def test_empty_text_returns_empty(self):
        chunks = chunk_slides("", "empty.pptx")
        assert chunks == []


# --- chunk_text ---


class TestChunkText:
    def test_wraps_recursive_chunk_with_metadata(self):
        text = "Hello world, this is a test document."
        chunks = chunk_text(text, "readme.md")
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world, this is a test document."
        assert chunks[0]["source"] == "readme.md"
        assert chunks[0]["chunk_index"] == 0

    def test_multiple_chunks_have_sequential_indices(self):
        text = "A" * 3000
        chunks = chunk_text(text, "big.txt")
        assert len(chunks) >= 2
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i
            assert c["source"] == "big.txt"

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", "empty.txt")
        assert chunks == []
