---
name: bare-claim-citations
description: Use whenever drafting or editing academic/research prose that cites evidence retrieved from TheGenie's MCP tools (search_references, get_reference) and will carry an internal [[REF:citation-id]] marker. Also use whenever asked to fix a citation that TheGenie's verifier flagged as UNSUPPORTED, UNVERIFIABLE, or PARTIALLY_SUPPORTED — that failure is very often caused by attribution phrasing, not a bad citation. Make sure to apply this any time you write a cited sentence yourself, even if the user didn't ask for phrasing help — this is a silent correctness guard, not an opt-in style preference. Applies in every language the draft is written in, including Persian drafts citing English sources.
---

# Bare-claim citations

## The problem this prevents

TheGenie verifies every `[[REF:citation-id]]` claim with a natural-language-inference
(NLI) model: it checks whether the source passage actually entails the cited
sentence. That model is a literal reader. When a citation is phrased as reported
speech — "**Tutul et al. found that** trust increases over time" — the model reads
this as a claim about what *some paper* says, which it cannot verify from the source
passage alone, rather than reading straight through to the tested proposition ("trust
increases over time"). This has been measured directly: an otherwise perfectly
supported claim's entailment score collapses from ~0.99 to ~0.01–0.07 the moment it's
wrapped in an attribution clause — in English and in Persian alike. The fix isn't to
argue with the model; it's to not write citations that way.

This matters because attribution is redundant here in the first place: the
`[[REF:citation-id]]` marker already *is* the attribution. It resolves (via
`get_reference`) to the exact source, page, and authors. Restating "who said it" in
the same sentence that's being tested adds nothing but risk.

## The rule

**The guaranteed-safe default is to write the cited sentence as the bare
proposition** and put the marker directly on the plain claim, with any named
attribution moved to a separate clause that carries no marker.

| Don't | Do |
|---|---|
| Tutul et al. found that trust in AI increases over time `[[REF:abc123]]`. | Trust in AI increases over time `[[REF:abc123]]`. |
| According to Tutul et al. (2024), trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| In this study, trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| Research shows that trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| طبق گزارش توتول و همکاران، اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. | اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. |
| در این پژوهش، اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. | اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. |

Patterns to avoid immediately before a cited claim when you cannot use the
"safe template" below (non-exhaustive — the underlying issue is any
reporting/reported-speech frame the verifier's stripper doesn't recognize, or
one placed anywhere but the very start of the cited sentence, not this exact
word list):

- "X et al. found / showed / reported / argued / demonstrated / concluded / noted /
  observed / stated / claimed / suggested / indicated that ..."
- "According to X, ..." / "According to X (YEAR), ..."
- "In this/that/the study/paper/research/article/work, ..."
- "This/that/the study/paper found/showed/reported that ..."
- Persian: "طبق گزارش X،" / "به گفته X،" / "در این پژوهش،" / "X نشان داد که"

## If you want "X et al. found that ..." prose on the surface

TheGenie's verifier (`strip_reporting_frame` in
`src/thegenie/verification/checks.py`) already strips a *leading* reporting
clause from the cited sentence before NLI scoring, specifically so ordinary
academic attribution phrasing doesn't collapse an otherwise-supported claim's
score. Confirmed directly against the current implementation:

```
"Tutul et al. found that trust in AI increases over time."
  -> stripped to: "trust in AI increases over time."
"Tutul et al. (2024) found that trust in AI increases over time."
  -> stripped to: "trust in AI increases over time."
```

So writing the reporting clause directly onto the cited sentence is safe —
**but only under a narrow, verified template**:

1. **The reporting clause must be the very first thing in the sentence that
   carries the marker.** The stripper anchors at the start of the text
   (`^\s*`); a trailing or embedded attribution ("Trust increases over time,
   as Tutul et al. report `[[REF:abc123]]`.") is not stripped and has not
   been measured as safe — treat it as the risky, unverified case, not a
   second safe form.
2. **The reporting verb must be on the supported list**: found / shows /
   showed / reports / reported / argues / argued / demonstrates /
   demonstrated / concludes / concluded / notes / noted / observes / observed
   / states / stated / claims / claimed / suggests / suggested / indicates /
   indicated (plus the `"according to X,"` / `"in this study,"` frames, and
   their Persian equivalents in the checker). A reporting verb outside this
   list ("posits," "contends," "documents," "reveals," …) is not stripped and
   falls back to the same collapse risk the "Don't" column above describes.

Safe template: **`<Author(s)> [et al.] [(YEAR)] <supported-verb> that <bare
claim> [[REF:citation-id]].`** — e.g. "Tutul et al. (2024) found that trust
in AI increases over time `[[REF:abc123]]`." is safe today, verified against
the actual stripping regex.

**One more real caveat, not a theoretical one:** a *separate* check
(`attribution_check`) validates a named author against that source's
`authors` metadata from `get_reference` **when metadata is present** — but in
practice, for PDFs whose Info/XMP dictionary doesn't carry populated
title/author fields (common for publisher-distributed academic PDFs;
verified empty across multiple documents in this project's own corpus,
scanned and born-digital alike), `get_reference` returns `authors: []` and
this check silently no-ops ("no author metadata for attribution comparison")
rather than confirming or rejecting the name. A passing verification is
**not** proof the named author is correct in that situation — get it right
from the source passage's own text (author names are usually visible in the
retrieved chunk itself, e.g. "Mayer et al., 1995") rather than trusting the
verifier to catch a wrong name.

Anything that doesn't fit the safe template — an unsupported verb, or
attribution anywhere but the leading clause — falls back to the split-clause
form: state the bare claim with its marker, and put the named attribution in
an adjacent clause or sentence that does not itself carry a citation marker
(see the next section).

## When naming the source in prose actually matters

Sometimes the argument genuinely needs the source named — e.g. contrasting two
researchers' findings ("Smith found X, while Jones found Y"). In that case, split it:
state the bare claim with its marker in one clause or sentence, and put the named
attribution in a separate clause or sentence that does **not** itself carry a
citation marker.

> Trust calibration improves with feedback `[[REF:abc123]]` — a finding consistent
> with Smith's earlier work on human-AI collaboration.

Here the marker sits on the tested proposition; the "Smith" mention is unverified
color commentary, not something the NLI model needs to check.

## If you're fixing a failed verification

If `thegenie verify` reports `UNSUPPORTED`, `UNVERIFIABLE`, or `PARTIALLY_SUPPORTED`
for a claim that looks correct when you read the source passage yourself, check the
phrasing before assuming the citation is wrong or the evidence is insufficient.
Strip any reporting clause from the cited sentence first, re-verify, and only then
treat it as a genuine evidence gap if it still fails.
