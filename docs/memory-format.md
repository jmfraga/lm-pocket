# LM-Pocket open export format — v0.1 (draft)

Licensed CC-BY-4.0. Anyone may implement a reader or writer. The goal: **your memory must be readable without LM-Pocket**.

```text
lm-pocket-export/
├── manifest.json     # schemas/manifest.schema.json
├── memories.jsonl    # one object per line, schemas/memory.schema.json
├── spaces.json       # schemas/spaces.schema.json
├── policies.json     # profiles and auto-rules (free-form in v0.1)
└── audit.jsonl       # one event per line
```

## Rules

- UTF-8, NFC-normalized text. Timestamps in UTC, ISO 8601 (`2026-10-01T18:30:00Z`).
- IDs are UUIDv7 strings. Never reuse an id; updates create a new memory with `supersedes`.
- `manifest.json` lists the record count and SHA-256 of every file. **An importer must verify counts and checksums before reading content** — a file with 70 valid lines out of 100 expected looks perfectly fine otherwise.
- Unknown fields must be preserved on re-export (forward compatibility).
- `format_version` follows semver. Readers must refuse a major version they do not know.
- An encrypted export is the same tree inside an `age`-encrypted tar; the plaintext layout is identical.

See [examples/sample-export/](../examples/sample-export/) — entirely fictional data.
