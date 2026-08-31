from __future__ import annotations

import re

from thegenie.citation import parse_ref_markers, strip_ref_markers

from .models import Claim, ClaimType

_SENTENCE_END = re.compile(r"(?<=[.!?؟؛。！？])(?:[\"'»”)]*)\s+|\n+")
_TRANSITION = re.compile(r"^(however|therefore|moreover|in conclusion|nevertheless|با این حال|بنابراین|در نتیجه)\b", re.I)
_PROCEDURAL = re.compile(r"\b(we (?:use|used|calculate|define)|this (?:paper|section) (?:uses|describes)|روش|محاسبه|استفاده می‌کنیم)\b", re.I)
_LITERATURE = re.compile(r"\b(stud(?:y|ies)|research|evidence|reported|found|according to|مطالعه|پژوهش|شواهد|نشان داد|گزارش)\b", re.I)
_INFERENCE = re.compile(r"\b(suggests?|implies?|therefore|thus|احتمالاً|نشان می‌دهد|می‌توان نتیجه گرفت)\b", re.I)
_OPINION = re.compile(r"\b(i (?:think|believe)|we argue|in our view|به نظر|معتقدیم)\b", re.I)
_FACT_SIGNAL = re.compile(r"(?:\d|[%٪]|\b(?:19|20)\d{2}\b|[\"“”«»])")


def classify_claim(text: str, citation_ids: tuple[str, ...] = ()) -> ClaimType:
    plain = strip_ref_markers(text).strip()
    if not plain:
        return ClaimType.TRANSITION
    if _TRANSITION.search(plain) and len(plain.split()) < 12:
        return ClaimType.TRANSITION
    if _PROCEDURAL.search(plain):
        return ClaimType.PROCEDURAL
    if citation_ids or _LITERATURE.search(plain) or _FACT_SIGNAL.search(plain):
        return ClaimType.LITERATURE_CLAIM
    if _OPINION.search(plain):
        return ClaimType.OPINION
    if _INFERENCE.search(plain):
        return ClaimType.INFERENCE
    if len(plain.split()) >= 4:
        return ClaimType.GENERAL_FACT
    return ClaimType.UNCERTAIN


_ABBREVIATIONS = frozenset({
    "et al", "e.g", "i.e", "cf", "vs", "approx", "etc", "fig", "figs",
    "eq", "eqs", "vol", "vols", "pp", "no", "dr", "mr", "mrs", "ms", "prof",
})


def _ends_with_abbreviation(text: str) -> bool:
    stripped = text.rstrip().rstrip(".").lower()
    words = stripped.split()
    if not words:
        return False
    return words[-1] in _ABBREVIATIONS or " ".join(words[-2:]) in _ABBREVIATIONS


def extract_claims(text: str) -> tuple[Claim, ...]:
    claims: list[Claim] = []
    paragraph = 0
    cursor = 0
    for boundary in list(_SENTENCE_END.finditer(text)) + [None]:
        if boundary and _ends_with_abbreviation(text[cursor : boundary.start()]):
            continue
        end = boundary.start() if boundary else len(text)
        raw = text[cursor:end]
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        start = cursor + leading
        claim_end = cursor + trailing
        if claim_end > start:
            claim_text = text[start:claim_end]
            markers = parse_ref_markers(claim_text)
            ids = tuple(dict.fromkeys(m.citation_id for m in markers if not m.malformed and m.citation_id))
            claims.append(
                Claim(
                    text=claim_text,
                    start=start,
                    end=claim_end,
                    paragraph=paragraph,
                    claim_type=classify_claim(claim_text, ids),
                    citation_ids=ids,
                )
            )
        if boundary:
            paragraph += boundary.group(0).count("\n")
            cursor = boundary.end()
    return tuple(claims)
