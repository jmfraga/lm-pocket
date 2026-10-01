# Roadmap

Rule: **do not add components until the current milestone works end to end.**

## v0.0 — Specification (now)
- [x] SPEC v0.2 draft, threat model, MCP contract, bridge design
- [x] Export format v0.1 + JSON Schemas + fictional sample
- [ ] Community review of the spec (open issues, argue, decide)

## v0.1 — Local MVP (spec frozen at tag `spec-v0.2-frozen`)

First goal: **prove the basic hypothesis on a USB/SSD**, not finish LM-Pocket.
1. Data folder: create, unlock (Argon2id → KEK → DEK), lock, recovery key
2. SQLCipher storage + FTS5 search (English and Spanish, accent-insensitive)
3. Spaces + permission profiles enforced on every read
4. MCP server (stdio + localhost HTTP): read + propose tools
5. Localhost UI: memories, proposals (batch review), spaces, audit
6. Prompt bridge: export prompt, tolerant import parser, context packages
7. Full export/import with counts + checksums
8. The first demo from SPEC § 23 working, recorded and in the README
9. Offline install from a wheelhouse on the USB, documented and tested (docs/offline.md)

## v0.1.x — Right after the demo
- Derivation UI with declassification review (SPEC § 10)

## v0.2 — Reach
- Remote bridge (streamable HTTP + tunnel), TTL, rate limit, OAuth 2.1
- API adapter for OpenAI-compatible endpoints (local models without a chat UI)
- Opt-in auto-rules, candidate expiry, duplicate detection

## Integrity and tamper evidence (planned, not v0.1)
- Hash-chained audit log (each event commits to the previous one)
- Authenticated checkpoints of the audit log (HMAC keyed from the DEK, or device-key signature) stored outside the DB
- `manifest.authentication`: HMAC or signature over export manifests
- Rollback detection (monotonic counter / last-seen checkpoint)

## Later
Self-contained runtime on the USB (standalone Python per OS) · signed binaries · optional vector retrieval behind the same MCP contract · per-space keys · hardware keys (FIDO2) · untrusted-host mode · optional encrypted sync
