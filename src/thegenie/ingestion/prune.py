"""Delete indexed data that no longer corresponds to a live source document.

Two distinct kinds of stale data are removed:

* ``MISSING_SOURCE`` — the manifest still lists a PDF that has been deleted from disk.
* ``ORPHAN_VECTORS`` — Qdrant holds points the manifest does not account for. Ingestion
  upserts chunk batches before writing the manifest entry, so a run that is interrupted
  mid-document leaves points behind; because a retry allocates a fresh ``document_id``,
  nothing else ever reclaims them and they stay searchable and citable.

Nothing here loads an embedding model: the repository adopts the collection's existing
vector size instead of asking an embedder for its dimension.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from thegenie.config import Settings
from thegenie.database.qdrant import IndexedDocument, QdrantRepository
from thegenie.models import Manifest, PruneItem, PruneReason, PruneReport

from .pipeline import load_manifest, manifest_path, save_manifest


class PruneRepository(Protocol):
    def delete_document(
        self, document_id: UUID | str, *, document_hash: str | None = None
    ) -> None: ...

    def indexed_documents(self) -> tuple[IndexedDocument, ...]: ...


def prune_index(
    settings: Settings,
    path: str | Path | None = None,
    *,
    repository: PruneRepository | None = None,
    dry_run: bool = False,
) -> PruneReport:
    """Remove entries for deleted PDFs, then sweep vectors the manifest does not claim.

    ``path`` narrows only the deleted-source pass. The orphan sweep is always index-wide,
    because an orphaned group has no manifest entry to scope it by and is a repair rather
    than a scoped operation.
    """
    manifest = load_manifest(settings)
    repository = repository or QdrantRepository.connect(
        settings.qdrant_url, settings.qdrant_collection
    )

    items: list[PruneItem] = []
    removed = 0
    base = settings.documents_path.resolve()

    for key in _missing_sources(manifest, path, base):
        entry = manifest.documents[key]
        try:
            if not dry_run:
                repository.delete_document(entry.document_id, document_hash=entry.document_hash)
                del manifest.documents[key]
            items.append(
                PruneItem(
                    source_path=entry.source_path,
                    reason=PruneReason.MISSING_SOURCE,
                    document_id=entry.document_id,
                    chunk_count=entry.chunk_count,
                )
            )
            removed += entry.chunk_count
        except Exception as exc:
            items.append(
                PruneItem(
                    source_path=entry.source_path,
                    reason=PruneReason.MISSING_SOURCE,
                    document_id=entry.document_id,
                    error=str(exc),
                )
            )

    if not dry_run:
        save_manifest(manifest_path(settings), manifest)

    # A dry run leaves the deleted-source entries in `claimed`, so their vectors are not
    # also reported as orphans; a real run has already deleted both by this point.
    claimed = {
        (str(entry.document_id), entry.document_hash) for entry in manifest.documents.values()
    }
    for document in repository.indexed_documents():
        if (document.document_id, document.document_hash) in claimed:
            continue
        try:
            if not dry_run:
                repository.delete_document(
                    document.document_id, document_hash=document.document_hash
                )
            items.append(
                PruneItem(
                    source_path=Path(document.source_path or document.document_id),
                    reason=PruneReason.ORPHAN_VECTORS,
                    document_id=_as_uuid(document.document_id),
                    chunk_count=document.chunk_count,
                )
            )
            removed += document.chunk_count
        except Exception as exc:
            items.append(
                PruneItem(
                    source_path=Path(document.source_path or document.document_id),
                    reason=PruneReason.ORPHAN_VECTORS,
                    document_id=_as_uuid(document.document_id),
                    error=str(exc),
                )
            )

    return PruneReport(removed_chunks=removed, dry_run=dry_run, items=tuple(items))


def _missing_sources(manifest: Manifest, path: str | Path | None, base: Path) -> list[str]:
    """Manifest keys in scope whose source file is gone.

    The scope path is compared without touching the filesystem, since the whole point is
    that it may itself have been deleted.
    """
    target: Path | None = None
    if path is not None:
        candidate = Path(path)
        target = (candidate if candidate.is_absolute() else Path.cwd() / candidate).resolve()

    keys: list[str] = []
    for key, entry in manifest.documents.items():
        source = (base / entry.source_path).resolve()
        if target is not None and source != target and not source.is_relative_to(target):
            continue
        if not source.exists():
            keys.append(key)
    return sorted(keys)


def _as_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None
