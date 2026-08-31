from .checks import (
    attribution_check,
    negation_check,
    normalize_for_match,
    numeric_stat_check,
    quote_check,
    quoted_passages,
    strengthening_checks,
)
from .claims import classify_claim, extract_claims
from .models import (
    Claim,
    ClaimType,
    Confidence,
    EvidenceResult,
    EvidenceVerdict,
    NLIScores,
    RevisionAction,
    RevisionItem,
    RevisionPlan,
    VerificationReport,
)
from .nli import LazyCrossEncoderNLI, NLIAdapter
from .reporting import revision_plan, write_json_report, write_revision_plan
from .verifier import AlternativeRetriever, ClaimVerifier, VerificationRepository

__all__ = [
    "AlternativeRetriever",
    "Claim",
    "ClaimType",
    "ClaimVerifier",
    "Confidence",
    "EvidenceResult",
    "EvidenceVerdict",
    "LazyCrossEncoderNLI",
    "NLIAdapter",
    "NLIScores",
    "RevisionAction",
    "RevisionItem",
    "RevisionPlan",
    "VerificationReport",
    "VerificationRepository",
    "attribution_check",
    "classify_claim",
    "extract_claims",
    "negation_check",
    "normalize_for_match",
    "numeric_stat_check",
    "quote_check",
    "quoted_passages",
    "revision_plan",
    "strengthening_checks",
    "write_json_report",
    "write_revision_plan",
]
