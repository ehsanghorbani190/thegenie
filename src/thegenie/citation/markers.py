from __future__ import annotations

import hashlib
import re
import unicodedata

from .models import CitationMarker

CITATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,127}$")
_CANDIDATE_PATTERN = re.compile(
    r"(?i)(?P<prefix>\[\[)?REF(?P<separator>:)?(?P<body>[^\]\r\n]*)(?P<suffix>\]\])?"
)


def citation_fingerprint(
    document_id: object,
    page: int | None = None,
    text: str | None = None,
    *,
    length: int = 16,
) -> str:
    """Return the canonical fingerprint of document ID, one-based page, and exact text.

    A single text argument retains the previous text-only behavior for callers that
    have not yet migrated; stored citation fingerprints must use all three fields.
    """
    if not 8 <= length <= 64:
        raise ValueError("fingerprint length must be between 8 and 64")
    if text is None:
        if page is not None or not isinstance(document_id, str):
            raise TypeError("citation_fingerprint requires document_id, page, and text")
        payload = document_id.encode("utf-8")
    else:
        if not str(document_id) or page is None or page < 1:
            raise ValueError("document_id must be set and page must be one-based")
        payload = f"{document_id}\0{page}\0".encode("utf-8") + text.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def make_citation_id(document_id: str, page: int, text: str) -> str:
    if not document_id or page < 1:
        raise ValueError("document_id must be set and page must be one-based")
    return f"{document_id}:p{page}:{citation_fingerprint(document_id, page, text)}"


def validate_citation_fingerprint(*args: object) -> bool:
    """Validate a canonical fingerprint; two arguments retain text-only compatibility."""
    if len(args) == 2:
        text, expected = args
        values = (text,)
    elif len(args) == 4:
        document_id, page, text, expected = args
        values = (document_id, page, text)
    else:
        raise TypeError("expected (text, fingerprint) or (document_id, page, text, fingerprint)")
    if not isinstance(expected, str) or not 8 <= len(expected) <= 64:
        return False
    try:
        actual = citation_fingerprint(*values, length=len(expected))
    except (TypeError, ValueError):
        return False
    return actual == expected.lower()


def normalized_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def parse_ref_markers(text: str) -> tuple[CitationMarker, ...]:
    """Parse valid markers and REF-like malformed candidates without hiding errors."""
    markers: list[CitationMarker] = []
    for match in _CANDIDATE_PATTERN.finditer(text):
        body = match.group("body").strip()
        malformed_reason: str | None = None
        if match.group("prefix") != "[[" or match.group("separator") != ":" or match.group("suffix") != "]]":
            malformed_reason = "citation marker must use canonical [[REF:citation_id]] syntax"
        elif not body:
            malformed_reason = "empty citation identifier"
        elif not CITATION_ID_PATTERN.fullmatch(body):
            malformed_reason = "invalid citation identifier"
        markers.append(
            CitationMarker(
                raw=match.group(0),
                citation_id=body or None,
                start=match.start(),
                end=match.end(),
                malformed=malformed_reason is not None,
                reason=malformed_reason,
            )
        )
    return tuple(markers)


def strip_ref_markers(text: str) -> str:
    markers = parse_ref_markers(text)
    for marker in reversed(markers):
        text = text[: marker.start] + text[marker.end :]
    return text
