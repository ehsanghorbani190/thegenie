from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from thegenie.citation import CitationValidator, strip_ref_markers

from .checks import (
    attribution_check,
    negation_check,
    numeric_stat_check,
    quote_check,
    split_sentences,
    strengthening_checks,
    strip_reporting_frame,
)
from .claims import extract_claims
from .models import Claim, ClaimType, Confidence, EvidenceResult, EvidenceVerdict, NLIScores, VerificationReport
from .nli import NLIAdapter


class VerificationRepository(Protocol):
    def get_reference(self, citation_id: str) -> Any | None: ...


class AlternativeRetriever(Protocol):
    """High-level ReferenceSearch-compatible retriever."""

    def search(self, query: str, top_k: int = 3, document_filter: Any = None) -> Sequence[Any]: ...


def _value(item: Mapping[str, Any] | Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = item.get(name) if isinstance(item, Mapping) else getattr(item, name, None)
        if value is not None:
            return value
    return default


def _authors(reference: Any) -> tuple[str, ...]:
    value = _value(reference, "authors", default=()) or ()
    return (value,) if isinstance(value, str) else tuple(str(author) for author in value)


def _best_nli_scores(nli: NLIAdapter, evidence: str, claim_text: str) -> NLIScores:
    """Score the claim against each evidence sentence and keep the strongest signal.

    A retrieved chunk usually spans several sentences of surrounding, unrelated
    context. Scoring the whole chunk as one premise dilutes the NLI model's
    entailment signal even when one sentence directly supports the claim, so this
    scores sentence-by-sentence and keeps whichever result is most decisive.
    """
    sentences = [sentence for sentence in split_sentences(evidence) if len(sentence) > 8]
    if len(sentences) <= 1:
        return nli.score(evidence, claim_text)
    scored = [nli.score(sentence, claim_text) for sentence in sentences]
    best_entailment = max(scored, key=lambda score: score.entailment)
    best_contradiction = max(scored, key=lambda score: score.contradiction)
    return best_contradiction if best_contradiction.contradiction >= best_entailment.entailment else best_entailment


class ClaimVerifier:
    def __init__(
        self,
        repository: VerificationRepository,
        *,
        nli: NLIAdapter | None = None,
        retriever: AlternativeRetriever | None = None,
        citation_validator: CitationValidator | None = None,
        entailment_threshold: float = 0.65,
        contradiction_threshold: float = 0.65,
    ) -> None:
        self.repository = repository
        self.nli = nli
        self.retriever = retriever
        self.citation_validator = citation_validator or CitationValidator(repository)
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold

    def verify_text(self, text: str, *, source: str | Path | None = None, strict: bool = False) -> VerificationReport:
        structural = self.citation_validator.validate_text(text)
        results = tuple(self.verify_claim(claim) for claim in extract_claims(text))
        hard_structural = any(not result.valid for result in structural)
        hard_semantic = any(result.verdict in {EvidenceVerdict.CONTRADICTED, EvidenceVerdict.QUOTE_MISMATCH} for result in results)
        strict_failure = strict and any(
            result.claim.claim_type == ClaimType.LITERATURE_CLAIM
            and result.verdict in {EvidenceVerdict.PARTIALLY_SUPPORTED, EvidenceVerdict.UNSUPPORTED, EvidenceVerdict.UNVERIFIABLE}
            for result in results
        )
        return VerificationReport(
            source=str(source) if source is not None else None,
            strict=strict,
            structural=structural,
            claims=results,
            failed=hard_structural or hard_semantic or strict_failure,
        )

    def verify_claim(self, claim: Claim) -> EvidenceResult:
        if claim.claim_type != ClaimType.LITERATURE_CLAIM:
            return EvidenceResult(
                claim=claim,
                verdict=EvidenceVerdict.UNVERIFIABLE,
                confidence=Confidence.LOW,
                reasons=(f"{claim.claim_type} is not automatically treated as a cited literature claim",),
                citation_ids=claim.citation_ids,
            )
        references = tuple(filter(None, (self.repository.get_reference(cid) for cid in claim.citation_ids)))
        if not claim.citation_ids or not references:
            return self._failed(claim, EvidenceVerdict.UNVERIFIABLE, "literature claim has no resolvable citation")

        evidence = tuple(str(_value(ref, "text", "chunk_text", "passage", default="")) for ref in references)
        combined = "\n".join(evidence)
        claim_text = strip_ref_markers(claim.text).strip()
        quote_ok, quote_reason = quote_check(claim_text, combined)
        if quote_ok is False:
            return self._failed(claim, EvidenceVerdict.QUOTE_MISMATCH, quote_reason, evidence)

        reasons: list[str] = [quote_reason] if quote_ok else []
        numeric_ok, numeric_reason = numeric_stat_check(claim_text, combined)
        if numeric_ok is False:
            return self._failed(claim, EvidenceVerdict.CONTRADICTED, numeric_reason, evidence)
        if numeric_ok:
            reasons.append(numeric_reason)

        negation_ok, negation_reason = negation_check(claim_text, combined)
        if negation_ok is False:
            return self._failed(claim, EvidenceVerdict.CONTRADICTED, negation_reason, evidence)

        for reference in references:
            attribution_ok, attribution_reason = attribution_check(claim_text, authors=_authors(reference))
            if attribution_ok is False:
                return self._failed(claim, EvidenceVerdict.CONTRADICTED, attribution_reason, evidence)
            if attribution_ok:
                reasons.append(attribution_reason)

        strengthening = strengthening_checks(claim_text, combined)
        if self.nli is None:
            verdict = EvidenceVerdict.PARTIALLY_SUPPORTED if strengthening else EvidenceVerdict.UNVERIFIABLE
            reason = strengthening or ("semantic NLI adapter was not provided",)
            return self._result(claim, verdict, Confidence.MEDIUM if strengthening else Confidence.LOW, reasons + list(reason), evidence)

        hypothesis = strip_reporting_frame(claim_text)
        scores = _best_nli_scores(self.nli, combined, hypothesis)
        if scores.contradiction >= self.contradiction_threshold:
            return self._result(claim, EvidenceVerdict.CONTRADICTED, Confidence.HIGH, reasons + ["local NLI estimates contradiction"], evidence, scores)
        if scores.entailment >= self.entailment_threshold and not strengthening:
            return self._result(claim, EvidenceVerdict.SUPPORTED, Confidence.HIGH, reasons + ["local NLI estimates entailment"], evidence, scores)
        if scores.entailment >= self.entailment_threshold or strengthening:
            return self._result(claim, EvidenceVerdict.PARTIALLY_SUPPORTED, Confidence.MEDIUM, reasons + list(strengthening or ("evidence supports only part of the claim",)), evidence, scores)
        return self._result(claim, EvidenceVerdict.UNSUPPORTED, Confidence.MEDIUM, reasons + ["local NLI does not estimate entailment"], evidence, scores)

    def _alternatives(self, claim: Claim) -> tuple[str, ...]:
        if self.retriever is None:
            return ()
        found = self.retriever.search(strip_ref_markers(claim.text).strip(), top_k=3)
        alternatives: list[str] = []
        for item in found:
            citation_id = _value(item, "citation_id")
            if citation_id is None:
                citation_id = _value(_value(item, "chunk"), "citation_id")
            if citation_id is not None:
                alternatives.append(str(citation_id))
        return tuple(dict.fromkeys(alternatives))

    def _failed(self, claim: Claim, verdict: EvidenceVerdict, reason: str, evidence: tuple[str, ...] = ()) -> EvidenceResult:
        return self._result(claim, verdict, Confidence.HIGH if verdict in {EvidenceVerdict.CONTRADICTED, EvidenceVerdict.QUOTE_MISMATCH} else Confidence.LOW, [reason], evidence)

    def _result(
        self,
        claim: Claim,
        verdict: EvidenceVerdict,
        confidence: Confidence,
        reasons: list[str],
        evidence: tuple[str, ...],
        nli: NLIScores | None = None,
    ) -> EvidenceResult:
        alternatives = self._alternatives(claim) if verdict not in {EvidenceVerdict.SUPPORTED} else ()
        return EvidenceResult(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            reasons=tuple(reasons),
            evidence=evidence,
            citation_ids=claim.citation_ids,
            nli=nli,
            possible_alternatives=alternatives,
        )
