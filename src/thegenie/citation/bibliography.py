from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .models import BibliographyEntry

BibliographyFormatter = Callable[[BibliographyEntry], str]


def bibliography_entry(reference: Mapping[str, Any] | Any) -> BibliographyEntry:
    def value(name: str, default: Any = None) -> Any:
        return reference.get(name, default) if isinstance(reference, Mapping) else getattr(reference, name, default)

    authors = value("authors", ()) or ()
    if isinstance(authors, str):
        authors = (authors,)
    return BibliographyEntry(
        citation_id=str(value("citation_id")),
        title=value("title"),
        authors=tuple(str(author) for author in authors),
        year=value("year"),
        filename=value("filename"),
        source_path=str(value("source_path")) if value("source_path") is not None else None,
        page=value("page"),
        section=value("section"),
    )


def format_bibliography_entry(entry: BibliographyEntry) -> str:
    """Conservative default formatter: it never invents unavailable metadata."""
    creator = ", ".join(entry.authors) or entry.filename or entry.source_path or "Unknown source"
    year = f" ({entry.year})." if entry.year is not None else "."
    title = f" {entry.title}." if entry.title else ""
    location = f" p. {entry.page}." if entry.page is not None else ""
    return f"{creator}{year}{title}{location} [{entry.citation_id}]".replace("..", ".")


def format_bibliography(
    references: Iterable[Mapping[str, Any] | Any],
    formatter: BibliographyFormatter = format_bibliography_entry,
) -> tuple[str, ...]:
    unique: dict[str, BibliographyEntry] = {}
    for reference in references:
        entry = bibliography_entry(reference)
        unique.setdefault(entry.citation_id, entry)
    return tuple(formatter(unique[key]) for key in sorted(unique))
