"""Exa searches for published GPU resale / residual-value figures. endPublishedDate <= 2026-11-06 on every call; responses
cached under runs/longrun/exa_cache; the key is read by gpuf.scout._key() (environment or ../.env) and never printed.
Prints the cumulative cost and the highlights that carry a figure, for manual citation (date, title, link, sentence)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from gpuf.scout import _key  # noqa: E402

CACHE = ROOT / "runs/longrun/exa_cache"
END = "2026-11-06T23:59:59Z"
BUDGET = 3.0
QUERIES = [
    "used H100 GPU resale price per GPU 2026",
    "used A100 80GB resale price secondary market 2026",
    "H100 residual value percent of original price depreciation",
    "GPU depreciation schedule useful life debate hyperscalers H100 six years",
    "American Compute GPU resale index",
    "Silicon Data H100 market value depreciation used refurbished",
    "GPU-backed loan collateral H100 residual value lender",
    "Compute Exchange used GPU price H100 A100",
]
NUM = re.compile(r"(\$\s?\d[\d,\.]*\s?(k|K|thousand)?|\d+(\.\d+)?\s?%|per cent|percent)")


def search(q: str, n: int = 8) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{hashlib.sha256(f'{q}|{END}|{n}'.encode()).hexdigest()[:16]}.json"
    if path.exists():
        return json.loads(path.read_text())
    spent = sum(json.loads(p.read_text()).get("cost") or 0 for p in CACHE.glob("*.json"))
    if spent > BUDGET - 0.1:
        raise RuntimeError(f"Exa budget reached: {spent:.3f}")
    body = {"query": q, "type": "auto", "numResults": n, "endPublishedDate": END,
            "contents": {"highlights": {"numSentences": 3, "highlightsPerUrl": 3}}}
    req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-api-key": _key(), "User-Agent": "gpuf-longrun"})
    with urllib.request.urlopen(req, timeout=90) as r:
        out = json.loads(r.read())
    rec = {"query": q, "end_published": END, "cost": out.get("costDollars", {}).get("total"),
           "results": [{"url": x.get("url"), "title": x.get("title"), "publishedDate": x.get("publishedDate"),
                        "highlights": x.get("highlights") or []} for x in out.get("results", [])]}
    path.write_text(json.dumps(rec))
    return rec


if __name__ == "__main__":
    qs = sys.argv[1:] or QUERIES
    for q in qs:
        rec = search(q)
        print(f"\n## {q}  (cost {rec['cost']})")
        for x in rec["results"]:
            if (x.get("publishedDate") or "9999") > END:
                continue
            hl = [h for h in x["highlights"] if NUM.search(h)]
            if hl:
                print(f"- {(x.get('publishedDate') or '')[:10]} | {x['title']} | {x['url']}")
                for h in hl:
                    print("    >", h.replace("\n", " ")[:400])
    spent = sum(json.loads(p.read_text()).get("cost") or 0 for p in CACHE.glob("*.json"))
    print(f"\nTotal Exa cost so far: ${spent:.3f}")
