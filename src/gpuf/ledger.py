"""Hypothesis ledger: one JSON line per hypothesis, updated in place by id. The record of what the system tested and learned.

python -m gpuf.ledger            print a table
python -m gpuf.ledger --json     print the records
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from .data import DATA_OUT

PATH = DATA_OUT / "ledger.jsonl"
STATUSES = ("registered", "running", "supported", "refuted", "not_significant", "untestable")
FIELDS = ("id", "agent", "claim", "failure_mode", "prediction", "refuted_if", "status", "result", "evidence", "registered_utc", "updated_utc")


def load() -> list[dict]:
    return [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()] if PATH.exists() else []


def put(id: str, **fields) -> dict:
    """Create or update one hypothesis. `status` must be one of STATUSES; unknown fields are rejected."""
    bad = set(fields) - set(FIELDS)
    if bad:
        raise ValueError(f"unknown ledger fields {sorted(bad)}")
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    rows, now = load(), dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for r in rows:
        if r["id"] == id:
            r.update(fields, updated_utc=now)
            break
    else:
        r = {"id": id, "status": "registered", "registered_utc": now, "updated_utc": now, **fields}
        rows.append(r)
    PATH.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in rows))
    return r


if __name__ == "__main__":
    rows = load()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r['id']:<5} {r['status']:<16} {r.get('agent', ''):<12} {r.get('claim', '')[:110]}")
            if r.get("result"):
                print(f"      -> {r['result']}")
