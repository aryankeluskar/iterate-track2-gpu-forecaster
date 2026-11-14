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


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_cli_remember_then_recall_offline(env, monkeypatch, capsys):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    memory.put_audience("gpuf-evidence", identities=["scout", "forecaster"])
    assert memory._cli(["remember", "--as", "scout", "--audience", "gpuf-evidence", "--id", "scout-x", "--timestamp", "2026-10-01T00:00:00Z",
                        "--label", "Evidence: x.com", "--text", "Nebius raises H100 prices"]) == 0
    out = _json(capsys)
    assert out["status"] == "completed" and out["offline"] and out["id"] == "scout-x"
    assert memory._cli(["recall", "--as", "forecaster", "Nebius H100", "--top", "3"]) == 0
    res = _json(capsys)["results"]
    assert [r["source_id"] for r in res] == ["scout-x"] and res[0]["author"] == "scout" and res[0]["occurred_at"].startswith("2026-10-01")
    assert memory._cli(["recall", "--as", "forecaster", "Nebius", "--as-of", "2026-09-30"]) == 0
    assert _json(capsys)["results"] == []
    assert memory._cli(["recall", "--as", "stranger", "Nebius"]) == 0
    assert _json(capsys)["results"] == []


def test_cli_sync_ledger_sends_only_new_or_changed(env, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    led = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("PAST_LEDGER", str(led))
    row = lambda i, st: {"id": i, "agent": "a", "claim": "c", "status": st, "updated_utc": "2026-11-14T10:00:00+00:00"}
    led.write_text(json.dumps(row("H1", "running")) + "\n" + json.dumps(row("H2", "running")) + "\n")
    assert memory._cli(["sync-ledger"]) == 0 and _json(capsys)["sent"] == 2
    assert memory._cli(["sync-ledger"]) == 0 and _json(capsys)["sent"] == 0
    led.write_text(json.dumps(row("H1", "refuted")) + "\n" + json.dumps(row("H2", "running")) + "\n" + json.dumps(row("H3", "running")) + "\n")
    assert memory._cli(["sync-ledger", "--dry"]) == 0 and _json(capsys)["to_send"] == ["exp-H1", "exp-H3"]
    assert memory._cli(["sync-ledger"]) == 0 and _json(capsys)["sent"] == 2


def test_brief_sections_follow_reach(env, monkeypatch, capsys):
    monkeypatch.setenv("PAST_OFFLINE", "1")
    memory.put_audience("gpuf-evidence", identities=["forecaster", "proposer"])
    memory.put_audience("gpuf-failures", identities=["forecaster", "proposer"])
    memory.put_audience("gpuf-experiments", identities=["proposer"])
    memory.ingest([
        {"id": "exp-H1", "audience": "gpuf-experiments", "identity": "experimenter", "timestamp": "2026-11-14T10:00:00+00:00", "label": "Experiment: H1",
         "content": "Hypothesis ledger entry H1\nClaim: tail widening at h7", "metadata": {"agent": "experimenter", "kind": "experiment", "status": "refuted"}},
        {"id": "autopsy-e", "audience": "gpuf-failures", "identity": "autopsy", "timestamp": "2026-10-03T23:59:59Z", "label": "Autopsy: s",
         "content": "Autopsy event: tail at h7", "metadata": {"agent": "autopsy", "kind": "event"}}])
    p = memory.brief("proposer", "tail at h7")
    assert [s["key"] for s in p["sections"] if s["items"]] == ["refuted", "failures"]
    assert p["sections"][0]["items"][0]["author"] == "experimenter" and "exp-H1" in p["briefing"]
    f = memory.brief("forecaster", "tail at h7")
    assert f["sections"][0]["skipped"] and "exp-H1" not in f["briefing"] and "autopsy-e" in f["briefing"]


def test_cli_help_has_examples_and_failures_exit_nonzero(capsys):
    with pytest.raises(SystemExit) as e:
        memory._cli(["recall", "--help"])
    assert e.value.code == 0 and "example:" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        memory._cli(["remember", "--as", "x"])
    assert e.value.code == 2
