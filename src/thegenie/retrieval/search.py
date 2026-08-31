from __future__ import annotations

from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Protocol
from uuid import UUID

from thegenie.database import VectorSearchResult
from thegenie.embeddings import LocalCrossEncoder, LocalSentenceTransformerEmbedder
from thegenie.models import SearchFilter, SearchRequest, SearchResult


class VectorRepository(Protocol):
    def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document_filter: SearchFilter | UUID | str | None = None,
    ) -> list[VectorSearchResult]: ...


class ReferenceSearch:
    """Embed, retrieve, locally rerank, deduplicate, and diversify references."""

    repository: VectorRepository
    embedder: LocalSentenceTransformerEmbedder
    reranker: LocalCrossEncoder
    vector_candidates: int
    deduplication_threshold: float
    source_diversity: bool

    def __init__(
        self,
        repository: VectorRepository,
        embedder: LocalSentenceTransformerEmbedder,
        reranker: LocalCrossEncoder,
        *,
        vector_candidates: int = 20,
        deduplication_threshold: float = 0.9,
        source_diversity: bool = True,
    ) -> None:
        if vector_candidates < 1:
            raise ValueError("vector_candidates must be positive")
        if not 0 <= deduplication_threshold <= 1:
            raise ValueError("deduplication_threshold must be between 0 and 1")
        self.repository = repository
        self.embedder = embedder
        self.reranker = reranker
        self.vector_candidates = vector_candidates
        self.deduplication_threshold = deduplication_threshold
        self.source_diversity = source_diversity

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_filter: SearchFilter | UUID | str | None = None,
    ) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")

        candidates = self.repository.search(
            self.embedder.embed_query(query),
            limit=max(top_k, self.vector_candidates),
            document_filter=document_filter,
        )
        scores = self.reranker.score(query, [item.chunk.text for item in candidates])
        if len(scores) != len(candidates):
            raise RuntimeError("reranker returned an unexpected number of scores")

        ranked = sorted(
            (
                SearchResult(
                    chunk=item.chunk,
                    vector_score=item.score,
                    relevance_score=score,
                )
                for item, score in zip(candidates, scores, strict=True)
            ),
            key=lambda item: item.relevance_score,
            reverse=True,
        )
        unique = self._deduplicate(ranked)
        return self._select(unique, top_k)

    def query(self, request: SearchRequest) -> list[SearchResult]:
        return self.search(request.query, request.top_k, request.document_filter)

    def _deduplicate(self, ranked: Sequence[SearchResult]) -> list[SearchResult]:
        kept: list[SearchResult] = []
        for result in ranked:
            same_document = (
                previous
                for previous in kept
                if previous.chunk.document_id == result.chunk.document_id
            )
            if any(self._near_duplicate(result, previous) for previous in same_document):
                continue
            kept.append(result)
        return kept

    def _near_duplicate(self, left: SearchResult, right: SearchResult) -> bool:
        if left.chunk.fingerprint == right.chunk.fingerprint:
            return True
        return SequenceMatcher(None, left.chunk.text, right.chunk.text).ratio() >= self.deduplication_threshold

    def _select(self, ranked: Sequence[SearchResult], top_k: int) -> list[SearchResult]:
        if not self.source_diversity:
            return list(ranked[:top_k])
        selected: list[SearchResult] = []
        seen_documents: set[UUID] = set()
        for result in ranked:
            if result.chunk.document_id not in seen_documents:
                selected.append(result)
                seen_documents.add(result.chunk.document_id)
                if len(selected) == top_k:
                    return selected
        selected_ids = {result.chunk.citation_id for result in selected}
        selected.extend(
            result for result in ranked
            if result.chunk.citation_id not in selected_ids
        )
        return selected[:top_k]
