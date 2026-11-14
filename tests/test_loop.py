"""gpuf.loop: every step runs offline (LOOP_OFFLINE=1, PAST_OFFLINE=1) from the Exa cache and the memory journal, with the
network disabled; forecast refuses a validation origin; no key reaches the journals. Real files are copied to a temp dir."""
import io
import json
import pathlib
import shutil
import urllib.request
from contextlib import redirect_stdout

import pytest

from gpuf import ledger, loop

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAKE_EXA, FAKE_PAST = "exa-FAKE-KEY-0123456789abcdef", "past_sk_FAKE_do_not_leak_987654"
CLAIM = ("when an offer leaves a small panel the posted median steps to the neighbouring offer and does not revert, "
         "so the lower and upper tails should sit on the one-offer-out medians")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp("loop")
    for src, name in ((ROOT / "data_out/memory_journal.jsonl", "mj.jsonl"), (ROOT / "data_out/ledger.jsonl", "ledger.jsonl"),
                      (ROOT / "data_out/repricing_calendar.jsonl", "cal.jsonl")):
        shutil.copy(src, d / name)
    with pytest.MonkeyPatch.context() as mp:
        for k, v in {"LOOP_OFFLINE": "1", "PAST_OFFLINE": "1", "LOOP_JOURNAL": str(d / "lj.jsonl"), "LOOP_CALENDAR": str(d / "cal.jsonl"),
                     "LOOP_RUNS": str(d / "runs"), "PAST_JOURNAL": str(d / "mj.jsonl"), "PAST_LEDGER": str(d / "ledger.jsonl"),
                     "EXA_API_KEY": FAKE_EXA, "PAST_API_KEY": FAKE_PAST}.items():
            mp.setenv(k, v)
        mp.delenv("PAST_ALLOW_WRITES", raising=False)

        def boom(*a, **k):
            raise AssertionError("network used")

        mp.setattr(urllib.request, "urlopen", boom)
        mp.setattr(ledger, "PATH", d / "ledger.jsonl")
        yield d


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = loop.main(list(argv))
    return rc, json.loads(buf.getvalue())


def test_steps_offline(env):
    rc, a = run("autopsy", "--system", "mix")
    assert rc == 0 and a["n_cells"] == 4278 and abs(a["dev_skill"] - 0.1691) < 1e-3
    assert a["labels"].startswith("shipped") and a["memory"]["offline"] and a["memory"]["sent"] == 8
    assert {r["cause"] for r in a["table"]} == set(loop.CAUSES) and abs(sum(r["residual_share"] for r in a["table"]) - 1) < 1e-3

    rc, s = run("scout", "--as-of", "2026-10-06", "--max-usd", "1")
    assert rc == 0 and s["new_calls"] == {"search": 0, "contents": 0} and s["cost_usd_this_run"] == 0
    assert s["cache_hits"]["search"] == s["searches"] > 0 and s["skipped_offline_uncached"]["search"] == 0
    assert not s["new_calendar_entries"]          # the iteration's entry is already in the calendar copy

    rc, p = run("prior", "--claim", CLAIM)
    assert rc == 0 and p["sources"] and p["new_calls"]["search"] == 0 and p["recommendation"].startswith("already tested here")
    assert all(x["date"] <= "2026-11-06" for x in p["sources"])

    rc, pr = run("propose")
    assert rc == 0 and pr["autopsy_of"] == "mix" and len(pr["ranked"]) == len(loop.CAUSES)

    rc, g = run("gate", "--name", "T-loop-drift", "--candidate", "drift")
    assert rc == 0 and g["status"] == "refuted" and g["all"]["d"] < 0 and g["memory_sync"]["offline"]
    assert any(e["id"] == "T-loop-drift" for e in ledger.load())
    assert "T-loop-drift" not in (ROOT / "data_out/ledger.jsonl").read_text()

    out = env / "fc.csv"
    rc, f = run("forecast", "--origin", "2026-10-06", "--method", "drift", "--out", str(out))
    assert rc == 0 and f["scored"] is False and f["rows"] == 111 and out.exists()
    assert "loss" not in out.read_text().splitlines()[0]
    assert "nebius 2026-10-01" in f["calendar_check"]["usable_local"]

    rc, st = run("status")
    assert rc == 0 and st["calendar"]["entries"] >= 9 and st["exa_spend_usd"]["total"] > 0
    steps = [json.loads(x)["step"] for x in (env / "lj.jsonl").read_text().splitlines()]
    assert steps == ["autopsy", "scout", "prior", "propose", "gate", "forecast", "status"]


def test_forecast_refuses_validation_origin(env):
    out = env / "val.csv"
    rc, r = run("forecast", "--origin", "2026-10-20", "--method", "drift", "--out", str(out))
    assert rc == 2 and r["refused"].startswith("REFUSED") and not out.exists()


def test_no_key_in_journals(env):
    keys = {"fake_exa": FAKE_EXA, "fake_past": FAKE_PAST}
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                n, _, v = line.partition("=")
                if n.strip() in ("EXA_API_KEY", "PAST_API_KEY", "PAST_DEV_API_KEY") and len(v.strip()) > 6:
                    keys["real_" + n.strip()] = v.strip().strip('"').strip("'")
    texts = [(env / n).read_text() for n in ("lj.jsonl", "mj.jsonl") if (env / n).exists()]
    texts.append((ROOT / "data_out/loop_journal.jsonl").read_text() if (ROOT / "data_out/loop_journal.jsonl").exists() else "")
    leaked = [n for n, k in keys.items() if any(k in t for t in texts)]
    assert not leaked


# A page Exa dates 20 September whose text carries an update dated 2 November (fixture, not a real page)
LATE_TITLE = "Nebius raises on-demand GPU prices"
LATE_TEXT = ("Nebius raises on-demand GPU prices. Effective October 1, Nebius will raise the H100 from $3.85 to $4.50 per GPU-hour. "
             "Updated November 2, 2026: the new rates now apply in every region.")


def test_scout_eligibility_rejects_later_dated_content():
    from gpuf.loop import _calsys
    P = _calsys()[1].P
    pub = loop.dt.date(2026, 9, 20)
    early = loop.assess(LATE_TITLE, LATE_TEXT, pub, loop.dt.date(2026, 9, 25), P, "nebius", False, "https://example.org/nebius")
    assert not early["eligible"] and "edited after the as-of date" in early["why"]
    assert early["published"] == "2026-09-20" and early["latest_date_in_text"] == "2026-11-02" and early["effective_date"] == "2026-10-01"
    assert early["known"] == "2026-11-02"
    late = loop.assess(LATE_TITLE, LATE_TEXT, pub, loop.dt.date(2026, 11, 6), P, "nebius", False, "https://example.org/nebius")
    assert late["eligible"] and late["changes"][0]["old"] == 3.85 and late["changes"][0]["new"] == 4.5
    # the memory-write path uses the same decision: nothing is written for the early as-of, and the record for the late one
    # is timed by its availability date and carries the four dates separately
    ev, rej = loop.evidence_items([dict(early, found_for=[])], loop.dt.date(2026, 9, 25), set(), 15)
    assert ev == [] and rej == {"text carries a date after 2026-09-25": 1}
    ev, rej = loop.evidence_items([dict(late, found_for=[])], loop.dt.date(2026, 11, 6), set(), 15)
    md = ev[0]["metadata"]
    assert len(ev) == 1 and ev[0]["timestamp"].startswith("2026-11-02") and md["published"] == "2026-09-20"
    assert md["latest_date_in_text"] == "2026-11-02" and md["effective_date"] == "2026-10-01" and md["usable_from"] == "2026-11-02"
    # first day the new H100 price shows in the offer rows (experiments/calendar/results/b1_panel_check.csv: Oct 1 and Oct 2)
    assert md["first_observed"] == {"fastgpu_daily": "2026-10-02", "gpurentalprices": "2026-10-01"}


def test_scout_eligibility_rejects_undated_passages_and_evergreen():
    P = loop._calsys()[1].P
    pub, ao = loop.dt.date(2026, 8, 11), loop.dt.date(2026, 10, 6)
    j = loop.assess("Nebius Q2 earnings preview", "Nebius Q2 earnings preview. May 13th: Q1 management guidance.", pub, ao, P, "nebius")
    assert not j["eligible"] and j["why"].startswith("no passage")
    j = loop.assess("H100 Pricing (2026): per-hour cost", LATE_TEXT, pub, ao, P, "nebius")
    assert not j["eligible"] and j["why"].startswith("evergreen")


def test_trace_sources_reproduce_from_cache(env):
    """experiments/exatrace: the source facts behind the two events that change forecasts come from data_out/exa_cache alone
    (network disabled by the env fixture), and deleting the only Jarvislabs source leaves nothing to rebuild the entry from."""
    import sys
    sys.path.insert(0, str(ROOT / "experiments" / "exatrace"))
    import sources as S
    cal = {f"{e['provider']} {e['effective_date']}": e for e in map(json.loads, (ROOT / "data_out/repricing_calendar.jsonl").read_text().splitlines())}
    neb = {s["url"]: s for s in S.support(cal["nebius 2026-10-01"])}
    lb = neb["https://longbridge.com/en/topics/100000000903151"]
    assert lb["published"].startswith("2026-09-16") and lb["states_effective_date"] and len(lb["supports"]) == 4 and lb["quote_in_cached_text"]
    jl = S.support(cal["jarvislabs 2026-10-05"])
    assert len(jl) == 1 and jl[0]["published"].startswith("2026-09-24") and len(jl[0]["supports"]) == 3
    assert S.rebuild_without_first_source(cal["jarvislabs 2026-10-05"])[0] is None
    rebuilt, _ = S.rebuild_without_first_source(cal["nebius 2026-10-01"], drop=lb["url"])
    assert [(r["published"], sorted(c["gpu"] for c in r["changes"])) for r in rebuilt] == [("2026-09-16", ["B300"]), ("2026-09-28", ["B200", "H100", "H200"])]


def test_prior_as_of_bounds_search_and_recall(env):
    rc, p = run("prior", "--claim", CLAIM)
    assert rc == 0 and p["as_of"] == "2026-11-06" and not p["bounded_recall_and_ledger"]
    assert all(b["endPublishedDate"] == "2026-11-06T23:59:59Z" for b in p["exa_requests"].values())
    rc, h = run("prior", "--claim", CLAIM, "--as-of", "2026-09-25")
    assert rc == 0 and h["bounded_recall_and_ledger"] and h["new_calls"]["search"] == 0
    assert all(b["endPublishedDate"] == "2026-09-25T23:59:59Z" for b in h["exa_requests"].values())
    assert all(s["date"] <= "2026-09-25" for s in h["sources"])
    assert all(e["updated_utc"][:10] <= "2026-09-25" for e in ledger.load() if e["id"] in {x["hypothesis"] for x in h["ledger_nearest"]})
    rec = [json.loads(x) for x in (env / "mj.jsonl").read_text().splitlines() if '"recall"' in x]
    last = [r for r in rec if r["op"] == "recall" and r["request"]["body"].get("identity") == "proposer"][-1]
    assert last["request"]["body"]["queryTimestamp"] == "2026-09-25T23:59:59Z"
    rows, _ = loop._recall(CLAIM, "proposer", as_of="2026-09-25", limit=40)
    assert all(str(r.get("occurred_at"))[:10] <= "2026-09-25" for r in rows)
    with pytest.raises(SystemExit):
        run("prior", "--claim", CLAIM, "--as-of", "2026-11-07")
