"""Shared agent memory on past.dev, standard library only.

Every write and every recall is appended to data_out/memory_journal.jsonl (request, response, UTC time, calling agent).
PAST_OFFLINE=1: nothing touches the network. Writes go to the journal only; recall replays the most recent journalled
answer for the same query, identity and as-of date, or, if none exists, answers from the journalled writes (audience
and date rules applied) and journals that answer so the next call replays it.
Live writes and live recalls also need PAST_ALLOW_WRITES=1 (the owner approved the plan on 2026-11-14); `usage` is a
read-only GET and needs only the key. The key is read from PAST_API_KEY or PAST_DEV_API_KEY (environment, then .env,
then ../.env), is sent only in the Authorization header, and is scrubbed from every error text and journal line.
Docs: literature/pastdev-api.md.
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
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://api.past.dev"
KEY_NAMES = ("PAST_API_KEY", "PAST_DEV_API_KEY")
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$")
_dry = False


class PastError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None, code: str | None = None):
        super().__init__(_scrub(msg))
        self.status, self.code = status, code


def journal_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("PAST_JOURNAL") or ROOT / "data_out" / "memory_journal.jsonl")


def offline() -> bool:
    return os.environ.get("PAST_OFFLINE", "") not in ("", "0")


def set_dry_run(on: bool = True) -> None:
    global _dry
    _dry = on


def _key(required: bool = True) -> str | None:
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n].strip()
    for p in (ROOT / ".env", ROOT.parent / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                n, _, v = line.partition("=")
                if n.strip() in KEY_NAMES and v.strip():
                    return v.strip().strip('"').strip("'")
    if required:
        raise PastError("no past.dev key: set PAST_API_KEY (or PAST_DEV_API_KEY) in the environment or .env")
    return None


def _scrub(text: str) -> str:
    k = _key(False)
    if k:
        text = text.replace(k, "***")
    return re.sub(r"past_(sk|mk)_[A-Za-z0-9_\-]+", "past_\\1_***", text)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _agent(agent: str | None) -> str:
    return agent or os.environ.get("PAST_AGENT") or "unknown"


def _journal(op: str, agent: str, request: dict, response: dict, **extra) -> None:
    rec = {"time": _now(), "agent": agent, "op": op, "offline": offline(), "request": request, "response": response, **extra}
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(_scrub(json.dumps(rec, sort_keys=True, default=str)) + "\n")


def _read_journal() -> list[dict]:
    p = journal_path()
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _http(method: str, path: str, body=None) -> dict:
    if _dry:
        print(json.dumps({"method": method, "url": BASE + path, "headers": {"Authorization": "Bearer ***"}, "body": body}, default=str))
        return {"dry_run": True}
    data = None if body is None else json.dumps(body).encode()
    for attempt in range(5):
        req = urllib.request.Request(BASE + path, data=data, method=method, headers={
            "Authorization": f"Bearer {_key()}", "Content-Type": "application/json", "User-Agent": "gpuf-memory"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode()
                return {"status": r.status, **(json.loads(raw) if raw else {})}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace") if hasattr(e, "read") else ""
            try:
                j = json.loads(raw) if raw else {}
            except ValueError:
                j = {"debugMessage": raw[:300]}
            if (e.code == 429 or e.code >= 500) and attempt < 4 and j.get("code") not in ("project-cap-reached", "spend-cap-reached"):
                time.sleep(2 ** attempt)
                continue
            raise PastError(f"{method} {path} -> {e.code} {j.get('code')}: {j.get('debugMessage')}", e.code, j.get("code")) from None
        except urllib.error.URLError as e:
            raise PastError(f"{method} {path} network error: {e.reason}") from None
    raise PastError(f"{method} {path} failed after retries")


def _live_guard() -> None:
    if os.environ.get("PAST_ALLOW_WRITES") != "1" and not _dry:
        raise PastError("live past.dev writes and recalls are disabled: set PAST_ALLOW_WRITES=1 for live calls (owner-approved, see experiments/memory/README_memory.md), or use PAST_OFFLINE=1 to replay from the journal")


def _write(op: str, method: str, path: str, body, agent: str | None) -> dict:
    a = _agent(agent)
    if _dry:
        return _http(method, path, body)
    if offline():
        resp = {"offline": True}
        _journal(op, a, {"method": method, "path": path, "body": body}, resp)
        return resp
    _live_guard()
    resp = _http(method, path, body)
    _journal(op, a, {"method": method, "path": path, "body": body}, resp)
    return resp


def put_audience(slug: str, kind: str = "fixed", name: str | None = None, identities: list[str] | None = None,
                 rule: dict | None = None, agent: str | None = None) -> dict:
    if not SLUG.match(slug) or slug == "project":
        raise PastError(f"audience slug {slug!r} must be 2-40 lowercase letters, digits, dashes (not 'project')")
    body = {"kind": kind, "name": name or slug}
    body.update({"identities": identities or []} if kind == "fixed" else {"rule": rule})
    return _write("put_audience", "PUT", f"/api/v1/audiences/{slug}", body, agent)


def put_identity(identity: str, traits: dict[str, str] | None = None, agent: str | None = None) -> dict:
    if not 1 <= len(identity) <= 200 or "/" in identity:
        raise PastError("identity must be 1-200 characters without '/'")
    return _write("put_identity", "PUT", f"/api/v1/identities/{identity}", {"traits": traits or {}}, agent)


def _check_item(it: dict) -> dict:
    out = {k: v for k, v in it.items() if k in ("id", "content", "label", "timestamp", "metadata", "audience", "identity")}
    if not str(out.get("content", "")).strip():
        raise PastError(f"item {out.get('id')!r}: content is required")
    if "/" in str(out.get("id", "")):
        raise PastError(f"item id {out['id']!r} must not contain '/'")
    ts = out.get("timestamp")
    if not ts or not re.search(r"(Z|[+-]\d\d:\d\d)$", str(ts)):
        raise PastError(f"item {out.get('id')!r}: timestamp must be ISO 8601 with a zone, e.g. 2026-10-01T00:00:00Z")
    aud = out.get("audience")
    if aud and aud != "project" and not SLUG.match(aud):
        raise PastError(f"item {out.get('id')!r}: bad audience slug {aud!r}")
    return out


def ingest(items: list[dict], agent: str | None = None, idempotency_key: str | None = None) -> dict:
    """POST /api/v1/ingest/batch. Items: id, content, label, timestamp (with zone), audience, metadata, identity."""
    items = [_check_item(i) for i in items]
    ids = [i.get("id") for i in items]
    if not items or len(items) > 1000 or len(set(ids)) != len(ids):
        raise PastError("batch needs 1-1000 items with distinct ids")
    key = idempotency_key or "gpuf-" + hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:32]
    resp = _write("ingest", "POST", "/api/v1/ingest/batch", {"idempotencyKey": key, "items": items}, agent)
    if offline() and not _dry:
        resp = {**resp, "ingestionId": "offline-" + key}
    return resp


def wait(ingestion_id: str, timeout: float = 600.0) -> dict:
    """Poll GET /api/v1/ingest/{id} until status is completed (2 s for a minute, then 30 s). Polls cost nothing."""
    if offline() or ingestion_id.startswith("offline-"):
        return {"status": "completed", "offline": True}
    if _dry:
        return _http("GET", f"/api/v1/ingest/{ingestion_id}")
    t0 = time.time()
    while True:
        r = _http("GET", f"/api/v1/ingest/{ingestion_id}")
        if r.get("status") == "completed":
            return r
        if r.get("status") == "failed":
            raise PastError(f"ingestion {ingestion_id} failed: {r.get('failure')}")
        if time.time() - t0 > timeout:
            raise PastError(f"ingestion {ingestion_id} still {r.get('status')} after {timeout:.0f}s")
        time.sleep(2 if time.time() - t0 < 60 else 30)


def _iso(d) -> str | None:
    if d is None:
        return None
    if isinstance(d, dt.datetime):
        return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(d, dt.date):
        return f"{d}T23:59:59Z"
    return str(d)


def _local_answer(body: dict) -> dict:
    """Offline fallback: answer from journalled writes, honouring audience reach and the as-of bound."""
    recs = _read_journal()
    reach = {"project"}
    members: dict[str, set[str]] = {}
    for r in recs:
        q = r["request"]
        if r["op"] == "put_audience" and q["body"].get("kind") == "fixed":
            members[q["path"].rsplit("/", 1)[1]] = set(q["body"].get("identities", []))
    reach |= {a for a, m in members.items() if body["identity"] in m}
    hi, lo = body.get("queryTimestamp") or body.get("occurredTo"), body.get("occurredFrom")
    words = set(re.findall(r"\w+", body["query"].lower()))
    pts: dict[str, dict] = {}
    for r in recs:
        if r["op"] == "ingest":
            for it in r["request"]["body"]["items"]:
                pts[it["id"]] = it
    scored = []
    for it in pts.values():
        if (it.get("audience") or "project") not in reach:
            continue
        ts = it["timestamp"]
        if (hi and ts > hi) or (lo and ts < lo):
            continue
        scored.append((len(words & set(re.findall(r"\w+", (it.get("label", "") + " " + it["content"]).lower()))), ts, it))
    scored.sort(key=lambda x: (-x[0], x[1]))
    res = [{"id": "local-" + it["id"], "rank": n + 1, "occurredAt": it["timestamp"], "content": it["content"],
            "artifact": {"id": "local-" + it["id"], "kind": "source", "occurredAt": it["timestamp"]},
            "sources": [{"sourceId": it["id"], "occurredAt": it["timestamp"], "label": it.get("label"), "excerpts": [], "metadata": it.get("metadata")}]}
           for n, (s, _, it) in enumerate(scored[: body.get("limit", 100)])]
    return {"asOf": hi, "results": res, "offline": "local-from-journal"}


def _bound(resp: dict, ao: str | None) -> dict:
    if not ao or "results" not in resp:
        return resp
    keep = [x for x in resp["results"] if str(x.get("occurredAt") or "") <= ao]
    return {**resp, "results": [{**x, "rank": i + 1} for i, x in enumerate(keep)]}


def recall(query: str, identity: str, *, agent: str | None = None, as_of=None, occurred_from=None, occurred_to=None,
           limit: int | None = None, level: str | None = None, max_tokens: int | None = None, sort: str | None = None) -> dict:
    """POST /api/v1/recall. as_of (datetime, date or ISO string) sets queryTimestamp and occurredTo: only memories
    that occurred at or before it are eligible. A bare date means the end of that day UTC."""
    if level and max_tokens:
        raise PastError("send level or max_tokens, not both")
    body = {"query": query, "identity": identity}
    ao = _iso(as_of)
    if ao:
        body["queryTimestamp"] = ao
        body["occurredTo"] = _iso(occurred_to) or ao
    elif occurred_to:
        body["occurredTo"] = _iso(occurred_to)
    for k, v in (("occurredFrom", _iso(occurred_from)), ("limit", limit), ("level", level), ("maxTokens", max_tokens), ("sort", sort)):
        if v is not None:
            body[k] = v
    a = _agent(agent)
    req = {"method": "POST", "path": "/api/v1/recall", "body": body}
    if _dry:
        return _http("POST", "/api/v1/recall", body)
    if offline():
        for r in reversed(_read_journal()):
            if r["op"] == "recall" and r["request"]["body"].get("query") == query and r["request"]["body"].get("identity") == identity \
                    and r["request"]["body"].get("queryTimestamp") == body.get("queryTimestamp"):
                _journal("recall", a, req, r["response"], replayed=True)
                return _bound(r["response"], ao)
        resp = _local_answer(body)
        _journal("recall", a, req, resp, replayed=False)
        return _bound(resp, ao)
    _live_guard()
    resp = _http("POST", "/api/v1/recall", body)
    _journal("recall", a, req, resp)
    return _bound(resp, ao)


def usage() -> dict:
    """GET /api/v1/usage (read-only, spends nothing). Needs the key; not journalled."""
    if offline():
        raise PastError("usage needs the network; unset PAST_OFFLINE")
    return _http("GET", "/api/v1/usage")


def ledger_item(e: dict) -> dict:
    """One ledger entry (data_out/ledger.jsonl) as one data point for gpuf-experiments, authored by `experimenter`."""
    g = lambda k, d="not recorded": e.get(k) or d
    txt = (f"Hypothesis ledger entry {e['id']}, status {e['status']}, updated {e['updated_utc']} (written by experimenter; run by agent {g('agent', 'unknown')})\n"
           f"Hypothesis id: {e['id']}\nClaim: {g('claim')}\nFailure mode targeted: {g('failure_mode')}\nPrediction: {g('prediction')}\n"
           f"Refuted if: {g('refuted_if')}\nStatus: {e['status']}\nResult: {g('result', 'not recorded yet')}\nEvidence path: {g('evidence')}")
    return {"id": f"exp-{e['id']}", "audience": "gpuf-experiments", "identity": "experimenter", "timestamp": e["updated_utc"],
            "label": f"Experiment: {e['id']}", "metadata": {"agent": "experimenter", "kind": "experiment", "hypothesis": e["id"],
                                                             "status": e["status"], "ledger_agent": e.get("agent")}, "content": txt}


def _dedupe(resp: dict, top: int, excerpt_chars: int = 500) -> list[dict]:
    """Ranked results to one row per source data point: id, author, date, label, kind of the best hit, excerpt."""
    rows: dict[str, dict] = {}
    for r in resp.get("results", []):
        derived = r["artifact"]["kind"] != "source"
        for s in r.get("sources", []):
            sid = s["sourceId"]
            row = rows.get(sid)
            if row is None:
                if len(rows) >= top and top > 0:
                    continue
                md = s.get("metadata") or {}
                row = rows[sid] = {"rank": r["rank"], "source_id": sid, "author": md.get("agent"), "occurred_at": s.get("occurredAt"),
                                   "label": s.get("label"), "kind": r["artifact"]["kind"], "metadata": md, "excerpt": None, "text": None}
            if not derived and row["text"] is None:
                row["text"] = r["content"]
            if row["excerpt"] is None:
                row["excerpt"] = (r["content"] if derived else (s.get("excerpts") or [r["content"]])[0])[:excerpt_chars]
    return list(rows.values())


def _recall_rows(query, identity, top, as_of=None, agent=None):
    resp = recall(query, identity, agent=agent or identity, as_of=as_of, limit=min(200, max(20, top * 6)))
    return resp, _dedupe(resp, top)


def _clean(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in ("text", "metadata")}


def reach(identity: str, agent: str | None = None) -> list[str]:
    """Audience slugs `identity` can read (GET /identities/{id}; offline: last journalled answer, else the journalled audiences)."""
    if offline():
        for r in reversed(_read_journal()):
            if r["op"] == "reach" and r["request"]["identity"] == identity:
                return r["response"]["audiences"]
        out = {"project"}
        for r in _read_journal():
            q = r["request"]
            if r["op"] == "put_audience" and q["body"].get("kind") == "fixed" and identity in q["body"].get("identities", []):
                out.add(q["path"].rsplit("/", 1)[1])
        return sorted(out)
    _live_guard()
    resp = _http("GET", f"/api/v1/identities/{identity}")
    _journal("reach", _agent(agent or identity), {"identity": identity}, {"audiences": resp.get("audiences", [])})
    return resp.get("audiences", [])


def remember(identity: str, audience: str, id: str, timestamp: str, label: str, text: str, timeout: float = 600.0) -> dict:
    """Write one data point authored by `identity` and wait until it is completed."""
    t0 = time.time()
    r = ingest([{"id": id, "audience": audience, "identity": identity, "timestamp": timestamp, "label": label, "content": text,
                 "metadata": {"agent": identity}}], agent=identity)
    w = wait(r["ingestionId"], timeout)
    return {"id": id, "audience": audience, "author": identity, "timestamp": timestamp, "ingestion_id": r["ingestionId"],
            "unchanged": bool((r.get("items") or [{}])[0].get("unchanged")), "status": w.get("status"), "offline": offline(),
            "seconds": round(time.time() - t0, 1)}


def _ledger_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("PAST_LEDGER") or ROOT / "data_out" / "ledger.jsonl")


def sync_ledger(dry: bool = False) -> dict:
    """Send every ledger entry that is new or changed since the last sync, as `experimenter`. State: <journal dir>/memory_ledger_state[_offline].json."""
    state_p = journal_path().parent / ("memory_ledger_state_offline.json" if offline() else "memory_ledger_state.json")
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    items = [ledger_item(json.loads(x)) for x in _ledger_path().read_text().splitlines() if x.strip()]
    digest = lambda it: hashlib.sha256(json.dumps(it, sort_keys=True).encode()).hexdigest()
    todo = [it for it in items if state.get(it["id"]) != digest(it)]
    res = {"ledger_entries": len(items), "to_send": [i["id"] for i in todo], "sent": 0, "dry_run": dry, "offline": offline()}
    if todo and not dry:
        t0 = time.time()
        r = ingest(todo, agent="experimenter")
        w = wait(r["ingestionId"])
        state.update({it["id"]: digest(it) for it in todo})
        state_p.write_text(json.dumps(state, indent=1, sort_keys=True))
        res.update(sent=len(todo), ingestion_id=r["ingestionId"], status=w.get("status"), seconds=round(time.time() - t0, 1))
    return res


BRIEF_SECTIONS = (
    ("refuted", "Refuted or not significant hypotheses (do not re-test blindly)", "gpuf-experiments", {"experiment"},
     "Hypotheses already tested and refuted or not significant, on: {t}"),
    ("failures", "Failure modes and dated failure cases of the median forecast", "gpuf-failures", {"event", "failure_mode", "case"},
     "Failure modes and dated failure cases of the median forecast on: {t}"),
    ("evidence", "Dated web evidence", "gpuf-evidence", {"web_evidence"}, "Web evidence: provider announced GPU price increase, quoted sentence, URL, related to: {t}"),
)
_KEEP = ("Claim:", "Result:", "Quoted sentence:", "URL:", "Cause:", "Median:", "definition:", "share_of_blend_loss:", "share_of_last_value_loss:", "Explains:", "Prediction:")


def _summary(row: dict) -> str:
    if row.get("text"):
        lines = row["text"].splitlines()
        md = row.get("metadata") or {}
        head = (row.get("label") or lines[0]) + (f" ({md['status']})" if md.get("status") else "")
        keep = [l for l in lines[1:] if l.startswith(_KEEP)] or lines[1:3]
        return " | ".join([head] + keep)[:700]
    return (row.get("excerpt") or "")[:400]


def brief(identity: str, topic: str, as_of=None, top: int = 4) -> dict:
    """Two or three recalls (refuted hypotheses, failure modes, evidence) on `topic`, limited to what `identity` may read."""
    may = set(reach(identity))
    sections, text = [], [f"BRIEFING for {identity} on: {topic}" + (f" (as of {as_of})" if as_of else "")]
    for key, title, aud, kinds, q in BRIEF_SECTIONS:
        if aud not in may:
            sections.append({"key": key, "title": title, "skipped": f"{identity} may not read {aud}", "items": []})
            continue
        resp, rows = _recall_rows(q.format(t=topic), identity, 60 if top > 0 else 0, as_of)
        rows = [r for r in rows if r["metadata"].get("kind") in kinds]
        if key == "refuted":
            rows = [r for r in rows if r["metadata"].get("status") in ("refuted", "not_significant")]
        rows = rows[:top]
        sections.append({"key": key, "title": title, "query": q.format(t=topic), "items": [{**_clean(r), "summary": _summary(r)} for r in rows]})
        text.append(f"\n## {title}" + ("" if rows else "\n(nothing found)"))
        text += [f"- [{r['source_id']}] by {r['author']}, {str(r['occurred_at'])[:10]}: {_summary(r)}" for r in rows]
    return {"identity": identity, "topic": topic, "as_of": as_of, "offline": offline(), "sections": sections, "briefing": "\n".join(text)}


EPILOG = """\
commands (all print JSON on stdout; errors go to stderr with exit code 1; set PAST_ALLOW_WRITES=1 for live calls,
PAST_OFFLINE=1 to replay from data_out/memory_journal.jsonl with no network):
  recall        python -m gpuf.memory recall --as proposer "upper tail under-covered at 7 days" --top 5
  remember      python -m gpuf.memory remember --as researcher --audience gpuf-experiments --id exp-H30 \\
                  --timestamp 2026-11-14T21:00:00Z --label "Experiment: H30" --text-file notes.txt
  sync-ledger   python -m gpuf.memory sync-ledger          (new or changed ledger entries, as experimenter)
  brief         python -m gpuf.memory brief --as proposer "upper tail under-covered at 7 days"
  usage         python -m gpuf.memory usage              (credits left; read-only)
  dry-run       python -m gpuf.memory dry-run FILE.jsonl  (prints the requests, sends nothing)
identities: autopsy, scout, experimenter, proposer, forecaster, researcher. audiences: gpuf-failures, gpuf-evidence, gpuf-experiments.
Docs: experiments/memory/README_memory.md"""


def _parser():
    import argparse
    P = argparse.ArgumentParser(prog="python -m gpuf.memory", description="Shared agent memory on past.dev (journalled; offline replay).",
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = P.add_subparsers(dest="cmd", required=True)
    mk = lambda n, h, ex: sub.add_parser(n, help=h, description=h, epilog="example:\n  " + ex, formatter_class=argparse.RawDescriptionHelpFormatter)
    r = mk("recall", "Recall ranked memories as an identity; prints one row per source data point.",
           'python -m gpuf.memory recall --as forecaster --as-of 2026-10-06 "announced price increases effective soon" --top 5')
    r.add_argument("query"); r.add_argument("--as", dest="identity", required=True, help="reader identity (decides which audiences are visible)")
    r.add_argument("--as-of", help="YYYY-MM-DD: only memories that occurred at or before the end of that day UTC")
    r.add_argument("--top", type=int, default=8, help="max distinct sources printed (default 8)")
    w = mk("remember", "Write one data point and wait until it is completed. Same --id again updates it, never duplicates.",
           'python -m gpuf.memory remember --as scout --audience gpuf-evidence --id scout-abc123 --timestamp 2026-10-01T09:00:00Z --label "Evidence: example.com" --text "..."')
    w.add_argument("--as", dest="identity", required=True, help="author identity")
    w.add_argument("--audience", required=True, help="gpuf-failures | gpuf-evidence | gpuf-experiments")
    w.add_argument("--id", required=True, help="stable id, no '/'"); w.add_argument("--timestamp", required=True, help="ISO 8601 with zone: when the content occurred / became known")
    w.add_argument("--label", required=True); g = w.add_mutually_exclusive_group(required=True)
    g.add_argument("--text"); g.add_argument("--text-file")
    s = mk("sync-ledger", "Send every ledger entry new or changed since the last sync, as experimenter.", "python -m gpuf.memory sync-ledger --dry")
    s.add_argument("--dry", action="store_true", help="list what would be sent; send nothing")
    b = mk("brief", "Compact briefing before starting work: refuted hypotheses, failure modes and evidence on a topic.",
           'python -m gpuf.memory brief --as proposer "upper tail under-covered at 7 days" --as-of 2026-11-06 --top 4')
    b.add_argument("topic"); b.add_argument("--as", dest="identity", required=True); b.add_argument("--as-of")
    b.add_argument("--top", type=int, default=4, help="items per section (default 4)"); b.add_argument("--text", action="store_true", help="print only the briefing text")
    sub.add_parser("usage", help="credits left (read-only)"); d = sub.add_parser("dry-run", help="print the requests of a JSONL file, send nothing"); d.add_argument("file")
    return P


def _cli(argv: list[str]) -> int:
    a = _parser().parse_args(argv)
    dump = lambda o: print(json.dumps(o, indent=2, ensure_ascii=False))
    if a.cmd == "usage":
        dump(usage())
    elif a.cmd == "recall":
        resp, rows = _recall_rows(a.query, a.identity, a.top, a.as_of)
        dump({"identity": a.identity, "query": a.query, "as_of": a.as_of, "offline": offline(), "count": len(rows), "pending": resp.get("pending"),
              "results": [_clean(r) for r in rows]})
    elif a.cmd == "remember":
        text = a.text if a.text is not None else pathlib.Path(a.text_file).read_text()
        dump(remember(a.identity, a.audience, a.id, a.timestamp, a.label, text))
    elif a.cmd == "sync-ledger":
        dump(sync_ledger(a.dry))
    elif a.cmd == "brief":
        out = brief(a.identity, a.topic, a.as_of, a.top)
        print(out["briefing"]) if a.text else dump(out)
    elif a.cmd == "dry-run":
        set_dry_run(True)
        items = []
        for line in pathlib.Path(a.file).read_text().splitlines():
            if not line.strip():
                continue
            j = json.loads(line)
            op = j.pop("op", "item")
            if op == "audience":
                put_audience(j.pop("slug"), **j)
            elif op == "identity":
                put_identity(j.pop("identity"), j.get("traits"))
            elif op == "recall":
                recall(j.pop("query"), j.pop("identity"), **j)
            else:
                items.append(j)
        if items:
            ingest(items)
        print("dry run: nothing was sent", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_cli(sys.argv[1:]))
    except PastError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
