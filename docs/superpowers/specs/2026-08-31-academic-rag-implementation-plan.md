# TheGenie Academic RAG Implementation Plan

Date: 2026-08-31
Scope: Phase 1 runtime system; Phase 2 automated tests deferred by user request
Design: `docs/superpowers/specs/2026-08-31-academic-rag-design.md`

## Constraints

- Package and single CLI entry point: `thegenie`.
- Python 3.12 through 3.13; managed with `uv`.
- PDF processing, embeddings, retrieval, reranking, citation validation, and semantic verification stay local.
- OpenCode accesses only read-only MCP tools through `thegenie mcp`.
- Phase 1 includes verification and manual smoke checks.
- Phase 1 does not implement automated tests or benchmark dataset/evaluation logic.
- `thegenie revise` writes a revision plan; it never edits drafts or invokes a writer model.

## Phase 1 tasks

### 1. Project foundation

Create:

- `pyproject.toml`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- package directories under `src/thegenie/`
- runtime data/document directories

Configure one entry point:

```toml
[project.scripts]
thegenie = "thegenie.cli:main"
```

Add runtime dependencies only: PyMuPDF, qdrant-client, sentence-transformers, MCP, Pydantic Settings, and small CLI/logging dependencies only if stdlib cannot meet need.

Manual check:

```bash
uv run thegenie --help
```

### 2. Configuration and domain models

Implement:

- Central `RAG_*` settings.
- Path creation helpers.
- PDF metadata, page, chunk, retrieval result, citation result, claim, evidence result, and report schemas.
- Enums for claim types, evidence verdicts, confidence, and structural citation failures.
- Validation for chunk overlap, top-K limits, batches, and thresholds.

Manual check: load defaults and `.env` overrides without importing ML models.

### 3. PDF extraction

Implement:

- Streaming SHA-256 helper.
- PyMuPDF page extraction.
- Conservative metadata parsing.
- Unicode-safe filenames/text.
- Heading candidates from font/block information.
- Empty/image-page warnings.
- One-based page preservation.

Manual check: generate a small English/Persian PDF and inspect extracted pages and metadata.

### 4. Structure-aware chunking and citation IDs

Implement:

- Paragraph and multilingual sentence splitting.
- Section-aware, page-bounded chunks.
- Configurable target size and overlap.
- Oversized paragraph fallback splitting.
- Exact extracted text preservation.
- Stable document IDs through manifest.
- Deterministic citation IDs from document ID, page, and exact text fingerprint.

Manual check: verify pages, overlap, Persian text, stable IDs, and changed-text IDs.

### 5. Local model adapters

Implement lazy reusable adapters:

- `SentenceTransformer` embedder with normalized vectors and batching.
- `CrossEncoder` reranker.
- Multilingual NLI cross-encoder with label-map validation.
- Automatic device selection with explicit override.
- Configurable Hugging Face cache and offline mode.
- Model availability checks that do not trigger downloads.

Add a model download command only if it reduces setup friction without adding another entry point, likely:

```bash
thegenie models download
```

Manual check: import adapters without loading models; then perform explicit real-model smoke check when network/model resources permit.

### 6. Qdrant storage

Implement:

- Reachability check.
- Automatic cosine collection creation.
- Payload indexes.
- Batched chunk upserts.
- Delete by document ID/hash.
- Dense vector search with document filter.
- Citation lookup.
- Document existence and health counts.
- Payload-to-domain conversion with strict validation.

Manual check: start Docker Compose, create collection, upsert synthetic chunk, search, resolve, and delete it.

### 7. Incremental ingestion

Implement:

- Recursive PDF discovery.
- Atomic JSON manifest.
- New/changed/unchanged classification.
- Skip unchanged files before model loading.
- Upsert new chunks before deleting prior-hash chunks.
- Preserve old index on extraction/embedding failure.
- Explicit `--prune` behavior scoped to scanned root.
- Concise progress and summary output.

CLI:

```bash
thegenie ingest ./documents
thegenie ingest ./documents --prune
```

Manual check: new, unchanged, modified, duplicate, missing, and prune flows.

### 8. Retrieval and formatting

Implement:

- Local query embedding.
- Qdrant candidate retrieval.
- Local reranking.
- Same-document overlap deduplication.
- Source-diverse first pass, score-based fill.
- Compact human-readable and MCP formatting.
- Exact passage, page, section, known metadata, citation marker, and relevance estimate.

CLI:

```bash
thegenie search "specific academic claim"
thegenie reference CITATION_ID
```

Manual check: relevant result, top-K, document filter, deduplication, and citation resolution.

### 9. Structural citation validation

Implement:

- Marker extraction and malformed marker detection.
- Citation lookup.
- Source path existence.
- Current hash comparison.
- PDF page validation.
- Stored fingerprint validation.
- Unique source listing and extensible bibliography formatter boundary.

CLI:

```bash
thegenie citations proposal.md
thegenie verify proposal.md
```

Manual check: valid, malformed, unknown, missing, changed, invalid-page, and chunk-mismatch cases.

### 10. Claim-level evidence verification

Implement:

- Paragraph and multilingual sentence/claim extraction.
- Citation-to-claim association.
- Deterministic claim-type rules.
- Exact/normalized quote checks.
- Exact number/date/statistical value checks.
- Negation and attribution checks.
- Strengthening checks for modal removal, causation, exclusivity, and overgeneralization.
- Local multilingual NLI inference.
- Strict Pydantic evidence result.
- Normal and strict exit rules.
- Optional independent local retrieval for failed claims.
- Atomic JSON reports under `data/verification/`.
- Confidence labels framed as estimates.

CLI:

```bash
thegenie verify proposal.md
thegenie verify proposal.md --strict
```

Manual adversarial checks: support, wrong citation, exaggeration, contradiction, wrong number, fabricated quote, and valid-but-unsupported citation.

### 11. Revision plans

Implement:

- Read latest/new verification result or run verifier.
- Produce JSON and readable revision plan.
- Suggest remove, qualify, rewrite, or inspect alternative evidence.
- Never edit source document.
- Never call a writer model.

CLI:

```bash
thegenie revise proposal.md
```

Manual check: failed claims produce bounded actionable plan.

### 12. Read-only MCP server

Implement FastMCP stdio server with only:

```text
search_references(query, top_k=5, document_filter=None)
get_reference(citation_id)
```

Requirements:

- Models and clients initialized once and reused.
- Clear anti-hallucination tool descriptions.
- Compact context-efficient results.
- No mutation, ingestion, health, or verifier tools.
- No document text logging.

CLI:

```bash
thegenie mcp
```

Manual check: inspect registered schemas and invoke both tools through MCP client session.

### 13. Health command

Implement checks for:

- Qdrant reachability.
- Collection existence.
- Embedding model local availability.
- Reranker local availability.
- NLI model local availability.
- Documents directory.
- Indexed document and chunk counts.

CLI:

```bash
thegenie health
```

Return nonzero when required service/model checks fail.

### 14. OpenCode instructions and integration

Create `AGENTS.md` with approved academic writing and evidence workflow.

Verify installed OpenCode `1.18.25` configuration format using local help/schema or official current documentation. Document configuration launching:

```text
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

Explain that OpenCode starts MCP process and invokes MCP tools; it does not execute other CLI subcommands.

Manual check: register server, list MCP status/tools, and confirm an academic prompt invokes `academic-rag_search_references` or actual installed tool name.

### 15. README and troubleshooting

Document from-zero setup:

1. Install/select Python 3.12 through `uv`.
2. Sync dependencies.
3. Copy `.env.example`.
4. Start Qdrant.
5. Download models.
6. Add PDFs.
7. Ingest.
8. Search and inspect references.
9. Configure/restart OpenCode.
10. Confirm MCP tools and invocation.
11. Draft with `[[REF:...]]` markers.
12. Verify and produce revision plan.

Include architecture diagram, token/privacy explanation, security, CPU/GPU notes, model cache/offline use, Unicode/Persian support, extraction/OCR limits, retrieval limits, verifier limits, and human-review requirement.

### 16. Phase 1 manual acceptance

Run available checks in increasing scope:

```bash
uv run thegenie --help
docker compose config
docker compose up -d
uv run thegenie health
uv run thegenie ingest ./documents
uv run thegenie search "fixture-specific question"
uv run thegenie reference CITATION_ID
uv run thegenie verify acceptance.md --strict
uv run thegenie revise acceptance.md
```

Then invoke MCP search/reference through an MCP client and, if OpenCode configuration can be safely changed without overwriting user settings, verify server status and a real tool call.

Record commands actually run and exact unavailable checks. Do not claim Phase 2 acceptance.

## Phase 2 plan: deferred automated testing

Create requested test suite and benchmark after Phase 1 review:

- Chunking unit tests.
- Ingestion lifecycle tests.
- Retrieval ranking/deduplication/diversity tests.
- Citation structural tests.
- MCP startup/schema/invocation tests.
- Adversarial verification tests.
- At least 30 benchmark records.
- `thegenie evaluate` metrics: precision, recall, F1, macro F1, confusion matrix.
- Qdrant integration tests.
- Real-model marked tests.
- Full generated-PDF acceptance test.

Phase 2 completes production acceptance only after all required suites and end-to-end flow pass.

## Implementation order and checkpoints

Execute tasks in listed order. After each task:

1. Run smallest available manual check.
2. Inspect diagnostics.
3. Fix only failures caused by current work.
4. Keep models unloaded unless check requires inference.
5. Update README only after command behavior stabilizes.

Do not commit or initialize Git unless user explicitly asks.
