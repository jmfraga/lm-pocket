"""Prompt bridge (SPEC § 14) and context compiler (SPEC § 12).

- export_prompt(): text the user pastes into a closed LLM so it lists what it
  knows about them as JSON lines.
- parse_import(): tolerant parser for whatever the model answers.
- compile_context(): the minimal, budgeted context package. Used both by the
  MCP tool get_context and by the UI's copy/paste export.
"""

from __future__ import annotations

import json
import re

from .store import MEMORY_TYPES

EXPORT_PROMPT = """\
I keep my long-term memory in a user-owned store called LM-Pocket. Please export
what you know or remember about me so I can review it there.

Rules:
- Output ONLY JSON lines: one JSON object per line, no prose, no numbering.
- Each object: {"content": "...", "type": "...", "confidence": 0.0-1.0, "tags": ["..."]}
- "type" is one of: fact, preference, event, interpretation, skill, decision, relationship, goal.
- Use "interpretation" for anything you inferred rather than something I told you,
  and give it a lower confidence.
- One idea per object, written as a short standalone sentence about me.
- Do not include passwords, keys, account numbers or health identifiers.
- Write each sentence in the language I usually use with you.
"""

MAX_CONTENT = 2000

_FENCE = re.compile(r"```[a-zA-Z]*")


def parse_import(text: str) -> tuple[list[dict], int]:
    """Return (items, skipped). Accepts JSON lines, a JSON array, code fences and stray prose."""
    cleaned = _FENCE.sub("\n", text or "")
    decoder = json.JSONDecoder()
    found: list = []
    i = 0
    while i < len(cleaned):
        ch = cleaned[i]
        if ch in "[{":
            try:
                obj, end = decoder.raw_decode(cleaned, i)
            except json.JSONDecodeError:
                i += 1
                continue
            found.extend(obj if isinstance(obj, list) else [obj])
            i = end
        else:
            i += 1

    items, skipped, seen = [], 0, set()
    for obj in found:
        if not isinstance(obj, dict):
            skipped += 1
            continue
        content = str(obj.get("content", "")).strip()
        if not content or len(content) > MAX_CONTENT:
            skipped += 1
            continue
        key = " ".join(content.lower().split())
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        mtype = obj.get("type")
        if mtype not in MEMORY_TYPES:
            mtype = "interpretation"  # unknown type: treat as an inference, not a fact
        try:
            conf = float(obj.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        tags = obj.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        items.append({
            "content": content,
            "type": mtype,
            "confidence": min(1.0, max(0.0, conf)),
            "tags": [str(t)[:40] for t in tags][:10],
        })
    return items, skipped


SECTIONS = [
    ("Relevant preferences", ("preference",)),
    ("Relevant history", ("fact", "event", "relationship", "skill")),
    ("Current projects and goals", ("goal", "decision")),
    ("Inferred, not confirmed by the user", ("interpretation",)),
]


def _line(m: dict) -> str:
    date = m.get("created_at", "")[:10]
    # Full id: the first characters of a UUIDv7 are a timestamp, so a prefix is not unique,
    # and the model needs the whole id to call get_memory.
    return f"- {m['content']}  [{m['source_type']}, {date}, id {m['id']}]"


def compile_context(memories: list[dict], *, scope: list[str], purpose: str, max_tokens: int = 800) -> dict:
    """Build a context package within a rough token budget (~4 chars per token)."""
    budget = max(200, int(max_tokens)) * 4
    header = (
        "CONTEXT PACKAGE — from a user-owned LM-Pocket\n"
        f"Scope: {', '.join(scope) if scope else '(nothing readable)'}\n"
        f"Purpose: {purpose or 'session context'}\n"
        "Persistence requested: none — do not store this in your own memory."
    )
    out, used, included, omitted = [header], len(header), [], 0
    for title, types in SECTIONS:
        group = [m for m in memories if m["type"] in types]
        if not group:
            continue
        block = [f"\n{title}:"]
        for m in group:
            line = _line(m)
            if used + len(line) + len(block[0]) > budget:
                omitted += 1
                continue
            block.append(line)
            used += len(line) + 1
            included.append(m["id"])
        if len(block) > 1:
            out.append("\n".join(block))
            used += len(block[0])
    if omitted:
        out.append(f"\n({omitted} more relevant memories omitted to stay within the budget.)")
    if not included:
        out.append("\n(No relevant memories in the allowed scope.)")
    return {"text": "\n".join(out) + "\n", "memory_ids": included, "omitted": omitted}
