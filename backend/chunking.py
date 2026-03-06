"""Type-specific chunking strategies for Drive file content."""
from backend.config import CHUNK_MAX_CHARS, CHUNK_OVERLAP


def recursive_chunk(
    text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Recursive character splitter. Skips empty/whitespace-only chunks."""
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def chunk_pdf(pdf_bytes: bytes, file_name: str) -> list[dict]:
    """Extract PDF page-by-page, chunk each page with recursive splitter."""
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    chunks = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if not text.strip():
            continue
        page_chunks = recursive_chunk(text)
        for i, chunk_text in enumerate(page_chunks):
            chunks.append(
                {
                    "text": chunk_text,
                    "source": file_name,
                    "page": page_num + 1,
                    "chunk_index": i,
                }
            )
    doc.close()
    return chunks


def chunk_sheet(csv_text: str, file_name: str) -> list[dict]:
    """Row-level chunking with headers prepended to every row."""
    if not csv_text or not csv_text.strip():
        return []
    lines = csv_text.strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0]
    chunks = []
    for row_num, row in enumerate(lines[1:], start=2):
        chunk_text = f"{header}\n{row}"
        chunks.append(
            {
                "text": chunk_text,
                "source": file_name,
                "row": row_num,
                "chunk_index": 0,
            }
        )
    return chunks


def chunk_slides(text: str, file_name: str) -> list[dict]:
    """Split slides on double newline boundary, filter empty slides."""
    if not text or not text.strip():
        return []
    slides = text.split("\n\n")
    chunks = []
    for slide_num, slide_text in enumerate(slides, start=1):
        if not slide_text.strip():
            continue
        chunks.append(
            {
                "text": slide_text.strip(),
                "source": file_name,
                "slide": slide_num,
                "chunk_index": 0,
            }
        )
    return chunks


def chunk_text(text: str, file_name: str) -> list[dict]:
    """Recursive chunking for plain text / markdown files."""
    raw_chunks = recursive_chunk(text)
    return [
        {"text": c, "source": file_name, "chunk_index": i}
        for i, c in enumerate(raw_chunks)
    ]
