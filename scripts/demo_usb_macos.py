"""First demo on a real mounted volume (macOS).

Creates a 64 MB exFAT disk image, mounts it like a USB stick, runs the demo
from SPEC § 23 against it with a real MCP stdio client, then force-ejects the
volume mid-session and checks that MCP access stops.

    uv run python scripts/demo_usb_macos.py

Nothing touches your real disks: the image lives in a temp folder and is
deleted at the end.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS = "demo passphrase 2026"


def step(n, text):
    print(f"\n\033[1m{n}. {text}\033[0m")


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


async def mcp_call(env, profile, tool, args):
    params = StdioServerParameters(command=sys.executable, args=["-m", "lm_pocket", "mcp", "--profile", profile],
                                   env=env)
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        res = await s.call_tool(tool, args)
        if res.is_error:
            return True, res.content[0].text
        data = res.structured_content
        return False, data["result"] if isinstance(data, dict) and set(data) == {"result"} else data


def call(env, profile, tool, **args):
    return asyncio.run(mcp_call(env, profile, tool, args))


def main():
    if sys.platform != "darwin":
        sys.exit("This script uses hdiutil (macOS). On Linux/Windows, run it against a real USB path manually.")
    tmp = Path(tempfile.mkdtemp(prefix="lm-pocket-demo-"))
    env = {**os.environ, "LM_POCKET_HOME": str(tmp / "home")}
    image = tmp / "usb.dmg"
    proc = None
    mount = None
    try:
        step(1, "Plug in a USB stick (64 MB exFAT disk image)")
        sh("hdiutil", "create", "-size", "64m", "-fs", "ExFAT", "-volname", "LMPOCKET", str(image))
        out = sh("hdiutil", "attach", str(image), "-nobrowse")
        mount = Path(re.findall(r"(/Volumes/\S+)", out)[-1])
        folder = mount / "LM-Pocket"
        print(f"   mounted at {mount}")

        step(2, "Create the pocket with fictional sample memories")
        out = sh(sys.executable, "-m", "lm_pocket", "init", str(folder), "--sample", "--passphrase-stdin",
                 input=f"{PASS}\n{PASS}\n", env=env)
        print("   " + "\n   ".join(l for l in out.splitlines() if l.strip() and "LMPK" not in l))
        print("   files on the USB:", sorted(p.name for p in folder.iterdir()))
        raw = (folder / "pocket.db").read_bytes()
        print(f"   pocket.db is {len(raw)} bytes; plaintext 'Valparaíso' on disk: {'Valparaíso'.encode() in raw}")

        step(3, "Open LM-Pocket Local (locked until the passphrase is entered)")
        proc = subprocess.Popen([sys.executable, "-m", "lm_pocket", "open", str(folder), "--no-browser", "--port", "0"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        base, token = None, None
        while not base:
            m = re.search(r"(http://127\.0\.0\.1:\d+)/login\?t=(\S+)", proc.stdout.readline())
            if m:
                base, token = m.groups()
        ui = httpx.Client(base_url=base, follow_redirects=True)
        for _ in range(100):
            try:
                ui.get(f"/login?t={token}")
                break
            except httpx.ConnectError:
                time.sleep(0.05)
        err, msg = call(env, "work", "search_memories", query="")
        print(f"   MCP before unlocking -> error={err}: {msg[:80]}")

        step(4, "Unlock with the passphrase in the localhost UI")
        print("   unlocked:", "Your pocket is unlocked" in ui.post("/unlock", data={"secret": PASS}).text)

        step(5, "Claude (profile 'work') reads memory over MCP")
        _, hits = call(env, "work", "search_memories", query="python code")
        for h in hits:
            print(f"   [{h['space']}] {h['content']}  ({h['source_type']} via {h['provenance']['method']})")

        step(6, "Profile 'work' cannot reach personal memories")
        err, msg = call(env, "work", "search_memories", query="", space="personal")
        print(f"   explicit personal search -> error={err}: {msg[:90]}")
        _, ctx = call(env, "work", "get_context", topic="", max_tokens=2000)
        print(f"   'Valparaíso' (personal) in work context package: {'Valparaíso' in ctx['text']}")
        _, mine = call(env, "personal", "search_memories", query="valparaiso")
        print(f"   same search with profile 'personal' -> {mine[0]['content']}")

        step(7, "The model proposes a new memory -> candidate")
        _, prop = call(env, "work", "propose_memory", content="Prefers async code reviews over meetings",
                       type="preference", provider="anthropic", model="claude")
        print(f"   {prop}")
        _, before = call(env, "work", "search_memories", query="async reviews")
        print(f"   readable before approval: {bool(before)}")

        step(8, "Approve it from localhost")
        print("  ", re.search(r"Approved \d+, rejected \d+", ui.post(
            "/proposals", data={"sel": prop["id"], "action": "approve"}).text).group(0))
        _, after = call(env, "work", "search_memories", query="async reviews")
        print(f"   readable after approval: {after[0]['content']}")

        step(9, "Prompt bridge: import from a closed model, export a context package")
        answer = ('Sure!\n```json\n{"content": "Writes tests before refactoring", "type": "skill", '
                  '"confidence": 0.8}\n```')
        prev = ui.post("/import/preview", data={"text": answer, "space": "portable_professional",
                                                "provider": "openai", "model": "gpt"}).text
        print("  ", re.search(r"\d+ items found", prev).group(0))
        already = set(re.findall(r'value="([0-9a-f-]{36})"', ui.get("/proposals").text))
        ui.post("/import/confirm", data={"space": "portable_professional", "provider": "openai", "model": "gpt",
                                         "keep": "0", "content_0": "Writes tests before refactoring",
                                         "type_0": "skill", "confidence_0": "0.8"})
        pending = [m for m in re.findall(r'value="([0-9a-f-]{36})"', ui.get("/proposals").text) if m not in already]
        ui.post("/proposals", data={"sel": pending, "action": "approve"})
        pkg = ui.get("/export", params={"profile": "work", "purpose": "new job"}).text
        block = re.search(r"CONTEXT PACKAGE.*?(?=</textarea>)", pkg, re.S).group(0)
        print("   " + block.replace("&#39;", "'").replace("&amp;", "&").replace("\n", "\n   ")[:900])

        step(10, "Yank the USB out (force eject while the pocket is open)")
        sh("hdiutil", "detach", str(mount), "-force")
        mount = None
        time.sleep(1.5)
        err, msg = call(env, "work", "search_memories", query="")
        print(f"   MCP after unplugging -> error={err}: {msg[:110]}")

        step(11, "Same question again: the memory is no longer available")
        err, msg = call(env, "personal", "get_profile")
        print(f"   error={err}: {msg[:80]}")
        print("\n\033[1mDemo complete.\033[0m")
    finally:
        if proc:
            proc.terminate()
            proc.wait(10)
        if mount:
            subprocess.run(["hdiutil", "detach", str(mount), "-force"], capture_output=True)
        subprocess.run(["rm", "-rf", str(tmp)])


if __name__ == "__main__":
    main()
