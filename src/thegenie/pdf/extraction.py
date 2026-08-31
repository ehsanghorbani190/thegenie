from __future__ import annotations

import hashlib
import re
import statistics
from collections.abc import Iterator
from pathlib import Path

import pymupdf

from .models import DocumentMetadata, ExtractedDocument, ExtractedPage, TextBlock

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[IVXLC]+[.)])\s+\S", re.IGNORECASE)


def file_sha256(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_metadata(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().strip("\x00")
    return value or None


def _metadata(raw: dict[str, object]) -> DocumentMetadata:
    title = _clean_metadata(raw.get("title"))
    author = _clean_metadata(raw.get("author"))
    subject = _clean_metadata(raw.get("subject"))
    keywords = _clean_metadata(raw.get("keywords"))
    searchable = " ".join(value for value in (subject, keywords) if value)
    year_match = _YEAR_RE.search(_clean_metadata(raw.get("creationDate")) or "")
    doi_match = _DOI_RE.search(searchable)
    authors = tuple(part.strip() for part in re.split(r"\s*(?:;|\band\b)\s*", author) if part.strip()) if author else ()
    return DocumentMetadata(
        title=title,
        authors=authors,
        year=int(year_match.group()) if year_match else None,
        doi=doi_match.group().rstrip(".,;)") if doi_match else None,
    )


def _iter_text_blocks(page: pymupdf.Page) -> Iterator[TextBlock]:
    page_data = page.get_text("dict", sort=False)
    for block in page_data.get("blocks", ()):
        if block.get("type") != 0:
            continue
        lines = block.get("lines", ())
        spans = [span for line in lines for span in line.get("spans", ()) if span.get("text")]
        if not spans:
            continue
        text = "\n".join("".join(str(span.get("text", "")) for span in line.get("spans", ())) for line in lines)
        if not text:
            continue
        sizes = [float(span.get("size", 0.0)) for span in spans]
        bold = any(int(span.get("flags", 0)) & 16 or "bold" in str(span.get("font", "")).lower() for span in spans)
        yield TextBlock(
            text=text,
            bbox=tuple(float(value) for value in block.get("bbox", (0, 0, 0, 0))),
            font_size=max(sizes, default=0.0),
            bold=bold,
        )


def _mark_headings(blocks: tuple[TextBlock, ...]) -> tuple[TextBlock, ...]:
    body_sizes = [block.font_size for block in blocks if len(block.text.strip()) >= 40 and block.font_size > 0]
    body_size = statistics.median(body_sizes or [block.font_size for block in blocks if block.font_size > 0] or [0.0])
    marked: list[TextBlock] = []
    for block in blocks:
        line = block.text.strip()
        short = bool(line) and "\n" not in line and len(line) <= 120
        shape = short and not line.endswith((".", "!", "?", "؟", ";", "؛", ",", "،"))
        prominent = block.font_size >= body_size * 1.15 or (block.bold and block.font_size >= body_size)
        numbered = bool(_NUMBERED_HEADING_RE.match(line)) and block.font_size >= body_size * 0.95
        heading = shape and (prominent or numbered)
        marked.append(TextBlock(block.text, block.bbox, block.font_size, block.bold, heading))
    return tuple(marked)


def extract_pdf(path: str | Path) -> ExtractedDocument:
    source_path = Path(path)
    pages: list[ExtractedPage] = []
    warnings: list[str] = []
    with pymupdf.open(source_path) as document:
        metadata = _metadata(document.metadata or {})
        for index, page in enumerate(document, start=1):
            text = page.get_text("text", sort=False)
            blocks = _mark_headings(tuple(_iter_text_blocks(page)))
            if not text.strip():
                warnings.append(f"Page {index} contains no extractable text; it may be image-only.")
            pages.append(ExtractedPage(index, text, blocks, tuple(block.text for block in blocks if block.heading)))
    return ExtractedDocument(source_path, source_path.name, metadata, tuple(pages), file_sha256(source_path), tuple(warnings))
