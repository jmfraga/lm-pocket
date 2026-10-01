#!/usr/bin/env bash
# Prove the offline path in docs/offline.md on this machine:
# install LM-Pocket with --no-index from a wheelhouse into a fresh venv, then
# init -> open -> status -> one MCP call -> close -> MCP refused.
#
#   scripts/verify-offline-install.sh <wheelhouse-platform-dir> [python]
#   e.g. scripts/verify-offline-install.sh /Volumes/USB/app/wheelhouse/macos-arm64-cp312 python3.12
set -euo pipefail
WH="${1:?usage: verify-offline-install.sh <wheelhouse-platform-dir> [python]}"
PY="${2:-python3}"
T="$(mktemp -d)"
cleanup() { [ -n "${DAEMON:-}" ] && kill "$DAEMON" 2>/dev/null || true; rm -rf "$T"; }
trap cleanup EXIT
export LM_POCKET_HOME="$T/home"
# A hostile proxy must not matter: everything is localhost.
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 http_proxy=http://127.0.0.1:9

"$PY" -m venv "$T/venv"
"$T/venv/bin/pip" install --quiet --no-index --find-links "$WH" lm-pocket
echo "installed offline: lm-pocket $("$T/venv/bin/lm-pocket" --version)"

printf 'offline passphrase 1\noffline passphrase 1\n' | "$T/venv/bin/lm-pocket" init "$T/LM-Pocket" --sample --passphrase-stdin | grep Loaded
echo 'offline passphrase 1' | "$T/venv/bin/lm-pocket" open "$T/LM-Pocket" --no-browser --unlock-stdin --port 0 >"$T/open.log" 2>&1 &
DAEMON=$!
for _ in $(seq 50); do "$T/venv/bin/lm-pocket" status >/dev/null 2>&1 && break; sleep 0.2; done
"$T/venv/bin/lm-pocket" status

cat >"$T/check.py" <<PY
import asyncio, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    p = StdioServerParameters(command="$T/venv/bin/lm-pocket", args=["mcp", "--profile", "work"], env=dict(os.environ))
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        res = await s.call_tool("search_memories", {"query": "python"})
        print("MCP error ->" if res.is_error else "MCP ok ->", res.content[0].text.replace(chr(10), " ")[:100])
        return res.is_error
is_error = asyncio.run(main())  # exit outside the async context managers
sys.exit(int(is_error) if sys.argv[1] == "expect-ok" else int(not is_error))
PY
"$T/venv/bin/python" "$T/check.py" expect-ok 2>/dev/null
kill "$DAEMON"; wait "$DAEMON" 2>/dev/null || true; DAEMON=
"$T/venv/bin/python" "$T/check.py" expect-error 2>/dev/null
[ ! -e "$T/LM-Pocket/pocket.lock" ] && echo "lock released on close"
echo "OFFLINE INSTALL VERIFIED"
