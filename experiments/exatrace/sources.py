"""Source facts for calendar entries, read only from data_out/exa_cache (no network).

cached(url)  -> {"url", "published" (earliest Exa publishedDate seen), "title", "text" (contents text if cached, else highlights),
                 "files": [cache files that returned it], "has_full_text"}
support(e)   -> per source of entry e: does its cached text, run through gpuf.loop.extract_announcement (the scout's rule),
                give the entry's effective date and old -> new prices?
rebuild_without_first_source(e, drop=None) -> the entry rebuilt from its remaining sources only (None if nothing remains usable)
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
import re

from gpuf import loop

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "data_out" / "exa_cache"


@functools.lru_cache(maxsize=1)
def _index() -> dict:
    idx = {}
    for p in sorted(CACHE.glob("*.json")):
        r = json.loads(p.read_text())
        res = ((r.get("response") or {}).get("results")) or r.get("results") or []
        for x in res:
            u = x.get("url")
            if not u:
                continue
            d = idx.setdefault(u, {"url": u, "published": None, "title": "", "text": "", "highlights": [], "files": [], "has_full_text": False})
            d["files"].append(p.name)
            pub = (x.get("publishedDate") or "")[:19]
            if pub and (d["published"] is None or pub < d["published"]):
                d["published"] = pub
            d["title"] = d["title"] or (x.get("title") or "")
            if x.get("text") and len(x["text"]) > len(d["text"]):
                d["text"], d["has_full_text"] = x["text"], True
            for h in x.get("highlights") or []:
                if h not in d["highlights"]:
                    d["highlights"].append(h)
    return idx


def cached(url: str) -> dict | None:
    d = _index().get(url)
    if d is None:
        return None
    body = d["text"] if d["has_full_text"] else " | ".join(d["highlights"])
    return {**d, "body": f"{d['title']}. {body}"}


def sources_of(e: dict) -> list[dict]:
    out = []
    for u in [e["url"]] + [x["url"] for x in e.get("also", [])]:
        c = cached(u)
        out.append({"url": u, "primary": u == e["url"], "in_cache": c is not None, "published": c and c["published"],
                    "title": c and c["title"], "has_full_text": bool(c and c["has_full_text"]), "n_cache_files": len(c["files"]) if c else 0})
    return sorted(out, key=lambda s: s["published"] or "9999")


def extract(url: str) -> dict:
    """The scout's extraction on the cached text of one source."""
    c = cached(url)
    if c is None or not c["published"]:
        return {"url": url, "eff": None, "changes": [], "quote": "", "reason": "not in cache or undated"}
    pub = dt.date.fromisoformat(c["published"][:10])
    eff, ch, q = loop.extract_announcement(c["body"], pub)
    return {"url": url, "published": str(pub), "eff": eff and str(eff), "changes": ch, "quote": q,
            "latest_date_in_text": str(loop.latest_date(c["body"], pub)), "reason": None if ch else "no dated old -> new price passage"}


def _match(ch_e: dict, ch_x: list[dict]) -> bool:
    return any(set(c["panel_gpus"]) & set(ch_e["panel_gpus"]) and abs(c["old"] - (ch_e["old"] or -1)) < 1e-6
               and abs(c["new"] - (ch_e["new"] or -1)) < 1e-6 for c in ch_x)


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0")
    s = s + "0" if s.endswith(".") else s
    return rf"\$?\s?{re.escape(s)}0?0?(?!\d)"


def states_change(body: str, ch: dict, window: int = 160) -> bool:
    """The cached text names the GPU and, within `window` characters after it, both the old and the new price."""
    if ch.get("old") is None or ch.get("new") is None:
        return False
    g = ch["gpu"].split(" (")[0]
    tok = g if g.upper().startswith("RTX") else g.split()[0]
    for m in re.finditer(re.escape(tok), body, re.I):
        w = body[m.start():m.start() + window]
        o, n = re.search(_num(ch["old"]), w), re.search(_num(ch["new"]), w)
        if o and n and o.start() < n.start():
            return True
    return False


def states_date(body: str, eff: str, pub: str) -> bool:
    d = loop._day(eff)
    y = int(pub[:4])
    return any(p and abs(p.toordinal() - d) <= 1 for p in (loop._parse_date(x.group(0), y) for x in loop.DATE_RX.finditer(body)))


def support(e: dict) -> list[dict]:
    """Per source: which of the entry's (GPU, old, new) its cached text states (GPU name, then old and new price within 160
    characters, and the effective date anywhere in the text), and what the scout's own extraction rule recovers from it."""
    out = []
    for s in sources_of(e):
        x = extract(s["url"])
        c = cached(s["url"]) or {}
        body = c.get("body", "")
        dated = bool(body) and states_date(body, e["effective_date"], (c.get("published") or "2026")[:10])
        sup = [f"{ch['gpu']} {ch['old']}->{ch['new']}" for ch in e["changes"] if dated and states_change(body, ch)]
        out.append({**s, "states_effective_date": dated, "supports": sup, "n_changes": len(e["changes"]),
                    "scout_rule_eff": x["eff"], "scout_rule_changes": [f"{c_['gpu']} {c_['old']}->{c_['new']}" for c_ in x["changes"]],
                    "scout_rule_quote": x["quote"], "latest_date_in_text": x.get("latest_date_in_text"),
                    "quote_in_cached_text": _quote_found(e, s, body)})
    return out


def _quote_found(e: dict, s: dict, body: str) -> bool | None:
    q = e["quote"] if s["primary"] else next((x.get("quote") for x in e.get("also", []) if x["url"] == s["url"]), None)
    if not q or not body:
        return None
    parts = [p.strip(" '\".") for p in re.split(r"\.\.\.|\|", q) if len(p.strip()) > 25]
    norm = lambda t: re.sub(r"\s+", " ", t).lower()
    return all(norm(p)[:60] in norm(body) for p in parts) if parts else None


def rebuild_without_first_source(e: dict, drop: str | None = None) -> tuple[dict | None, str]:
    """Delete one source (default: the earliest by Exa timestamp) and rebuild the entry from what the remaining sources' cached text
    states (see `support`); a change is usable from the earliest remaining source that states it."""
    sup = support(e)
    gone = drop or sup[0]["url"]
    best = {}
    for s in sup:
        if s["url"] == gone or not s["published"]:
            continue
        for ch in e["changes"]:
            if f"{ch['gpu']} {ch['old']}->{ch['new']}" in s["supports"]:
                k = (ch["gpu"], ch["tier"])
                if k not in best or s["published"][:10] < best[k][0]:
                    best[k] = (s["published"][:10], ch, s["url"])
    if not best:
        return None, f"deleted {gone}; no remaining source states any (GPU, old, new) of the entry with its effective date"
    out = []   # one line per publication date, each change on the line of the earliest remaining source that states it
    for pub in sorted({v[0] for v in best.values()}):
        vs = [v for v in best.values() if v[0] == pub]
        out.append({**e, "published": pub, "changes": [v[1] for v in vs], "url": sorted({v[2] for v in vs})[0], "also": [],
                    "rebuilt_from": sorted({v[2] for v in vs})})
    return out, f"deleted {gone}; rebuilt: " + "; ".join(f"{r['published']} {[c['gpu'] for c in r['changes']]} from {r['rebuilt_from']}" for r in out)
