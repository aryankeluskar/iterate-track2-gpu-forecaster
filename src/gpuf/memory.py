"""Shared agent memory on past.dev, standard library only.

Every write and every recall is appended to data_out/memory_journal.jsonl (request, response, UTC time, calling agent).
PAST_OFFLINE=1: nothing touches the network. Writes go to the journal only; recall replays the most recent journalled
answer for the same query, identity and as-of date, or, if none exists, answers from the journalled writes (audience
and date rules applied) and journals that answer so the next call replays it.
Live writes and live recalls also need PAST_ALLOW_WRITES=1 (the owner has not yet approved sending data); `usage` is a
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
        raise PastError("live past.dev writes and recalls are disabled: set PAST_ALLOW_WRITES=1 after the owner approves experiments/memory/plan.md, or use PAST_OFFLINE=1")


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
            "sources": [{"sourceId": it["id"], "occurredAt": it["timestamp"], "label": it.get("label"), "excerpts": []}]}
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


def _cli(argv: list[str]) -> int:
    if argv[:1] == ["usage"]:
        print(json.dumps(usage(), indent=2))
        return 0
    if argv[:1] == ["dry-run"] and len(argv) == 2:
        set_dry_run(True)
        items = []
        for line in pathlib.Path(argv[1]).read_text().splitlines():
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
    print("usage: python -m gpuf.memory usage | dry-run FILE.jsonl", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_cli(sys.argv[1:]))
    except PastError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
