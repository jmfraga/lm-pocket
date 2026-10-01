"""End-to-end: real CLI, real daemon, real MCP client over stdio.

Mirrors the first demo (SPEC § 23). Unplugging is simulated by moving the
folder away; scripts/demo-usb-macos.sh does it with a real mounted volume.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS = "correct horse battery"


@pytest.fixture
def daemon(tmp_path):
    env = {**os.environ, "LM_POCKET_HOME": str(tmp_path / "home")}
    folder = tmp_path / "USB" / "LM-Pocket"
    out = subprocess.run([sys.executable, "-m", "lm_pocket", "init", str(folder), "--sample", "--passphrase-stdin"],
                         input=PASS + "\n" + PASS + "\n", text=True, capture_output=True, env=env, check=True).stdout
    assert "RECOVERY KEY" in out and "Loaded 10" in out
    proc = subprocess.Popen([sys.executable, "-m", "lm_pocket", "open", str(folder), "--no-browser", "--port", "0"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    url = None
    for _ in range(100):
        line = proc.stdout.readline()
        m = re.search(r"(http://127\.0\.0\.1:\d+)/login\?t=(\S+)", line)
        if m:
            url = m.groups()
            break
    assert url, "daemon did not start"
    ui = httpx.Client(base_url=url[0], follow_redirects=True)
    for _ in range(100):  # the URL is printed just before uvicorn starts listening
        try:
            ui.get(f"/login?t={url[1]}")
            break
        except httpx.ConnectError:
            time.sleep(0.05)
    yield env, folder, ui, proc
    proc.terminate()
    proc.wait(10)


async def mcp_calls(env, profile, calls):
    params = StdioServerParameters(command=sys.executable, args=["-m", "lm_pocket", "mcp", "--profile", profile],
                                   env=env)
    results = []
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = {t.name for t in (await s.list_tools()).tools}
        assert {"search_memories", "propose_memory", "get_context"} <= tools
        assert not any("write" in t or "delete" in t for t in tools)
        for name, args in calls:
            res = await s.call_tool(name, args)
            if res.is_error:
                results.append((True, res.content[0].text))
                continue
            data = res.structured_content
            if isinstance(data, dict) and set(data) == {"result"}:  # lists are wrapped
                data = data["result"]
            results.append((False, data))
    return results


def mcp(env, profile, *calls):
    return asyncio.run(mcp_calls(env, profile, list(calls)))


def test_first_demo_end_to_end(daemon):
    env, folder, ui, proc = daemon

    # 1. locked: MCP cannot read anything
    [(err, msg)] = mcp(env, "work", ("search_memories", {"query": ""}))
    assert err and "pocket_locked" in msg

    # 2. unlock with the passphrase in the localhost UI
    assert "Your pocket is unlocked" in ui.post("/unlock", data={"secret": PASS}).text

    # 3. read over MCP, 4. profile blocks other spaces
    (e1, work_hits), (e2, denied), (e3, ctx) = mcp(
        env, "work",
        ("search_memories", {"query": "python"}),
        ("search_memories", {"query": "", "space": "personal"}),
        ("get_context", {"topic": "", "max_tokens": 2000}),
    )
    assert not e1 and work_hits and {h["space"] for h in work_hits} == {"portable_professional"}
    assert e2 and "denied" in denied
    assert not e3 and "Valparaíso" not in ctx["text"] and "Lucía" not in ctx["text"]
    [(_, personal_hits)] = mcp(env, "personal", ("search_memories", {"query": "valparaiso"}))
    assert personal_hits[0]["space"] == "personal"

    # 5. propose a memory -> candidate
    [(err, prop)] = mcp(env, "work", ("propose_memory", {"content": "Prefers async code reviews",
                                                          "type": "preference", "provider": "test", "model": "e2e"}))
    assert not err and prop["status"] == "candidate"
    [(_, before)] = mcp(env, "work", ("search_memories", {"query": "async reviews"}))
    assert before == []

    # 6. approve it from localhost
    assert "Prefers async code reviews" in ui.get("/proposals").text
    assert "Approved 1" in ui.post("/proposals", data={"sel": prop["id"], "action": "approve"}).text
    [(_, after)] = mcp(env, "work", ("search_memories", {"query": "async reviews"}))
    assert after[0]["id"] == prop["id"] and after[0]["provenance"]["client"].startswith("mcp")

    # 7. prompt bridge: import from a closed model, export a context package
    ui.post("/import/confirm", data={"space": "portable_professional", "provider": "openai", "model": "gpt",
                                     "keep": "0", "content_0": "Writes tests before refactoring",
                                     "type_0": "skill", "confidence_0": "0.8"})
    assert "Writes tests before refactoring" in ui.get("/proposals").text
    pkg = ui.get("/export", params={"profile": "work", "purpose": "new job"}).text
    assert "CONTEXT PACKAGE" in pkg and "Prefers async code reviews" in pkg

    # 8. unplug -> MCP stops reading
    shutil.move(str(folder.parent), str(folder.parent.with_name("USB-unplugged")))
    time.sleep(1.5)
    [(err, msg)] = mcp(env, "work", ("search_memories", {"query": ""}))
    assert err and "pocket_locked" in msg and "disappeared" in msg
    assert "Locked because" in ui.get("/").text

    # 9. closing the app also cuts MCP off
    proc.terminate()
    proc.wait(10)
    [(err, msg)] = mcp(env, "work", ("get_profile", {}))
    assert err and ("not open" in msg or "not running" in msg)


def test_lock_button_cuts_mcp(daemon):
    env, _, ui, _ = daemon
    ui.post("/unlock", data={"secret": PASS})
    [(err, _)] = mcp(env, "personal", ("get_profile", {}))
    assert not err
    ui.post("/lock")
    [(err, msg)] = mcp(env, "personal", ("get_profile", {}))
    assert err and "pocket_locked" in msg


def test_sigterm_releases_lock_and_runtime(daemon):
    env, folder, ui, proc = daemon
    ui.post("/unlock", data={"secret": PASS})
    assert (folder / "pocket.lock").exists()
    assert (Path(env["LM_POCKET_HOME"]) / "runtime.json").exists()
    proc.terminate()  # SIGTERM, like closing a terminal or `kill`
    proc.wait(10)
    assert not (folder / "pocket.lock").exists()
    assert not (Path(env["LM_POCKET_HOME"]) / "runtime.json").exists()
    [(err, msg)] = mcp(env, "work", ("get_profile", {}))
    assert err and "not open" in msg
