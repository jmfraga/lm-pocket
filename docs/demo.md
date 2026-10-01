# First demo — does the hypothesis hold on a USB?

> *A personal longitudinal memory can live physically under the user's control and provide useful continuity across different LLMs without depending on a specific provider.* (SPEC § 25)

This page shows the v0.1 demo with **real output** from 2026-10-01 on macOS (Apple Silicon). All memories are fictional (a persona called Ana).

Three ways to reproduce it:

| What | Command | Proves |
|---|---|---|
| Automated, every platform | `uv run pytest tests/test_e2e.py` | Real CLI + real daemon + real MCP stdio client, in CI on macOS, Linux and Windows |
| Real mounted volume (macOS) | `uv run python scripts/demo_usb_macos.py` | Same flow on an exFAT disk image, **force-ejected** mid-session |
| With your own LLM | Quick start in the README | A model actually using the pocket |

## 1–2. Plug in a USB, create the pocket

```text
1. Plug in a USB stick (64 MB exFAT disk image)
   mounted at /Volumes/LMPOCKET
2. Create the pocket with fictional sample memories
   Loaded 10 fictional sample memories.
   Pocket created at /Volumes/LMPOCKET/LM-Pocket
   files on the USB: ['README.txt', 'backups', 'exports', 'keys', 'logs', 'pocket.db', 'pocket.json']
   pocket.db is 65536 bytes; plaintext 'Valparaíso' on disk: False
```

The database is SQLCipher; the key is a random DEK wrapped by an Argon2id-derived KEK and, separately, by a recovery key shown once.

## 3–4. Locked until the passphrase is entered

```text
3. Open LM-Pocket Local (locked until the passphrase is entered)
   MCP before unlocking -> error=True: ... pocket_locked: LM-Pocket is locked
4. Unlock with the passphrase in the localhost UI
   unlocked: True
```

## 5–6. Read over MCP, limited by profile

```text
5. Claude (profile 'work') reads memory over MCP
   [portable_professional] Likes code examples in Python first, then a short explanation.  (imported via prompt_bridge)
6. Profile 'work' cannot reach personal memories
   explicit personal search -> error=True: ... denied: profile 'work' cannot read space 'personal'
   'Valparaíso' (personal) in work context package: False
   same search with profile 'personal' -> Ana lives in Valparaíso and works remotely as a data engineer.
```

## 7–8. Propose → approve

```text
7. The model proposes a new memory -> candidate
   {'status': 'candidate', 'id': '01a0f942-…', 'space': 'portable_professional', 'note': 'Saved as a candidate. ...'}
   readable before approval: False
8. Approve it from localhost
   Approved 1, rejected 0
   readable after approval: Prefers async code reviews over meetings
```

## 9. Prompt bridge (models without MCP)

```text
   1 items found
   CONTEXT PACKAGE — from a user-owned LM-Pocket
   Scope: portable_professional
   Purpose: new job
   Persistence requested: none — do not store this in your own memory.

   Relevant preferences:
   - Prefers async code reviews over meetings  [llm, 2026-10-01, id 01a0f943-…]
   - Likes code examples in Python first, then a short explanation.  [imported, 2026-09-03, id 0192f0a0-…]
   - Prefers written proposals over meetings for decisions that need more than one person.  [user, 2026-09-02, id …]

   Relevant history:
   - Writes tests before refactoring  [imported, 2026-10-01, id 01a0f943-…]
   - Can lead a batch-to-orchestrator migration: ...  [derived, 2026-09-06, id …]
```

The import went: export prompt → closed model → paste the answer (prose and code fences tolerated) → preview → proposals → approve.

## 10–11. Yank the USB out

```text
10. Yank the USB out (force eject while the pocket is open)
   MCP after unplugging -> error=True: ... pocket_locked: LM-Pocket is locked: data folder disappeared (USB unplugged?)
11. Same question again: the memory is no longer available
   error=True: ... pocket_locked: ...
```

## With a real model: Claude Code + Claude Haiku

Pocket opened with the sample, MCP entry with profile `work`, Claude Code restricted to the pocket's tools. Prompt (English, the model answered in Spanish):

> (1) How do I prefer to receive code examples, and where does each fact come from? (2) Where do I live? If you cannot see it, say so. (3) I just told you: I prefer short daily written updates over status meetings. Propose that as a memory.

Answer, verbatim:

```text
(1) Preferencias de código:
- Preferencia: Python primero, luego explicación breve (confianza: 0.8)
- Fuente: Importado desde ChatGPT/OpenAI el 2026-09-03

(2) Ubicación:
No encontré información sobre dónde vives en tu memoria accesible.

(3) Propuesta guardada:
✓ "Prefers short daily written updates over status meetings" — está como candidato en tu memoria.
```

Audit log afterwards (events, never content):

```text
8 | proposal_received  | work | claude-code/2.1.285 | {'memory_id': '01a0f948-…', 'space': 'portable_professional'}
7 | profile_read       | work | claude-code/2.1.285 | {}
6 | memories_retrieved | work | claude-code/2.1.285 | {'tool': 'search_memories', 'count': 0, 'spaces': [], 'query_chars': 19}
5 | memories_retrieved | work | claude-code/2.1.285 | {'tool': 'search_memories', 'count': 1, 'spaces': ['portable_professional'], 'query_chars': 24}
4 | pocket_unlocked    |      |                     | {'via': 'passphrase'}
```

The model cited provenance, could not see the personal space (Ana's city exists in the pocket, just not for this profile), and its write landed as a candidate waiting for review.

## What this demo does **not** prove

- Security against a determined attacker: no independent review yet ([threat model](threat-model.md)).
- Windows and Linux on a physical USB: CI runs the flow there, but the unplug simulation and SIGTERM checks are skipped on Windows.
- Continuity *across providers* with real usage over weeks — that needs people using it. That is the next experiment.
