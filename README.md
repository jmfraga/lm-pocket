# LM-Pocket — Longitudinal Memory Pocket

**Your AI memory, physically yours.**

[Español](README.es.md)

> Your model can change. Your history doesn't have to.

LM-Pocket is a personal, portable, local-first, model-agnostic memory layer that you own. It lives in a folder — on a USB stick, an external SSD, or your laptop — and keeps your context, preferences, decisions and learnings across time, regardless of which LLM, app, company or device you use.

It is **not** an assistant and **not** a model. It is a **continuity layer**: storage, provenance, governance and access control for your long-term memory, exposed to any LLM through MCP or through copy/paste prompt bridges.

> **Status:** specification stage (v0.2 draft). No code yet. This is the right moment to join and argue about the design.

## Why

Every AI provider is building memory, and every one of them keeps it on their servers, in their format, under their rules. Switch providers and you start from zero. Lose your account and your history goes with it.

LM-Pocket bets on the opposite: **the canonical copy of your memory belongs to you**, in an open format, and the model is a replaceable processor that reads only what you allow.

## What makes it different

Pieces of this exist elsewhere (memory engines, MCP memory servers, portable agent memory formats). What LM-Pocket combines:

- **Physically yours** — the canonical copy is a folder you can unplug.
- **Spaces** — `personal`, `portable_professional`, `work:<id>`… isolated by default. Your employer's LLM never sees your personal life or your previous employer's secrets.
- **Proposal → review → durable** — no LLM ever writes directly to your canonical memory.
- **Provenance on everything** — every memory answers *"where did this come from?"* and inferences are distinguished from facts you stated.
- **Portable experience** — keep the *lesson* ("validate small hypotheses before scaling") without carrying the *proprietary data* it came from.
- **Open export format** — nothing should stop another program from reading your memory.

## How models connect

| Client | Path | Notes |
|---|---|---|
| Claude Desktop / Claude Code / Cursor | Local MCP (stdio) | Native, nothing leaves your machine except what the model reads. |
| Gemini CLI | Local MCP (stdio) | Native MCP support. |
| Local models (LM Studio, Open WebUI, Ollama-based clients) | Local MCP (stdio or HTTP) | Fully offline end to end. |
| ChatGPT | Remote MCP **bridge** (Cloudflare Tunnel or similar) or prompt bridge | ChatGPT only accepts remote HTTPS MCP. Optional, off by default. See [docs/bridge.md](docs/bridge.md). |
| Gemini app and other closed chats | Prompt bridge | Copy a context package in; paste the model's memory export back. |

Client support changes fast — see [docs/mcp.md](docs/mcp.md) for details and please send corrections.

## Documents

- [SPEC.md](SPEC.md) — the MVP specification (v0.2 draft)
- [docs/threat-model.md](docs/threat-model.md) — what LM-Pocket protects against, and what it cannot
- [docs/mcp.md](docs/mcp.md) — MCP tools, permission profiles, client setup
- [docs/bridge.md](docs/bridge.md) — exposing a read-only bridge for ChatGPT and other remote clients
- [docs/memory-format.md](docs/memory-format.md) — the open export format
- [schemas/](schemas/) — JSON Schemas for the format
- [examples/](examples/) — a fictional sample memory export
- [ROADMAP.md](ROADMAP.md) — what gets built, in what order
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to join

Spanish versions live in [docs/es/](docs/es/).

## Principles that must not break

1. The memory belongs to the user.
2. The system works offline.
3. An LLM never writes directly to canonical memory.
4. Spaces are isolated by default.
5. Every memory has provenance.
6. The format is exportable.
7. MCP is an interface, not the memory.
8. The model is replaceable.
9. The user can physically disconnect their memory.
10. The developer disappearing must not destroy the user's history.

## License

- Code: [Apache-2.0](LICENSE)
- Specification, documentation and schemas: [CC-BY-4.0](LICENSE-SPEC)

The business, if there ever is one, can live in hardware, UX, support, enterprise administration, optional sync or managed services. **Never in charging rent to access your own memory.**
