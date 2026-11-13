"""Read and normalize source data. TODO: implement functions."""
from pathlib import Path
from .models import DocumentPage
from pypdf import PdfReader


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    reader = PdfReader(path)
    pages = []
    for i, pdf_page in enumerate(reader.pages):
        raw = pdf_page.extract_text() or ""
        pages.append(DocumentPage(document_id= document_id,
                                  source= source,
                                  page= i+1,
                                  text= raw,
                                  metadata= {"empty" : not raw.strip()}))
    return pages



def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    raise NotImplementedError("TODO: normalize_text")