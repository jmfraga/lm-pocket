# LM-Pocket — MVP Specification

**Version:** 0.2
**Status:** **conceptually frozen for the v0.1 implementation** (2026-10-01, git tag `spec-v0.2-frozen`). Changes discovered during implementation are recorded in [docs/spec-conflicts.md](docs/spec-conflicts.md) with a proposed minimal modification — never applied silently.
**Goal:** a personal, portable, local-first, model-agnostic longitudinal memory, owned by the user, carried in a folder (USB/SSD/laptop) and reachable through MCP or manual prompt bridges.

> Changes from v0.1 (the original brainstorm) are listed in [§ 24](#24-changes-from-v01).

---

## 1. Design principle

> **Your AI memory must belong to you, not to the model provider.**

LM-Pocket is not an assistant and not a model. It is a **personal continuity layer** that keeps context, memory, preferences, learnings and provenance over time, independent of the LLM, app, company or device in use.

The user must be able to:

- Physically own the canonical copy of their memory.
- Use it without a mandatory subscription.
- Connect it to different LLMs.
- Decide which spaces each environment can read.
- Import memories from other models.
- Export context to models that cannot integrate directly.
- Audit every access and modification.
- Keep personal, work and shareable contexts separate.

## 2. Architecture

```text
              ┌──────────────────────────┐
              │        LM-POCKET         │
              │  folder on USB / SSD /   │
              │  laptop, encrypted by    │
              │  the app (not the disk)  │
              │                          │
              │  memories · provenance   │
              │  spaces · policies       │
              │  audit                   │
              └────────────┬─────────────┘
                           │
                  LM-Pocket Local (app)
          localhost UI · MCP server · import/export
                           │
       ┌───────────────────┼─────────────────────┐
       │                   │                     │
  Local MCP (stdio)   Optional bridge       Prompt bridge
  Claude, Cursor,     (HTTPS tunnel)        (copy / paste)
  Gemini CLI,         ChatGPT, other        Gemini app,
  local models        remote MCP clients    any closed chat
```

Conceptual separation:

- **LM-Pocket data folder** — the longitudinal memory and its governance.
- **LM-Pocket Local** — the app: UI, security, import/export, MCP server.
- **MCP** — an access channel, not the memory.
- **LLM** — a temporary processor.
- **USB/SSD** — physical storage under the user's control (optional; any folder works).

## 3. MVP scope

The MVP must run entirely locally with no external services.

### In scope (v0.1)

1. App-level encrypted data folder (see § 4).
2. Passphrase unlock.
3. SQLite storage with full-text search (FTS5).
4. Spaces (namespaces).
5. Memories with provenance.
6. Proposal → review → durable flow, with batch review and simple rules.
7. Local MCP server (stdio and localhost HTTP).
8. Web UI on `localhost`.
9. Prompt bridge: import (paste a model's export) and context packages (copy into a model).
10. Full export/import in the open format.
11. Audit log.
12. Permission profiles per MCP connection.

### Out of scope for v0.1

Vector DB, graph DB, cloud sync, fine-tuning, bundled local models, multi-user, mobile app, proprietary hardware, secure element, inference on the USB, signed installers, the remote bridge (documented, built in v0.2), cryptographic signatures / tamper-evident audit (see § 18–19, roadmap).

### Non-goals (not v0.1, not later)

LM-Pocket demonstrates **sovereign, portable, governed longitudinal memory of the user**. It does **not** model an artificial agent: no self-model, no intentions, no artificial identity. Those belong to a separate research layer that may *consume* LM-Pocket through its MCP contract and export format. Keeping them out is what keeps LM-Pocket small, auditable and model-agnostic.

## 4. Storage and encryption

**Decision:** encryption happens **in the app**, not at the volume level. Volume encryption (APFS, BitLocker, LUKS, VeraCrypt) does not work across macOS, Windows and Linux without extra drivers. With app-level encryption the USB is just a folder formatted exFAT and the same pocket opens on any OS.

### Data folder

```text
LM-Pocket/
├── README.txt            # plain text: what this is, how to open it, how to recover
├── pocket.json           # non-secret metadata: format version, KDF params, salt
├── pocket.db             # SQLCipher database (encrypted at rest)
├── keys/
│   └── dek.wrapped       # data encryption key, wrapped by the KEK
├── exports/              # explicit exports only (encrypted unless the user opts out)
├── backups/
└── logs/                 # audit log lives inside pocket.db; this is app diagnostics only
```

### Key hierarchy

```text
passphrase
   ↓  Argon2id (parameters stored in pocket.json)
Key Encryption Key (KEK)
   ↓  unwraps
Data Encryption Key (DEK)
   ↓
SQLCipher database
```

- The passphrase is never the key. Changing it re-wraps the DEK; data is not re-encrypted.
- A **recovery key** (printed / written once at setup) can also unwrap the DEK.
- Mature, audited libraries only (SQLCipher, libsodium / `cryptography`). No home-made crypto.

Future: FIDO2, Secure Enclave / TPM, per-space keys, auto-lock, attempt limits, duress passphrase.

## 5. Distribution

Two different promises, kept separate:

- **The data is portable everywhere.** The pocket folder is plain files on exFAT; any machine that can run LM-Pocket can open it.
- **The app is not yet "plug anywhere offline".** v0.1 needs a runtime on the host.

| Situation | What v0.1 needs on the host |
|---|---|
| Online machine | `uv` installed → `uvx lm-pocket …` (downloads Python + dependencies on first run) |
| Offline machine, prepared | Python 3.11–3.14 **or** `uv` with a cached Python, **plus** the wheelhouse for that OS/CPU/Python carried on the USB (`app/wheelhouse/`) — see [docs/offline.md](docs/offline.md) |
| Offline machine with nothing installed | **Not supported in v0.1.** Requires bundling a standalone Python per OS (roadmap). |

Signed binaries (macOS, Windows, AppImage) and a self-contained runtime on the USB come later; they are expensive to maintain and are not needed to validate the idea.

## 6. Main flow

```text
Plug in USB  →  run LM-Pocket Local  →  enter passphrase  →  pocket unlocked
     →  choose permission profile  →  MCP available  →  connect authorized LLM
Lock / unplug  →  keys wiped from memory  →  MCP returns "pocket locked"
```

### UI screens (localhost)

Home · Unlock/Lock · Memories · Proposals (review) · Spaces · Import · Export · Connections & profiles · Audit · Backup/Restore.

## 7. Memory model

A memory is not just text.

```yaml
id: uuid (v7, time-ordered)
content: string
type: fact | preference | event | interpretation | skill | decision | relationship | goal
created_at: timestamp (UTC, ISO 8601)
updated_at: timestamp
status: candidate | durable | archived | rejected
space: personal | portable_professional | work:<id> | shared | public
sensitivity: normal | sensitive | confidential
portable: boolean
source_type: user | llm | imported | derived
provenance:
  provider: optional        # e.g. anthropic, openai, google, local
  model: optional
  client: optional          # e.g. claude-desktop, chatgpt, lm-studio
  method: mcp | prompt_bridge | manual | derivation
  conversation_ref: optional
  external_ref: optional
  recorded_at: timestamp
confidence: float (0–1)     # how sure the proposer was; user-stated facts default to 1.0
derived_from: [memory_ids]
declassified_at: optional    # set only by a declassification review (§ 10)
supersedes: [memory_ids]
tags: [string]
```

**Removed from v0.1:** the `visibility` field. It overlapped with `space` + `portable`; access is decided by space and permission profile only. One mechanism, not two.

Full schema: [schemas/memory.schema.json](schemas/memory.schema.json).

## 8. Proposals (candidate memories)

No LLM can write directly to canonical memory.

```text
LLM → propose_memory() → candidate → dedup / provenance / policy → review → durable
```

Why: hallucinations, unverified inferences, cross-contamination between spaces, abusive writes, duplicates, over-interpretation.

### Review must not be a chore

If reviewing is tedious, users stop reviewing and the gate becomes theater. The MVP includes:

- **Batch review** — approve/reject/edit many at once, grouped by conversation.
- **Duplicate detection** — a proposal that matches an existing durable memory is shown as "already known" or as an update (`supersedes`).
- **Simple auto-rules**, user-defined and off by default, e.g. *"auto-approve `preference` proposals from profile `work` into `portable_professional` with confidence ≥ 0.9"*. Every auto-approval is logged and reversible.
- **Expiry** — unreviewed candidates expire after N days (configurable) instead of piling up.

## 9. Spaces

Strong separation between contexts:

```text
personal
portable_professional
work:company_a
work:company_b
shared
public
```

> **Default rule:** no space can read another space without explicit authorization.

A work environment may read `portable_professional`, but never `personal` or `work:previous_company`.

## 10. Portable experience

Distinguish proprietary data from portable learning.

- Proprietary: *"Client X has this confidential strategy."*
- Portable: *"In ambiguous projects, validating small hypotheses before scaling works for me."*

The system lets the user save **derived abstractions** without carrying the original data.

**`derived` never implies `portable`.** An abstraction can still leak institutional data even without the original text: a client's name, a codename, a figure, a date, a market, or simply a lesson so specific that it identifies its source. Portability is granted only by an explicit declassification review:

```text
source memory (work:company_a)
   ↓  user or LLM drafts an abstraction
derived candidate   source_type: derived, portable: false, status: candidate
   ↓  declassification review (side by side with the source)
portable memory     portable: true, declassified_at: <timestamp>
```

The declassification review shows the source next to the abstraction and asks the user to confirm, item by item, that the abstraction contains no names of people, clients or projects, no figures, dates or places that point back to the source, and nothing they would not say in a job interview with a competitor. Rejected → the candidate stays non-portable or is discarded.

```yaml
derived_from: [<memory in work:company_a>]
content: "Validating small hypotheses before scaling reduces rework."
space: portable_professional
source_type: derived
portable: true
declassified_at: 2026-10-01T18:30:00Z   # required whenever source_type is derived and portable is true
```

The derived memory keeps a link to its source, but **exporting the derived memory never exports the source**.

*v0.1 note:* the data model and rule ship in v0.1; the derivation UI ships right after the first demo (ROADMAP).

## 11. Permission profiles

A local stdio MCP server cannot reliably know *which* client launched it. So identity is not verified at the protocol level; instead **each MCP connection is configured with a named profile**, and each profile is a separate entry in the client's MCP config:

```yaml
# profile: work
allow:
  - read:portable_professional
  - propose:memory
propose_into: portable_professional
deny:
  - read:personal
  - read:work:*
```

```jsonc
// Claude Desktop config: two entries, two profiles
{
  "mcpServers": {
    "pocket-personal": { "command": "uvx", "args": ["lm-pocket", "mcp", "--profile", "personal"] },
    "pocket-work":     { "command": "uvx", "args": ["lm-pocket", "mcp", "--profile", "work"] }
  }
}
```

Scopes: `read:<space>`, `propose:memory`, `export:context`, `import:memory`, `audit:read`.
Never exposed via MCP: writing durable memories, deleting, changing policies. Those happen only in the local UI.

Remote (bridge) connections additionally require a bearer token or OAuth bound to a profile — see [docs/bridge.md](docs/bridge.md).

## 12. MCP

MCP is the door, not the house.

### Minimal tools

```text
pocket.search_memories     # text + metadata filters, within allowed spaces
pocket.get_memory
pocket.get_context         # compiled context package for a topic/purpose
pocket.get_recent_context
pocket.get_profile         # what this connection is allowed to do
pocket.list_spaces         # only spaces visible to this profile
pocket.propose_memory      # always lands as candidate
pocket.get_policies        # read-only
```

### Retrieval → context compiler

```text
request → profile check → retrieval (FTS5 + metadata) → context compiler → minimal context to the LLM
```

**Never send the whole corpus to the LLM.** The compiler enforces a token budget and returns provenance with each item so the model can say where a fact came from.

Client setup: [docs/mcp.md](docs/mcp.md).

## 13. Connection levels

| Level | Path | Clients (as of writing — verify) |
|---|---|---|
| 1 — Local MCP | stdio or `localhost` HTTP | Claude Desktop, Claude Code, Cursor, Gemini CLI, LM Studio, Open WebUI and other local-model clients |
| 2 — Remote MCP bridge (optional) | HTTPS tunnel → local MCP | ChatGPT (remote MCP connectors), any client that only accepts remote MCP |
| 3 — API adapter (later) | adapter → provider API | scripted use, local models via OpenAI-compatible APIs |
| 4 — Prompt bridge | copy / paste | Gemini app, any closed chat |

Level 2 is **off by default** and conflicts with "works offline" by definition, so it is an explicit opt-in with its own threat model.

## 14. Prompt bridge

### Import (model → pocket)

1. LM-Pocket generates an **export prompt** asking the model to list what it knows/remembers about the user in a structured format (JSON lines matching the proposal schema).
2. The user pastes it into the model and copies the answer back into `http://localhost:<port>/import`.
3. LM-Pocket parses, classifies, shows a preview, records provenance (`method: prompt_bridge`, provider, model), lets the user edit, and saves everything **as candidates**.

Parsing must be tolerant: models wrap JSON in prose and code fences.

### Context package (pocket → model)

When a model cannot use MCP, LM-Pocket compiles a portable block:

```text
CONTEXT PACKAGE — from a user-owned LM-Pocket
Scope: portable_professional
Purpose: session context
Persistence requested: none — do not store this in your own memory

Relevant preferences: …
Relevant history: …
Current projects: …
Important constraints: …
```

The user copies it into the model. The package is generated per purpose and space, never "everything".

## 15. Security principles

Local-first · encryption at rest · least privilege · zero trust between spaces · no plaintext secrets · access logs · fast lock · explicit exports · the user keeps the keys.

What LM-Pocket **cannot** protect against is just as important — see [docs/threat-model.md](docs/threat-model.md). In short: anything already sent to a cloud LLM is outside the pocket's control, and an unlocked pocket on a compromised machine is exposed.

## 16. Untrusted machines (future)

Minimize writes to the host disk, keep sensitive material in RAM, clear caches on close, never copy the canonical memory to the host, temporary sessions.

## 17. Provenance

Every memory must answer: **where did this come from?** Inferences (`interpretation`, `source_type: llm|derived`) are always distinguishable from facts the user stated (`source_type: user`).

## 18. Audit log

Log events, not sensitive content:

```text
pocket unlocked · MCP client connected (profile: work) · space portable_professional read
12 memories retrieved · proposal received · candidate approved (auto-rule #2)
context package generated · pocket locked
```

The audit log is **application append-only**: LM-Pocket's code only ever inserts events and exposes no way to edit or delete them. It is **not immutable** — anyone holding the key can modify the database directly, and v0.1 cannot detect that. It is included in full exports.

Future (roadmap): a **hash chain** over events (each event commits to the previous one) plus **authenticated checkpoints** (HMAC with a key derived from the DEK, or a signature with a device key) stored outside the database, so that edits, deletions or truncation of the log become detectable.

## 19. Export format

```text
lm-pocket-export/
├── manifest.json        # format version, created_at, counts, checksums
├── memories.jsonl       # one memory per line
├── spaces.json
├── policies.json        # profiles and auto-rules
└── audit.jsonl
```

`provenance` lives inside each memory (no separate `provenance.jsonl`: one source of truth).

**Integrity is not authenticity.** The manifest includes record counts and SHA-256 checksums. They detect **accidental corruption and incomplete exports** (a truncated copy, a file missing from the folder). They do **not** detect malicious modification: whoever edits a file can recompute its checksum and the manifest. Protection against deliberate tampering requires an authenticated mechanism — an HMAC keyed from the pocket's key, or a digital signature over the manifest — which is on the roadmap, not in v0.1. An *encrypted* export is protected by its AEAD encryption, which does detect modification of the ciphertext.

Exports are encrypted by default (age / passphrase); a plaintext export is an explicit, logged choice.

Spec: [docs/memory-format.md](docs/memory-format.md). Schemas: [schemas/](schemas/). Nothing may prevent other software from implementing this format.

## 20. Functional requirements (v0.1)

- **FR-01** Open a valid LM-Pocket data folder from any path.
- **FR-02** Require the passphrase before accessing private content.
- **FR-03** Show available spaces.
- **FR-04** Search memories by text and metadata.
- **FR-05** Expose search via MCP, filtered by profile.
- **FR-06** Accept memory proposals via MCP.
- **FR-07** Proposals always land as `candidate`.
- **FR-08** Approve / reject / edit candidates, individually and in batch.
- **FR-09** Import pasted text from a model (prompt bridge).
- **FR-10** Generate export prompts for closed LLMs.
- **FR-11** Generate context packages for copy/paste.
- **FR-12** Log accesses in the audit log.
- **FR-13** Backup and restore.
- **FR-14** Export all data in the open format, with counts and checksums.
- **FR-15** Work without internet.
- **FR-16** Locking (or unplugging) makes every MCP call return "locked".

## 21. Non-functional requirements

- **Simplicity** — running in minutes with one command on a machine with `uv`.
- **Compatibility** — macOS, Windows, Linux; the same data folder opens on all three (the app runtime requirements are in § 5).
- **Evolvability** — moving from SQLite to Postgres/vector/graph must not change the MCP contract or the export format.
- **Performance** — never send the whole corpus to the LLM.
- **Security** — encryption at rest is mandatory.
- **Portability** — no proprietary identifiers.
- **Recovery** — backup/restore and lost-passphrase recovery documented.
- **Language** — full-text search must work in at least English and Spanish (accent-insensitive).

## 22. Suggested stack (not mandatory)

- Backend: Python + FastAPI
- DB: SQLite via SQLCipher, FTS5
- UI: FastAPI + Jinja/HTMX (no build step)
- MCP: official MCP Python SDK
- Crypto: `argon2-cffi`, `cryptography` / libsodium, SQLCipher
- Packaging: `uv` / `uvx`

## 23. First demo

1. Plug in USB.
2. `uvx lm-pocket --data /Volumes/USB/LM-Pocket`, enter passphrase.
3. See 10 example memories (fictional).
4. Connect Claude Desktop (or Cursor, Gemini CLI, LM Studio) with profile `work`.
5. Ask something that depends on memory; get an answer using pocket context, with provenance.
6. Show that a `personal` memory is **not** reachable from profile `work`.
7. The model proposes a new memory → it appears as a candidate.
8. Approve it from localhost.
9. Unplug the USB.
10. Repeat the question: the MCP answers "pocket locked".

Extra demo (prompt bridge): generate export prompt → paste into a closed chat → paste the answer back → review candidates → approve → generate a context package → paste it into a different provider.

## 24. Changes from v0.1

| v0.1 | v0.2 | Why |
|---|---|---|
| Encrypted volume on the USB | App-level encryption (SQLCipher), USB is a plain exFAT folder | Volume encryption is not portable across OSes. |
| "MCP validates identity" | Named permission profiles per MCP entry; tokens only for remote bridge | stdio MCP cannot verify which client launched it. |
| ChatGPT via MCP | ChatGPT via optional remote bridge or prompt bridge | ChatGPT only accepts remote HTTPS MCP. |
| Gemini, local models not covered | Gemini CLI and local-model clients via local MCP; Gemini app via prompt bridge | Model-agnostic means all of them. |
| Signed installers in MVP | `uvx` one-liner; signed binaries later | Signing for three OSes is months of work. |
| Plain review queue | Batch review, dedup, opt-in auto-rules, expiry | Tedious review becomes no review. |
| `visibility` + `space` | `space` + `portable` only | Two overlapping access mechanisms invite bugs. |
| `provenance.jsonl` separate | Provenance inside each memory; manifest with counts + checksums | One source of truth; detect incomplete exports. |
| — | Threat model document | Sent-to-cloud data and compromised hosts must be stated plainly. |
| "Checksums protect the export" | Checksums = integrity/completeness; HMAC/signatures = tamper evidence (roadmap) | A checksum can be recomputed by whoever edits the file. |
| Audit log implied immutable | Application append-only; hash chain + authenticated checkpoints on the roadmap | Honest about what v0.1 can detect. |
| "Runs offline anywhere" | Data portable everywhere; app needs a runtime (§ 5, docs/offline.md) | No bundled Python yet. |
| Derived memories portable by default | `derived` ≠ `portable`; explicit declassification review | Abstractions can leak institutional data. |
| — | Non-goals: no self-model, intentions or artificial identity | LM-Pocket is the user's memory, not an agent. |

## 25. MVP hypothesis

> A personal longitudinal memory can live physically under the user's control and provide useful continuity across different LLMs without depending on a specific provider or a permanent subscription.

The MVP demonstrates **sovereignty + continuity + interoperability + provenance + context control**. Nothing more.

## 26. Next step

Build v0.1 with only:

```text
encrypted data folder + SQLite/FTS5 + FastAPI + localhost UI
+ MCP read/propose + candidates + spaces + profiles + provenance + audit
+ prompt import/export
```

Do not add components until this flow works end to end.

---

*Guiding phrases:* **Your AI memory, physically yours.** · **Your model can change. Your history doesn't have to.** · **LM-Pocket is not the model. It is the continuity layer.**
