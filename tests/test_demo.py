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
    led = [r for r in demo.jl(demo.P["ledger"]) if not r["id"].startswith("L")]
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


def test_loop_reruns_not_counted(built):
    _, text, _, _, facts = built
    rows = demo.jl(demo.P["ledger"])
    assert facts["ledger_total"] == sum(not r["id"].startswith("L") for r in rows)
    assert not re.search(r'data-id="L', text)
    assert facts["ledger_plain_missing"] == sorted(set(r["id"] for r in rows if not r["id"].startswith("L")) - set(json.loads(demo.P["plain"].read_text())))


def test_no_90_interval_on_validation_numbers(built):
    _, text, *_ = built
    outside_longrun = re.sub(r"<section id=s7 .*?</section>", "", text, flags=re.S)
    # allowed only where a quoted record says the ranges are *not* 90% intervals
    assert not re.search(r"(?<!not )90% intervals?", outside_longrun), re.search(r".{80}90% interval.{40}", outside_longrun)
    assert not re.search(r"90% interval[^<]{0,12}[+−-]?\d", outside_longrun)
    assert "rough range" in text.lower()


def test_clean_number_leads_and_strict_tests(built):
    _, text, _, _, facts = built
    gate = {r["name"]: r for r in demo.jl(demo.P["val_gate"])}
    s1 = re.search(r"<section id=s1 .*?</section>", text, re.S).group(0)
    assert s1.index(f"{gate['q11_final_nonhead']['skill']:.3f}") < s1.index(f"{gate['q10_final_headline']['skill']:.3f}")
    st = json.loads(demo.P["stats"].read_text())
    assert facts["bh_kept"] == sorted(st["bh10_pass_logged_p_one_sided"])
    assert facts["bh_kept_gauss"] == sorted(st["bh10_pass_p_sim_gauss_devacf"])
    assert facts["bh_kept_boot"] == sorted(st["bh10_pass_p_sim_block_bootstrap"])
    for v in st["directions"].values():
        ps = sorted((v["val"]["p_sim_gauss_devacf"], v["val"]["p_sim_block_bootstrap"]))
        assert f"{ps[0]:.3f} to {ps[1]:.3f}" in text
    assert "id=s1k" in text and "What to keep in mind" in text


def test_longrun_and_score_caveats_match_files(built):
    _, text, _, _, facts = built
    s7 = re.search(r"<section id=s7 .*?</section>", text, re.S).group(0)
    s1k = re.search(r"<section id=s1k .*?</section>", text, re.S).group(0)
    paths = pd.read_csv(demo.P["longrun_paths"])
    paths = paths[paths.base == "v3_unique"]
    h100 = paths[(paths.chip == "H100") & (paths.weights == "frozen") & (paths.h_months == 24)].iloc[0]
    a100 = paths[(paths.chip == "A100") & (paths.weights == "frozen")].iloc[0]
    assert f"{h100.level_nov2026:.2f}" in s7 and "2.28" in s7
    assert f"{a100.level_nov2026:.2f}" in s7
    assert "3.49" not in s7 and "2.35 today" not in s7
    late = json.loads(demo.P["late"].read_text())["headline"]
    late_eq = json.loads(demo.P["hill_late"].read_text())
    hill = json.loads(demo.P["hill_agg"].read_text())["slices"]["h1"]
    assert facts["keep_late_pooled"] == late["final"]["pooled_skill"]
    assert facts["keep_late_mean"] == round(late_eq["final"]["mean"], 4)
    assert facts["keep_h1_mean"] == round(hill["final"]["mean"], 4)
    assert f"{late['final']['pooled_skill']:.3f}" in s1k
    assert f"{late_eq['final']['mean']:.3f}" in s1k
    assert "0.1109" in s1k and "0.1419" in s1k
    origins = late["by_origin"]
    beat = sum(origins[day]["final"] > origins[day]["drift"] for day in origins)
    assert f"{beat} of {len(origins)}" in s1k


def test_hashes_shown_equal_files(built):
    _, text, *_ = built
    for k in ("headline", "all", "members"):
        rel = str(demo.P[k].relative_to(demo.ROOT))
        m = re.search(rf"<code>{re.escape(rel)}</code></td><td class=h><code>([0-9a-f]{{64}})</code>", text)
        assert m and m.group(1) == demo.sha(demo.P[k])
    for _, paths in demo.EVIDENCE:
        assert all((demo.ROOT / p).exists() for p in paths)
