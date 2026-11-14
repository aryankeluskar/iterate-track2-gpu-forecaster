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
