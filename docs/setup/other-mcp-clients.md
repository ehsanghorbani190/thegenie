# Any other MCP-compatible agent

TheGenie's MCP server is a standard stdio server built on the official MCP
Python SDK (`mcp.server.fastmcp`). It requires no client-specific behavior,
so any MCP client that supports local stdio servers can use it — Claude
Desktop, Cursor, Windsurf, Zed, Continue, and most other MCP-compatible
tools, in addition to the two covered in dedicated guides
([OpenCode](opencode.md), [Claude Code](claude-code.md)).

## The command every client needs

```bash
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

Get the absolute path with `pwd` while standing in this repository, and
substitute it for every `/ABSOLUTE/PATH/TO/thegenie` placeholder below.

## The de facto standard config shape

Most desktop MCP clients (Claude Desktop, Cursor, Windsurf, and others) use
the same `mcpServers` JSON object, split into `command` and `args` rather
than one combined array:

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

Where this file lives is client-specific:

- **Claude Desktop**: `claude_desktop_config.json`, found via the app's
  Settings → Developer → Edit Config, or directly at
  `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
  or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).
- **Cursor**: `.cursor/mcp.json` in the project, or the global
  `~/.cursor/mcp.json`.
- **Windsurf**: `~/.codeium/windsurf/mcp_config.json`.
- **Zed**: `settings.json`, under a `context_servers` key with a slightly
  different shape (`command`/`args` nested under `command`) — check Zed's
  current MCP docs if the shape below doesn't validate.
- **Others**: check the client's own MCP documentation for the exact file
  path; the `mcpServers` → `command`/`args` shape above is the most common
  starting point.

If the config already has other servers, merge the `academic-rag` entry into
the existing `mcpServers` object rather than replacing the file.

## If your client wants one combined command array instead

A few clients (OpenCode among them) expect `command` as a single array
instead of separate `command`/`args`:

```json
{
  "academic-rag": {
    "command": [
      "uv",
      "run",
      "--directory",
      "/ABSOLUTE/PATH/TO/thegenie",
      "thegenie",
      "mcp"
    ]
  }
}
```

Check whichever client-specific fields it additionally requires (a `type`
discriminator, `enabled`, `timeout`, etc.) in that client's own MCP
documentation.

## After configuring: verify, don't assume

1. Restart the client (or reload its MCP servers) so it picks up the change.
2. List its configured/connected MCP servers and confirm three tools are
   registered: `search_references`, `get_reference`, and `list_documents`
   (possibly prefixed with the server name, e.g.
   `academic-rag_search_references`, depending on the client).
3. Prompt it explicitly, naming the tool:

   ```text
   Use the academic-rag search tool to find local evidence about <a topic you
   know is in your ingested PDFs>. Show the exact returned citation marker
   and passage, then resolve that citation ID with the get_reference tool
   before stating anything as fact.
   ```

4. Inspect the client's tool-call/activity log or trace. Confirm the actual
   invocation, its arguments, and that the result contains a real citation
   ID, page number, and exact passage from your ingested PDFs — a
   sourced-sounding answer alone is not proof the tool ran.

## What the agent can and cannot do through this server

Regardless of client, only three read-only tools are exposed:

- `search_references(query, top_k=5, document_filter=None)`
- `get_reference(citation_id)`
- `list_documents()` — filenames, document IDs, chunk counts, and index
  timestamps for what's currently ingested; no document text.

No agent can ingest documents, run verification, check health, or download
models through MCP — those are commands you run yourself:
`thegenie ingest`, `thegenie verify`, `thegenie revise`, `thegenie citations`,
`thegenie health`, `thegenie models download`. If an agent's response implies
it "re-indexed" or "checked health," it did not — it has no tool to do that.

## Carrying over the evidence-discipline instructions

This repository's `AGENTS.md` documents the required evidence workflow:
search per claim (not one broad topic search), inspect every returned
passage before citing it, resolve citation IDs with `get_reference` when
exact wording/page/metadata matters, never invent a title/author/year/DOI/
page/quote/statistic, preserve `[[REF:CITATION_ID]]` markers through
drafting, and run `thegenie citations` / `thegenie verify --strict` /
`thegenie revise` (as a human, outside the agent) before finalizing.

If your client supports a project-level instructions file (`AGENTS.md`,
`CLAUDE.md`, `.cursorrules`, custom system prompt, etc.), copy or adapt this
repository's `AGENTS.md` content into it. Without those instructions, the
agent has the retrieval tools but nothing enforcing careful use of them.

## Troubleshooting

### Server won't start / client reports a connection failure

Run the exact command manually in a terminal:

```bash
uv run --directory /ABSOLUTE/PATH/TO/thegenie thegenie mcp
```

It should hang waiting for stdio input (Ctrl+C to exit) — that's the correct
behavior for a stdio server run outside a client. If it errors instead, the
client will fail identically; fix the underlying error first (missing
dependencies, bad path, etc.) — see the main `README.md` Troubleshooting
section.

### Server connects, but tool calls fail, time out, or return nothing

That's a TheGenie-side problem, not a client config problem. Verify directly:

```bash
uv run thegenie health
uv run thegenie search "..."
```

If those fail or return nothing, fix ingestion/health first (see the main
`README.md`), then retry through the client. If calls are slow, increase
whatever timeout setting the client exposes — first-call latency includes
loading the embedding and reranker models into memory.

### Tool names don't match what's documented here

Some clients prefix or transform tool names (adding the server name, changing
casing, etc.). Trust the exact name shown in that client's own tool
list/trace, not the bare names in this document.
