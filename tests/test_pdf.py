import pytest

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from config import MAX_FILE_SIZE_BYTES
from services.pdf_handler import PDFError, chunk_text, extract_text, process_pdf, validate_pdf


def make_pdf(lines: list[str]) -> bytes:
    """Create a small PDF in memory (no sample files needed in the repo)."""
    document = pymupdf.open()
    page = document.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 20
    data = document.tobytes()
    document.close()
    return data


def test_valid_pdf_text_is_extracted():
    data = make_pdf(["Photosynthesis converts light energy into chemical energy."])
    text, pages = extract_text(data)
    assert "Photosynthesis" in text
    assert pages == 1


def test_non_pdf_extension_rejected():
    with pytest.raises(PDFError, match="Only PDF"):
        validate_pdf("notes.docx", b"%PDF-1.7 fake")


def test_empty_file_rejected():
    with pytest.raises(PDFError, match="empty"):
        validate_pdf("notes.pdf", b"")


def test_oversized_file_rejected():
    with pytest.raises(PDFError, match="maximum"):
        validate_pdf("big.pdf", b"%PDF-" + b"0" * MAX_FILE_SIZE_BYTES)


def test_renamed_non_pdf_rejected():
    with pytest.raises(PDFError, match="valid PDF"):
        validate_pdf("fake.pdf", b"just some text pretending to be a pdf")


def test_blank_pdf_reports_no_readable_text():
    with pytest.raises(PDFError, match="No readable text"):
        extract_text(make_pdf([]))


def test_chunk_text_uses_overlap():
    text = " ".join(f"w{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) == 3
    assert chunks[1].split()[0] == "w160"
    assert chunks[-1].split()[-1] == "w499"


def test_chunk_text_empty_input():
    assert chunk_text("") == []


def test_process_pdf_returns_document_dict():
    document = process_pdf("bio.pdf", make_pdf(["Cells are the basic unit of life in biology."]))
    assert document["name"] == "bio.pdf"
    assert document["chunks"]
    assert document["word_count"] > 0