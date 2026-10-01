"""LM-Pocket Local: localhost UI + internal API for MCP proxies.

Security on localhost is not free:
- Host header must be 127.0.0.1:<port> or localhost:<port> (DNS rebinding).
- The UI requires a session cookie obtained from a one-time URL printed in
  the terminal (like Jupyter). Cookie is HttpOnly + SameSite=Strict (CSRF).
- POSTs with a foreign Origin are rejected.
- The MCP API requires the bearer token from runtime.json.
- Durable writes, deletes and policy changes exist only here, never in MCP.
"""

from __future__ import annotations

import hmac
import json
import sys
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import crypto, prompt_bridge
from .pocket import PocketError
from .policy import ProfileError
from .service import BadRequest, Denied, Locked, NotFound, PocketService
from .store import MEMORY_TYPES

COOKIE = "lmp_session"
CSP = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def mcp_command(profile: str) -> list[str]:
    return [sys.executable, "-m", "lm_pocket", "mcp", "--profile", profile]


def create_app(service: PocketService, *, api_token: str, ui_token: str, allowed_hosts: set[str]) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    allowed_origins = {f"http://{h}" for h in allowed_hosts}

    def same(a: str | None, b: str) -> bool:
        return a is not None and hmac.compare_digest(a.encode(), b.encode())

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host") not in allowed_hosts:
            return Response("bad host", status_code=400)
        path = request.url.path
        if path.startswith("/api/"):
            auth = request.headers.get("authorization", "")
            if not same(auth.removeprefix("Bearer "), api_token):
                return JSONResponse({"ok": False, "error": {"code": "unauthorized"}}, status_code=401)
        elif path != "/login":
            if not same(request.cookies.get(COOKIE), ui_token):
                return HTMLResponse(
                    "<h1>LM-Pocket</h1><p>Open the link printed in the terminal where you started LM-Pocket.</p>",
                    status_code=401,
                )
            origin = request.headers.get("origin")
            if request.method == "POST" and origin is not None and origin not in allowed_origins:
                return Response("bad origin", status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def page(request: Request, name: str, **ctx):
        ctx.setdefault("msg", request.query_params.get("msg"))
        ctx["unlocked"] = service.unlocked
        return TEMPLATES.TemplateResponse(request, name, ctx)

    def go(url: str, msg: str | None = None):
        if msg:
            url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
        return RedirectResponse(url, status_code=303)

    def attempt(fn):
        """Run a UI action. Domain errors become a message; Locked goes to the handler below."""
        try:
            return fn(), None
        except (BadRequest, Denied, NotFound, ProfileError, PocketError, ValueError) as exc:
            return None, str(exc)

    @app.exception_handler(Locked)
    def on_locked(request: Request, exc: Locked):
        return go("/", f"Locked: {exc}")

    # --- session --------------------------------------------------------

    @app.get("/login")
    def login(t: str = ""):
        if not same(t, ui_token):
            return HTMLResponse("<p>Invalid or expired link.</p>", status_code=401)
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, ui_token, httponly=True, samesite="strict")
        return resp

    # --- lock / unlock --------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        if not service.unlocked:
            return page(request, "unlock.html", reason=service.last_lock_reason, folder=str(service.folder.path))
        store = service.store
        profiles = store.profiles()
        configs = {
            name: json.dumps({"mcpServers": {f"pocket-{name}": {"command": mcp_command(name)[0],
                                                                "args": mcp_command(name)[1:]}}}, indent=2)
            for name in profiles
        }
        return page(request, "home.html", counts=store.counts(), profiles=profiles, configs=configs,
                    folder=str(service.folder.path), claude_code={n: " ".join(mcp_command(n)) for n in profiles})

    @app.post("/unlock")
    def unlock(request: Request, secret: str = Form(...), force: bool = Form(False)):
        try:
            service.unlock(secret, force=force)
        except crypto.WrongKey:
            return go("/", "Wrong passphrase or recovery key.")
        except PocketError as exc:
            return go("/", str(exc))
        return go("/", "Unlocked.")

    @app.post("/lock")
    def lock():
        service.lock("user")
        return go("/", "Locked. MCP clients can no longer read the pocket.")

    # --- memories -------------------------------------------------------

    @app.get("/memories", response_class=HTMLResponse)
    def memories(request: Request, space: str = "", q: str = ""):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        store = service.store
        spaces = [s["id"] for s in store.spaces()]
        chosen = [space] if space in spaces else spaces
        rows = store.search(q, spaces=chosen, limit=200) if q.strip() else store.list(spaces=chosen, limit=200)
        return page(request, "memories.html", rows=rows, spaces=spaces, space=space, q=q, types=MEMORY_TYPES)

    @app.post("/memories")
    def add_memory(content: str = Form(...), type: str = Form(...), space: str = Form(...), tags: str = Form("")):
        _, err = attempt(lambda: service.add_user_memory(
            content, type, space, [t.strip() for t in tags.split(",") if t.strip()]))
        return go("/memories", err or "Memory saved.")

    @app.post("/memories/{memory_id}/archive")
    def archive(memory_id: str):
        _, err = attempt(lambda: service.archive(memory_id))
        return go("/memories", err or "Archived.")

    # --- proposals ------------------------------------------------------

    @app.get("/proposals", response_class=HTMLResponse)
    def proposals(request: Request):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        rows = service.store.list(status="candidate", limit=500, order="space, created_at")
        return page(request, "proposals.html", rows=rows)

    @app.post("/proposals")
    async def review(request: Request):
        form = await request.form()
        selected = form.getlist("sel")
        edits = {k.removeprefix("content_"): v for k, v in form.items() if k.startswith("content_")}
        action = form.get("action")
        res, err = attempt(lambda: service.review(selected if action == "approve" else [],
                                                  selected if action == "reject" else [], edits))
        return go("/proposals", err or f"Approved {res['approved']}, rejected {res['rejected']}.")

    # --- spaces & profiles ---------------------------------------------

    @app.get("/spaces", response_class=HTMLResponse)
    def spaces(request: Request):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        return page(request, "spaces.html", rows=service.store.spaces())

    @app.post("/spaces")
    def add_space(space_id: str = Form(...), label: str = Form(...)):
        _, err = attempt(lambda: service.add_space(space_id.strip(), label.strip()))
        return go("/spaces", err or "Space created.")

    @app.get("/profiles", response_class=HTMLResponse)
    def profiles(request: Request):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        rows = {n: json.dumps(b, indent=2) for n, b in service.store.profiles().items()}
        return page(request, "profiles.html", rows=rows)

    @app.post("/profiles")
    def set_profile(name: str = Form(...), body: str = Form(...)):
        def apply():
            try:
                parsed = json.loads(body)
            except ValueError as exc:
                raise BadRequest(f"invalid JSON: {exc}") from exc
            service.set_profile(name.strip(), parsed)

        _, err = attempt(apply)
        return go("/profiles", err or f"Profile '{name}' saved.")

    # --- prompt bridge --------------------------------------------------

    @app.get("/import", response_class=HTMLResponse)
    def import_page(request: Request):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        return page(request, "import.html", prompt=prompt_bridge.EXPORT_PROMPT,
                    spaces=[s["id"] for s in service.store.spaces()])

    @app.post("/import/preview", response_class=HTMLResponse)
    def import_preview(request: Request, text: str = Form(...), space: str = Form(...),
                       provider: str = Form(""), model: str = Form("")):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        items, skipped = prompt_bridge.parse_import(text)
        return page(request, "import_preview.html", items=items, skipped=skipped, space=space,
                    provider=provider, model=model, types=MEMORY_TYPES)

    @app.post("/import/confirm")
    async def import_confirm(request: Request):
        form = await request.form()
        keep = set(form.getlist("keep"))
        items = []
        for i in sorted(keep, key=int):
            try:
                conf = float(form.get(f"confidence_{i}", 0.5))
            except ValueError:
                conf = 0.5
            items.append({
                "content": str(form.get(f"content_{i}", "")).strip(),
                "type": form.get(f"type_{i}") if form.get(f"type_{i}") in MEMORY_TYPES else "interpretation",
                "confidence": min(1.0, max(0.0, conf)),
                "tags": [t.strip() for t in str(form.get(f"tags_{i}", "")).split(",") if t.strip()],
            })
        items = [it for it in items if it["content"]]
        res, err = attempt(lambda: service.import_candidates(items, space=str(form.get("space")),
                                                              provider=str(form.get("provider", "")),
                                                              model=str(form.get("model", ""))))
        if err:
            return go("/import", err)
        return go("/proposals", f"Imported {len(res)} candidates. Review them below.")

    @app.get("/export", response_class=HTMLResponse)
    def export(request: Request, profile: str = "", topic: str = "", purpose: str = "", max_tokens: int = 800):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        names = list(service.store.profiles())
        pkg, error = None, None
        if profile:
            pkg, error = attempt(lambda: service.context_package(profile, topic=topic, purpose=purpose,
                                                                 max_tokens=max_tokens))
        return page(request, "export.html", profiles=names, profile=profile, topic=topic, purpose=purpose,
                    max_tokens=max_tokens, pkg=pkg, msg=error or request.query_params.get("msg"))

    # --- audit ----------------------------------------------------------

    @app.get("/audit", response_class=HTMLResponse)
    def audit(request: Request):
        service.require()  # raises Locked -> redirect, also if the USB is gone
        return page(request, "audit.html", rows=service.store.audit_events(limit=300))

    # --- internal API for MCP proxies ----------------------------------

    @app.get("/api/v1/status")
    def status():
        return {"ok": True, "result": {"unlocked": service.unlocked, "reason": service.last_lock_reason}}

    @app.post("/api/v1/call")
    async def call(request: Request):
        try:
            body = await request.json()
            profile, tool = str(body["profile"]), str(body["tool"])
            args, client = body.get("args") or {}, body.get("client")
        except (ValueError, KeyError, TypeError):
            return {"ok": False, "error": {"code": "bad_request", "message": "invalid body"}}
        try:
            result = service.call(profile, tool, args, client=str(client)[:100] if client else None)
        except Locked as exc:
            return {"ok": False, "error": {"code": "pocket_locked", "message": f"LM-Pocket is locked: {exc}"}}
        except Denied as exc:
            return {"ok": False, "error": {"code": "denied", "message": str(exc)}}
        except NotFound as exc:
            return {"ok": False, "error": {"code": "not_found", "message": str(exc)}}
        except (BadRequest, ValueError) as exc:
            return {"ok": False, "error": {"code": "bad_request", "message": str(exc)}}
        return {"ok": True, "result": result}

    return app
