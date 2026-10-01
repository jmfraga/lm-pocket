import pytest

from conftest import PASS
from lm_pocket.pocket import PocketFolder
from lm_pocket.store import Store, uuid7

PROV = {"method": "manual", "recorded_at": "2026-10-01T00:00:00Z"}


@pytest.fixture
def store(tmp_path):
    folder, _ = PocketFolder.create(tmp_path / "p", PASS)
    s = Store(folder.db_path, folder.unwrap_dek(PASS))
    for sp in ("personal", "portable_professional", "work:acme"):
        s.add_space(sp, sp)
    yield s
    s.close()


def mem(content, space="personal", **kw):
    return {"content": content, "type": "fact", "status": "durable", "space": space,
            "source_type": "user", "provenance": PROV, **kw}


def test_uuid7_is_time_ordered_and_versioned():
    import time

    a = uuid7()
    time.sleep(0.002)  # ordering is guaranteed across milliseconds, not within one
    b = uuid7()
    assert a[14] == "7" and a[19] in "89ab" and a < b


def test_search_is_accent_insensitive_and_space_filtered(store):
    store.add_memory(mem("Le gusta la canción de cuna"))
    store.add_memory(mem("Cancion favorita en el trabajo", space="work:acme"))
    hits = store.search("cancion", spaces=["personal"])
    assert [h["space"] for h in hits] == ["personal"]
    assert store.search("CANCIÓN", spaces=["personal", "work:acme"]).__len__() == 2
    assert store.search("cancion", spaces=[]) == []


def test_search_ignores_candidates(store):
    store.add_memory(mem("propuesta pendiente", status="candidate"))
    assert store.search("propuesta", spaces=["personal"]) == []


def test_fts_follows_updates(store):
    m = store.add_memory(mem("old words"))
    store.update(m["id"], content="new words")
    assert store.search("old", spaces=["personal"]) == []
    assert store.search("new", spaces=["personal"])[0]["id"] == m["id"]


def test_derived_portable_requires_declassification(store):
    with pytest.raises(Exception):
        store.add_memory(mem("lesson", space="portable_professional", source_type="derived", portable=True))
    ok = store.add_memory(mem("lesson", space="portable_professional", source_type="derived", portable=True,
                              declassified_at="2026-10-01T00:00:00Z"))
    assert ok["portable"] is True


def test_unknown_fields_are_preserved(store):
    m = store.add_memory(mem("x", future_field={"a": 1}))
    assert store.get(m["id"])["future_field"] == {"a": 1}


def test_query_with_fts_syntax_is_safe(store):
    store.add_memory(mem("plain text"))
    assert store.search('" OR * NEAR( -- ', spaces=["personal"]) is not None
