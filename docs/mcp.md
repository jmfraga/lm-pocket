# MCP: tools, profiles and client setup

> **v0.1 status:** implemented over **stdio** only, with tool names **without** the `pocket.` prefix (`search_memories`, …). Both are proposed spec changes — see [spec-conflicts.md](spec-conflicts.md) #1 and #2. Localhost HTTP MCP comes with the v0.2 bridge. Verified clients: the MCP Python SDK client and Claude Code. Other client configs below reflect each client at the time of writing — **please send corrections**.

The command to put in a client config is shown on the LM-Pocket home page for each profile: `<python> -m lm_pocket mcp --profile <name>`. The proxy holds no keys; it forwards to the running `lm-pocket open`, so the pocket must be open and unlocked.

## Tools

| Tool | Scope needed | Returns |
|---|---|---|
| `get_profile` | — | Name, allowed spaces and scopes of this connection |
| `list_spaces` | — | Only the spaces this profile can read |
| `search_memories` | `read:<space>` | Matching durable memories, with provenance |
| `get_memory` | `read:<space>` | One memory by id |
| `get_context` | `read:<space>` | A compiled, token-budgeted context package for a topic |
| `get_recent_context` | `read:<space>` | Recent durable memories |
| `get_policies` | — | Read-only view of this profile's rules |
| `propose_memory` | `propose:memory` | Creates a **candidate** in the profile's `propose_into` space |

Never exposed: durable writes, deletes, policy changes. When the pocket is locked or its folder disappears, every tool returns a `pocket_locked` error; when the app is closed, `not open`/`not running`.

## Profiles

One MCP config entry = one profile. The client never chooses its own permissions; the entry does.

```bash
lm-pocket mcp --profile work            # stdio (v0.1)
```

## Client setup

### Claude Desktop
`claude_desktop_config.json`:
```json
{ "mcpServers": {
    "pocket-work": { "command": "uvx", "args": ["lm-pocket", "mcp", "--profile", "work"] }
} }
```

### Claude Code
```bash
claude mcp add pocket-work -- uvx lm-pocket mcp --profile work
```

### Cursor
`~/.cursor/mcp.json` — same `mcpServers` shape as Claude Desktop.

### Gemini CLI
`~/.gemini/settings.json` — same `mcpServers` shape (`command` + `args`).

### Local models
The model runtime (Ollama, llama.cpp, MLX, vLLM) does not speak MCP by itself; the **chat client** does.

- **LM Studio** — `mcp.json` with the `mcpServers` shape.
- **Open WebUI** — connect to `lm-pocket mcp --http` (streamable HTTP) or through the `mcpo` proxy.
- **Any OpenAI-compatible endpoint** — the planned API adapter (connection level 3) runs a small tool loop between the endpoint and the pocket, so scripts and agents can use local models with no chat UI at all.

With a local model and a local client, nothing leaves the machine.

### ChatGPT
ChatGPT only connects to **remote** MCP servers over HTTPS. Use the optional bridge: [bridge.md](bridge.md). Otherwise, use the prompt bridge.

### Gemini app and other closed chats
No custom MCP. Use the prompt bridge: context packages in, export prompts out (SPEC § 14).
