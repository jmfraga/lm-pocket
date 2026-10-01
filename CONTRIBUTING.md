# Contributing

Welcome, fellow obsessive. LM-Pocket is at the specification stage, which means the most valuable contributions right now are **arguments, not code**.

## Right now
- **Challenge the spec.** Open an issue: what is wrong, missing, over-built, or naive? Point to the section (`SPEC § 11`).
- **Client reality checks.** Does a given client (ChatGPT, Gemini, LM Studio, Open WebUI, …) support what `docs/mcp.md` says? Corrections with a date are gold.
- **Threat model.** Attacks we have not listed.
- **The format.** Would you be able to write an independent reader from `docs/memory-format.md` alone? If not, what is missing?

## Ground rules
- The ten principles in the README are the constitution. A proposal that breaks one needs to say so explicitly and argue why.
- Sample data is always fictional. Never commit real memories, real names or real conversations.
- English is the canonical language; Spanish translations live in `docs/es/`. Discussion in either language is welcome.
- Small PRs. One topic per PR.

## When code starts
Python, `uv`, `pytest`, tests first for anything that touches access control or crypto. Details will land here with the first commit of code.

By contributing you agree that code is licensed Apache-2.0 and documentation/spec CC-BY-4.0.
