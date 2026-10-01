import json
import re

import pytest
from fastapi.testclient import TestClient

from conftest import PASS
from lm_pocket.pocket import PocketFolder
from lm_pocket.service import PocketService
from lm_pocket.web import create_app

API, UI = "api-token-123", "ui-token-456"


@pytest.fixture
def env(tmp_path):
    PocketFolder.create(tmp_path / "p", PASS)
    svc = PocketService(tmp_path / "p", watch_interval=0.05)
    svc.unlock(PASS)
    svc.load_sample()
    svc.lock()
    app = create_app(svc, api_token=API, ui_token=UI, allowed_hosts={"testserver"})
    c = TestClient(app)
    yield svc, c
    svc.lock()


def login(c):
    r = c.get(f"/login?t={UI}", follow_redirects=False)
    assert r.status_code == 303
    assert "samesite=strict" in r.headers["set-cookie"].lower() and "httponly" in r.headers["set-cookie"].lower()


def api(c, tool, profile="work", **args):
    return c.post("/api/v1/call", headers={"Authorization": f"Bearer {API}"},
                  json={"profile": profile, "tool": tool, "args": args, "client": "test"}).json()


def test_ui_requires_session(env):
    _, c = env
    assert c.get("/").status_code == 401
    assert c.get("/login?t=wrong").status_code == 401
    login(c)
    assert c.get("/").status_code == 200


def test_bad_host_rejected(env):
    _, c = env
    login(c)
    assert c.get("/", headers={"Host": "evil.example:7420"}).status_code == 400
    assert c.post("/api/v1/call", headers={"Host": "evil.example", "Authorization": f"Bearer {API}"}).status_code == 400


def test_foreign_origin_post_rejected(env):
    _, c = env
    login(c)
    r = c.post("/unlock", data={"secret": PASS}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_api_requires_token(env):
    _, c = env
    assert c.post("/api/v1/call", json={}).status_code == 401
    assert c.post("/api/v1/call", headers={"Authorization": "Bearer nope"}, json={}).status_code == 401


def test_full_ui_flow(env):
    svc, c = env
    login(c)
    assert "Unlock your pocket" in c.get("/").text
    assert api(c, "search_memories", query="")["error"]["code"] == "pocket_locked"

    r = c.post("/unlock", data={"secret": "wrong passphrase"})
    assert "Wrong passphrase" in r.text and not svc.unlocked
    r = c.post("/unlock", data={"secret": PASS})
    assert "Your pocket is unlocked" in r.text and "pocket-work" in r.text

    # MCP read respects the profile
    hits = api(c, "search_memories", query="")["result"]
    assert {h["space"] for h in hits} == {"portable_professional"}
    assert api(c, "search_memories", query="", space="personal")["error"]["code"] == "denied"

    # propose -> shows in proposals -> approve with edit -> readable over MCP
    pid = api(c, "propose_memory", content="Prefers pairing on hard bugs", type="preference")["result"]["id"]
    page = c.get("/proposals").text
    assert "Prefers pairing on hard bugs" in page
    r = c.post("/proposals", data={"sel": pid, "action": "approve", f"content_{pid}": "Prefers pairing on hard bugs."})
    assert "Approved 1" in r.text
    assert api(c, "get_memory", id=pid)["result"]["content"] == "Prefers pairing on hard bugs."

    # lock from the UI -> MCP is cut off
    c.post("/lock")
    assert api(c, "get_memory", id=pid)["error"]["code"] == "pocket_locked"
    assert "Unlock your pocket" in c.get("/memories", follow_redirects=True).text


def test_prompt_bridge_import_and_export(env):
    svc, c = env
    login(c)
    c.post("/unlock", data={"secret": PASS})
    answer = 'Here you go:\n```\n{"content": "Uses Neovim", "type": "preference", "confidence": 0.9}\n' \
             '{"content": "Might be a night owl", "type": "interpretation", "confidence": 0.3}\n```'
    prev = c.post("/import/preview", data={"text": answer, "space": "portable_professional",
                                           "provider": "openai", "model": "gpt"}).text
    assert "2 items found" in prev and "Uses Neovim" in prev
    form = {"space": "portable_professional", "provider": "openai", "model": "gpt", "keep": ["0"],
            "content_0": "Uses Neovim", "type_0": "preference", "confidence_0": "0.9", "tags_0": "tools",
            "content_1": "Might be a night owl", "type_1": "interpretation", "confidence_1": "0.3"}
    r = c.post("/import/confirm", data=form)
    assert "Imported 1 candidates" in r.text
    cand = [m for m in svc.store.list(status="candidate", limit=50) if m["content"] == "Uses Neovim"][0]
    assert cand["source_type"] == "imported" and cand["provenance"]["method"] == "prompt_bridge"
    assert cand["provenance"]["provider"] == "openai" and cand["tags"] == ["tools"]
    assert not [m for m in svc.store.list(status="candidate", limit=50) if "night owl" in m["content"]]

    pkg = c.get("/export", params={"profile": "work", "topic": "", "purpose": "demo"}).text
    assert "CONTEXT PACKAGE" in pkg and "Valparaíso" not in pkg and "Python" in pkg
    assert "Valparaíso" in c.get("/export", params={"profile": "personal"}).text


def test_profiles_editable_only_with_valid_rules(env):
    svc, c = env
    login(c)
    c.post("/unlock", data={"secret": PASS})
    r = c.post("/profiles", data={"name": "bad", "body": json.dumps({"allow": ["write:durable"]})})
    assert "unknown scope" in r.text
    r = c.post("/profiles", data={"name": "acme", "body": json.dumps(
        {"allow": ["read:work:acme", "read:portable_professional", "propose:memory"], "propose_into": "work:acme"})})
    assert "saved" in r.text
    assert {h["space"] for h in api(c, "search_memories", profile="acme", query="", limit=50)["result"]} == {
        "work:acme", "portable_professional"}


def test_html_is_escaped(env):
    svc, c = env
    login(c)
    c.post("/unlock", data={"secret": PASS})
    api(c, "propose_memory", content="<script>alert(1)</script>")
    page = c.get("/proposals").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "default-src 'none'" in c.get("/proposals").headers["content-security-policy"]
