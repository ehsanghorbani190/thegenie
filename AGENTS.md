# Academic Evidence Rules

These instructions govern academic research and writing in this project.

## Core standard

- Treat TheGenie as a local evidence-retrieval system, not as an authority or writer model.
- Use the `thegenie_search_references` and `thegenie_get_reference` MCP tools for local literature evidence, and `thegenie_list_documents` only to see what sources are indexed (filenames, IDs, chunk counts — no document text). The installed tool prefix may differ if the MCP server is configured under another name; use the actual registered names.
- Never claim that TheGenie, retrieval, citation validation, NLI, or any language model makes hallucinations impossible.
- Distinguish clearly among source evidence, general knowledge, inference, interpretation, recommendation, and uncertainty.
- For serious academic work, require human review of the original source and surrounding page context before final submission.

## Required evidence workflow

1. Break the task into subsections and atomic, checkable claims before drafting.
2. Identify which claims require literature evidence: quotations, numerical or dated statements, attributed findings, methodological statements, comparisons, causal claims, and claims about prior research normally require support.
3. Search separately for each claim or tightly related claim group. Use a specific query expressing the proposition, population, context, and relevant variables rather than a broad topic alone.
4. Inspect every returned passage. A relevance estimate is only a ranking signal; it is not evidence that the passage entails the claim.
5. Resolve promising citation IDs with `thegenie_get_reference` when exact provenance, wording, page, or metadata matters.
6. Prefer the strongest available primary source. Use systematic reviews or other secondary sources for synthesis, not as a substitute for an available primary source when making a specific empirical claim.
7. Seek independent sources for important, disputed, causal, safety-relevant, or high-impact claims. Do not treat multiple passages from one document as independent corroboration.
8. Draft only what the inspected passages support. Preserve qualifiers, population, jurisdiction, time period, uncertainty, direction, and effect strength.
9. Place the exact internal marker `[[REF:CITATION_ID]]` next to the claim it supports. Do not place one marker at the end of a paragraph containing several unrelated claims.
10. State the cited sentence as the bare claim, not wrapped in reporting phrases such as "X et al. found that," "According to X," "Research shows that," or "In this study,". The `[[REF:CITATION_ID]]` marker already carries attribution; state the finding directly and let the marker do the attribution's job. If naming the source in prose matters for the argument, do it in a separate sentence or clause that does not itself carry the marker. See `.claude/skills/bare-claim-citations/SKILL.md` for the measured reason this matters and worked examples in English and Persian.
11. Before finalization, ask the user or human operator to run `thegenie citations`, `thegenie verify --strict`, and, when failures exist, `thegenie revise`. OpenCode accesses MCP tools only; it does not run these CLI commands through TheGenie.
12. Review the verification report and original PDF. Correct unsupported wording rather than optimizing prose merely to satisfy the verifier.

## Source and citation integrity

- Use only citation IDs returned by TheGenie. Never invent, reconstruct, shorten, or alter an ID.
- Never invent a title, author, year, DOI, journal, page number, quotation, statistic, sample size, method, or finding.
- If metadata is absent, say it is unavailable or identify the source by its known filename/path and citation ID. Do not infer bibliography fields from conventions or memory.
- Quote exact source wording and preserve meaningful punctuation. Clearly mark paraphrases as paraphrases. Only place quotation marks around the source's own original wording — if writing in a different language than the source, state the content as a paraphrase without quotation marks rather than quoting a translation, since structural verification checks quotations against the literal source text and cannot recognize a faithful translation as a match.
- Do not cite a passage merely because it shares keywords with the claim.
- Do not use a citation supporting association to claim causation.
- Do not remove source modal language such as “may,” “suggests,” or “is associated with.”
- Do not turn a factor into the primary, sole, universal, or necessary cause unless the evidence states that scope.
- Preserve numbers, units, denominators, dates, confidence intervals, statistical direction, and population boundaries exactly.
- Check negation and contrast carefully, especially in multilingual passages.
- A structurally valid citation proves only that the indexed passage and source can be resolved; it does not prove that the claim is supported or true.
- If the source changed, is missing, has an invalid page, or has a chunk mismatch, do not use the citation until a human resolves and reindexes the source.

## Retrieval discipline and token use

- Retrieve evidence per subsection or claim, not the entire library at once.
- Start with the default result count. Increase `top_k` only when the first search is insufficient or source diversity is needed.
- Avoid repeating an identical search when its results remain available in the current context.
- Reuse an already inspected passage only for claims it actually supports.
- Refine weak queries rather than accumulating many marginal passages.
- Use `document_filter` only when there is a justified reason to constrain the search; otherwise permit independent sources to surface.
- Keep full PDFs out of model context unless the user explicitly needs broader page review. TheGenie’s token benefit comes from sending only query-specific passages.

## Writing and uncertainty

- Keep claims no broader than the evidence.
- Label synthesis and inference explicitly; cite the premises and explain the inferential step.
- Separate recommendations or opinions from empirical findings.
- When evidence conflicts, report the disagreement and relevant differences rather than selecting one result without explanation.
- When retrieval finds no adequate support, say so. Narrow, qualify, remove, or flag the claim for further research; do not fill the gap from plausible-sounding memory.
- General knowledge may be used for orientation, but do not present it as locally retrieved evidence. Retrieve support when the statement is material to the academic argument.
- Treat `SUPPORTED`, confidence labels, and NLI scores as fallible evidence assessments, not truth guarantees.
- Treat `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `UNVERIFIABLE`, and `QUOTE_MISMATCH` as review signals requiring inspection of the claim and source.

## Draft and finalization rules

- Retain `[[REF:...]]` markers throughout drafting and revision so structural and semantic checks remain possible.
- Do not silently replace a failed citation with an alternative search result. Present the alternative and re-evaluate the wording against it.
- Do not silently edit quotations, numbers, or attributions to make verification pass.
- The revision plan is advisory. Apply changes only after inspecting the cited evidence and preserving the author’s intended meaning where support exists.
- Do not report verification as completed unless the human operator actually ran it and provided or confirmed the result.
- Do not claim automated tests or benchmark acceptance: Phase 1 uses manual smoke checks; Phase 2 testing and benchmark work are deferred.
- A final academic deliverable should state unresolved evidence gaps and limitations when they remain.

## OpenCode integration boundary

OpenCode starts one long-running stdio process:

```text
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

Through that process, OpenCode may invoke only the read-only MCP tools `search_references`, `get_reference`, and `list_documents`. Other `thegenie` commands—ingestion, pruning, direct search/reference inspection, citation listing, verification, revision planning, health, and model download—are operator workflows, not MCP tools. When evidence use is questioned, inspect OpenCode’s visible tool trace and identify the actual MCP tool invocation rather than asserting that retrieval occurred.
