from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient, models

from thegenie.models import Chunk, DocumentMetadata, SearchFilter


INDEXED_PAYLOAD_FIELDS = (
    "citation_id",
    "document_id",
    "document_hash",
    "filename",
    "source_path",
)


@dataclass(frozen=True)
class VectorSearchResult:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class RepositoryHealth:
    reachable: bool
    collection_exists: bool
    document_count: int = 0
    chunk_count: int = 0
    detail: str | None = None


class QdrantRepository:
    """Qdrant collection lifecycle and strongly typed Chunk persistence."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_size: int,
        *,
        upsert_batch_size: int = 64,
    ) -> None:
        if vector_size < 1:
            raise ValueError("vector_size must be positive")
        if upsert_batch_size < 1:
            raise ValueError("upsert_batch_size must be positive")
        self.client = client
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.upsert_batch_size = upsert_batch_size

    @classmethod
    def from_url(
        cls,
        url: str,
        collection_name: str,
        vector_size: int,
        **client_kwargs: Any,
    ) -> QdrantRepository:
        return cls(QdrantClient(url=url, **client_kwargs), collection_name, vector_size)

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        else:
            self._validate_collection()

        for field in INDEXED_PAYLOAD_FIELDS:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    raise

    def upsert_chunks(
        self,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        points = [
            models.PointStruct(
                id=_point_id(chunk.citation_id),
                vector=list(vector),
                payload=_chunk_to_payload(chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        for start in range(0, len(points), self.upsert_batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start : start + self.upsert_batch_size],
                wait=True,
            )

    def delete_document(
        self,
        document_id: UUID | str,
        *,
        document_hash: str | None = None,
    ) -> None:
        conditions = [_match("document_id", str(document_id))]
        if document_hash is not None:
            conditions.append(_match("document_hash", document_hash))
        self._delete_filter(models.Filter(must=conditions))

    def delete_document_hash(self, document_hash: str) -> None:
        self._delete_filter(models.Filter(must=[_match("document_hash", document_hash)]))

    def search(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        document_filter: SearchFilter | UUID | str | None = None,
    ) -> list[VectorSearchResult]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query_filter = _search_filter(document_filter)
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=list(vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            points = response.points
        else:
            points = self.client.search(
                collection_name=self.collection_name,
                query_vector=list(vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        return [VectorSearchResult(_payload_to_chunk(point.payload), float(point.score)) for point in points]

    def get_chunk(self, citation_id: str) -> Chunk | None:
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=[_match("citation_id", citation_id)]),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        return _payload_to_chunk(records[0].payload) if records else None

    def get_reference(self, citation_id: str) -> Chunk | None:
        """Compatibility alias for citation and verification repository contracts."""
        return self.get_chunk(citation_id)

    def document_exists(self, document_id: UUID | str) -> bool:
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=[_match("document_id", str(document_id))]),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(records)

    def chunk_count(self) -> int:
        result = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        )
        return int(result.count)

    def document_count(self) -> int:
        document_ids: set[str] = set()
        offset: Any = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=["document_id"],
                with_vectors=False,
            )
            document_ids.update(
                str(record.payload["document_id"])
                for record in records
                if record.payload and record.payload.get("document_id") is not None
            )
            if offset is None:
                return len(document_ids)

    def health(self) -> RepositoryHealth:
        try:
            reachable = bool(self.client.get_collections())
            exists = self.client.collection_exists(self.collection_name)
            if not exists:
                return RepositoryHealth(reachable=reachable, collection_exists=False)
            return RepositoryHealth(
                reachable=reachable,
                collection_exists=True,
                document_count=self.document_count(),
                chunk_count=self.chunk_count(),
            )
        except Exception as exc:
            return RepositoryHealth(
                reachable=False,
                collection_exists=False,
                detail=str(exc),
            )

    def _delete_filter(self, point_filter: models.Filter) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(filter=point_filter),
            wait=True,
        )

    def _validate_collection(self) -> None:
        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        if not isinstance(vectors, models.VectorParams):
            raise ValueError("named-vector collections are not supported")
        if vectors.size != self.vector_size or vectors.distance != models.Distance.COSINE:
            raise ValueError(
                f"collection {self.collection_name!r} must use "
                f"{self.vector_size}-dimensional cosine vectors"
            )


def _point_id(citation_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"thegenie:{citation_id}"))


def _match(key: str, value: Any) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _search_filter(value: SearchFilter | UUID | str | None) -> models.Filter | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return models.Filter(must=[_match("document_id", str(value))])
    if isinstance(value, str):
        return models.Filter(
            should=[
                _match("document_id", value),
                _match("filename", value),
                _match("title", value),
            ]
        )
    conditions = []
    if value.document_id is not None:
        conditions.append(_match("document_id", str(value.document_id)))
    if value.filename is not None:
        conditions.append(_match("filename", value.filename))
    if value.title is not None:
        conditions.append(_match("title", value.title))
    return models.Filter(must=conditions) if conditions else None


def _chunk_to_payload(chunk: Chunk) -> dict[str, Any]:
    payload = chunk.model_dump(mode="json")
    metadata = payload.pop("metadata")
    payload.update(metadata)
    return payload


def _payload_to_chunk(payload: Mapping[str, Any] | None) -> Chunk:
    if payload is None:
        raise ValueError("Qdrant point has no payload")
    data = dict(payload)
    metadata = {
        key: data.pop(key, None)
        for key in ("title", "authors", "year", "doi", "source_type")
    }
    metadata["authors"] = tuple(metadata["authors"] or ())
    data["metadata"] = DocumentMetadata.model_validate(metadata)
    data["source_path"] = Path(data["source_path"])
    return Chunk.model_validate(data)
