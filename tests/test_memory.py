"""past.dev memory client: offline round trip, key hygiene, dry run. No network is ever used."""
import io
import json
import urllib.error
import urllib.request

import pytest

from gpuf import memory

FAKE = "past_sk_TESTKEY_do_not_leak_123456"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAST_JOURNAL", str(tmp_path / "j.jsonl"))
    monkeypatch.setenv("PAST_API_KEY", FAKE)
    monkeypatch.delenv("PAST_ALLOW_WRITES", raising=False)
    monkeypatch.setattr(memory, "_dry", False)

    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    return tmp_path / "j.jsonl"


ITEMS = [
    {"id": "scout-a", "content": "Nebius raises on-demand H100 prices to 4.50", "label": "AskGPU", "timestamp": "2026-10-01T00:00:00Z", "audience": "gpuf-evidence"},
    {"id": "scout-b", "content": "Nebius repricing follow-up on B300", "label": "News", "timestamp": "2026-10-10T00:00:00Z", "audience": "gpuf-evidence"},
]


def test_offline_round_trip_and_replay(env, monkeypatch):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    memory.put_audience("gpuf-evidence", identities=["proposer"], agent="setup")
    r = memory.ingest(ITEMS, agent="scout")
    assert memory.wait(r["ingestionId"])["status"] == "completed"
    a = memory.recall("Nebius H100 repricing", "proposer", agent="proposer")
    assert {x["sources"][0]["sourceId"] for x in a["results"]} == {"scout-a", "scout-b"}
    b = memory.recall("Nebius H100 repricing", "proposer", agent="proposer")
    assert b == a
    assert [j["replayed"] for j in map(json.loads, env.read_text().splitlines()) if j["op"] == "recall"] == [False, True]
    # a stranger outside the audience sees nothing
    assert memory.recall("Nebius H100 repricing", "stranger")["results"] == []


def test_recall_as_of_is_date_bounded(monkeypatch):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    memory.put_audience("gpuf-evidence", identities=["forecaster"])
    memory.ingest(ITEMS, agent="scout")
    res = memory.recall("Nebius", "forecaster", as_of="2026-10-05")["results"]
    assert [x["sources"][0]["sourceId"] for x in res] == ["scout-a"]


def test_key_never_in_journal_or_exceptions(env, monkeypatch):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    memory.put_identity("proposer", {"role": "reader"}, agent="setup")
    memory.ingest(ITEMS, agent="scout")
    memory.recall("x", "proposer")
    assert FAKE not in env.read_text()
    monkeypatch.delenv("PAST_OFFLINE")
    with pytest.raises(memory.PastError) as e:
        memory.recall("x", "proposer")  # guard refuses before any network call
    assert FAKE not in str(e.value)
    bad = [{**ITEMS[0], "content": f"leak {FAKE}", "timestamp": "2026-10-01"}]
    with pytest.raises(memory.PastError) as e2:
        memory.ingest(bad)
    assert FAKE not in str(e2.value) and FAKE not in repr(e2.value)

    def fail(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "x", {}, io.BytesIO(json.dumps({"code": "unauthorized", "debugMessage": f"bad key {FAKE}"}).encode()))

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(memory.PastError) as e3:
        memory.usage()
    assert FAKE not in str(e3.value) and e3.value.code == "unauthorized"


def test_dry_run_sends_nothing(env, capsys, tmp_path):
    f = tmp_path / "in.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in [{"op": "audience", "slug": "gpuf-evidence", "identities": ["proposer"]}, *ITEMS]))
    assert memory._cli(["dry-run", str(f)]) == 0
    out = capsys.readouterr().out
    assert "/api/v1/audiences/gpuf-evidence" in out and "/api/v1/ingest/batch" in out and FAKE not in out
    assert not env.exists()


def test_live_writes_need_explicit_opt_in():
    with pytest.raises(memory.PastError, match="PAST_ALLOW_WRITES"):
        memory.ingest(ITEMS)
