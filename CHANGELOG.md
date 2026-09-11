# Changelog

All notable changes to TheGenie are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While
the project is below `1.0.0`, breaking changes raise the minor version.

Verification claims in this file refer to manual smoke checks. Phase 1 does not
include automated tests or benchmark evaluation (see the implementation plan in
`docs/superpowers/specs/`).

## [0.3.0] — 2026-09-11

### Added

- **OCR fallback for image-only/scanned pages.** `extract_pdf` in
  `src/thegenie/pdf/extraction.py` previously only flagged a page as
  "image-only" when its embedded text was completely empty. That missed pages
  that carry a small amount of incidental real text — page numbers, running
  headers, a distributor's "reproduced with permission" stamp — while the
  actual body content is a raster scan with no text layer at all. Any page
  whose extracted text falls under `_MIN_PAGE_TEXT_CHARS` (200 chars) is now
  rendered at 300 DPI and OCR'd via the system `tesseract` binary as a
  fallback; if OCR recovers more text than was embedded, the page's text is
  replaced and a warning records what happened. If `tesseract` isn't
  installed, ingestion still succeeds with the pre-existing sparse-text
  warning instead of failing.

  Found via a real corpus gap: `10.1518.hfes.46.1.50.30392.pdf` — Lee & See
  (2004), "Trust in Automation: Designing for Appropriate Reliance", the most
  heavily cited paper in a 51-PDF human-agent-trust corpus — is a genuine
  scan (`Producer: image2pdf.c`) whose only real embedded text was the
  copyright stamp, repeated once per page. It ingested without error (31
  chunks, all near-identical boilerplate) and was therefore silently
  unsearchable; claims that should have cited this primary source were
  instead sourced through secondary papers that paraphrase it. Re-ingesting
  after this fix recovered the actual body text on all 31 pages (3,255 total
  extracted chars before, 151,944 after) and produced 97 real, searchable
  chunks.

- **Ingest surfaces extraction warnings.** `ExtractedDocument.warnings` was
  already populated per page but never read anywhere past extraction. It is
  now attached to `IngestionItem.warnings` and printed by the `ingest` CLI
  command (`  ! <warning>`), so a sparse-text or OCR-fallback page is visible
  at ingest time instead of only discoverable by manually auditing
  `pdftotext` output per file.

### Notes

- This is a fallback for individual sparse-text pages, not a general OCR
  pipeline: it recovers text but not layout (OCR'd pages contribute no
  heading/section metadata), and a fully scanned document is still better
  served by sourcing a genuine text-based copy when one exists.

## [0.2.0] — 2026-09-11

Breaking release. `ingest --prune` is gone, replaced by a standalone `prune`
command. It also fixes an ingestion hang that silently affected a large share of
a real corpus.

### Fixed

- **Ingestion could hang forever on some PDFs.** `_page_chunks` in
  `src/thegenie/pdf/chunking.py` advanced its window with
  `start = next_start if next_start < end else end`. The overlap rewind walks
  `next_start` backwards while the retained units fit inside `chunk_overlap`, so
  whenever every unit in a window summed to at most the overlap it walked all the
  way back to `start`, and that line then reassigned `start` to itself. The loop
  appended the same chunk forever until the process died. Advancing by at least
  one unit (`start = max(next_start, start + 1)`) guarantees termination while
  keeping the intended overlap where it fits, mirroring the guard `_hard_split`
  already had.

  Reproduce on the old code with unit token sizes `[30, 30, 500]` at
  `chunk_size=512` and `chunk_overlap=64`. On a 51-PDF corpus, 7 documents
  triggered it and could never complete. After the fix the whole corpus chunks in
  about 54 seconds. Chunk boundaries for inputs that already terminated are
  unchanged.

  Because the failure presented as slowness rather than an error, an affected run
  looked indistinguishable from normal CPU embedding. If an ingest has previously
  appeared to stall indefinitely, that is the likely cause.

- **Ingest progress output did not render, and appeared to load the model twice.**
  Chunk progress used a second positioned `tqdm` bar. Any bar a dependency creates
  while positioned bars are live is assigned its own position, and the resulting
  cursor-up escapes left a stranded copy of the `transformers` "Loading weights"
  line on screen — one model load, drawn twice. Ingest now uses a single bar and
  carries chunk progress in its postfix, and sets `HF_HUB_DISABLE_PROGRESS_BARS=1`
  in the ingest path only, so `models download` keeps its own progress output.
  Measured after the fix: zero `Loading weights` lines and zero cursor-up escapes.

- **Progress was invisible during the slowest phase.** The bar was created lazily
  inside the completion callback, which only fires after a whole document
  finishes, leaving the terminal blank for the first minute or more of a new
  document. The bar is now created before work starts, shows the in-flight
  filename immediately (covering model load), and updates per embedded batch.

### Added

- **`thegenie prune [PATH] [--dry-run]`** — removes stale index data without
  indexing anything. It reports two distinct reasons:

  - `missing_source` — the manifest lists a PDF that has been deleted from disk.
  - `orphan_vectors` — Qdrant holds points the manifest does not account for.

  `PATH` narrows only the `missing_source` pass. The orphan sweep is always
  index-wide, because an orphaned group has no manifest entry to scope it by and
  is a repair rather than a scoped operation. `--dry-run` reports without
  modifying the manifest or the collection.

- **Orphaned vector recovery.** Ingestion upserts chunk batches before writing the
  manifest entry, so a run interrupted mid-document leaves points with no manifest
  record. A retry allocates a fresh `document_id`, so nothing previously reclaimed
  them and they stayed searchable and citable as a partial duplicate of a document
  that was never fully indexed. `prune` now detects them by grouping every stored
  point by `(document_id, document_hash)` and deleting groups the manifest does not
  claim. This also covers stale-hash leftovers from an interrupted re-index.

- **`QdrantRepository.connect()`** — attaches to an existing collection and adopts
  its configured vector size, instead of asking an embedder for its dimension.
  This is why `prune` loads no embedding model; a full prune runs in about 1.2
  seconds rather than paying the model load first.

- **`QdrantRepository.indexed_documents()`** and the `IndexedDocument` record —
  scrolls the collection and returns per-document chunk counts actually present in
  storage, which is what makes manifest-versus-storage reconciliation possible.

- **`on_activity` ingestion callback** — `(document_key, chunks_embedded,
  chunks_total)`, invoked while a single document is in flight. `chunks_total` is
  `0` until chunking determines it, so a caller can display the current document
  before its chunk count is known. Optional and backward compatible.

- **`PruneReport`, `PruneItem`, and `PruneReason`** models describing prune results.

### Changed

- `save_manifest` is now a module-level function in
  `src/thegenie/ingestion/pipeline.py`, so `prune` reuses the same atomic
  write-and-replace with `fsync` instead of duplicating it.
- The `prune` CLI exits non-zero if any individual deletion failed.
- Version is now defined only in `src/thegenie/__init__.py` and read by Hatchling,
  removing the second copy in `pyproject.toml` that could drift.

### Removed

- **`ingest --prune`** (breaking). Deletion was coupled to ingestion, so pruning a
  single removed file required `ingest ./documents --prune`, which also re-indexed
  every unindexed PDF beneath the root. Use `thegenie prune` instead.
- `IngestionStatus.PRUNED` and `IngestionPipeline._prunable_keys`, both dead once
  pruning moved out of the ingestion pipeline.

### Documentation

- `README.md` documents the `prune` command, both prune reasons, and the
  interrupted-ingest orphan window.
- Setup guides and `AGENTS.md` list `prune` among operator-only CLI commands; it is
  deliberately not exposed over MCP, which still offers only `search_references`,
  `get_reference`, and `list_documents`.
- The dated design and implementation specs carry `Superseded in 0.2.0` notes at
  the points describing `--prune`, rather than being rewritten, so the original
  design record stays intact.

### Known issues

- The orphan window itself remains. `prune` cleans up after an interrupted ingest,
  but ingestion still upserts chunks before writing the manifest entry, so
  interrupting a run still creates orphaned vectors. Closing it requires writing
  the manifest entry first or introducing an in-progress sentinel.
- There is no regression test for the chunking loop. Automated tests are deferred
  to Phase 2, so this release relies on manual smoke checks: the `[30, 30, 500]`
  repro, a full-corpus chunk scan, and end-to-end ingest, prune, dry-run,
  path-scoped prune, idempotent re-prune, and search checks.
- Embedding throughput is unchanged and remains the ingestion bottleneck at
  roughly 1.8 seconds per 512-token chunk on CPU. Profiling showed the workload is
  memory-bandwidth bound rather than core bound — 4, 8, and 16 torch threads
  measured 4210, 3943, and 3901 ms per 1000-token chunk — so raising thread counts
  does not help. Dynamic per-tensor int8 quantization was measured at 2.59x faster
  but rejected: document-vector cosine against fp32 averaged 0.924 with a minimum
  of 0.888, and the top-1 result changed on 2 of 4 probe queries, which is not an
  acceptable trade for an evidence-retrieval system.

## [0.1.0]

Initial release: local PDF ingestion, chunking, and embedding into Qdrant;
retrieval with reranking; citation validation; claim-level semantic verification;
revision planning; and a read-only MCP server exposing `search_references`,
`get_reference`, and `list_documents`.
