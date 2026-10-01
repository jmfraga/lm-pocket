# MCP: tools, profiles and client setup

> LM-Pocket's MCP server does not exist yet. This document is the contract it will implement. Client config details reflect the state of each client at the time of writing — **they change often, please send corrections**.

## Tools

| Tool | Scope needed | Returns |
|---|---|---|
| `pocket.get_profile` | — | Name, allowed spaces and scopes of this connection |
| `pocket.list_spaces` | — | Only the spaces this profile can read |
| `pocket.search_memories` | `read:<space>` | Matching durable memories, with provenance |
| `pocket.get_memory` | `read:<space>` | One memory by id |
| `pocket.get_context` | `read:<space>` | A compiled, token-budgeted context package for a topic |
| `pocket.get_recent_context` | `read:<space>` | Recent durable memories |
| `pocket.get_policies` | — | Read-only view of this profile's rules |
| `pocket.propose_memory` | `propose:memory` | Creates a **candidate** in the profile's `propose_into` space |

Never exposed: durable writes, deletes, policy changes. When the pocket is locked, every tool returns a `pocket_locked` error.

## Profiles

One MCP config entry = one profile. The client never chooses its own permissions; the entry does.

```bash
lm-pocket mcp --profile work            # stdio
lm-pocket mcp --profile work --http 7421   # streamable HTTP on localhost only
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
