from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    title: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = None
    doi: str | None = None
    source_type: str | None = None


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    font_size: float
    bold: bool = False
    heading: bool = False


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page: int
    text: str
    blocks: tuple[TextBlock, ...] = ()
    headings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    source_path: Path
    filename: str
    metadata: DocumentMetadata
    pages: tuple[ExtractedPage, ...]
    document_hash: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    document_id: str
    page: int
    section: str | None
    chunk_index: int
    text: str
    citation_id: str
    fingerprint: str
    token_count: int
    metadata: dict[str, object] = field(default_factory=dict)
