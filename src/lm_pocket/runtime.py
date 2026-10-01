"""Where a running LM-Pocket Local announces itself to MCP proxies.

~/.lm-pocket/runtime.json (0600) holds the localhost port and a random API
token. It contains no memory and no key; it only lets processes of the same
OS user reach the daemon. Override the directory with LM_POCKET_HOME.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("LM_POCKET_HOME") or Path.home() / ".lm-pocket")


def runtime_path() -> Path:
    return home() / "runtime.json"


def write(info: dict) -> Path:
    path = runtime_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(info, f)
    os.replace(tmp, path)
    return path


def read() -> dict | None:
    try:
        return json.loads(runtime_path().read_text("utf-8"))
    except (OSError, ValueError):
        return None


def clear(pid: int) -> None:
    info = read()
    if info and info.get("pid") == pid:
        try:
            runtime_path().unlink()
        except OSError:
            pass


# Never route the bearer token through HTTP_PROXY/HTTPS_PROXY: localhost only, no proxies.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Unreachable(Exception):
    """No LM-Pocket Local answering on the port in runtime.json."""


def request(info: dict, method: str, path: str, body: dict | None = None, timeout: float = 15) -> dict:
    """Talk to the local daemon with the stdlib only (no extra dependency for the MCP proxy)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {info['api_token']}", "Content-Type": "application/json"},
    )
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read())
        except ValueError:
            raise Unreachable(str(exc)) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise Unreachable(str(exc)) from exc
