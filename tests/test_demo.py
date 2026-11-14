"""Demo page: self-contained, numbers equal their source files, every scored series is in the explorer."""
import csv
import json
import re
from html.parser import HTMLParser

import pandas as pd
import pytest

from gpuf import demo


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs, self.srcs, self.tags, self.ids, self.scripts, self._sid = [], [], [], set(), {}, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        for k in ("src", "srcset", "data", "action", "poster"):
            if k in a:
                self.srcs.append((tag, a[k]))
        if tag == "link":
            self.srcs.append((tag, a.get("href", "")))
        if tag == "script":
            self._sid = a.get("id", "inline")
            self.scripts[self._sid] = ""

    def handle_endtag(self, tag):
        if tag == "script":
            self._sid = None

    def handle_data(self, d):
        if self._sid:
            self.scripts[self._sid] += d


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo") / "index.html"
    demo.build(out)
    text = out.read_text()
    s = Scan()
    s.feed(text)
    s.close()
    return out, text, s, json.loads(s.scripts["explorer-data"]), json.loads(s.scripts["facts-data"])


def test_self_contained(built):
    out, text, s, _, _ = built
    assert out.stat().st_size < 3_000_000
    assert not s.srcs or all(v.startswith("data:") for _, v in s.srcs), s.srcs
    assert "<link" not in text and "@import" not in text and "<iframe" not in text
    style = re.search(r"<style>(.*?)</style>", text, re.S).group(1)
    assert "url(" not in style
    assert all(h.startswith(("https://", "http://", "#")) for h in s.hrefs)
    stripped = re.sub(r'<a href="[^"]*"', "<a", text)
    assert not re.search(r"https?://", stripped), re.search(r".{60}https?://.{60}", stripped)
    assert re.search(r"fetch\(|XMLHttpRequest|import\(|WebSocket|sendBeacon", s.scripts["inline"]) is None
    assert {f"s{i}" for i in range(1, 9)} <= s.ids
    assert sum(h.startswith("http") for h in s.hrefs) >= 9  # the cited sources are links


def test_deterministic(built, tmp_path):
    out, text, *_ = built
    other = tmp_path / "again.html"
    demo.build(other)
    assert other.read_text() == text


def test_numbers_match_sources(built):
    _, text, _, ex, facts = built
    gate = {r["name"]: r for r in demo.jl(demo.P["val_gate"])}
    fh, fn = gate["q10_final_headline"], gate["q11_final_nonhead"]
    # 1. final blend on validation, both looks
    assert facts["final_head_skill"] == round(fh["skill"], 4) and facts["final_non_skill"] == round(fn["skill"], 4)
    assert facts["final_head_drift"] == round(fh["drift_skill"], 4) and facts["final_non_drift"] == round(fn["drift_skill"], 4)
    for v in (fh["skill"], fh["drift_skill"], fn["skill"], fn["drift_skill"]):
        assert f"{v:.3f}" in text
    # 2. loss by cause totals
    with open(demo.P["loss"]) as f:
        tot = next(r for r in csv.DictReader(f) if r["cause"] == "total")
    assert facts["loss_total"] == {k: round(float(tot[f"{k}_loss_over_lv"]), 4) for k in ("S0", "S1", "S2", "S3")}
    # 3. ledger counts
    led = demo.jl(demo.P["ledger"])
    assert facts["ledger_total"] == len(led)
    for k in ("supported", "refuted", "not_significant", "untestable"):
        assert facts[f"ledger_{k}"] == sum(r["status"] == k for r in led)
    # 4. calendar check against the panel and the Exa attribution
    chk = json.loads(demo.P["cal_check"].read_text())
    exa = json.loads(demo.P["exa_head"].read_text())
    assert (facts["cal_hits"], facts["cal_checkable"]) == (chk["b1_hits"], chk["b1_checkable"])
    assert (facts["exa_announced"], facts["exa_events"]) == (exa["n_announced_before"], exa["n_events"])
    # 5. every forecast quantile and the index-quality card in the explorer
    fc = pd.read_csv(demo.P["headline"])
    card = pd.read_csv(demo.P["card"]).set_index("series_id")
    for s in ex["series"]:
        f = fc[fc.series_id == s["id"]].sort_values("horizon_days")
        assert s["fc"] == [[int(r.horizon_days), round(r.q10, 4), round(r.q50, 4), round(r.q90, 4)] for r in f.itertuples()]
        assert s["card"]["frag"] == round(card.loc[s["id"], "fragility_pct"], 4)
        assert s["card"]["offers"] == card.loc[s["id"], "n_offers"]


def test_every_headline_series_in_explorer(built):
    _, _, _, ex, facts = built
    ids = {s["id"] for s in ex["series"]}
    assert ids == set(pd.read_csv(demo.P["headline"]).series_id)
    assert facts["headline_series"] == len(ids)
    assert ex["default"] in ids and all(p[0] in ids for p in ex["presets"])


def test_explorer_panel_reproduces_card(built):
    """The offers drawn for 6 November are the offers behind the median: count and median match the card."""
    _, _, _, ex, _ = built
    for s in ex["series"]:
        if s["kind"] == "panel":
            last = sorted(o["v"][-1] for o in s["offers"] if o["v"][-1] is not None)
            assert len(last) == s["card"]["offers"]
            m = (last[(len(last) - 1) // 2] + last[len(last) // 2]) / 2
            assert m == pytest.approx(s["card"]["median"], abs=1e-3)
            assert all(len(o["v"]) == len(ex["days"]) for o in s["offers"])
        else:
            assert s["rows"] == s["card"]["offers"]
            assert s["origin_median"] == pytest.approx(s["card"]["median"], abs=1e-3)
    assert ex["days"][-1] == "2026-11-06"
