import pytest

from lm_pocket import crypto

PASS = "correct horse battery"


@pytest.fixture(autouse=True)
def fast_kdf(monkeypatch):
    # Real parameters take ~0.5 s per derivation; tests use cheap ones.
    monkeypatch.setattr(crypto, "DEFAULT_KDF", {**crypto.DEFAULT_KDF, "time_cost": 1, "memory_cost_kib": 8192})
