from __future__ import annotations

import hashlib
import re
import statistics
import subprocess
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

import pymupdf

from .models import DocumentMetadata, ExtractedDocument, ExtractedPage, TextBlock

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[IVXLC]+[.)])\s+\S", re.IGNORECASE)

# Below this many characters, a page's embedded text is assumed to be incidental
# (running headers, a database's "reproduced with permission" stamp, page numbers)
# rather than real body content — the classic signature of a scanned/image-only
# page that still carries a sliver of overlay text, so the naive "text is empty"
# check below never catches it. Ordinary born-digital academic pages in this
# corpus run at several thousand characters each, so this threshold has wide
# margin without risking false positives on short-but-real pages (e.g. a title
# page).
_MIN_PAGE_TEXT_CHARS = 200
_OCR_DPI = 300


def _ocr_page(page: pymupdf.Page) -> str | None:
    """Render a page to an image and OCR it with the system `tesseract` binary.

    Returns None (not raising) when tesseract isn't installed or fails, so a
    missing OCR toolchain degrades to the pre-existing empty/sparse-text
    behavior instead of breaking ingestion.
    """
    pixmap = page.get_pixmap(dpi=_OCR_DPI)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        image_path = Path(handle.name)
    try:
        pixmap.save(image_path)
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        image_path.unlink(missing_ok=True)


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


def _metadata(raw: Mapping[str, object]) -> DocumentMetadata:
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
    # PyMuPDF's stubs don't narrow get_text()'s return type by the mode literal; "dict" mode
    # always returns a dict at runtime (unlike "text"/"words"/etc., which return str/list).
    page_data = cast("dict[str, Any]", page.get_text("dict", sort=False))
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
        x0, y0, x1, y1 = block.get("bbox", (0.0, 0.0, 0.0, 0.0))
        yield TextBlock(
            text=text,
            bbox=(float(x0), float(y0), float(x1), float(y1)),
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
        # PyMuPDF's Document iterates over its pages at runtime; the stub doesn't declare __iter__.
        pages_iter = cast(Iterable[pymupdf.Page], cast(object, document))
        for index, page in enumerate(pages_iter, start=1):
            # "text" mode always returns str at runtime; see the "dict" mode note above.
            text = cast(str, page.get_text("text", sort=False))
            blocks = _mark_headings(tuple(_iter_text_blocks(page)))
            if len(text.strip()) < _MIN_PAGE_TEXT_CHARS:
                ocr_text = _ocr_page(page)
                if ocr_text is None:
                    warnings.append(
                        f"Page {index} has only {len(text.strip())} extractable chars; it may be "
                        "image-only, and OCR fallback is unavailable (install the tesseract binary)."
                    )
                elif len(ocr_text.strip()) > len(text.strip()):
                    warnings.append(
                        f"Page {index} had only {len(text.strip())} extractable chars; replaced with "
                        f"{len(ocr_text.strip())} chars recovered via OCR fallback (verify against the "
                        "original scan before trusting exact wording)."
                    )
                    text = ocr_text
                    # OCR text carries no font/position metadata, so this page contributes no
                    # heading blocks; chunking falls back to inheriting the prior page's section.
                    blocks = ()
                else:
                    warnings.append(
                        f"Page {index} has only {len(text.strip())} extractable chars and OCR fallback "
                        "did not recover more; it is likely genuinely blank or non-text (e.g. a figure)."
                    )
            pages.append(ExtractedPage(index, text, blocks, tuple(block.text for block in blocks if block.heading)))
    return ExtractedDocument(source_path, source_path.name, metadata, tuple(pages), file_sha256(source_path), tuple(warnings))
