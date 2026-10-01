"""Key hierarchy: passphrase -> Argon2id -> KEK -> unwraps DEK.

No home-made primitives: Argon2id from argon2-cffi, AES-256-GCM from
cryptography. The DEK is the raw SQLCipher key.
"""

from __future__ import annotations

import base64
import os
import secrets

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_LEN = 32
NONCE_LEN = 12

# RFC 9106 "second recommended option": t=3, m=64 MiB, p=4.
DEFAULT_KDF = {"algorithm": "argon2id", "time_cost": 3, "memory_cost_kib": 65536, "parallelism": 4}


class WrongKey(Exception):
    """The passphrase or recovery key does not unwrap the DEK."""


def new_salt() -> bytes:
    return os.urandom(16)


def new_key() -> bytes:
    return os.urandom(KEY_LEN)


def derive_kek(passphrase: str, salt: bytes, params: dict) -> bytes:
    if params.get("algorithm") != "argon2id":
        raise ValueError(f"unsupported KDF: {params.get('algorithm')}")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=params["time_cost"],
        memory_cost=params["memory_cost_kib"],
        parallelism=params["parallelism"],
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def wrap(key: bytes, secret: bytes, aad: bytes) -> str:
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, secret, aad)
    return base64.b64encode(nonce + ct).decode("ascii")


def unwrap(key: bytes, blob: str, aad: bytes) -> bytes:
    raw = base64.b64decode(blob)
    try:
        return AESGCM(key).decrypt(raw[:NONCE_LEN], raw[NONCE_LEN:], aad)
    except InvalidTag as exc:
        raise WrongKey from exc


# Recovery key: 32 random bytes shown once as grouped base32, e.g. LMPK-ABCD-EFGH-...
def new_recovery_key() -> tuple[bytes, str]:
    raw = secrets.token_bytes(KEY_LEN)
    text = base64.b32encode(raw).decode("ascii").rstrip("=")
    groups = [text[i : i + 4] for i in range(0, len(text), 4)]
    return raw, "LMPK-" + "-".join(groups)


def parse_recovery_key(text: str) -> bytes:
    cleaned = text.strip().upper().replace(" ", "")
    if cleaned.startswith("LMPK-"):
        cleaned = cleaned[5:]
    cleaned = cleaned.replace("-", "")
    cleaned += "=" * (-len(cleaned) % 8)
    try:
        raw = base64.b32decode(cleaned)
    except ValueError as exc:
        raise WrongKey("malformed recovery key") from exc
    if len(raw) != KEY_LEN:
        raise WrongKey("malformed recovery key")
    return raw


def looks_like_recovery_key(text: str) -> bool:
    return text.strip().upper().startswith("LMPK-")
