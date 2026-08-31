from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TypeAlias

from thegenie.models import SearchResult

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def format_human(results: SearchResult | Sequence[SearchResult]) -> str:
    """Compact readable output for a terminal or conversational response."""
    return "\n\n".join(
        f"[{result.chunk.citation_id}] {_source(result)} (page {result.chunk.page}, "
        + f"score {result.relevance_score:.3f})\n{result.chunk.text}"
        for result in _items(results)
    )


def format_mcp(results: SearchResult | Sequence[SearchResult]) -> list[JsonObject]:
    """Compact JSON-compatible output for MCP tools."""
    return [
        {
            "citation_id": result.chunk.citation_id,
            "source": _source(result),
            "page": result.chunk.page,
            "section": result.chunk.section,
            "score": result.relevance_score,
            "text": result.chunk.text,
        }
        for result in _items(results)
    ]


def format_reference(result: SearchResult) -> JsonObject:
    """Full JSON-compatible reference, including provenance and both scores."""
    return result.model_dump(mode="json")


def format_references(results: Sequence[SearchResult]) -> list[JsonObject]:
    return [format_reference(result) for result in results]


def format_mcp_json(results: SearchResult | Sequence[SearchResult]) -> str:
    return json.dumps(format_mcp(results), ensure_ascii=False)


def _items(results: SearchResult | Sequence[SearchResult]) -> Sequence[SearchResult]:
    return (results,) if isinstance(results, SearchResult) else results


def _source(result: SearchResult) -> str:
    metadata = result.chunk.metadata
    return metadata.title or result.chunk.filename
