from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from thegenie.citation.models import CitationValidationResult


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class Claim(StrictModel):
    text: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    paragraph: int = Field(ge=0)
    claim_type: ClaimType
    citation_ids: tuple[str, ...] = ()


class NLIScores(StrictModel):
    entailment: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)
    contradiction: float = Field(ge=0, le=1)


class EvidenceResult(StrictModel):
    claim: Claim
    verdict: EvidenceVerdict
    confidence: Confidence
    reasons: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    nli: NLIScores | None = None
    possible_alternatives: tuple[str, ...] = ()


class VerificationReport(StrictModel):
    source: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    strict: bool = False
    structural: tuple[CitationValidationResult, ...] = ()
    claims: tuple[EvidenceResult, ...] = ()
    failed: bool = False


class RevisionAction(StrEnum):
    REMOVE = "REMOVE"
    QUALIFY = "QUALIFY"
    REWRITE = "REWRITE"
    INSPECT_ALTERNATIVE_EVIDENCE = "INSPECT_ALTERNATIVE_EVIDENCE"


class RevisionItem(StrictModel):
    claim: str
    verdict: EvidenceVerdict
    action: RevisionAction
    reason: str
    current_evidence: tuple[str, ...] = ()
    possible_alternatives: tuple[str, ...] = ()


class RevisionPlan(StrictModel):
    source: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: tuple[RevisionItem, ...]
    note: str = "This plan does not edit the source document or prove factual truth."
