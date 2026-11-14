"""One text-in, text-out call to a language model, cached on disk so a research run can be replayed offline.

Live calls go through the headless Devin CLI (`devin -p`) started in an empty temporary folder with read-only
permissions, so the model sees the prompt and nothing else of this repository. A reply that used any tool is
refused: the model must answer from the prompt alone. Every call (live or replayed) is appended to
data_out/llm_journal.jsonl with its wall time and sizes.

  ask(prompt, tag="proposer")            -> {"text", "cached", "seconds", "prompt_chars", "prompt_tokens_est", ...}
  ask_json(prompt, tag="proposer")       -> (parsed object, the same record)

Environment
  GPUF_LLM_MODEL    model id for `devin --model` (default gpt-6-astra-medium)
  GPUF_LLM_OFFLINE  "1": answer from the cache only and raise LookupError on a miss (tests, reproduction)

Cache key: sha256 of model, tag-free prompt and `salt` (use `salt` to draw independent replicates of one prompt).
Token counts: `prompt_tokens_est` is len(prompt) / 4, the size of what this project sent. The CLI's own count
(`harness_prompt_tokens`) includes its fixed system preamble and is kept only for information.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import data

CACHE = data.ROOT / "data_out/llm_cache"
JOURNAL = data.ROOT / "data_out/llm_journal.jsonl"
DEFAULT_MODEL = "gpt-6-astra-medium"
PREAMBLE = ("Answer from the text below only. Do not use any tool, do not read files, do not search the web. "
            "Reply with the answer and nothing else.\n\n")


def _key(model: str, prompt: str, salt: str) -> str:
    return hashlib.sha256(json.dumps([model, prompt, salt]).encode()).hexdigest()[:24]


def _live(prompt: str, model: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="gpuf_llm_") as tmp:
        pf, ex = Path(tmp) / "prompt.txt", Path(tmp) / "export.json"
        pf.write_text(PREAMBLE + prompt)
        t0 = time.time()
        r = subprocess.run(["devin", "-p", "--prompt-file", str(pf), "--model", model, "--permission-mode", "auto",
                            "--respect-workspace-trust", "false", "--export", str(ex)],
                           cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        secs = time.time() - t0
        if r.returncode != 0:
            raise RuntimeError(f"llm: devin exited {r.returncode}: {r.stderr[-400:]}")
        out = {"text": r.stdout.strip(), "seconds": round(secs, 2), "tool_calls": 0}
        if ex.exists():
            e = json.loads(ex.read_text())
            fm = e.get("final_metrics") or {}
            out["harness_prompt_tokens"] = fm.get("total_prompt_tokens")
            out["completion_tokens"] = fm.get("total_completion_tokens")
            out["tool_calls"] = sum(len(s.get("tool_calls") or []) for s in e.get("steps", []) if s.get("source") == "agent")
            out["model_name"] = (e.get("agent") or {}).get("model_name")
        if out["tool_calls"]:
            raise RuntimeError(f"llm: the model used {out['tool_calls']} tool call(s); replies must come from the prompt alone")
        return out


def ask(prompt: str, tag: str = "", model: str | None = None, salt: str = "", timeout: int = 600) -> dict:
    model = model or os.environ.get("GPUF_LLM_MODEL", DEFAULT_MODEL)
    k = _key(model, prompt, salt)
    p = CACHE / f"{k}.json"
    if p.exists():
        rec = {**json.loads(p.read_text()), "cached": True}
    elif os.environ.get("GPUF_LLM_OFFLINE") == "1":
        raise LookupError(f"llm: no cached reply for key {k} (tag {tag!r}) and GPUF_LLM_OFFLINE=1")
    else:
        rec = {"key": k, "model": model, "salt": salt, "prompt": prompt, **_live(prompt, model, timeout),
               "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cached": False}
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({x: y for x, y in rec.items() if x != "cached"}, indent=1))
    rec["prompt_chars"] = len(prompt)
    rec["prompt_tokens_est"] = len(prompt) // 4
    with JOURNAL.open("a") as f:
        f.write(json.dumps({"key": k, "tag": tag, "model": model, "cached": rec["cached"], "seconds": rec.get("seconds"),
                            "prompt_chars": rec["prompt_chars"], "prompt_tokens_est": rec["prompt_tokens_est"],
                            "completion_tokens": rec.get("completion_tokens"), "reply_chars": len(rec["text"]),
                            "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + "\n")
    return rec


def parse_json(text: str):
    """The first JSON object or array in `text` (fenced or bare)."""
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    s = m.group(1) if m else text
    start = min((i for i in (s.find("{"), s.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("llm: no JSON in the reply")
    return json.JSONDecoder().raw_decode(s[start:])[0]


def ask_json(prompt: str, tag: str = "", **kw):
    rec = ask(prompt, tag=tag, **kw)
    return parse_json(rec["text"]), rec
