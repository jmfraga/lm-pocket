"""Permission profiles (SPEC § 11).

A profile is chosen by the MCP config entry, never by the client:

    {"allow": ["read:portable_professional", "propose:memory"],
     "deny":  ["read:personal", "read:work:*"],
     "propose_into": "portable_professional"}

Deny always wins over allow. Anything not allowed is denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from .store import SPACE_RE

SCOPES = ("read:", "propose:memory", "export:context", "import:memory", "audit:read")

DEFAULT_PROFILES = {
    "personal": {
        "description": "Your own assistant at home. Reads personal and portable spaces.",
        "allow": ["read:personal", "read:portable_professional", "read:shared", "propose:memory"],
        "deny": [],
        "propose_into": "personal",
    },
    "work": {
        "description": "Any work environment. Only portable professional memory; never personal or other employers.",
        "allow": ["read:portable_professional", "propose:memory"],
        "deny": ["read:personal", "read:work:*"],
        "propose_into": "portable_professional",
    },
}

DEFAULT_SPACES = [
    ("personal", "Personal", "Your private life. Isolated by default."),
    ("portable_professional", "Portable professional", "Lessons and preferences you can take to any job."),
    ("shared", "Shared", "Things you are happy for most profiles to know."),
]


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    allow: tuple[str, ...]
    deny: tuple[str, ...] = ()
    propose_into: str | None = None
    description: str = ""
    extra: dict = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, name: str, body: dict) -> "Profile":
        validate(body)
        return cls(
            name=name,
            allow=tuple(body.get("allow", [])),
            deny=tuple(body.get("deny", [])),
            propose_into=body.get("propose_into"),
            description=body.get("description", ""),
        )

    def _match(self, rules, scope: str) -> bool:
        return any(fnmatchcase(scope, r) for r in rules)

    def has(self, scope: str) -> bool:
        return not self._match(self.deny, scope) and self._match(self.allow, scope)

    def can_read(self, space: str) -> bool:
        return self.has(f"read:{space}")

    def readable(self, spaces: list[str]) -> list[str]:
        return [s for s in spaces if self.can_read(s)]

    def can_propose(self) -> bool:
        return self.has("propose:memory") and bool(self.propose_into)


def validate(body: dict) -> None:
    if not isinstance(body, dict):
        raise ProfileError("profile must be an object")
    for key in ("allow", "deny"):
        rules = body.get(key, [])
        if not isinstance(rules, list) or not all(isinstance(r, str) for r in rules):
            raise ProfileError(f"'{key}' must be a list of strings")
        for r in rules:
            if not r.startswith(SCOPES):
                raise ProfileError(f"unknown scope: {r}")
    into = body.get("propose_into")
    if into is not None and not SPACE_RE.match(into):
        raise ProfileError(f"invalid propose_into space: {into}")
    if "propose:memory" in body.get("allow", []) and not into:
        raise ProfileError("a profile that can propose needs 'propose_into'")
