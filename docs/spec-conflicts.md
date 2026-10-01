# Spec conflicts found during implementation

The spec (`SPEC.md`, tag `spec-v0.2-frozen`) is frozen for v0.1. When implementation hits something that forces a change, it is **recorded here with the minimal proposed modification** instead of silently editing the spec. Each entry stays `proposed` until the maintainer accepts or rejects it; accepted entries are then merged into the spec in a dedicated commit.

| # | Status | Spec section | Conflict | Minimal proposed change |
|---|---|---|---|---|
| 1 | proposed | § 12 MCP tools | Tool names `pocket.search_memories` contain dots. Several clients (and the Claude API) only accept `[a-zA-Z0-9_-]` in tool names. | Drop the prefix: `search_memories`, `get_context`, … The MCP server name (`lm-pocket`) already namespaces them. **Implemented this way.** |
| 2 | proposed | § 3 item 7, § 11 | "Local MCP server (stdio **and localhost HTTP**)". An unauthenticated MCP endpoint on localhost is reachable by any local process and, with DNS rebinding, by web pages. Doing it safely needs the same auth work as the remote bridge. | v0.1 ships **stdio only**. Localhost HTTP MCP moves to v0.2 together with the bridge and its token/OAuth. Clients that need HTTP (some Open WebUI setups) use the prompt bridge until then. |
| 3 | proposed | § 6 "keys wiped from memory" | Python cannot guarantee zeroing memory; references are dropped and the SQLCipher connection (with `cipher_memory_security = ON`) is closed. | Reword to "keys are dropped from the app's memory (best effort; the runtime cannot guarantee zeroing)". Add to the threat model. |
| 4 | proposed | § 18 audit | Attempts made **while the pocket is locked** cannot be written to the audit log: the log lives inside the encrypted database. | State it: "events are recorded while the pocket is unlocked; MCP attempts against a locked pocket are rejected but not audited in v0.1". |

## Clarifications (no spec change needed)

- **Process model.** The spec does not say who owns the unlocked pocket. Implementation: `lm-pocket open` is the single owner (UI + internal API on 127.0.0.1). Each MCP client launches `lm-pocket mcp --profile X`, a stdio proxy that holds no keys and forwards every call to the owner with a bearer token from `~/.lm-pocket/runtime.json` (0600). Locking, profile enforcement and audit happen in one place, and closing the app cuts every MCP client off.
- **Full open-format export/import (§ 3 item 10, FR-13, FR-14)** is in the spec but outside the first demo the maintainer asked for. Not dropped: it is the next item after the demo (ROADMAP).
- **Supply chain.** SQLCipher comes from `sqlcipher3-wheels`, a community project that builds wheels for macOS, Windows and Linux (the official `sqlcipher3-binary` only ships Linux x86-64). It is a single-maintainer dependency; worth watching, and a candidate for vendoring or an alternative (SQLite3 Multiple Ciphers via `apsw-sqlite3mc`) if it stalls.
- **UI has no JavaScript.** The spec suggested HTMX; plain HTML forms were enough and avoid vendoring a library to stay offline. CSP is `default-src 'none'`.
