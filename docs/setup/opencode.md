# OpenCode integration

Verified against installed OpenCode `1.18.25` and the official
[MCP server documentation](https://opencode.ai/docs/mcp-servers/) and
[configuration documentation](https://opencode.ai/docs/config/). A local MCP
server uses `type: "local"` and an argv-array `command`.

## 1. Confirm your OpenCode version

```bash
opencode --version
```

The config shape below is for the local-server format current as of
`1.18.25`. If your installed version differs meaningfully, check
`opencode.ai/docs/mcp-servers/` for the current schema before pasting this in.

## 2. Get the absolute path to this repository

```bash
cd /path/to/thegenie && pwd
```

Copy that output — you'll substitute it for every
`/ABSOLUTE/PATH/TO/thegenie` placeholder below.

## 3. Add the server to `opencode.json`

Create or merge this into `opencode.json` in the project directory where you
run OpenCode (this can be a *different* project than TheGenie itself — that's
the point, OpenCode is writing/researching elsewhere and calling out to this
server for evidence):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "academic-rag": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--directory",
        "/ABSOLUTE/PATH/TO/thegenie",
        "thegenie",
        "mcp"
      ],
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

If `opencode.json` already has other `mcp` entries or top-level keys, merge
this `academic-rag` entry into the existing `mcp` object rather than
replacing the file.

Notes on the fields:

- `"academic-rag"` is the server name; OpenCode prefixes tool names with it
  (`academic-rag_search_references`, `academic-rag_get_reference`). You can
  rename it, but then use the actual resulting tool names everywhere else,
  including in `AGENTS.md` if you customize it.
- `timeout: 30000` (ms) covers first-call latency while models load into
  memory on first use after the server starts. Increase it if your machine is
  slow to load `BAAI/bge-m3` and the reranker.

## 4. Restart OpenCode and verify registration

```bash
opencode mcp list
```

`academic-rag` should show as connected. If not, see Troubleshooting below.

## 5. Confirm tool discovery and a real invocation

Ask OpenCode, in a prompt that names the tool explicitly:

```text
Use academic-rag_search_references to find local evidence about <a topic you
know is in your ingested PDFs>. Show the exact returned citation marker and
passage. Then use academic-rag_get_reference on that citation ID before
making any claim.
```

Expand OpenCode's tool-call/activity trace. You should see
`academic-rag_search_references` invoked with your query, followed by
`academic-rag_get_reference` when exact provenance is requested. The result
must contain a real local citation ID, page number, and exact passage — don't
accept a sourced-sounding answer as proof the tool actually ran.

## What OpenCode actually runs

OpenCode starts exactly one long-running process, `thegenie mcp`, and only
ever calls `search_references` and `get_reference` through it. It does **not**
run `thegenie ingest`, `search`, `reference`, `verify`, `revise`, `citations`,
`health`, or `models download` — those remain commands you run yourself in a
terminal.

## Project instructions (`AGENTS.md`)

OpenCode reads `AGENTS.md` from the project root automatically. This
repository's `AGENTS.md` documents the required evidence workflow (search per
claim, inspect before citing, never invent metadata, preserve
`[[REF:...]]` markers, run `thegenie verify --strict` before finalizing). If
OpenCode is writing in a *different* project than this repository, copy (or
adapt) `AGENTS.md` into that project's own `AGENTS.md` so the same discipline
applies there — the MCP tools alone don't enforce it.

## Troubleshooting

### Server doesn't appear / shows disconnected in `opencode mcp list`

Run the exact command from the config manually and confirm it doesn't error
immediately:

```bash
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

It should hang waiting for stdio input (Ctrl+C to exit) — that's success. If
it errors instead, fix that first; OpenCode will show the same failure.

### Startup diagnostics

Run OpenCode with logs visible:

```bash
opencode --print-logs --log-level DEBUG
```

Validate the resolved configuration:

```bash
opencode debug config
```

`opencode mcp debug` is aimed primarily at remote/OAuth connections; for this
local stdio server, the process logs and the tool-call trace are the useful
evidence.

### Tool calls happen but return no results / errors

That's a TheGenie-side problem, not an OpenCode config problem. Run
`uv run thegenie health` and `uv run thegenie search "..."` directly — if
those fail or return nothing, fix ingestion/health first (see the main
`README.md`), then retry through OpenCode.
