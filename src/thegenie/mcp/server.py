from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from thegenie.app import Application
from thegenie.retrieval import format_mcp


def create_server(app: Application | None = None) -> FastMCP:
    application = app or Application()
    server = FastMCP(
        "TheGenie Academic References",
        instructions=(
            "Search and inspect local academic passages. Relevance scores are not proof of support. "
            "Use only exact returned metadata and cite only passages that support the claim; never invent sources."
        ),
    )

    @server.tool(
        description=(
            "Search local indexed academic passages. Inspect the exact text before citing it: relevance "
            "is not evidence of entailment, and missing source metadata must never be invented."
        )
    )
    def search_references(
        query: str, top_k: int = 5, document_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Return relevant exact passages with citation IDs and known provenance."""
        return format_mcp(
            application.search(
                query, top_k=top_k, document_filter=document_filter
            )
        )

    @server.tool(
        description=(
            "Resolve one citation ID to its exact stored passage and known provenance. "
            "Do not infer or invent fields absent from the result."
        )
    )
    def get_reference(citation_id: str) -> dict[str, Any]:
        """Return the exact stored passage and complete known source metadata."""
        reference = application.get_reference(citation_id)
        if reference is None:
            raise ValueError("reference not found")
        return reference

    return server


def run(app: Application | None = None) -> None:
    create_server(app).run(transport="stdio")
