"""gpuf.llm: cache replay, offline refusal, JSON extraction. No network and no model call."""
import json

import pytest

from gpuf import llm


def test_replay_and_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(llm, "JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setenv("GPUF_LLM_OFFLINE", "1")
    with pytest.raises(LookupError):
        llm.ask("what moved the median?", tag="t")
    k = llm._key(llm.DEFAULT_MODEL, "what moved the median?", "")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / f"{k}.json").write_text(json.dumps({"key": k, "text": '```json\n{"claim": "x"}\n```', "seconds": 1.5}))
    obj, rec = llm.ask_json("what moved the median?", tag="t")
    assert obj == {"claim": "x"} and rec["cached"] and rec["prompt_tokens_est"] == len("what moved the median?") // 4
    with pytest.raises(LookupError):  # a different salt is a different draw
        llm.ask("what moved the median?", tag="t", salt="r2")
    rows = [json.loads(x) for x in (tmp_path / "journal.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["cached"] and rows[0]["tag"] == "t"


def test_parse_json():
    assert llm.parse_json('noise {"a": [1, 2]} trailing') == {"a": [1, 2]}
    assert llm.parse_json("[1, 2]") == [1, 2]
    with pytest.raises(ValueError):
        llm.parse_json("no json here")
