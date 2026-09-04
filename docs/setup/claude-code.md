# Claude Code integration

Verified against installed Claude Code `2.1.251`. Claude Code supports MCP
servers via the `claude mcp` CLI or a project-scoped `.mcp.json` file.

## 1. Get the absolute path to this repository

```bash
cd /path/to/thegenie && pwd
```

Substitute that output for every `/ABSOLUTE/PATH/TO/thegenie` placeholder
below.

## 2. Register the server

### Option A — CLI (recommended for a quick, local-only setup)

```bash
claude mcp add academic-rag -- uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

This defaults to `local` scope (visible only to you, in this project). Add
`--scope project` instead if you want it committed to `.mcp.json` and shared
with everyone working in the project:

```bash
claude mcp add academic-rag --scope project -- uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

### Option B — project-scoped `.mcp.json`

Create or merge this into `.mcp.json` at the root of the project where you
run Claude Code (again, this can be a different project than TheGenie
itself):

```json
{
  "mcpServers": {
    "academic-rag": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/ABSOLUTE/PATH/TO/thegenie",
        "thegenie",
        "mcp"
      ]
    }
  }
}
```

If `.mcp.json` already exists with other servers, merge `academic-rag` into
the existing `mcpServers` object.

## 3. Approve and verify

Project-scoped `.mcp.json` servers require one-time approval the first time
Claude Code sees them in a session — it will prompt you. After approving (or
if you used the CLI, which doesn't require approval), verify:

```bash
claude mcp list
claude mcp get academic-rag
```

`academic-rag` should show as connected, exposing `search_references`,
`get_reference`, and `list_documents`.

## 4. Confirm a real invocation

In a Claude Code session, prompt explicitly:

```text
Use the academic-rag search_references tool to find local evidence about
<a topic you know is in your ingested PDFs>. Show the exact returned citation
marker and passage. Then use get_reference on that citation ID before making
any claim.
```

Check the visible tool-call trace for the actual `academic-rag` invocation,
its arguments, and a result containing a real citation ID, page number, and
exact passage — not just a sourced-sounding answer.

## What Claude Code actually runs

Claude Code starts exactly one long-running process, `thegenie mcp`, and only
calls `search_references`, `get_reference`, and `list_documents` through it.
It does **not** run `thegenie ingest`, `search`, `reference`, `verify`,
`revise`, `citations`, `health`, or `models download` — those remain commands
you run yourself in a terminal.

## Project instructions (`AGENTS.md` / `CLAUDE.md`)

Claude Code reads `CLAUDE.md` (and also honors `AGENTS.md` if present) from
the project root automatically. This repository's `AGENTS.md` documents the
required evidence workflow (search per claim, inspect before citing, never
invent metadata, preserve `[[REF:...]]` markers, run
`thegenie verify --strict` before finalizing). If Claude Code is writing in a
*different* project than this repository, copy (or adapt) that content into
that project's own `CLAUDE.md`/`AGENTS.md` — the MCP tools alone don't
enforce the discipline.

## Troubleshooting

### Server fails to connect

Run the exact command manually and confirm it doesn't error immediately:

```bash
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

It should hang waiting for stdio input (Ctrl+C to exit) — that's success.

### Server connects but calls fail or return nothing

That's a TheGenie-side problem. Run `uv run thegenie health` and
`uv run thegenie search "..."` directly — if those fail or return nothing,
fix ingestion/health first (see the main `README.md`), then retry through
Claude Code.

### Removing or resetting

```bash
claude mcp remove academic-rag
claude mcp reset-project-choices   # if you need to re-approve a project .mcp.json entry
```
