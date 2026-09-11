---
name: genie-retrieval-economy
description: Use whenever calling TheGenie's MCP tools (search_references, get_reference) during academic drafting under the AGENTS.md evidence workflow — any session that decomposes claims and retrieves citations from the local corpus. Controls the token/cost overhead of the search-per-claim workflow without weakening citation integrity: right-sized top_k, claim grouping, avoiding redundant get_reference calls, passage reuse, and stable MCP session state. Apply proactively on every thegenie-backed writing session, not just when the user raises cost — this is a silent efficiency guard, the cost-side counterpart to bare-claim-citations' verification guard.
---

# Genie retrieval economy

## Why this exists

Measured directly on this project's own corpus (5-paragraph human-agent-trust paper,
51-PDF corpus): a session using TheGenie's MCP tools ended at 97K tokens of final
context and $0.87 spent, over 171 conversation turns. A same-task session without
TheGenie ended *smaller* (72K tokens) but cost *more* ($1.12), over 91 turns. TheGenie
won on cost but lost on final context size and roughly doubled the turn count.

The gap traces to two mechanical facts, not a flaw in the retrieval idea:

1. `search_references` defaults to `top_k=5`, and each returned chunk can run up to
   the corpus's configured `chunk_size` (512 tokens here) — so one call can return
   up to ~2,500 tokens of passage text before any of it has actually been read or
   used.
2. The AGENTS.md workflow calls for a separate search per atomic claim. A
   5-paragraph paper with ~15-20 citations means 15-20+ round trips, and every round
   trip re-pays that turn's fixed system + tool-definition overhead on top of its
   own payload.

None of this is a bug — it is the search → inspect → cite discipline working as
designed. It is, however, controllable without touching that discipline.

## Rules

1. **Right-size `top_k` per call.** Pass `top_k=2` or `3` for a claim with an
   obvious, well-scoped proposition. Reserve the `top_k=5` default (or higher) for
   genuinely ambiguous claims, contested definitions, or when triangulating
   independent sources for a disputed/causal/high-impact claim (AGENTS.md rule 7).
   Don't request more candidates than you actually intend to inspect.

2. **Group tightly-related claims into one query.** AGENTS.md rule 3 already
   permits searching for "a claim or tightly related claim group" — use that
   latitude. If two adjacent sentences make closely related sub-points that
   plausibly share a source, search once with a query covering both before
   splitting into separate searches.

3. **Don't re-fetch text you already have.** `search_references`'s `text` field
   already *is* the exact stored passage — the same text `get_reference` would
   return for that same chunk. Call `get_reference` once per unique `citation_id`,
   and only for what the search result didn't give you (complete author/DOI/year
   metadata for the bibliography, or resolving genuine ambiguity about provenance)
   — not to re-confirm a quote that is already sitting in context.

4. **Reuse before you re-search.** Before firing a new `search_references` call,
   check whether a passage already retrieved earlier in this session already
   supports the new claim. This is already an AGENTS.md retrieval-discipline rule —
   treat it as binding, not optional. Re-searching for something already in context
   wastes both the call and its result tokens.

5. **Keep TheGenie's MCP connection state fixed for the whole session.** Don't
   enable/disable it mid-session. Toggling the tool list changes the tool-schema
   fingerprint sent to the model provider, which can invalidate prompt caching on
   the system+tools prefix and force a full-price recompute on the next turn.

6. **Narrow with `document_filter` once you know where to look.** If earlier
   searches establish that a subsection's claims cluster in a handful of specific
   papers, pass `document_filter` on subsequent searches in that subsection instead
   of re-searching the whole corpus every time.

7. **Don't run unrelated MCP servers during a heavy-retrieval session.**
   Tool-definition tokens are a fixed cost paid on *every single turn*, and in
   measurement they were dominated by whichever tools happen to be registered, not
   necessarily TheGenie's own three (`search_references`, `get_reference`,
   `list_documents`). Disable MCP servers not needed for this task before a long
   drafting session — this lever is usually bigger than anything TheGenie itself
   controls, and matches the README's own "avoid enabling unrelated MCP servers
   unnecessarily" guidance.

## What NOT to trade away for savings

- Don't skip inspecting a returned passage's exact text, or skip a genuinely needed
  `get_reference` call, to save a round trip if wording, page, or provenance
  actually needs verifying before citing (AGENTS.md rules 4-5). This skill targets
  *redundant* calls, not verification itself.
- Don't merge unrelated claims into one query just to save a round trip if their
  evidence might come from different sources — grouping (rule 2) is for claims
  likely to share support, not a blanket batching mandate.
- Don't drop independent-source triangulation (AGENTS.md rule 7) for
  disputed/causal/high-impact claims to save tokens — that verification cost is the
  product this project sells, not overhead to be optimized away.
