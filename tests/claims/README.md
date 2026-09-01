# Demo/acceptance claims

Hand-built claim files for manually exercising `thegenie verify`, used for
the showcase demo and for regression-checking the verifier after code
changes. These are not an automated test suite (Phase 2's automated tests
and benchmark are still deferred — see the implementation plan under
`docs/superpowers/specs/`); run them manually with the CLI.

## Prerequisite

These citation IDs only resolve if the same two source PDFs are ingested
(PDFs are gitignored — `documents/*` — so a fresh clone won't have them):

- `10.1080_10447318.2024.2328910_8ppm.pdf` — Tutul, Nirjhar & Chaspari,
  "Investigating Trust in Human-AI Collaboration for a Speech-Based Data
  Analytics Task"
- `10.1177_00187208251398449_7uu5.pdf` — Ebinger, Neuhuber & Kubicek,
  "How Can I Trust You? The Effect of Risk and Automation Failures on Trust
  and Reliance Behavior"

Place both under `documents/` and run `uv run thegenie ingest ./documents`
before using these files. If you ingest different PDFs, these citation IDs
won't resolve — regenerate the files against your own corpus using
`thegenie search` to find a real passage and citation ID first.

## Files and expected results

Run with `uv run thegenie verify tests/claims/<file> --strict`.

| File | Verdict | Exit | What it demonstrates |
|---|---|---|---|
| `paper1-supported.md` | `SUPPORTED` | 0 | A correct paraphrase — exercises the semantic NLI layer directly (no quotation marks to lean on). |
| `paper1-contradicted.md` | `CONTRADICTED` | 1 | Same claim with the finding flipped ("decreases" instead of "increases"). No fabricated quote or number — only catchable if the model actually reasons about the claim. |
| `paper2-supported.md` | `SUPPORTED` | 0 | A correct exact quotation — exercises the deterministic quote-matching layer. |
| `paper2-quote-mismatch.md` | `QUOTE_MISMATCH` | 1 | Same claim with the quoted wording altered ("never recovered" instead of "fully recovered"). Caught by the cheap deterministic check, before the NLI model even runs. |

The two "broken" files are deliberate adversarial fixtures — don't treat a
future passing verdict on `paper1-contradicted.md` or
`paper2-quote-mismatch.md` as good news; it would mean the checks have
regressed to accepting something they should reject.
