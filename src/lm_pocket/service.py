"""PocketService: the single owner of an unlocked pocket.

Every read and write — from the UI or from MCP — goes through here, so
locking, profile enforcement and auditing happen in exactly one place.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path

from . import crypto, policy, prompt_bridge
from .pocket import PocketError, PocketFolder, now
from .store import MEMORY_TYPES, Store

PROPOSALS_PER_HOUR = 30
MAX_SEARCH = 50


class Locked(Exception):
    """The pocket is locked (or its folder disappeared)."""


class Denied(Exception):
    """The profile does not allow this."""


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


class PocketService:
    def __init__(self, path: Path, *, watch_interval: float = 1.0):
        self.folder = PocketFolder(Path(path))
        self.folder.meta()  # fail early if this is not a pocket
        self.store: Store | None = None
        self._dek: bytes | None = None
        self._mutex = threading.RLock()
        self._watch_interval = watch_interval
        self._watcher: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_lock_reason: str | None = None

    # --- lifecycle ------------------------------------------------------

    @property
    def unlocked(self) -> bool:
        return self.store is not None

    def unlock(self, secret: str, *, force: bool = False) -> None:
        with self._mutex:
            if self.unlocked:
                return
            dek = self.folder.unwrap_dek(secret)  # raises crypto.WrongKey
            self.folder.acquire(force=force)
            try:
                store = Store(self.folder.db_path, dek)
            except Exception:
                self.folder.release()
                raise
            if store.is_empty():
                for sid, label, desc in policy.DEFAULT_SPACES:
                    store.add_space(sid, label, desc)
                for name, body in policy.DEFAULT_PROFILES.items():
                    store.set_profile(name, body)
            self.store, self._dek = store, dek
            self.last_lock_reason = None
            via = "recovery_key" if crypto.looks_like_recovery_key(secret) else "passphrase"
            store.audit("pocket_unlocked", via=via)
        self._start_watcher()

    def lock(self, reason: str = "user") -> None:
        with self._mutex:
            if not self.unlocked:
                return
            store = self.store
            self.store, self._dek = None, None  # best effort: Python cannot zero memory
            self.last_lock_reason = reason
            if self.folder.is_present():
                try:
                    store.audit("pocket_locked", reason=reason)
                except Exception:
                    pass
            store.close()
            self.folder.release()
        self._stop.set()

    def _start_watcher(self) -> None:
        self._stop.clear()
        if self._watcher and self._watcher.is_alive():
            return

        def watch():
            while not self._stop.wait(self._watch_interval):
                if self.unlocked and not self.folder.is_present():
                    self.lock(reason="data folder disappeared (USB unplugged?)")
                    return

        self._watcher = threading.Thread(target=watch, name="pocket-watcher", daemon=True)
        self._watcher.start()

    def require(self) -> Store:
        store = self.store
        if store is None:
            raise Locked(self.last_lock_reason or "pocket is locked")
        if not self.folder.is_present():
            self.lock(reason="data folder disappeared (USB unplugged?)")
            raise Locked(self.last_lock_reason)
        return store

    # --- profiles -------------------------------------------------------

    def profile(self, name: str) -> policy.Profile:
        body = self.require().profiles().get(name)
        if body is None:
            raise Denied(f"unknown profile: {name}")
        return policy.Profile.from_dict(name, body)

    def _readable(self, prof: policy.Profile, store: Store) -> list[str]:
        return prof.readable([s["id"] for s in store.spaces()])

    # --- MCP surface (SPEC § 12) ---------------------------------------

    def call(self, profile_name: str, tool: str, args: dict | None = None, client: str | None = None):
        args = args or {}
        handler = getattr(self, f"_tool_{tool}", None)
        if handler is None:
            raise BadRequest(f"unknown tool: {tool}")
        store = self.require()
        try:
            prof = self.profile(profile_name)
        except Denied:
            store.audit("mcp_denied", profile_name, client, tool=tool, reason="unknown profile")
            raise
        try:
            return handler(store, prof, client, **args)
        except TypeError as exc:
            raise BadRequest(f"bad arguments for {tool}: {exc}") from exc
        except Denied as exc:
            store.audit("mcp_denied", prof.name, client, tool=tool, reason=str(exc))
            raise
        except (NotFound, BadRequest):
            raise
        except Exception:
            if not self.unlocked:  # locked (or unplugged) while the call was running
                raise Locked(self.last_lock_reason or "pocket is locked") from None
            raise

    def _tool_get_profile(self, store, prof, client):
        store.audit("profile_read", prof.name, client)
        return {
            "profile": prof.name,
            "description": prof.description,
            "readable_spaces": self._readable(prof, store),
            "can_propose": prof.can_propose(),
            "proposals_go_to": prof.propose_into if prof.can_propose() else None,
        }

    def _tool_list_spaces(self, store, prof, client):
        readable = set(self._readable(prof, store))
        return [s for s in store.spaces() if s["id"] in readable]

    def _tool_get_policies(self, store, prof, client):
        return {"allow": list(prof.allow), "deny": list(prof.deny), "propose_into": prof.propose_into,
                "note": "Durable writes, deletes and policy changes are only possible in the local UI."}

    def _tool_search_memories(self, store, prof, client, query: str = "", limit: int = 10, space: str | None = None):
        spaces = self._readable(prof, store)
        if space is not None:
            if space not in spaces:
                raise Denied(f"profile '{prof.name}' cannot read space '{space}'")
            spaces = [space]
        hits = store.search(str(query), spaces=spaces, limit=max(1, min(int(limit), MAX_SEARCH)))
        store.audit("memories_retrieved", prof.name, client, tool="search_memories", count=len(hits),
                    spaces=sorted({h["space"] for h in hits}), query_chars=len(str(query)))
        return hits

    def _tool_get_memory(self, store, prof, client, id: str):
        m = store.get(str(id))
        # Same answer for "does not exist" and "not yours": no existence leaks.
        if m is None or m["status"] != "durable" or not prof.can_read(m["space"]):
            raise NotFound(f"memory not found: {id}")
        store.audit("memories_retrieved", prof.name, client, tool="get_memory", count=1, spaces=[m["space"]])
        return m

    def _tool_get_recent_context(self, store, prof, client, limit: int = 10):
        hits = store.list(spaces=self._readable(prof, store), limit=max(1, min(int(limit), MAX_SEARCH)))
        store.audit("memories_retrieved", prof.name, client, tool="get_recent_context", count=len(hits),
                    spaces=sorted({h["space"] for h in hits}))
        return hits

    def _tool_get_context(self, store, prof, client, topic: str = "", purpose: str = "", max_tokens: int = 800):
        pkg = self.context_package(prof.name, topic=topic, purpose=purpose, max_tokens=max_tokens,
                                   client=client, _store=store)
        return pkg

    def _tool_propose_memory(self, store, prof, client, content: str, type: str = "fact",
                             confidence: float = 0.5, tags: list | None = None, provider: str | None = None,
                             model: str | None = None, conversation_ref: str | None = None):
        if not prof.can_propose():
            raise Denied(f"profile '{prof.name}' cannot propose memories")
        content = str(content).strip()
        if not content or len(content) > prompt_bridge.MAX_CONTENT:
            raise BadRequest(f"content must be 1–{prompt_bridge.MAX_CONTENT} characters")
        if type not in MEMORY_TYPES:
            raise BadRequest(f"type must be one of {', '.join(MEMORY_TYPES)}")
        hour_ago = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if store.count_events_since("proposal_received", prof.name, hour_ago) >= PROPOSALS_PER_HOUR:
            raise Denied(f"too many proposals: limit is {PROPOSALS_PER_HOUR} per hour per profile")
        space = prof.propose_into
        existing = store.find_same_content(content, space)
        if existing:
            store.audit("proposal_duplicate", prof.name, client, memory_id=existing["id"])
            return {"status": "already_known", "id": existing["id"]}
        prov = {"method": "mcp", "client": client or "unknown", "recorded_at": now()}
        for k, v in (("provider", provider), ("model", model), ("conversation_ref", conversation_ref)):
            if v:
                prov[k] = str(v)[:200]
        m = store.add_memory({
            "content": content, "type": type, "status": "candidate", "space": space, "source_type": "llm",
            "provenance": prov, "confidence": min(1.0, max(0.0, float(confidence))),
            "tags": [str(t)[:40] for t in (tags or [])][:10],
        })
        store.audit("proposal_received", prof.name, client, memory_id=m["id"], space=space)
        return {"status": "candidate", "id": m["id"], "space": space,
                "note": "Saved as a candidate. The user reviews it in LM-Pocket before it becomes durable."}

    # --- context packages (shared by MCP and UI) -----------------------

    def context_package(self, profile_name: str, *, topic: str = "", purpose: str = "", max_tokens: int = 800,
                        client: str | None = "ui", _store: Store | None = None) -> dict:
        store = _store or self.require()
        prof = self.profile(profile_name)
        spaces = self._readable(prof, store)
        mems = store.search(topic, spaces=spaces, limit=MAX_SEARCH) if topic.strip() else store.list(
            spaces=spaces, limit=MAX_SEARCH)
        pkg = prompt_bridge.compile_context(mems, scope=spaces, purpose=purpose, max_tokens=max_tokens)
        store.audit("context_package_generated", prof.name, client, count=len(pkg["memory_ids"]),
                    omitted=pkg["omitted"], spaces=spaces)
        return pkg

    # --- local-UI-only operations (never exposed over MCP) -------------

    def review(self, approve: list[str], reject: list[str], edits: dict[str, str] | None = None) -> dict:
        store = self.require()
        edits = edits or {}
        done = {"approved": 0, "rejected": 0}
        for mid in approve:
            m = store.get(mid)
            if not m or m["status"] != "candidate":
                continue
            fields = {"status": "durable"}
            new = (edits.get(mid) or "").strip()
            if new and new != m["content"]:
                fields["content"] = new
                fields["extra"] = {"edited_by_user_at": now()}
            store.update(mid, **fields)
            store.audit("candidate_approved", memory_id=mid, edited="content" in fields)
            done["approved"] += 1
        for mid in reject:
            m = store.get(mid)
            if not m or m["status"] != "candidate":
                continue
            store.update(mid, status="rejected")
            store.audit("candidate_rejected", memory_id=mid)
            done["rejected"] += 1
        return done

    def add_user_memory(self, content: str, type: str, space: str, tags: list[str] | None = None) -> dict:
        store = self.require()
        if space not in {s["id"] for s in store.spaces()}:
            raise BadRequest(f"unknown space: {space}")
        m = store.add_memory({
            "content": content, "type": type, "status": "durable", "space": space, "source_type": "user",
            "provenance": {"method": "manual", "client": "lm-pocket-ui", "recorded_at": now()},
            "confidence": 1.0, "tags": tags or [],
        })
        store.audit("memory_created", memory_id=m["id"], space=space)
        return m

    def archive(self, memory_id: str) -> None:
        store = self.require()
        store.update(memory_id, status="archived")
        store.audit("memory_archived", memory_id=memory_id)

    def add_space(self, space_id: str, label: str) -> None:
        store = self.require()
        store.add_space(space_id, label)
        store.audit("space_created", space=space_id)

    def set_profile(self, name: str, body: dict) -> None:
        store = self.require()
        policy.validate(body)
        if not name.replace("-", "").replace("_", "").isalnum():
            raise BadRequest("profile name: letters, digits, - and _ only")
        store.set_profile(name, body)
        store.audit("profile_changed", name)

    def import_candidates(self, items: list[dict], *, space: str, provider: str, model: str) -> list[str]:
        store = self.require()
        if space not in {s["id"] for s in store.spaces()}:
            raise BadRequest(f"unknown space: {space}")
        ids = []
        for it in items:
            if store.find_same_content(it["content"], space):
                continue
            prov = {"method": "prompt_bridge", "client": "lm-pocket-ui", "recorded_at": now()}
            if provider:
                prov["provider"] = provider[:100]
            if model:
                prov["model"] = model[:100]
            m = store.add_memory({
                "content": it["content"], "type": it["type"], "status": "candidate", "space": space,
                "source_type": "imported", "provenance": prov, "confidence": it.get("confidence", 0.5),
                "tags": it.get("tags", []),
            })
            ids.append(m["id"])
        store.audit("import_received", count=len(ids), space=space, provider=provider or None)
        return ids

    def load_sample(self) -> int:
        """Load the fictional sample export (examples/sample-export) into an empty pocket."""
        store = self.require()
        if store.counts():
            raise PocketError("sample data can only be loaded into an empty pocket")
        pkg = resources.files("lm_pocket") / "sample"
        for s in json.loads((pkg / "spaces.json").read_text("utf-8")):
            store.add_space(s["id"], s["label"], s.get("description", ""))
        for name, body in json.loads((pkg / "policies.json").read_text("utf-8"))["profiles"].items():
            store.set_profile(name, body)
        n = 0
        for line in (pkg / "memories.jsonl").read_text("utf-8").splitlines():
            if line.strip():
                store.add_memory(json.loads(line))
                n += 1
        store.audit("sample_loaded", count=n)
        return n
