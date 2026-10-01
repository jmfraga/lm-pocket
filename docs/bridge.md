# Remote bridge (ChatGPT and other remote-only MCP clients)

> **Optional, off by default, planned for v0.2.** Read the [threat model](threat-model.md) first. A bridge puts your pocket on the internet; it breaks "works offline" on purpose.

Some clients — ChatGPT in particular — only accept MCP servers reachable over public HTTPS. The bridge is LM-Pocket's local MCP server in streamable-HTTP mode, published through a tunnel, with stricter rules than a local connection.

```text
ChatGPT ──HTTPS──▶ tunnel edge (Cloudflare) ──▶ cloudflared on your machine ──▶ lm-pocket bridge (localhost) ──▶ pocket
```

## Hard rules for any bridge

1. **One profile, never `personal`.** The bridge refuses to start with a profile that can read `personal` or any `sensitive`/`confidential` memory.
2. **Read + propose only.** Same tool set as local MCP; nothing durable.
3. **Time-boxed.** `--ttl` is mandatory (default 2 h). When it expires the bridge stops and the tunnel has nothing behind it.
4. **Authenticated.** See the options below. An open URL is not acceptable.
5. **Rate-limited and audited.** Every request is logged with the profile and the remote client.
6. **Kill switch.** Locking the pocket or closing the app ends the bridge immediately.

## Option A — Cloudflare quick tunnel (testing)

```bash
lm-pocket bridge --profile work --ttl 2h --port 7421   # prints a one-time token
cloudflared tunnel --url http://localhost:7421         # prints https://<random>.trycloudflare.com
```

Add `https://<random>.trycloudflare.com/mcp` as a connector in ChatGPT. The URL changes every run, which is good for testing and bad for daily use.

## Option B — Named Cloudflare tunnel (daily use)

A named tunnel on your own domain (`pocket.example.com`) with a stable hostname. Configure it with `cloudflared tunnel create`, a DNS route, and an ingress rule pointing to `http://localhost:7421`. Add Cloudflare WAF rules (rate limiting; optionally restrict to the client's published egress IP ranges).

Alternatives with the same shape: Tailscale Funnel, ngrok.

## Authentication options

Which one works depends on what the remote client supports at the moment — **verify before relying on it**.

| Option | Strength | Notes |
|---|---|---|
| OAuth 2.1 (MCP authorization spec) | Best | The bridge acts as its own authorization server; you approve the client once on localhost. Planned. |
| Bearer token in header | Good | Only for clients that let you set custom headers. |
| Unguessable path token (`/mcp/<token>`) | Weak, last resort | Treat the URL as a password; combine with short TTL and IP restrictions. |

## What you are trusting when you enable a bridge

The tunnel provider (TLS termination), your token handling, the remote client and its provider (who receives whatever it reads). Keep the profile narrow and the TTL short.
