"""Origin splits from EVAL_PROTOCOL.md. Test access is gated and logged; val use is logged by the harness."""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os

from .data import DATA_OUT


def _day(s: str) -> int:
    return dt.date.fromisoformat(s).toordinal()


def _days(a: str, b: str, step: int = 1) -> list[int]:
    return list(range(_day(a), _day(b) + 1, step))


DEV = tuple(_days("2026-05-01", "2026-08-31"))
VAL = tuple(_days("2026-09-08", "2026-10-04"))
TEST = tuple(_days("2026-10-12", "2026-10-30"))
STARTER15 = tuple(_days("2026-07-15", "2026-10-24", 7))  # 15 weekly origins, last one 2026-10-21
assert len(STARTER15) == 15

VAL_LOG = DATA_OUT / "val_query_log.jsonl"
TEST_LOG = DATA_OUT / "test_unlock_log.jsonl"


class LockedSplit(PermissionError):
    pass


def append_log(path, record: dict) -> None:
    os.makedirs(path.parent, exist_ok=True)
    rec = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "user": getpass.getuser(), **record}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def origins(name: str, unlock_test: bool = False, who: str = "") -> list[int]:
    """Origin days (ordinals) of a split. 'test' needs unlock_test=True and logs the unlock."""
    if name == "dev":
        return list(DEV)
    if name == "val":
        return list(VAL)
    if name == "starter15":
        return list(STARTER15)
    if name == "test":
        if not unlock_test:
            raise LockedSplit("the test split is locked; pass --unlock-test (scored once, at the end)")
        append_log(TEST_LOG, {"event": "unlock", "who": who})
        return list(TEST)
    raise ValueError(f"unknown split {name!r}")


def touches(origin_days, split_days) -> bool:
    return bool(set(origin_days) & set(split_days))
