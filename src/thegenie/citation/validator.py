from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from .markers import parse_ref_markers, validate_citation_fingerprint
from .models import CitationFailure, CitationIssue, CitationMarker, CitationValidationResult


class CitationRepository(Protocol):
    def get_reference(self, citation_id: str) -> Any | None: ...


def _value(item: Mapping[str, Any] | Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = item.get(name) if isinstance(item, Mapping) else getattr(item, name, None)
        if value is not None:
            return value
    return default


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reference_dict(reference: Any) -> dict[str, Any]:
    if isinstance(reference, Mapping):
        return dict(reference)
    if hasattr(reference, "model_dump"):
        return reference.model_dump(mode="json")
    return dict(vars(reference))


class CitationValidator:
    def __init__(self, repository: CitationRepository, *, hash_file=file_sha256) -> None:
        self.repository = repository
        self.hash_file = hash_file

    def validate_text(self, text: str) -> tuple[CitationValidationResult, ...]:
        return tuple(self.validate_marker(marker) for marker in parse_ref_markers(text))

    def validate_marker(self, marker: CitationMarker) -> CitationValidationResult:
        if marker.malformed or not marker.citation_id:
            issue = CitationIssue(failure=CitationFailure.MALFORMED_CITATION, message=marker.reason or "malformed marker")
            return CitationValidationResult(marker=marker, valid=False, issues=(issue,))

        reference = self.repository.get_reference(marker.citation_id)
        if reference is None:
            issue = CitationIssue(failure=CitationFailure.UNKNOWN_CITATION, message="citation was not found")
            return CitationValidationResult(marker=marker, valid=False, issues=(issue,))

        issues: list[CitationIssue] = []
        stored_id = _value(reference, "citation_id")
        if stored_id != marker.citation_id:
            issues.append(CitationIssue(failure=CitationFailure.CHUNK_MISMATCH, message="stored citation ID disagrees with lookup ID"))

        source_path = _value(reference, "source_path", "path")
        path = Path(source_path) if source_path else None
        if path is None or not path.is_file():
            issues.append(CitationIssue(failure=CitationFailure.MISSING_DOCUMENT, message="source document is missing"))
        else:
            expected_hash = _value(reference, "document_hash", "source_hash", "sha256")
            if expected_hash and self.hash_file(path) != expected_hash:
                issues.append(CitationIssue(failure=CitationFailure.CHANGED_DOCUMENT, message="source document hash changed"))

        page = _value(reference, "page", "page_number")
        page_count = _value(reference, "page_count")
        if not isinstance(page, int) or page < 1 or (isinstance(page_count, int) and page > page_count):
            issues.append(CitationIssue(failure=CitationFailure.INVALID_PAGE, message="citation page is outside the indexed document"))

        document_id = _value(reference, "document_id")
        chunk_text = _value(reference, "text", "chunk_text", "passage")
        fingerprint = _value(reference, "chunk_fingerprint", "fingerprint")
        if (
            document_id is None
            or not isinstance(page, int)
            or not isinstance(chunk_text, str)
            or not isinstance(fingerprint, str)
            or not validate_citation_fingerprint(document_id, page, chunk_text, fingerprint)
        ):
            issues.append(CitationIssue(failure=CitationFailure.CHUNK_MISMATCH, message="chunk fingerprint does not match document ID, page, and exact stored text"))

        return CitationValidationResult(
            marker=marker,
            valid=not issues,
            issues=tuple(issues),
            reference=_reference_dict(reference),
        )
