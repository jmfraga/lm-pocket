"""lm-pocket command line.

    lm-pocket init <folder> [--sample]     create a pocket (prints the recovery key once)
    lm-pocket open <folder>                start LM-Pocket Local (UI + MCP endpoint) on 127.0.0.1
    lm-pocket mcp --profile <name>         stdio MCP server for an MCP client config
    lm-pocket status                       is a pocket open and unlocked?
    lm-pocket reset-passphrase <folder>    set a new passphrase using the recovery key
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import socket
import sys
import webbrowser
from pathlib import Path

from . import __version__, crypto, runtime
from .pocket import PocketError, PocketFolder

DEFAULT_PORT = 7420


def _read_secret(prompt: str, from_stdin: bool, confirm: bool = False) -> str:
    if from_stdin:
        line = sys.stdin.readline()
        return line.rstrip("\n")
    value = getpass.getpass(prompt)
    if confirm and getpass.getpass("Repeat: ") != value:
        sys.exit("Passphrases do not match.")
    return value


def cmd_init(a) -> None:
    passphrase = _read_secret("New passphrase (10+ characters): ", a.passphrase_stdin, confirm=True)
    try:
        folder, recovery = PocketFolder.create(Path(a.folder), passphrase)
    except PocketError as exc:
        sys.exit(str(exc))
    if a.sample:
        from .service import PocketService

        svc = PocketService(folder.path)
        svc.unlock(passphrase)
        n = svc.load_sample()
        svc.lock("init")
        print(f"Loaded {n} fictional sample memories.")
    print(f"\nPocket created at {folder.path}\n")
    print("RECOVERY KEY — write it down and keep it apart from the USB. It is shown only once:\n")
    print(f"    {recovery}\n")
    print(f"Next: lm-pocket open {folder.path}")


def _free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise SystemExit("no free port")


def cmd_open(a) -> None:
    import uvicorn

    from .service import PocketService
    from .web import create_app

    try:
        svc = PocketService(Path(a.folder))
    except PocketError as exc:
        sys.exit(str(exc))
    if a.unlock_stdin:
        try:
            svc.unlock(_read_secret("", True), force=a.force)
        except (crypto.WrongKey, PocketError) as exc:
            sys.exit(f"Could not unlock: {exc or 'wrong passphrase'}")
    port = _free_port(a.port)
    api_token, ui_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    app = create_app(svc, api_token=api_token, ui_token=ui_token, allowed_hosts=hosts)
    runtime.write({"pid": os.getpid(), "port": port, "api_token": api_token, "data": str(svc.folder.path)})
    url = f"http://127.0.0.1:{port}/login?t={ui_token}"
    print(f"LM-Pocket Local {__version__} — {svc.folder.path}")
    print(f"Open: {url}")
    print("Ctrl+C to quit (locks the pocket).", flush=True)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        svc.lock("app closed")
        runtime.clear(os.getpid())


def cmd_mcp(a) -> None:
    from .mcp_proxy import run

    run(a.profile)


def cmd_status(a) -> None:
    import httpx

    info = runtime.read()
    if not info:
        sys.exit("No LM-Pocket is open.")
    try:
        r = httpx.get(f"http://127.0.0.1:{info['port']}/api/v1/status",
                      headers={"Authorization": f"Bearer {info['api_token']}"}, timeout=5).json()
    except httpx.HTTPError:
        sys.exit("LM-Pocket is not running (stale runtime file).")
    state = "unlocked" if r["result"]["unlocked"] else f"locked ({r['result']['reason'] or 'waiting for passphrase'})"
    print(f"{info['data']}: {state} on port {info['port']}")


def cmd_reset(a) -> None:
    folder = PocketFolder(Path(a.folder))
    rec = _read_secret("Recovery key: ", a.passphrase_stdin)
    try:
        dek = folder.unwrap_dek(rec if crypto.looks_like_recovery_key(rec) else "LMPK-" + rec)
    except crypto.WrongKey:
        sys.exit("Wrong recovery key.")
    new = _read_secret("New passphrase (10+ characters): ", a.passphrase_stdin, confirm=not a.passphrase_stdin)
    try:
        folder.set_passphrase(dek, new)
    except PocketError as exc:
        sys.exit(str(exc))
    print("Passphrase changed. The recovery key is still valid.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="lm-pocket", description="Longitudinal Memory Pocket")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a new pocket")
    s.add_argument("folder")
    s.add_argument("--sample", action="store_true", help="load the fictional sample memories")
    s.add_argument("--passphrase-stdin", action="store_true", help="read the passphrase from stdin (scripts)")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("open", help="start LM-Pocket Local on 127.0.0.1")
    s.add_argument("folder")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--no-browser", action="store_true")
    s.add_argument("--unlock-stdin", action="store_true", help="read the passphrase from stdin and unlock")
    s.add_argument("--force", action="store_true", help="take over a pocket marked open on another computer")
    s.set_defaults(fn=cmd_open)

    s = sub.add_parser("mcp", help="stdio MCP server for one permission profile")
    s.add_argument("--profile", required=True)
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("status", help="show whether a pocket is open")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("reset-passphrase", help="set a new passphrase with the recovery key")
    s.add_argument("folder")
    s.add_argument("--passphrase-stdin", action="store_true")
    s.set_defaults(fn=cmd_reset)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
