import filecmp
import shutil
import time
from pathlib import Path

import pytest

from conftest import PASS
from lm_pocket import crypto
from lm_pocket.pocket import PocketFolder
from lm_pocket.service import BadRequest, Denied, Locked, NotFound, PocketService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def svc(tmp_path):
    PocketFolder.create(tmp_path / "LM-Pocket", PASS)
    s = PocketService(tmp_path / "LM-Pocket", watch_interval=0.05)
    s.unlock(PASS)
    s.load_sample()
    yield s
    s.lock()


def ids_by_space(svc):
    return {m["id"]: m["space"] for m in svc.store.list(limit=1000)}


def test_packaged_sample_matches_examples():
    for name in ("memories.jsonl", "spaces.json", "policies.json"):
        assert filecmp.cmp(ROOT / "examples/sample-export" / name, ROOT / "src/lm_pocket/sample" / name, shallow=False)


def test_wrong_passphrase_keeps_pocket_locked(tmp_path):
    PocketFolder.create(tmp_path / "p", PASS)
    s = PocketService(tmp_path / "p")
    with pytest.raises(crypto.WrongKey):
        s.unlock("wrong passphrase!!")
    assert not s.unlocked
    with pytest.raises(Locked):
        s.call("work", "search_memories", {"query": ""})


def test_work_profile_never_sees_personal_or_other_work(svc):
    hits = svc.call("work", "search_memories", {"query": "", "limit": 50})
    assert hits and {h["space"] for h in hits} == {"portable_professional"}
    assert {s["id"] for s in svc.call("work", "list_spaces")} == {"portable_professional"}
    for mid, space in ids_by_space(svc).items():
        if space != "portable_professional":
            with pytest.raises(NotFound):
                svc.call("work", "get_memory", {"id": mid})
    with pytest.raises(Denied):
        svc.call("work", "search_memories", {"query": "", "space": "personal"})
    pkg = svc.call("work", "get_context", {"topic": "", "max_tokens": 2000})
    assert "Valparaíso" not in pkg["text"] and "Lucía" not in pkg["text"]


def test_personal_profile_reads_personal(svc):
    hits = svc.call("personal", "search_memories", {"query": "valparaiso"})
    assert hits[0]["space"] == "personal"


def test_candidates_are_invisible_over_mcp(svc):
    cand = [m for m in svc.store.list(status="candidate", limit=100)]
    assert cand
    with pytest.raises(NotFound):
        svc.call("personal", "get_memory", {"id": cand[0]["id"]})


def test_unknown_profile_denied(svc):
    with pytest.raises(Denied):
        svc.call("root", "search_memories", {})


def test_propose_lands_as_candidate_in_profile_space(svc):
    r = svc.call("work", "propose_memory", {"content": "Prefers async standups", "type": "preference",
                                             "provider": "anthropic", "model": "claude"}, client="claude-code")
    assert r["status"] == "candidate" and r["space"] == "portable_professional"
    m = svc.store.get(r["id"])
    assert m["status"] == "candidate" and m["source_type"] == "llm"
    assert m["provenance"]["method"] == "mcp" and m["provenance"]["client"] == "claude-code"
    assert svc.call("work", "search_memories", {"query": "standups"}) == []
    again = svc.call("work", "propose_memory", {"content": "prefers   ASYNC standups", "type": "preference"})
    assert again == {"status": "already_known", "id": r["id"]}


def test_propose_validates_and_rate_limits(svc, monkeypatch):
    with pytest.raises(BadRequest):
        svc.call("work", "propose_memory", {"content": "x", "type": "secret"})
    with pytest.raises(BadRequest):
        svc.call("work", "propose_memory", {"content": "x", "space": "personal"})  # cannot choose the space
    monkeypatch.setattr("lm_pocket.service.PROPOSALS_PER_HOUR", 2)
    svc.call("work", "propose_memory", {"content": "one"})
    svc.call("work", "propose_memory", {"content": "two"})
    with pytest.raises(Denied):
        svc.call("work", "propose_memory", {"content": "three"})


def test_review_approves_with_edit_and_rejects(svc):
    a = svc.call("work", "propose_memory", {"content": "Likes small PRs"})["id"]
    b = svc.call("work", "propose_memory", {"content": "Hates Mondays"})["id"]
    assert svc.review([a], [b], {a: "Likes small, focused PRs"}) == {"approved": 1, "rejected": 1}
    hit = svc.call("work", "search_memories", {"query": "focused"})
    assert hit[0]["id"] == a and hit[0]["edited_by_user_at"]
    assert svc.store.get(b)["status"] == "rejected"


def test_lock_stops_mcp(svc):
    svc.lock()
    with pytest.raises(Locked):
        svc.call("work", "search_memories", {"query": ""})


def test_unplug_locks_within_watch_interval(svc, tmp_path):
    shutil.move(str(tmp_path / "LM-Pocket"), str(tmp_path / "elsewhere"))  # simulates the USB going away
    deadline = time.time() + 2
    while svc.unlocked and time.time() < deadline:
        time.sleep(0.02)
    assert not svc.unlocked
    with pytest.raises(Locked, match="disappeared"):
        svc.call("work", "search_memories", {"query": ""})


def test_unplug_detected_even_before_watcher_tick(tmp_path):
    PocketFolder.create(tmp_path / "p", PASS)
    s = PocketService(tmp_path / "p", watch_interval=60)
    s.unlock(PASS)
    shutil.move(str(tmp_path / "p"), str(tmp_path / "gone"))
    with pytest.raises(Locked):
        s.call("work", "get_profile")


def test_recovery_key_unlocks(tmp_path):
    _, recovery = PocketFolder.create(tmp_path / "p", PASS)
    s = PocketService(tmp_path / "p")
    s.unlock(recovery.lower())
    assert s.unlocked
    assert s.store.audit_events(event="pocket_unlocked")[0]["detail"]["via"] == "recovery_key"
    s.lock()


def test_audit_records_events_without_content(svc):
    svc.call("work", "search_memories", {"query": "very private words"})
    ev = svc.store.audit_events(event="memories_retrieved")[0]
    assert ev["profile"] == "work" and "very private" not in str(ev)
    assert ev["detail"]["query_chars"] == len("very private words")
