# Roadmap

Rule: **do not add components until the current milestone works end to end.**

## v0.0 — Specification (now)
- [x] SPEC v0.2 draft, threat model, MCP contract, bridge design
- [x] Export format v0.1 + JSON Schemas + fictional sample
- [ ] Community review of the spec (open issues, argue, decide)

## v0.1 — Local MVP (spec frozen at tag `spec-v0.2-frozen`)

First goal: **prove the basic hypothesis on a USB/SSD**, not finish LM-Pocket.
- [x] Data folder: create, unlock (Argon2id → KEK → DEK), lock, recovery key
- [x] SQLCipher storage + FTS5 search (English and Spanish, accent-insensitive)
- [x] Spaces + permission profiles enforced on every read
- [x] MCP server, stdio: read + propose tools (localhost HTTP → v0.2, spec-conflicts #2)
- [x] Localhost UI: memories, proposals (batch review), spaces, profiles, audit
- [x] Prompt bridge: export prompt, tolerant import parser, context packages
- [ ] Full open-format export/import with counts + checksums — **next**
- [x] The first demo from SPEC § 23 working ([docs/demo.md](docs/demo.md)), tested in CI and on a real exFAT volume
- [x] Offline install from a wheelhouse on the USB, documented and verified on macOS arm64 (`scripts/verify-offline-install.sh`)
- [ ] Decide the proposed changes in [docs/spec-conflicts.md](docs/spec-conflicts.md)
- [ ] Independent security review before anyone stores real secrets

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
