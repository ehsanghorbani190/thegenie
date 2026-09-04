from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReferenceRepository:
    """Expose Qdrant chunks through the citation/verification repository contract."""

    def __init__(self, repository: Any, documents_path: Path | str = Path()) -> None:
        self.repository = repository
        self.documents_path = Path(documents_path)

    def get_reference(self, citation_id: str) -> dict[str, Any] | None:
        chunk = self.repository.get_chunk(citation_id)
        if chunk is None:
            return None
        reference = chunk.model_dump(mode="json")
        metadata = reference.pop("metadata")
        reference.update(metadata)
        source_path = Path(reference["source_path"])
        if not source_path.is_absolute():
            reference["source_path"] = str((self.documents_path / source_path).resolve())
        return reference


class Application:
    """Lazy composition root for CLI and MCP entry points."""

    def __init__(self) -> None:
        self._settings: Any = None
        self._embedder: Any = None
        self._reranker: Any = None
        self._repository: Any = None
        self._references: Any = None
        self._search: Any = None

    @property
    def settings(self) -> Any:
        if self._settings is None:
            from thegenie.config import Settings

            self._settings = Settings()
        return self._settings

    @property
    def embedder(self) -> Any:
        if self._embedder is None:
            from thegenie.embeddings import LocalSentenceTransformerEmbedder

            settings = self.settings
            self._embedder = LocalSentenceTransformerEmbedder(
                settings.embedding_model,
                cache_dir=settings.cache_path,
                device=settings.device,
                batch_size=settings.embedding_batch_size,
                offline=settings.offline,
                token=settings.hf_token,
            )
        return self._embedder

    @property
    def reranker(self) -> Any:
        if self._reranker is None:
            from thegenie.embeddings import LocalCrossEncoder

            settings = self.settings
            self._reranker = LocalCrossEncoder(
                settings.reranker_model,
                cache_dir=settings.cache_path,
                device=settings.device,
                batch_size=settings.embedding_batch_size,
                offline=settings.offline,
                token=settings.hf_token,
            )
        return self._reranker

    @property
    def repository(self) -> Any:
        if self._repository is None:
            from thegenie.database import QdrantRepository

            settings = self.settings
            self._repository = QdrantRepository.from_url(
                settings.qdrant_url,
                settings.qdrant_collection,
                self.embedder.dimension,
            )
        return self._repository

    @property
    def references(self) -> ReferenceRepository:
        if self._references is None:
            self._references = ReferenceRepository(self.repository, self.settings.documents_path)
        return self._references

    @property
    def search_service(self) -> Any:
        if self._search is None:
            from thegenie.retrieval import ReferenceSearch

            settings = self.settings
            self._search = ReferenceSearch(
                self.repository,
                self.embedder,
                self.reranker,
                vector_candidates=settings.vector_candidates,
                deduplication_threshold=settings.deduplication_threshold,
                source_diversity=settings.source_diversity,
            )
        return self._search

    def ingest(self, path: Path, *, prune: bool = False, on_progress: Any = None) -> Any:
        from thegenie.ingestion import IngestionPipeline

        settings = self.settings
        pipeline = IngestionPipeline(
            settings,
            embedder=self.embedder,
            repository_factory=lambda dimension: self._make_repository(dimension),
        )
        return pipeline.ingest(path, prune=prune, on_progress=on_progress)

    def _make_repository(self, dimension: int) -> Any:
        from thegenie.database import QdrantRepository

        settings = self.settings
        repository = QdrantRepository.from_url(
            settings.qdrant_url, settings.qdrant_collection, dimension
        )
        self._repository = repository
        self._references = None
        return repository

    def search(self, query: str, *, top_k: int | None = None, document_filter: str | None = None) -> list[Any]:
        return self.search_service.search(
            query,
            top_k=top_k or self.settings.result_count,
            document_filter=document_filter,
        )

    def get_reference(self, citation_id: str) -> dict[str, Any] | None:
        return self.references.get_reference(citation_id)

    def list_documents(self) -> list[dict[str, Any]]:
        from thegenie.ingestion import load_manifest

        manifest = load_manifest(self.settings)
        return [
            {
                "document_id": str(entry.document_id),
                "source_path": str(entry.source_path),
                "chunk_count": entry.chunk_count,
                "indexed_at": entry.indexed_at.isoformat(),
            }
            for _, entry in sorted(manifest.documents.items())
        ]

    def verify(self, document: Path, *, strict: bool = False) -> tuple[Any, Path]:
        from thegenie.verification import ClaimVerifier, LazyCrossEncoderNLI, write_json_report

        text = document.read_text(encoding="utf-8")
        settings = self.settings
        verifier = ClaimVerifier(
            self.references,
            nli=LazyCrossEncoderNLI(
                settings.nli_model,
                cache_folder=settings.cache_path,
                device=settings.device,
                local_files_only=settings.offline,
                token=settings.hf_token,
            ),
            retriever=_AlternativeRetriever(self.search_service),
            entailment_threshold=settings.entailment_threshold,
            contradiction_threshold=settings.contradiction_threshold,
        )
        report = verifier.verify_text(text, source=document, strict=strict)
        path = self._verification_file(document, "verification.json")
        write_json_report(report, path)
        return report, path

    def revise(self, document: Path) -> tuple[Any, Path, Path]:
        from thegenie.verification import revision_plan, write_revision_plan

        report, _ = self.verify(document)
        plan = revision_plan(report)
        json_path = self._verification_file(document, "revision.json")
        markdown_path = self._verification_file(document, "revision.md")
        write_revision_plan(plan, json_path, markdown_path)
        return plan, json_path, markdown_path

    def citations(self, document: Path) -> tuple[tuple[str, ...], tuple[Any, ...]]:
        from thegenie.citation import CitationValidator, format_bibliography

        results = CitationValidator(self.references).validate_text(
            document.read_text(encoding="utf-8")
        )
        references = [result.reference for result in results if result.reference]
        return format_bibliography(references), results

    def health(self) -> dict[str, Any]:
        from thegenie.database import QdrantRepository
        from thegenie.embeddings import LocalCrossEncoder, LocalSentenceTransformerEmbedder

        settings = self.settings
        embedding = LocalSentenceTransformerEmbedder(settings.embedding_model, cache_dir=settings.cache_path)
        reranker = LocalCrossEncoder(settings.reranker_model, cache_dir=settings.cache_path)
        nli = LocalCrossEncoder(settings.nli_model, cache_dir=settings.cache_path)
        models = {
            "embedding": embedding.is_available_locally(),
            "reranker": reranker.is_available_locally(),
            "nli": nli.is_available_locally(),
        }
        repository = QdrantRepository.from_url(
            settings.qdrant_url, settings.qdrant_collection, 1
        )
        storage = repository.health()
        try:
            repository.client.get_collections()
            reachable = True
        except Exception:
            reachable = False
        ok = reachable and storage.collection_exists and all(models.values()) and settings.documents_path.is_dir()
        return {
            "status": "ok" if ok else "error",
            "qdrant_reachable": reachable,
            "collection_exists": storage.collection_exists,
            "models": models,
            "documents_path_exists": settings.documents_path.is_dir(),
            "document_count": storage.document_count,
            "chunk_count": storage.chunk_count,
            "detail": storage.detail,
        }

    def download_models(self) -> tuple[str, ...]:
        settings = self.settings
        settings.cache_path.mkdir(parents=True, exist_ok=True)
        _ = self.embedder.model
        _ = self.reranker.model
        from sentence_transformers import CrossEncoder

        CrossEncoder(
            settings.nli_model,
            cache_folder=str(settings.cache_path),
            device=settings.device,
            token=settings.hf_token,
        )
        return settings.embedding_model, settings.reranker_model, settings.nli_model

    def _verification_file(self, document: Path, suffix: str) -> Path:
        safe_name = document.name.replace("/", "_")
        return self.settings.verification_path / f"{safe_name}.{suffix}"



class _AlternativeRetriever:
    def __init__(self, search: Any) -> None:
        self.search_service = search

    def search(self, query: str, top_k: int = 3, document_filter: Any = None) -> tuple[dict[str, str], ...]:
        return tuple(
            {"citation_id": result.chunk.citation_id}
            for result in self.search_service.search(query, top_k=top_k, document_filter=document_filter)
        )


def json_text(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, indent=2)
