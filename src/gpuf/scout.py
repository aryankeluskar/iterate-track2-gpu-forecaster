"""Exa scout: dated web search with an on-disk cache, and a leak-safe event signal for a forecast origin.

Every search is restricted to pages published inside one calendar day (startPublishedDate = endPublishedDate = that day),
so the signal for an origin is built only from days <= origin. Responses are cached under data_out/exa_cache so a
backtest is reproducible and costs nothing to rerun. The key is read from EXA_API_KEY (environment or ../.env).

Known limit, stated in the README: Exa's publishedDate is the page's own date. An evergreen page that is edited later keeps
an early date, so its *text* can contain later information. The signal therefore uses only the count of dated hits whose
title or highlight matches a price-change pattern, and `python -m gpuf.scout audit` lists every hit used.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "data_out" / "exa_cache"
QUERIES = (
    "GPU cloud provider raises or cuts GPU rental prices per hour",
    "H100 H200 B200 on-demand GPU price change announcement neocloud",
    "GPU compute shortage or oversupply rental price news",
)
UP = re.compile(r"\b(rais\w+|hik\w+|increas\w+|surg\w+|jump\w*|soar\w*|shortage|spik\w+|climb\w*|up \d+%|\+\d+%)", re.I)
DOWN = re.compile(r"\b(cut\w*|slash\w*|drop\w*|fall\w*|fell|declin\w+|lower\w*|cheaper|price war|oversupply|glut|down \d+%|-\d+%)", re.I)
PRICE = re.compile(r"(price|pricing|\$\s?\d|per hour|/hr|rate card|rental)", re.I)
GPU = re.compile(r"(gpu|h100|h200|b200|b300|a100|l40s|rtx|nvidia|neocloud|coreweave|lambda|nebius|runpod|vast\.ai|crusoe)", re.I)


def _key() -> str:
    k = os.environ.get("EXA_API_KEY")
    if not k:
        for p in (ROOT / ".env", ROOT.parent / ".env"):
            if p.exists():
                for line in p.read_text().splitlines():
                    if line.startswith("EXA_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        raise RuntimeError("EXA_API_KEY is not set")
    return k


def search_day(query: str, day: dt.date, n: int = 10) -> dict:
    """One Exa search limited to pages published on `day`. Cached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{query}|{day}|{n}".encode()).hexdigest()[:16]
    path = CACHE / f"{day}_{h}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = {"query": query, "type": "auto", "numResults": n,
            "startPublishedDate": f"{day}T00:00:00Z", "endPublishedDate": f"{day}T23:59:59Z",
            "contents": {"highlights": True}}
    req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-api-key": _key(), "User-Agent": "gpuf-scout"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read())
            break
        except Exception as e:  # rate limit or network: back off, then give up loudly
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    rec = {"query": query, "day": str(day), "fetched_at": dt.datetime.utcnow().isoformat() + "Z",
           "cost": out.get("costDollars", {}).get("total"),
           "results": [{"url": x.get("url"), "title": x.get("title"), "publishedDate": x.get("publishedDate"),
                        "highlights": x.get("highlights") or []} for x in out.get("results", [])]}
    path.write_text(json.dumps(rec))
    return rec


def day_hits(day: dt.date, fetch: bool = True) -> list[dict]:
    """De-duplicated hits for one day that talk about GPU prices, each tagged up / down / both / none."""
    seen, hits = set(), []
    for q in QUERIES:
        h = hashlib.sha256(f"{q}|{day}|10".encode()).hexdigest()[:16]
        if not fetch and not (CACHE / f"{day}_{h}.json").exists():
            continue
        for x in search_day(q, day)["results"]:
            pd_ = (x.get("publishedDate") or "")[:10]
            if x["url"] in seen or pd_ != str(day):      # drop anything Exa returned outside the day
                continue
            seen.add(x["url"])
            text = " ".join([x.get("title") or ""] + x["highlights"])
            if not (PRICE.search(text) and GPU.search(text)):
                continue
            title = x.get("title") or ""
            hits.append({"day": str(day), "url": x["url"], "title": title, "up": bool(UP.search(text)), "down": bool(DOWN.search(text)),
                         "title_up": bool(UP.search(title)), "title_down": bool(DOWN.search(title))})
    return hits


def signal(origin: dt.date, window: int = 7, fetch: bool = False) -> dict:
    """Counts over the `window` days ending at the origin (inclusive). Uses the cache only unless fetch=True."""
    hits = [h for k in range(window) for h in day_hits(origin - dt.timedelta(days=k), fetch=fetch)]
    return {"n": len(hits), "up": sum(h["up"] for h in hits), "down": sum(h["down"] for h in hits),
            "title_up": sum(h["title_up"] for h in hits), "title_down": sum(h["title_down"] for h in hits), "hits": hits}


if __name__ == "__main__":
    cmd = sys.argv[1]
    a, b = dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
    days = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    if cmd == "fetch":
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(lambda d: day_hits(d, True), days))
        cost = sum(json.loads(p.read_text()).get("cost") or 0 for p in CACHE.glob("*.json"))
        print("days", len(days), "cached files", len(list(CACHE.glob('*.json'))), "total cost $", round(cost, 3))
    elif cmd == "audit":
        for d in days:
            for h in day_hits(d, False):
                print(h["day"], "U" if h["up"] else "-", "D" if h["down"] else "-", h["title"][:95], "|", h["url"][:90])


def exa_call(endpoint: str, body: dict, tag: str = "attr") -> dict:
    """Cached POST to https://api.exa.ai/<endpoint> (search or contents). Cache key is the full request body, so reruns are free and offline.
    Returns {"request", "response", "cost", "fetched_at"} or, on an API error, {"request", "error", "status"}. Errors are cached too."""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{endpoint}|{json.dumps(body, sort_keys=True)}".encode()).hexdigest()[:20]
    path = CACHE / f"{tag}_{endpoint}_{h}.json"
    if path.exists():
        return json.loads(path.read_text())
    req = urllib.request.Request(f"https://api.exa.ai/{endpoint}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-api-key": _key(), "User-Agent": "gpuf-scout"})
    rec = {"request": body, "fetched_at": dt.datetime.utcnow().isoformat() + "Z"}
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                out = json.loads(r.read())
            rec["response"] = out
            c = out.get("costDollars")
            rec["cost"] = c.get("total") if isinstance(c, dict) else c
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(2 * (attempt + 1)); continue
            rec["status"], rec["error"] = e.code, e.read().decode()[:600]
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    path.write_text(json.dumps(rec))
    return rec


def exa_spend(tag: str = "attr") -> float:
    return round(sum(json.loads(p.read_text()).get("cost") or 0 for p in CACHE.glob(f"{tag}_*.json")), 4)
