from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from thegenie.citation import citation_fingerprint

from .models import ChunkRecord, ExtractedPage

TokenCounter = Callable[[str], int]
_BOUNDARY_RE = re.compile(r"(?<=[.!?؟])(?=[\s\n])|(?<=[؛;])(?=\s)")
_PARAGRAPH_RE = re.compile(r"\n(?:[ \t]*\n)+")


def approximate_token_count(text: str) -> int:
    words = len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    return max(1, round(words * 1.3)) if text else 0


def _split_preserving(text: str, pattern: re.Pattern[str]) -> list[str]:
    parts: list[str] = []
    start = 0
    for match in pattern.finditer(text):
        end = match.end()
        if end > start:
            parts.append(text[start:end])
        start = end
    if start < len(text):
        parts.append(text[start:])
    return parts


def _hard_split(text: str, target_size: int, count: TokenCounter) -> list[str]:
    if count(text) <= target_size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        low, high = start + 1, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if count(text[start:middle]) <= target_size:
                low = middle
            else:
                high = middle - 1
        end = max(low, start + 1)
        parts.append(text[start:end])
        start = end
    return parts


def _units(text: str, target_size: int, count: TokenCounter) -> list[str]:
    units: list[str] = []
    for paragraph in _split_preserving(text, _PARAGRAPH_RE):
        if count(paragraph) <= target_size:
            units.append(paragraph)
            continue
        for sentence in _split_preserving(paragraph, _BOUNDARY_RE):
            units.extend(_hard_split(sentence, target_size, count))
    return units


def _page_chunks(text: str, target_size: int, overlap: int, count: TokenCounter) -> list[str]:
    units = _units(text, target_size, count)
    chunks: list[str] = []
    start = 0
    while start < len(units):
        end = start
        size = 0
        while end < len(units) and (end == start or size + count(units[end]) <= target_size):
            size += count(units[end])
            end += 1
        chunks.append("".join(units[start:end]))
        if end == len(units):
            break
        next_start = end
        retained = 0
        while next_start > start and retained + count(units[next_start - 1]) <= overlap:
            next_start -= 1
            retained += count(units[next_start])
        start = next_start if next_start < end else end
    return chunks


def _slug(filename: str) -> str:
    stem = unicodedata.normalize("NFKC", Path(filename).stem).casefold()
    slug = re.sub(r"[^\w]+", "-", stem, flags=re.UNICODE).strip("-_" )
    return slug[:64] or hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]


def citation_parts(document_id: object, page: int, text: str, filename: str) -> tuple[str, str]:
    fingerprint = citation_fingerprint(document_id, page, text)
    return f"{_slug(filename)}_p{page}_c_{fingerprint}", fingerprint


def _section_for_chunk(page: ExtractedPage, text: str, previous: str | None) -> str | None:
    section = previous
    positions = sorted((page.text.find(heading), heading) for heading in page.headings if page.text.find(heading) >= 0)
    chunk_position = page.text.find(text)
    for position, heading in positions:
        if position <= chunk_position:
            section = heading.strip() or section
    return section


def chunk_pages(
    pages: Sequence[ExtractedPage] | Iterable[ExtractedPage],
    *,
    document_id: object,
    filename: str,
    target_size: int = 512,
    overlap: int = 64,
    token_counter: TokenCounter | None = None,
) -> list[ChunkRecord]:
    if target_size <= 0 or overlap < 0 or overlap >= target_size:
        raise ValueError("target_size must be positive and overlap must satisfy 0 <= overlap < target_size")
    count = token_counter or approximate_token_count
    records: list[ChunkRecord] = []
    section: str | None = None
    for page in pages:
        for text in _page_chunks(page.text, target_size, overlap, count):
            if not text:
                continue
            section = _section_for_chunk(page, text, section)
            citation_id, fingerprint = citation_parts(document_id, page.page, text, filename)
            records.append(ChunkRecord(str(document_id), page.page, section, len(records), text, citation_id, fingerprint, count(text)))
    return records
