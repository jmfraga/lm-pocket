import json

import pytest

from conftest import PASS
from lm_pocket import crypto
from lm_pocket.pocket import PocketError, PocketFolder
from lm_pocket.store import Store


def test_create_and_unlock_with_passphrase_and_recovery(tmp_path):
    folder, recovery = PocketFolder.create(tmp_path / "p", PASS)
    assert recovery.startswith("LMPK-")
    dek1 = folder.unwrap_dek(PASS)
    dek2 = folder.unwrap_dek(recovery)
    assert dek1 == dek2 and len(dek1) == 32


def test_wrong_passphrase_and_wrong_recovery_fail(tmp_path):
    folder, _ = PocketFolder.create(tmp_path / "p", PASS)
    with pytest.raises(crypto.WrongKey):
        folder.unwrap_dek("not the passphrase")
    _, other = crypto.new_recovery_key()
    with pytest.raises(crypto.WrongKey):
        folder.unwrap_dek(other)


def test_short_passphrase_rejected(tmp_path):
    with pytest.raises(PocketError):
        PocketFolder.create(tmp_path / "p", "short")


def test_change_passphrase_keeps_data(tmp_path):
    folder, recovery = PocketFolder.create(tmp_path / "p", PASS)
    dek = folder.unwrap_dek(recovery)
    folder.set_passphrase(dek, "a brand new passphrase")
    assert folder.unwrap_dek("a brand new passphrase") == dek
    with pytest.raises(crypto.WrongKey):
        folder.unwrap_dek(PASS)


def test_tampered_key_slot_fails(tmp_path):
    folder, _ = PocketFolder.create(tmp_path / "p", PASS)
    slots = json.loads(folder.keys_path.read_text())
    raw = bytearray(__import__("base64").b64decode(slots["passphrase"]))
    raw[-1] ^= 1
    slots["passphrase"] = __import__("base64").b64encode(bytes(raw)).decode()
    folder.keys_path.write_text(json.dumps(slots))
    with pytest.raises(crypto.WrongKey):
        folder.unwrap_dek(PASS)


def test_database_is_encrypted_on_disk(tmp_path):
    folder, _ = PocketFolder.create(tmp_path / "p", PASS)
    store = Store(folder.db_path, folder.unwrap_dek(PASS))
    store.add_space("personal", "Personal")
    store.add_memory({"content": "my secret canción", "type": "fact", "status": "durable", "space": "personal",
                      "source_type": "user", "provenance": {"method": "manual", "recorded_at": "2026-10-01T00:00:00Z"}})
    store.close()
    raw = folder.db_path.read_bytes()
    assert b"SQLite format 3" not in raw
    assert b"secret" not in raw and "canción".encode() not in raw
    with pytest.raises(Exception):
        Store(folder.db_path, crypto.new_key())


def test_lock_file_blocks_second_owner_on_same_host(tmp_path, monkeypatch):
    folder, _ = PocketFolder.create(tmp_path / "p", PASS)
    folder.acquire()
    folder.acquire()  # same process: fine
    import subprocess
    import sys

    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        data = json.loads(folder.lock_path.read_text())
        data["pid"] = other.pid  # another live process on this machine owns it
        folder.lock_path.write_text(json.dumps(data))
        with pytest.raises(PocketError):
            folder.acquire()
    finally:
        other.kill()
        other.wait()
    folder.acquire()  # that process is gone now: stale lock, taken over
    folder.acquire(force=True)
    folder.release()
    assert not folder.lock_path.exists()
