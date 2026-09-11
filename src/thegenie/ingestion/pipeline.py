from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from thegenie.config import Settings
from thegenie.database.qdrant import QdrantRepository
from thegenie.embeddings.local import LocalSentenceTransformerEmbedder
from thegenie.models import (
    Chunk,
    DocumentMetadata,
    IngestionItem,
    IngestionReport,
    IngestionStatus,
    Manifest,
    ManifestEntry,
    SourceType,
)
from thegenie.pdf import chunk_pages, extract_pdf, file_sha256
from thegenie.pdf.models import ChunkRecord, ExtractedDocument


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def tokenizer(self) -> Any: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


class Repository(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert_chunks(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None: ...

    def delete_document(self, document_id: UUID | str, *, document_hash: str | None = None) -> None: ...


RepositoryFactory = Callable[[int], Repository]
ProgressCallback = Callable[[int, int, IngestionItem], None]
ActivityCallback = Callable[[str, int, int], None]
"""Called as (document_key, chunks_embedded, chunks_total) while a document is in flight.

``chunks_total`` is 0 until chunking has determined it, which lets a caller display the
document being worked on before its chunk count is known.
"""


def manifest_path(settings: Settings) -> Path:
    return settings.metadata_path / "index.json"


def load_manifest(settings: Settings) -> Manifest:
    """Read the ingestion manifest without loading any embedder or repository."""
    path = manifest_path(settings)
    if not path.exists():
        return Manifest()
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: Manifest) -> None:
    """Replace the manifest atomically so an interrupted write cannot truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as target:
            _ = target.write(manifest.model_dump_json(indent=2))
            _ = target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        embedder: Embedder | None = None,
        repository: Repository | None = None,
        repository_factory: RepositoryFactory | None = None,
    ) -> None:
        self.settings: Settings = settings or Settings()
        self.embedder: Embedder = embedder or LocalSentenceTransformerEmbedder(
            self.settings.embedding_model,
            cache_dir=self.settings.cache_path,
            device=self.settings.device,
            batch_size=self.settings.embedding_batch_size,
            offline=self.settings.offline,
            token=self.settings.hf_token,
        )
        self.repository: Repository | None = repository
        self.repository_factory: RepositoryFactory = repository_factory or (
            lambda dimension: QdrantRepository.from_url(
                self.settings.qdrant_url,
                self.settings.qdrant_collection,
                dimension,
            )
        )
        self.manifest_path: Path = manifest_path(self.settings)

    def ingest(
        self,
        path: str | Path,
        *,
        on_progress: ProgressCallback | None = None,
        on_activity: ActivityCallback | None = None,
    ) -> IngestionReport:
        scan_path = Path(path).resolve()
        if not scan_path.exists():
            raise FileNotFoundError(scan_path)
        if not scan_path.is_dir() and scan_path.suffix.casefold() != ".pdf":
            raise ValueError(f"ingestion path is not a PDF or directory: {scan_path}")

        manifest = self._load_manifest()
        base = self.settings.documents_path.resolve()
        discovered = self._discover(scan_path)
        keyed_files = [(self._manifest_key(file, base), file) for file in discovered]
        hashes = {key: file_sha256(file) for key, file in keyed_files}
        items: list[IngestionItem] = []
        updated_chunks = 0
        repository: Repository | None = self.repository

        total = len(keyed_files)
        done = 0

        def report(item: IngestionItem) -> None:
            nonlocal done
            done += 1
            if on_progress:
                on_progress(done, total, item)

        for key, source in keyed_files:
            previous = manifest.documents.get(key)
            document_hash = hashes[key]
            if previous and previous.document_hash == document_hash:
                item = IngestionItem(source_path=Path(key), status=IngestionStatus.UNCHANGED, document_id=previous.document_id, chunk_count=previous.chunk_count)
                items.append(item)
                report(item)
                continue

            document_id = previous.document_id if previous else uuid4()
            status = IngestionStatus.CHANGED if previous else IngestionStatus.NEW
            try:
                if on_activity:
                    on_activity(key, 0, 0)
                extracted = extract_pdf(source)
                records = chunk_pages(
                    extracted.pages,
                    document_id=document_id,
                    filename=source.name,
                    target_size=self.settings.chunk_size,
                    overlap=self.settings.chunk_overlap,
                    token_counter=self._token_count,
                )
                chunks = [self._chunk(record, extracted, Path(key), document_hash) for record in records]
                repository = repository or self._repository()
                repository.ensure_collection()
                if on_activity:
                    on_activity(key, 0, len(chunks))
                embedded = 0
                for start in range(0, len(chunks), self.settings.embedding_batch_size):
                    batch = chunks[start : start + self.settings.embedding_batch_size]
                    repository.upsert_chunks(batch, self.embedder.embed_documents([chunk.text for chunk in batch]))
                    embedded += len(batch)
                    if on_activity:
                        on_activity(key, embedded, len(chunks))
                if previous:
                    repository.delete_document(document_id, document_hash=previous.document_hash)
                manifest.documents[key] = ManifestEntry(
                    source_path=Path(key),
                    document_id=document_id,
                    document_hash=document_hash,
                    indexed_at=datetime.now(UTC),
                    chunk_count=len(chunks),
                )
                self._write_manifest(manifest)
                updated_chunks += len(chunks)
                item = IngestionItem(
                    source_path=Path(key),
                    status=status,
                    document_id=document_id,
                    chunk_count=len(chunks),
                    warnings=extracted.warnings,
                )
                items.append(item)
                report(item)
            except Exception as exc:
                item = IngestionItem(source_path=Path(key), status=IngestionStatus.FAILED, document_id=document_id, error=str(exc))
                items.append(item)
                report(item)

        return IngestionReport(found=len(discovered), updated_chunks=updated_chunks, items=tuple(items))

    def _repository(self) -> Repository:
        if self.repository is None:
            self.repository = self.repository_factory(self.embedder.dimension)
        return self.repository

    def _token_count(self, text: str) -> int:
        tokenizer = self.embedder.tokenizer
        encoded = tokenizer.encode(text, add_special_tokens=False)  # type: ignore[attr-defined]
        return len(encoded)

    @staticmethod
    def _discover(path: Path) -> list[Path]:
        if path.is_file():
            return [path]
        return sorted((file for file in path.rglob("*") if file.is_file() and file.suffix.casefold() == ".pdf"), key=lambda file: str(file).casefold())

    @staticmethod
    def _manifest_key(path: Path, base: Path) -> str:
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            return Path(os.path.relpath(path, base)).as_posix()

    @staticmethod
    def _chunk(record: ChunkRecord, document: ExtractedDocument, source_path: Path, document_hash: str) -> Chunk:
        source_type = document.metadata.source_type
        metadata = DocumentMetadata(
            title=document.metadata.title,
            authors=document.metadata.authors,
            year=document.metadata.year,
            doi=document.metadata.doi,
            source_type=SourceType(source_type) if source_type else None,
        )
        return Chunk(
            document_id=UUID(record.document_id),
            document_hash=document_hash,
            source_path=source_path,
            filename=document.filename,
            metadata=metadata,
            page=record.page,
            section=record.section,
            chunk_index=record.chunk_index,
            text=record.text,
            citation_id=record.citation_id,
            fingerprint=record.fingerprint,
        )

    def _load_manifest(self) -> Manifest:
        return load_manifest(self.settings)

    def _write_manifest(self, manifest: Manifest) -> None:
        save_manifest(self.manifest_path, manifest)


