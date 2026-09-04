# Connecting an agent to TheGenie

TheGenie exposes evidence retrieval to any MCP-capable coding agent through one
read-only stdio server: `thegenie mcp`. It provides exactly three tools:

- `search_references(query, top_k=5, document_filter=None)`
- `get_reference(citation_id)`
- `list_documents()` — filenames, document IDs, chunk counts, and index
  timestamps for what's currently ingested; no document text.

No agent runs `thegenie ingest`, `search`, `verify`, `revise`, `health`, or
`models download` through MCP. Those remain human-operated CLI commands (see
the main `README.md`). The agent only ever talks to the tools above.

## Before configuring any agent

1. Finish the main [README.md](../../README.md) setup through step 6
   (`uv run thegenie ingest ./documents`).
2. Confirm `uv run thegenie health` reports `"status": "ok"`.
3. Confirm `uv run thegenie search "some known phrase"` returns a real result.

If those three don't work yet, fix them first — no agent configuration will
make a broken local index work.

## Guides

- [OpenCode](opencode.md) — the primary integration this project was built
  for, using OpenCode's `opencode.json` local MCP server config.
- [Claude Code](claude-code.md) — `claude mcp add` and project-scoped
  `.mcp.json`.
- [Any other MCP client](other-mcp-clients.md) — the generic `mcpServers`
  stdio JSON shape used by Claude Desktop, Cursor, Windsurf, Zed, and most
  other MCP-compatible tools, plus how to carry over the evidence-discipline
  instructions from `AGENTS.md` to an agent that doesn't read that file
  automatically.

## Shared building block: the launch command

Every client, regardless of its config format, ultimately runs the same
long-running stdio process:

```bash
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

Replace `/ABSOLUTE/PATH/TO/thegenie` with the real absolute path to this
repository (`pwd` while standing in it). Running this command directly in a
terminal will appear to hang waiting for input — that's correct; it's a
stdio server and the agent owns its stdin/stdout, not you.

## Verifying any integration, once configured

Regardless of which agent you configured, verification looks the same:

1. Restart the agent (or reload its MCP servers) so it picks up the new config.
2. List its MCP servers/tools and confirm three tools are registered, typically
   named with the server name as a prefix, e.g. `thegenie_search_references`,
   `thegenie_get_reference`, and `thegenie_list_documents` (exact
   prefix/formatting varies by client).
3. Give the agent an explicit prompt that names the tool, for example:

   ```text
   Use the thegenie search tool to find local evidence about <a topic you
   know is in your ingested PDFs>. Show the exact returned citation marker and
   passage, then resolve that citation ID with the get_reference tool before
   stating anything as fact.
   ```

4. Inspect the agent's visible tool-call/activity trace — don't infer
   successful retrieval just because the answer sounds sourced. You should
   see the actual tool invocation, its arguments, and a result containing a
   real citation ID, page number, and exact passage from your PDFs.

## Carrying over the evidence-discipline instructions

`AGENTS.md` in the repository root encodes the required evidence workflow:
searching per claim, inspecting passages before citing, never inventing
metadata, preserving `[[REF:CITATION_ID]]` markers, and running
`thegenie citations` / `thegenie verify --strict` before finalizing. OpenCode
and Claude Code both read `AGENTS.md` from the project directory
automatically. If your agent doesn't support a project instructions file,
paste `AGENTS.md`'s contents into its system prompt or project rules —
without it, the agent has the tools but not the discipline for using them
responsibly.

## The `bare-claim-citations` skill

This repository ships a **Skill** (a self-contained `SKILL.md` — name +
description always visible to the agent, full instructions loaded on demand)
that guards one specific, measured failure mode: the local NLI verifier
reads a citation phrased as reported speech — "X et al. found that Y",
"According to X, Y", "In this study, Y" — as an unverifiable claim about a
*different* document, and its entailment score for an otherwise fully
supported claim collapses accordingly (confirmed directly against the
model: ~0.99 entailment drops to ~0.01–0.07 once wrapped in an attribution
clause, in English and Persian alike). TheGenie's own verifier now strips
this framing before scoring as a runtime safety net, but it's better for
the agent to never write citations that way in the first place — that's
what this skill teaches, with English and Persian good/bad examples.

Both Claude Code and OpenCode support the same `SKILL.md` format and the
same trigger mechanism (a skill's `name`/`description` are always visible;
the agent loads the full file only when it looks relevant), so one file
works unmodified for both, with no OpenCode-specific rewrite needed. It's
checked into this repository at:

- `.claude/skills/bare-claim-citations/SKILL.md`

OpenCode's own skill discovery explicitly includes `.claude/skills/` as one
of its project-level lookup paths (alongside `.opencode/skills/` and
`.agents/skills/`), so this single copy is picked up by both agents without
duplication.

**Working directly in this repository:** nothing to install — both agents
pick it up automatically from the path above.

**Using it in a different project** (the far more common case — you're
usually drafting the actual paper somewhere else, with TheGenie wired in as
an MCP server): copy the `bare-claim-citations/` folder into that project,
or install it globally so every project sees it. OpenCode will find it
either under a copied `.claude/skills/` or its own `.opencode/skills/` — use
whichever matches the target project's existing convention:

```bash
# Per-project (place in the project you're drafting in)
cp -r /ABSOLUTE/PATH/TO/thegenie/.claude/skills/bare-claim-citations \
  /path/to/your-paper-project/.opencode/skills/          # OpenCode
cp -r /ABSOLUTE/PATH/TO/thegenie/.claude/skills/bare-claim-citations \
  /path/to/your-paper-project/.claude/skills/             # Claude Code

# Global (every project, on this machine)
mkdir -p ~/.config/opencode/skills ~/.claude/skills
cp -r /ABSOLUTE/PATH/TO/thegenie/.claude/skills/bare-claim-citations ~/.config/opencode/skills/
cp -r /ABSOLUTE/PATH/TO/thegenie/.claude/skills/bare-claim-citations ~/.claude/skills/
```

No restart is required beyond starting a new session in that project — skill
directories are scanned at session start. Verify it's registered by asking
the agent directly (e.g. "what skills do you have available?") or checking
its debug/skill-listing command if the client provides one.

If your agent doesn't support the `SKILL.md` format at all, paste the file's
contents into its system prompt, project rules, or `AGENTS.md`/`CLAUDE.md`
instead — it's plain Markdown with no TheGenie-specific tooling dependency.
