# Threat model

LM-Pocket protects your memory **at rest and at the boundary between spaces**. It cannot protect what has already left the pocket. Saying this plainly is part of the product.

## What LM-Pocket protects against

| Threat | Mitigation |
|---|---|
| Lost or stolen USB/SSD | SQLCipher at rest; Argon2id-derived KEK; no plaintext copy on the device. |
| A work LLM reading personal memories | Spaces isolated by default; profiles enforced server-side on every MCP call. |
| An LLM writing false or inflated memories | Proposals always land as `candidate`; durable writes only from the local UI. |
| Accidental corruption or incomplete exports | Export manifest with record counts and SHA-256 checksums (integrity/completeness, **not** authenticity). |
| Modification of the stored pocket or of an encrypted export | AES-GCM / SQLCipher authentication: tampered ciphertext fails to decrypt. |
| The developer or project disappearing | Open, documented export format; Apache-2.0 code; CC-BY spec. |
| Forgotten passphrase | Recovery key generated once at setup. |

## What LM-Pocket cannot protect against

- **Data already sent to a model.** Whatever a cloud LLM read during a session is now on that provider's side, subject to their retention and training policies. Unplugging the pocket stops *future* reads, not past ones. Use narrow profiles and small context packages.
- **A compromised host.** If the computer where you unlock the pocket has malware, it can read memory in RAM and anything the app displays. Do not unlock your personal space on machines you do not trust.
- **The model ignoring "do not persist".** Context packages ask the model not to store them; the pocket has no way to enforce that.
- **Deliberate edits by someone who has the key, or to a plaintext export.** SHA-256 checksums can be recomputed by whoever edits the files, and the audit log is *application* append-only, not immutable. Tamper evidence (hash-chained audit, HMAC or signed checkpoints and manifests) is on the roadmap, not in v0.1.
- **Rollback.** Replacing the pocket with an older copy of itself is not detected in v0.1.
- **You approving bad proposals.** The review gate is only as good as the review. Auto-rules are off by default for that reason.
- **The remote bridge, if you enable it.** Exposing the pocket to the internet adds the tunnel provider, your token handling and the remote client to the trust boundary. See [bridge.md](bridge.md).

## Assumptions

- The user's passphrase is strong (the setup screen enforces a minimum and shows entropy).
- The OS and Python runtime used to run LM-Pocket are reasonably up to date.
- Cryptography comes from mature libraries; LM-Pocket implements no primitives of its own.

Found a gap? Open an issue with the `security` label, or for anything sensitive see [SECURITY.md](../SECURITY.md).
