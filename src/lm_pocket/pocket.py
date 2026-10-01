"""The pocket folder: create, unlock, change passphrase.

Layout (SPEC § 4):

    LM-Pocket/
    ├── README.txt
    ├── pocket.json        non-secret metadata: format, pocket id, KDF params + salt
    ├── pocket.db          SQLCipher database
    ├── keys/dek.wrapped   DEK wrapped by the passphrase KEK and by the recovery key
    ├── exports/ backups/ logs/
"""

from __future__ import annotations

import base64
import json
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import FORMAT_VERSION, crypto

README_TXT = """\
This folder is an LM-Pocket: a personal, encrypted, longitudinal memory.

Everything private is inside pocket.db, encrypted with SQLCipher. The key is
derived from your passphrase (Argon2id) or from your recovery key.

To open it you need the LM-Pocket app (https://github.com/jmfraga/lm-pocket):

    lm-pocket open <this folder>

Lost passphrase: `lm-pocket reset-passphrase <this folder>` with your recovery key.
Without the passphrase AND the recovery key, the data cannot be recovered.
"""

MIN_PASSPHRASE = 10


class PocketError(Exception):
    pass


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PocketFolder:
    path: Path

    @property
    def meta_path(self) -> Path:
        return self.path / "pocket.json"

    @property
    def db_path(self) -> Path:
        return self.path / "pocket.db"

    @property
    def keys_path(self) -> Path:
        return self.path / "keys" / "dek.wrapped"

    @property
    def lock_path(self) -> Path:
        return self.path / "pocket.lock"

    def is_present(self) -> bool:
        return self.meta_path.is_file()

    def meta(self) -> dict:
        try:
            meta = json.loads(self.meta_path.read_text("utf-8"))
        except FileNotFoundError as exc:
            raise PocketError(f"not an LM-Pocket folder: {self.path}") from exc
        if meta.get("format") != "lm-pocket":
            raise PocketError(f"not an LM-Pocket folder: {self.path}")
        return meta

    def _aad(self, slot: str) -> bytes:
        return f"lm-pocket:dek:{self.meta()['pocket_id']}:{slot}".encode()

    # --- creation -------------------------------------------------------

    @classmethod
    def create(cls, path: Path, passphrase: str) -> tuple["PocketFolder", str]:
        """Create a new pocket. Returns the folder and the recovery key (show it once)."""
        if len(passphrase) < MIN_PASSPHRASE:
            raise PocketError(f"passphrase must have at least {MIN_PASSPHRASE} characters")
        path = Path(path)
        if path.exists() and any(path.iterdir()):
            raise PocketError(f"folder is not empty: {path}")
        for sub in ("keys", "exports", "backups", "logs"):
            (path / sub).mkdir(parents=True, exist_ok=True)
        folder = cls(path)
        salt = crypto.new_salt()
        meta = {
            "format": "lm-pocket",
            "format_version": FORMAT_VERSION,
            "pocket_id": str(uuid.uuid4()),
            "created_at": now(),
            "kdf": {**crypto.DEFAULT_KDF, "salt": base64.b64encode(salt).decode()},
        }
        folder.meta_path.write_text(json.dumps(meta, indent=2) + "\n", "utf-8")
        (path / "README.txt").write_text(README_TXT, "utf-8")

        dek = crypto.new_key()
        rec_raw, rec_text = crypto.new_recovery_key()
        kek = crypto.derive_kek(passphrase, salt, meta["kdf"])
        folder._write_keys(
            {
                "passphrase": crypto.wrap(kek, dek, folder._aad("passphrase")),
                "recovery": crypto.wrap(rec_raw, dek, folder._aad("recovery")),
            }
        )
        return folder, rec_text

    def _write_keys(self, slots: dict) -> None:
        tmp = self.keys_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(slots, indent=2) + "\n", "utf-8")
        os.replace(tmp, self.keys_path)

    def _slots(self) -> dict:
        return json.loads(self.keys_path.read_text("utf-8"))

    # --- unlocking ------------------------------------------------------

    def unwrap_dek(self, secret: str) -> bytes:
        """Accepts the passphrase or the recovery key. Raises crypto.WrongKey."""
        slots = self._slots()
        if crypto.looks_like_recovery_key(secret):
            return crypto.unwrap(crypto.parse_recovery_key(secret), slots["recovery"], self._aad("recovery"))
        meta = self.meta()
        kek = crypto.derive_kek(secret, base64.b64decode(meta["kdf"]["salt"]), meta["kdf"])
        return crypto.unwrap(kek, slots["passphrase"], self._aad("passphrase"))

    def set_passphrase(self, dek: bytes, new_passphrase: str) -> None:
        """Re-wrap the DEK with a new passphrase. Data is not re-encrypted."""
        if len(new_passphrase) < MIN_PASSPHRASE:
            raise PocketError(f"passphrase must have at least {MIN_PASSPHRASE} characters")
        meta = self.meta()
        salt = crypto.new_salt()
        meta["kdf"] = {**crypto.DEFAULT_KDF, "salt": base64.b64encode(salt).decode()}
        slots = self._slots()
        # Two files change; a crash in between leaves the passphrase slot unusable
        # but the recovery slot intact, so the pocket is never lost.
        kek = crypto.derive_kek(new_passphrase, salt, meta["kdf"])
        slots["passphrase"] = crypto.wrap(kek, dek, self._aad("passphrase"))
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=2) + "\n", "utf-8")
        self._write_keys(slots)
        os.replace(tmp, self.meta_path)

    # --- single-writer lock --------------------------------------------

    def acquire(self, force: bool = False) -> None:
        host = socket.gethostname()
        if self.lock_path.exists() and not force:
            try:
                info = json.loads(self.lock_path.read_text("utf-8"))
            except (OSError, ValueError):
                info = {}
            same_host = info.get("host") == host
            pid = info.get("pid")
            if pid == os.getpid() and same_host:
                pass
            elif same_host and pid and _pid_alive(pid):
                raise PocketError(f"pocket is already open by process {pid} on this machine")
            elif not same_host and info:
                raise PocketError(
                    f"pocket looks open on '{info.get('host')}' since {info.get('at')}. "
                    "If that machine is gone, open with --force."
                )
        self.lock_path.write_text(json.dumps({"pid": os.getpid(), "host": host, "at": now()}), "utf-8")

    def release(self) -> None:
        try:
            info = json.loads(self.lock_path.read_text("utf-8"))
            if info.get("pid") == os.getpid():
                self.lock_path.unlink()
        except (OSError, ValueError):
            pass


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":  # os.kill(pid, 0) sends CTRL_C on Windows; never use it there.
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
