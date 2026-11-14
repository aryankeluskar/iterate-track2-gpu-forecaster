"""Check that every decimal number in FINDINGS.md and README.md is listed, with a source, in numbers.md.

A decimal number is a token like 0.2141, +0.033, 2.1e-5, 26.1k or 1e-9 inside prose or tables. Dotted version strings
(0.1.1, 3.12.12) and digits inside hashes, URLs and `code spans` are not counted. A number counts as sourced when
numbers.md has a table row whose first cell equals it (sign ignored) and whose source cell is not empty.

Run from track_2/:  .venv/bin/python experiments/writeup/check_numbers.py
Exit code 0 when every number is sourced, 1 otherwise.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = [ROOT / "FINDINGS.md", ROOT / "README.md"]
TABLE = pathlib.Path(__file__).with_name("numbers.md")

URL = re.compile(r"https?://\S+|`[^`]*`|\b[0-9a-f]{12,}\b")
NUM = re.compile(r"(?<![\w.])[-+]?(\d+\.\d+(?:e-?\d+)?k?|\d+e-?\d+)(?![\w.]*\d)(?![A-Za-jl-z_])")


def norm(s: str) -> str:
    return s.strip().lstrip("+-").strip()


def sourced() -> dict[str, str]:
    out = {}
    for line in TABLE.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and NUM.fullmatch(cells[0]) and cells[2]:
            out[norm(cells[0])] = cells[2]
    return out


def main() -> int:
    table = sourced()
    found: dict[str, list[str]] = {}
    for doc in DOCS:
        for i, line in enumerate(doc.read_text().splitlines(), 1):
            for m in NUM.finditer(URL.sub(" ", line)):
                found.setdefault(norm(m.group(1)), []).append(f"{doc.name}:{i}")
    missing = {k: v for k, v in found.items() if k not in table}
    n_occ = sum(len(v) for v in found.values())
    print(f"decimal numbers: {n_occ} occurrences, {len(found)} distinct; sourced {len(found) - len(missing)}; unsourced {len(missing)}")
    for k, v in sorted(missing.items()):
        print(f"  UNSOURCED {k}: {', '.join(v)}")
    unused = sorted(set(table) - set(found))
    if unused:
        print(f"rows in numbers.md not found in the documents (informational): {len(unused)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
