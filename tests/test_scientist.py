"""gpuf.scientist and gpuf.store, offline: strict spec validation, the two deletion tests (origin-time facts; the selection
view at a checkpoint), dedupe, a duplicate refused without a test, and a replayed recorded iteration. No network."""
import copy
import json
import urllib.request

import numpy as np
import pandas as pd
import pytest

from gpuf import llm, panel, scientist as sc, splits, store

C = "2026-09-25"


@pytest.fixture(scope="module")
def S():
    return store.load()


@pytest.fixture()
def offline(tmp_path, monkeypatch):
    for k, v in {"GPUF_LLM_OFFLINE": "1", "PAST_OFFLINE": "1", "LOOP_OFFLINE": "1", "SCI_JOURNAL": str(tmp_path / "sj.jsonl"),
                 "PAST_JOURNAL": str(tmp_path / "mj.jsonl")}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("PAST_ALLOW_WRITES", raising=False)
    monkeypatch.setattr(llm, "JOURNAL", tmp_path / "llm.jsonl")

    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    return tmp_path


# ----------------------------------------------------------------------------- spec validation
GOOD = {"when": {"all": [{"fact": "cls", "op": "in", "value": ["marketplace_ask"]}, {"fact": "horizon", "op": ">=", "value": 3}]},
        "do": {"action": "scale_width", "lo": 1.1, "hi": 0.9}}


@pytest.mark.parametrize("bad", [
    {"when": {"fact": "nope", "op": "<", "value": 1}, "do": {"action": "last_zero"}},                       # unknown fact
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "members_only", "members": ["lstm"]}},  # unknown member
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "widen"}},                           # unknown action
    {"when": {"fact": "cls", "op": "==", "value": "marketplace"}, "do": {"action": "last_zero"}},             # unknown category value
    {"when": {"fact": "rows", "op": "in", "value": [1, 2]}, "do": {"action": "last_zero"}},                  # op not allowed for numbers
    {"when": {"fact": "in37", "op": "<", "value": True}, "do": {"action": "last_zero"}},                    # op not allowed for booleans
    {"when": {"fact": "rows", "op": "<", "value": True}, "do": {"action": "last_zero"}},                    # bool is not a number
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "scale_width", "lo": 1.0}},          # missing parameter
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "scale_width", "lo": 1, "hi": 5}},   # out of range
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "last_zero", "w": 1}},              # extra parameter
    {"when": {"fact": "rows", "op": "<", "value": 30, "x": 1}, "do": {"action": "last_zero"}},               # extra key
    {"when": {"all": []}, "do": {"action": "last_zero"}},                                                    # empty list
    {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "last_zero"}, "why": "x"},           # extra top-level key
    {"when": {"any": [{"fact": "rows", "op": ">", "value": i} for i in range(7)]}, "do": {"action": "last_zero"}},  # too many comparisons
])
def test_spec_validation_is_strict(S, bad):
    sc.validate_spec(GOOD, S.cats)
    with pytest.raises(sc.SpecError):
        sc.validate_spec(bad, S.cats)


def test_actions_change_only_their_cells(S):
    V = sc.selection(S, C)
    st = sc.run_system(V, sc.BASE_SYSTEM)
    m = sc.cond_mask(V, GOOD["when"])
    F1 = sc.apply_rule(V, st, GOOD)["F"]
    ch = (np.abs(F1 - st["F"]) > 0).any(1)
    assert ch.any() and not (ch & ~m).any()
    assert (F1[:, 0] <= F1[:, 1]).all() and (F1[:, 1] <= F1[:, 2]).all()


# ----------------------------------------------------------------------------- deletion test 1: origin-time facts
SIDS = ["fastgpu_daily.neocloud_rate_card.H100_SXM_80GB.on_demand.median", "gpurentalprices.marketplace_ask.H100_SXM_80GB.on_demand.median",
        "afhubbard.hyperscaler_spot.H100_80GB.spot.median", "gpurentalprices.neocloud_rate_card.A100_SXM_80GB.on_demand.median"]
ORIG = [splits.DEV[10], splits.DEV[-1]]


@pytest.fixture(scope="module")
def series():
    return store.series_frame()


def _sids(series):
    have = set(series.series_id)
    out = [s for s in SIDS if s in have]
    out += [s for s in sorted(have) if s.startswith("fastgpu_daily.")][:2] + [s for s in sorted(have) if s.startswith("gpurentalprices.")][:2]
    assert sum(panel.supported(s) for s in out) >= 3
    return sorted(set(out))


@pytest.mark.parametrize("mode", ["delete", "corrupt", "control"])
def test_facts_ignore_rows_after_the_origin(series, mode, monkeypatch):
    sids = _sids(series)
    full = panel.load()
    rng = np.random.default_rng(3)
    for o in ORIG:
        pairs = [(s, o) for s in sids]
        ref = store.build_facts(series, pairs)
        late = series.day > o if mode != "control" else series.day == o   # control: change rows ON the origin, facts must change
        plate = full.day > o if mode != "control" else full.day == o
        if mode == "delete":
            alt_s, alt_p = series[~late], full[~plate]
        else:
            alt_s = series.assign(value=np.where(late, series.value * rng.uniform(0.3, 3.0, len(series)), series.value),
                                  n_providers=np.where(late, rng.integers(1, 30, len(series)), series.n_providers))
            extra = series[late].drop_duplicates("series_id").assign(day=lambda d: d.day + 1, value=99.0)
            alt_s = pd.concat([alt_s, extra]).sort_values(["series_id", "day"], kind="stable").reset_index(drop=True)
            alt_p = full.assign(price=np.where(plate, full.price * rng.uniform(0.3, 3.0, len(full)), full.price))
            fake = full[plate].drop_duplicates(["src", "cls", "gpu", "tier"]).assign(key="FAKE#0", provider="verda", price=0.01)
            alt_p = pd.concat([alt_p, fake], ignore_index=True)
        panel._index.cache_clear()
        monkeypatch.setattr(panel, "load", lambda alt=alt_p.reset_index(drop=True): alt)
        got = store.build_facts(alt_s.reset_index(drop=True), pairs)
        monkeypatch.undo()
        panel._index.cache_clear()
        if mode == "control":
            assert not ref.equals(got)
        else:
            pd.testing.assert_frame_equal(ref, got)


# ----------------------------------------------------------------------------- deletion test 2: the selection view
def _view_outputs(St):
    V = sc.selection(St, C)
    st = sc.run_system(V, sc.BASE_SYSTEM)
    F1 = sc.apply_rule(V, st, GOOD)["F"]
    return {"report": sc.failure_report(V, st["F"], sc.BASE_SYSTEM, C), "facts": sc.facts_text(V), "gate": sc.gate(V, st["F"], F1),
            "breakdown": sc.breakdown(V, st["F"], {"by": ["p_offers", "horizon"], "where": {"fact": "has_panel", "op": "==", "value": True}}),
            "query": sc._query_from(V, st["F"]), "F": st["F"].tobytes()}


@pytest.mark.parametrize("mode", ["delete", "corrupt"])
def test_selection_view_ignores_later_cells(S, mode):
    ref = _view_outputs(S)
    df = S.df.copy()
    late = (df.origin_day > sc._o(C) - 7).to_numpy()
    assert late.sum() > 1000
    if mode == "delete":
        alt = df[~late]
    else:
        rng = np.random.default_rng(5)
        for c in [c for c in df.columns if c.endswith(("_q10", "_q50", "_q90"))] + ["y", "baseline_loss", "last", "rows", "vol30", "p_offers"]:
            df.loc[late, c] = df.loc[late, c].to_numpy() * rng.uniform(0.2, 5.0, late.sum())
        for c in ("in37", "gate14", "has_panel"):
            df.loc[late, c] = ~df.loc[late, c].astype(bool)
        df.loc[late, "cause"] = "entry"
        alt = df
    assert _view_outputs(store.Store(alt)) == ref


def test_store_refuses_held_back_origins(S):
    with pytest.raises(store.HeldBack):
        store.check_origins([splits.VAL[0]])
    with pytest.raises(PermissionError):
        sc.selection(S, "2026-10-20")


# ----------------------------------------------------------------------------- dedupe
def test_canonical_forms_and_same_idea(S):
    V = sc.selection(S, C)
    a = {"when": {"all": [{"fact": "horizon", "op": ">=", "value": 3}, {"any": [{"fact": "cls", "op": "in", "value": ["marketplace_ask"]}]}]},
         "do": {"action": "drop_members", "members": ["gbm", "chronos"]}}
    b = {"when": {"all": [{"fact": "cls", "op": "==", "value": "marketplace_ask"}, {"not": {"not": {"fact": "horizon", "op": ">=", "value": 3.0}}}]},
         "do": {"action": "drop_members", "members": ["chronos", "gbm"]}}
    assert sc.spec_hash(a) == sc.spec_hash(b) and sc.same_idea(V, a, b)
    r1 = {"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "shrink_to_last", "w": 0.5}}
    r2 = {"when": {"fact": "rows", "op": "<", "value": 31}, "do": {"action": "shrink_to_last", "w": 0.53}}
    r3 = {"when": {"fact": "rows", "op": "<", "value": 31}, "do": {"action": "shrink_to_last", "w": 0.7}}
    r4 = {"when": {"fact": "rows", "op": "<", "value": 31}, "do": {"action": "scale_width", "lo": 0.5, "hi": 0.5}}
    r5 = {"when": {"fact": "rows", "op": ">=", "value": 30}, "do": {"action": "shrink_to_last", "w": 0.5}}
    assert sc.spec_hash(r1) != sc.spec_hash(r2) and sc.same_idea(V, r1, r2)       # same cells (Jaccard >= 0.9), parameter within 0.05
    assert not sc.same_idea(V, r1, r3) and not sc.same_idea(V, r1, r4) and not sc.same_idea(V, r1, r5)
    known = [{"id": "auto-x-i1", "verdict": "rejected", "spec": r1}]
    assert sc.find_duplicate(V, r2, known)["id"] == "auto-x-i1" and sc.find_duplicate(V, r3, known) is None


def test_duplicate_is_refused_without_a_test(S, offline, monkeypatch):
    dup = {"when": {"fact": "rows", "op": "<", "value": 31}, "do": {"action": "shrink_to_last", "w": 0.52}}
    replies = iter([{"breakdowns": [{"by": ["rows"], "where": None}], "search_query": "zzz scientist test query", "focus": "f"},
                    {"claim": "c", "mechanism": "m", "spec": dup, "falsification": "f", "prior_ids_used": [], "expects": "e"},
                    {"claim": "c2", "mechanism": "m", "spec": dup, "falsification": "f", "prior_ids_used": [], "expects": "e"}])
    monkeypatch.setattr(sc, "_ask", lambda p, tag, salt: (next(replies), {"key": tag, "cached": True, "seconds": 0.0, "prompt_tokens_est": len(p) // 4, "reply": ""}))
    V = sc.selection(S, C)
    own = [{"mem_id": "auto-t-i1", "verdict": "rejected", "checkpoint": C, "hypothesis": {"claim": "x"}, "gate": None,
            "canonical": sc.canon({"when": {"fact": "rows", "op": "<", "value": 30}, "do": {"action": "shrink_to_last", "w": 0.5}}), "dedupe": {}}]
    ctx0 = {"run_id": "t", "checkpoint": C, "memory": "none", "rep": "t", "exec_id": "t"}
    row, after = sc.iterate(V, copy.deepcopy(sc.BASE_SYSTEM), ctx0, 2, own)
    assert row["verdict"] == "duplicate" and row["gate"] is None and row["duplicates_avoided"] == 2
    assert row["dedupe"]["duplicate_of"] == "auto-t-i1" and after == sc.BASE_SYSTEM and row["human_interventions"] == 0
    assert row["memory_write"]["offline"] and row["prior"]["skipped"] == "offline_uncached"


# ----------------------------------------------------------------------------- replay of a recorded iteration
def test_recorded_iteration_replays_offline(S, offline):
    execs = sc.executions(sc.read_journal(sc.JOURNAL))
    rid = next((r for r in ("c0918-pastdev-wf", "c0925-none-r1") if r in execs), None)
    if rid is None:
        pytest.skip("no recorded run in data_out/scientist_journal.jsonl yet")
    import os
    os.environ["SCI_JOURNAL"] = str(sc.JOURNAL)   # replay reads the real journal, then writes to a temp one
    res = sc.replay(rid, max_iter=1, store=S)
    assert res["identical_rows"] and res["iterations_compared"] == 1
