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

**Write the cited sentence as the bare proposition. Do not wrap it in a reporting
clause.** Put the marker directly on the plain claim.

| Don't | Do |
|---|---|
| Tutul et al. found that trust in AI increases over time `[[REF:abc123]]`. | Trust in AI increases over time `[[REF:abc123]]`. |
| According to Tutul et al. (2024), trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| In this study, trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| Research shows that trust increases over time `[[REF:abc123]]`. | Trust increases over time `[[REF:abc123]]`. |
| طبق گزارش توتول و همکاران، اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. | اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. |
| در این پژوهش، اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. | اعتماد به هوش مصنوعی افزایش می‌یابد `[[REF:abc123]]`. |

Patterns to avoid immediately before a cited claim (non-exhaustive — the underlying
issue is any reporting/reported-speech frame, not this exact word list):

- "X et al. found / showed / reported / argued / demonstrated / concluded / noted /
  observed / stated / claimed / suggested / indicated that ..."
- "According to X, ..." / "According to X (YEAR), ..."
- "In this/that/the study/paper/research/article/work, ..."
- "This/that/the study/paper found/showed/reported that ..."
- Persian: "طبق گزارش X،" / "به گفته X،" / "در این پژوهش،" / "X نشان داد که"

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
