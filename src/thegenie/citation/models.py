from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CitationFailure(StrEnum):
    MALFORMED_CITATION = "MALFORMED_CITATION"
    UNKNOWN_CITATION = "UNKNOWN_CITATION"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    CHANGED_DOCUMENT = "CHANGED_DOCUMENT"
    INVALID_PAGE = "INVALID_PAGE"
    CHUNK_MISMATCH = "CHUNK_MISMATCH"


class CitationMarker(StrictModel):
    raw: str
    citation_id: str | None
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    malformed: bool = False
    reason: str | None = None


class CitationIssue(StrictModel):
    failure: CitationFailure
    message: str


class CitationValidationResult(StrictModel):
    marker: CitationMarker
    valid: bool
    issues: tuple[CitationIssue, ...] = ()
    reference: dict[str, Any] | None = None


class BibliographyEntry(StrictModel):
    citation_id: str
    title: str | None = None
    authors: tuple[str, ...] = ()
    year: int | str | None = None
    filename: str | None = None
    source_path: str | None = None
    page: int | None = None
    section: str | None = None
