from lm_pocket.prompt_bridge import EXPORT_PROMPT, compile_context, parse_import


def test_parses_json_lines_inside_prose_and_fences():
    text = """Sure! Here is what I remember about you:
```json
{"content": "Works as a data engineer", "type": "fact", "confidence": 0.9}
{"content": "Probably prefers mornings", "type": "interpretation", "confidence": 0.4, "tags": ["routine"]}
```
Let me know if you want more."""
    items, skipped = parse_import(text)
    assert [i["type"] for i in items] == ["fact", "interpretation"]
    assert items[1]["tags"] == ["routine"] and skipped == 0


def test_parses_json_array_and_cleans_bad_items():
    text = '[{"content": "A"}, {"content": ""}, {"content": "a"}, {"content": "B", "type": "secret", "confidence": 7}, 3]'
    items, skipped = parse_import(text)
    assert [i["content"] for i in items] == ["A", "B"]
    assert items[1]["type"] == "interpretation"  # unknown type is treated as an inference
    assert items[1]["confidence"] == 1.0 and items[0]["confidence"] == 0.5
    assert skipped == 3


def test_garbage_does_not_crash():
    assert parse_import("{{{ not json [[[") == ([], 0)
    assert parse_import("") == ([], 0)


def mem(i, t="fact"):
    return {"id": f"{i:08d}-x", "content": f"memory number {i} " + "x" * 50, "type": t,
            "source_type": "user", "created_at": "2026-09-01T00:00:00Z"}


def test_context_package_respects_budget_and_marks_inferences():
    mems = [mem(i) for i in range(100)] + [mem(999, "interpretation")]
    pkg = compile_context(mems, scope=["portable_professional"], purpose="demo", max_tokens=200)
    assert len(pkg["text"]) < 200 * 4 + 400
    assert pkg["omitted"] > 0 and "omitted" in pkg["text"]
    assert "do not store" in pkg["text"]
    small = compile_context([mem(1, "interpretation")], scope=["x"], purpose="", max_tokens=800)
    assert "Inferred, not confirmed" in small["text"]


def test_export_prompt_asks_for_json_lines():
    assert "JSON lines" in EXPORT_PROMPT and "interpretation" in EXPORT_PROMPT
