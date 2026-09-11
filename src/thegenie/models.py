from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]
Score = Annotated[float, Field(ge=0, le=1)]


class Model(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", str_strip_whitespace=True
    )


class SourceType(StrEnum):
    ARTICLE = "article"
    BOOK = "book"
    CHAPTER = "chapter"
    CONFERENCE = "conference"
    REPORT = "report"
    THESIS = "thesis"
    OTHER = "other"


class DocumentMetadata(Model):
    title: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = Field(default=None, ge=0)
    doi: str | None = None
    source_type: SourceType | None = None


class Chunk(Model):
    document_id: UUID
    document_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_path: Path
    filename: NonEmptyStr
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    page: int = Field(ge=1)
    section: str | None = None
    chunk_index: int = Field(ge=0)
    text: NonEmptyStr
    citation_id: NonEmptyStr
    fingerprint: NonEmptyStr


class ManifestEntry(Model):
    source_path: Path
    document_id: UUID
    document_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    indexed_at: datetime
    chunk_count: int = Field(ge=0)


class Manifest(Model):
    documents: dict[str, ManifestEntry] = Field(default_factory=dict)


class IngestionStatus(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    FAILED = "failed"


class IngestionItem(Model):
    source_path: Path
    status: IngestionStatus
    document_id: UUID | None = None
    chunk_count: int = Field(default=0, ge=0)
    error: str | None = None
    warnings: tuple[str, ...] = ()


class IngestionReport(Model):
    found: int = Field(ge=0)
    updated_chunks: int = Field(ge=0)
    items: tuple[IngestionItem, ...] = ()


class PruneReason(StrEnum):
    MISSING_SOURCE = "missing_source"
    ORPHAN_VECTORS = "orphan_vectors"


class PruneItem(Model):
    source_path: Path
    reason: PruneReason
    document_id: UUID | None = None
    chunk_count: int = Field(default=0, ge=0)
    error: str | None = None


class PruneReport(Model):
    removed_chunks: int = Field(default=0, ge=0)
    dry_run: bool = False
    items: tuple[PruneItem, ...] = ()


class SearchFilter(Model):
    document_id: UUID | None = None
    filename: str | None = None
    title: str | None = None


class SearchRequest(Model):
    query: NonEmptyStr
    top_k: int = Field(default=5, gt=0)
    document_filter: str | None = None


class SearchResult(Model):
    chunk: Chunk
    vector_score: float
    relevance_score: float


class CitationFailure(StrEnum):
    MALFORMED_CITATION = "MALFORMED_CITATION"
    UNKNOWN_CITATION = "UNKNOWN_CITATION"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    CHANGED_DOCUMENT = "CHANGED_DOCUMENT"
    INVALID_PAGE = "INVALID_PAGE"
    CHUNK_MISMATCH = "CHUNK_MISMATCH"


class CitationCheck(Model):
    citation_id: str
    valid: bool
    failure: CitationFailure | None = None
    detail: str | None = None
    chunk: Chunk | None = None


class ClaimType(StrEnum):
    LITERATURE_CLAIM = "LITERATURE_CLAIM"
    GENERAL_FACT = "GENERAL_FACT"
    INFERENCE = "INFERENCE"
    OPINION = "OPINION"
    TRANSITION = "TRANSITION"
    PROCEDURAL = "PROCEDURAL"
    UNCERTAIN = "UNCERTAIN"


class EvidenceVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TextSpan(Model):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Claim(Model):
    text: NonEmptyStr
    span: TextSpan
    claim_type: ClaimType
    citation_ids: tuple[str, ...] = ()


class NliScores(Model):
    entailment: Score
    neutral: Score
    contradiction: Score


class EvidenceAssessment(Model):
    citation_id: str
    verdict: EvidenceVerdict
    confidence: Confidence
    reason: NonEmptyStr
    nli_scores: NliScores | None = None


class ClaimVerification(Model):
    claim: Claim
    verdict: EvidenceVerdict
    confidence: Confidence
    assessments: tuple[EvidenceAssessment, ...] = ()
    failures: tuple[str, ...] = ()


class VerificationReport(Model):
    document: Path
    generated_at: datetime
    strict: bool = False
    citation_checks: tuple[CitationCheck, ...] = ()
    claims: tuple[ClaimVerification, ...] = ()
    passed: bool


class RevisionAction(StrEnum):
    REMOVE_CLAIM = "REMOVE_CLAIM"
    WEAKEN_CLAIM = "WEAKEN_CLAIM"
    CORRECT_QUOTE = "CORRECT_QUOTE"
    REPLACE_CITATION = "REPLACE_CITATION"
    ADD_EVIDENCE = "ADD_EVIDENCE"
    REVIEW_SOURCE = "REVIEW_SOURCE"


class RevisionItem(Model):
    claim: Claim
    reason: NonEmptyStr
    action: RevisionAction
    current_evidence: tuple[SearchResult, ...] = ()
    alternative_citations: tuple[SearchResult, ...] = ()


class RevisionPlan(Model):
    document: Path
    generated_at: datetime
    items: tuple[RevisionItem, ...] = ()


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


class HealthReport(Model):
    status: HealthStatus
    qdrant_reachable: bool
    collection_exists: bool
    models_available: bool
    documents_path_exists: bool
    document_count: int = Field(default=0, ge=0)
    chunk_count: int = Field(default=0, ge=0)
    details: tuple[str, ...] = ()
