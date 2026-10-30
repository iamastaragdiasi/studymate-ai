"""PDF validation, text extraction and chunking.

Files are processed in memory (no temporary files are written to disk),
so there is nothing to clean up afterwards.
"""
import re

try:
    import pymupdf
except ImportError:  # older PyMuPDF versions only expose the "fitz" name
    import fitz as pymupdf

from config import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    MIN_EXTRACTED_CHARS,
)


class PDFError(Exception):
    """Raised with a user-friendly message when a file cannot be used."""


def validate_pdf(file_name: str, file_bytes: bytes) -> None:
    """Check extension, size and PDF signature. Raises PDFError if invalid."""
    if not file_name.lower().endswith(".pdf"):
        raise PDFError("Only PDF files are supported. Please upload a file ending in .pdf.")
    if not file_bytes:
        raise PDFError("The uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise PDFError(f"File is {size_mb:.1f} MB. The maximum allowed size is {MAX_FILE_SIZE_MB} MB.")
    if b"%PDF-" not in file_bytes[:1024]:
        raise PDFError("This file does not look like a valid PDF (it may be renamed or corrupted).")


def clean_text(raw_text: str) -> str:
    """Normalise whitespace and re-join words hyphenated across line breaks."""
    text = raw_text.replace("\x00", "")
    text = re.sub(r"-\n(\w)", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(file_bytes: bytes) -> tuple[str, int]:
    """Extract text from a text-based PDF. Returns (text, page_count)."""
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as error:  # PyMuPDF raises several error types for bad files
        raise PDFError("The PDF could not be opened. It may be corrupted.") from error

    with document:
        if document.needs_pass:
            raise PDFError("This PDF is password-protected. Please upload an unlocked copy.")
        page_count = document.page_count
        pages = [page.get_text("text") for page in document]

    text = clean_text("\n\n".join(pages))
    if len(text) < MIN_EXTRACTED_CHARS:
        raise PDFError(
            "No readable text was found. This may be a scanned or image-only PDF, "
            "which is not supported (OCR is out of scope)."
        )
    return text, page_count


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS,
               overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word-based chunks.

    Overlap keeps sentences that cross a chunk boundary findable from both sides.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + chunk_size]))
        if start + chunk_size >= len(words):
            break
    return chunks


def process_pdf(file_name: str, file_bytes: bytes) -> dict:
    """Validate, extract and chunk a PDF. Returns a document dictionary for the UI."""
    validate_pdf(file_name, file_bytes)
    text, page_count = extract_text(file_bytes)
    return {
        "name": file_name,
        "text": text,
        "pages": page_count,
        "word_count": len(text.split()),
        "chunks": chunk_text(text),
    }