from __future__ import annotations

import re
import unicodedata

from thegenie.citation import strip_ref_markers

_QUOTE = re.compile(r'["“](.*?)["”]|«(.*?)»', re.S)
_NUMBER = re.compile(r"(?<!\w)(?:[npN]\s*=\s*)?[+-]?(?:\d{1,3}(?:[,٬]\d{3})+|\d+)(?:[.٫]\d+)?(?:\s*(?:%|٪|percent|درصد))?(?!\w)", re.I)
_DATE = re.compile(r"(?<!\d)(?:1[34]\d{2}|(?:19|20)\d{2})(?!\d)")
_STAT = re.compile(r"\b(?:p|r|β|alpha|or|rr|ci)\s*(?:=|<|>|≤|≥)\s*[+-]?(?:0?\.)?\d+", re.I)
_NEGATION = re.compile(r"\b(no|not|never|without|neither|nor|نیست|نبود|نمی|بدون|هرگز)\b", re.I)
_CAUSAL = re.compile(r"\b(causes?|caused|leads? to|results? in|اثر می‌گذارد|سبب|موجب)\b", re.I)
_ASSOCIATION = re.compile(r"\b(associated|correlated|related|linked|همبست|مرتبط)\b", re.I)
_MODAL = re.compile(r"\b(may|might|could|possibly|suggests?|احتمالاً|ممکن|شاید)\b", re.I)
_EXCLUSIVE = re.compile(r"\b(only|sole|primary|main|always|all|never|تنها|اصلی|همیشه|همه)\b", re.I)
_ATTRIBUTION = re.compile(r"(?:according to\s+([\w .'-]+)|([\w .'-]+?)\s+(?:reports?|argues?|finds?)|به گفته[ٔ ]+([^،,.]+))", re.I)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+")
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_REPORTING_FRAME = re.compile(
    r"^\s*(?:"
    r"according to\s+[\w .'-]+?(?:\s*\(\d{4}\))?\s*,\s*"
    r"|in (?:this|that|the) (?:study|paper|research|article|work)\s*,\s*"
    r"|(?:this|that|the) (?:study|paper|research|article|work)\s+"
    r"(?:found|shows?|showed|reports?|reported|argues?|argued|demonstrates?|demonstrated|"
    r"concludes?|concluded|notes?|noted|observes?|observed|states?|stated|claims?|claimed|"
    r"suggests?|suggested|indicates?|indicated)\s+that\s+"
    r"|[\w .'-]+?\s+(?:et al\.?\s*)?(?:\(\d{4}\)\s*)?"
    r"(?:found|shows?|showed|reports?|reported|argues?|argued|demonstrates?|demonstrated|"
    r"concludes?|concluded|notes?|noted|observes?|observed|states?|stated|claims?|claimed|"
    r"suggests?|suggested|indicates?|indicated)\s+that\s+"
    r"|طبق\s+(?:گفته|یافته[\u200cهای]*|گزارش|پژوهش)[\u064e\u064f\u0650\u0654 ]*[^،,]+[،,]\s*"
    r"|به\s+گفته[\u064e\u064f\u0650\u0654 ]*[^،,]+[،,]\s*"
    r"|در\s+(?:این|آن)\s+(?:پژوهش|مطالعه|مقاله|تحقیق)\s*[،,]\s*"
    r"|[^،,]+?\s+(?:گزارش داد|گزارش دادند|نشان داد|نشان دادند|بیان کرد|بیان کردند|"
    r"اظهار داشت|اظهار داشتند|عنوان کرد|عنوان کردند|نتیجه[\u200cگیری]*\s*کرد[ند]*)\s+که\s+"
    r")",
    re.IGNORECASE,
)


def strip_reporting_frame(text: str) -> str:
    """Strip a leading attribution/reporting clause (e.g. "X et al. found that", "In this study,").

    NLI models score entailment against the core proposition, not meta-level reported
    speech about who stated it — wrapping an otherwise well-supported claim in ordinary
    academic attribution phrasing can collapse an NLI model's entailment score from
    near-certain to near-zero. The citation marker and the structural citation validator
    already establish provenance, so stripping this framing before scoring lets the NLI
    model judge the actual testable content instead of misreading "X said Y" as a claim
    about a different, unverifiable document.
    """
    stripped = _REPORTING_FRAME.sub("", text, count=1)
    return stripped if stripped.strip() else text


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(_DIGIT_MAP)
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[\s\u200c]+", " ", text)
    return text.strip()


def quoted_passages(text: str) -> tuple[str, ...]:
    return tuple(next(group for group in match.groups() if group is not None).strip() for match in _QUOTE.finditer(text))


def quote_check(claim: str, evidence: str) -> tuple[bool | None, str]:
    quotes = quoted_passages(strip_ref_markers(claim))
    if not quotes:
        return None, "claim contains no quotation"
    normalized_evidence = normalize_for_match(evidence)
    if all(quote in evidence or normalize_for_match(quote) in normalized_evidence for quote in quotes):
        return True, "all quoted wording occurs exactly or after conservative normalization"
    return False, "quoted wording does not occur in cited evidence"


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_SPLIT.split(text) if sentence.strip()]


def _best_overlap_sentence(claim: str, evidence: str) -> str | None:
    """Find the evidence sentence sharing the most significant words with the claim.

    A cheap, deterministic stand-in for a quote anchor when the claim paraphrases
    rather than quotes — good enough to rule out unrelated sentences elsewhere in a
    multi-paragraph chunk, without needing a model.
    """
    claim_words = {word for word in normalize_for_match(strip_ref_markers(claim)).split() if len(word) > 2}
    if not claim_words:
        return None
    best_sentence, best_overlap = None, 1
    for sentence in split_sentences(evidence):
        sentence_words = {word for word in normalize_for_match(sentence).split() if len(word) > 2}
        overlap = len(claim_words & sentence_words)
        if overlap > best_overlap:
            best_sentence, best_overlap = sentence, overlap
    return best_sentence


def _relevant_window(claim: str, evidence: str) -> str:
    """Narrow evidence to the sentence(s) most relevant to the claim.

    Without this, checks that scan the full retrieved chunk (which can span several
    unrelated sentences) false-positive on incidental wording anywhere in the chunk
    rather than near the claim's actual evidence. Prefers an exact quoted match; falls
    back to lexical overlap for paraphrased claims with no quotation.
    """
    quotes = quoted_passages(strip_ref_markers(claim))
    if quotes:
        normalized_quotes = [normalize_for_match(quote) for quote in quotes]
        matches = [
            sentence
            for sentence in split_sentences(evidence)
            if any(quote in normalize_for_match(sentence) for quote in normalized_quotes)
        ]
        if matches:
            return " ".join(matches)
        return evidence
    return _best_overlap_sentence(claim, evidence) or evidence


def _tokens(pattern: re.Pattern[str], text: str) -> set[str]:
    return {normalize_for_match(match.group(0)).replace("٬", ",").replace("٫", ".") for match in pattern.finditer(text)}


def numeric_stat_check(claim: str, evidence: str) -> tuple[bool | None, str]:
    claim_values = _tokens(_NUMBER, claim) | _tokens(_DATE, claim) | _tokens(_STAT, claim)
    if not claim_values:
        return None, "claim contains no numeric, date, or statistical values"
    evidence_values = _tokens(_NUMBER, evidence) | _tokens(_DATE, evidence) | _tokens(_STAT, evidence)
    missing = sorted(claim_values - evidence_values)
    return (not missing, "all numeric/date/statistical values match" if not missing else f"evidence lacks exact values: {', '.join(missing)}")


def negation_check(claim: str, evidence: str) -> tuple[bool | None, str]:
    window = _relevant_window(claim, evidence)
    claim_negative = bool(_NEGATION.search(claim))
    evidence_negative = bool(_NEGATION.search(window))
    if claim_negative == evidence_negative:
        return None, "no surface negation conflict"
    return False, "claim and evidence differ in explicit negation"


def strengthening_checks(claim: str, evidence: str) -> tuple[str, ...]:
    window = _relevant_window(claim, evidence)
    findings: list[str] = []
    if _CAUSAL.search(claim) and _ASSOCIATION.search(window) and not _CAUSAL.search(window):
        findings.append("claim strengthens association into causation")
    if not _MODAL.search(claim) and _MODAL.search(window):
        findings.append("claim removes modal uncertainty present in evidence")
    if _EXCLUSIVE.search(claim) and not _EXCLUSIVE.search(window):
        findings.append("claim adds exclusivity, primacy, or unsupported generalization")
    return tuple(findings)


def attribution_check(claim: str, *, authors: tuple[str, ...] = ()) -> tuple[bool | None, str]:
    match = _ATTRIBUTION.search(claim)
    if not match:
        return None, "claim contains no explicit attribution"
    attributed = normalize_for_match(next(group for group in match.groups() if group))
    if not authors:
        return None, "source has no author metadata for attribution comparison"
    known = " ".join(normalize_for_match(author) for author in authors)
    if attributed in known or any(part in known for part in attributed.split() if len(part) > 2):
        return True, "attribution agrees with available author metadata"
    return False, "attribution does not agree with available author metadata"
