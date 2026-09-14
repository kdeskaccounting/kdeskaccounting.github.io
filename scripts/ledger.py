#!/usr/bin/env python3
"""Append-only decision ledger for KDesk autonomous actions.

Every live side effect in this repo writes exactly one line to decisions/decisions.jsonl.
Schema (fixed, matching entries 1-68): id, ts, tier, status, action, reasoning, files,
veto_window_close, stephen_reviewed.

  python3 scripts/ledger.py --tail 5
Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PATH = REPO / "decisions" / "decisions.jsonl"
TIERS = (0, 1, 2, 3)
STATUSES = ("executed", "in_progress", "planned", "pending_veto", "vetoed")


def _path(path: pathlib.Path | None) -> pathlib.Path:
    return pathlib.Path(path) if path is not None else DEFAULT_PATH


def _norm_files(value: object) -> list[str]:
    """`files` is a list on most rows but a Python-repr string on entries 59-63."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return [value]
        if isinstance(parsed, (list, tuple)):
            return [str(v) for v in parsed]
        return [str(parsed)]
    return []


def entries(path: pathlib.Path | None = None) -> list[dict]:
    p = _path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["files"] = _norm_files(row.get("files"))
        rows.append(row)
    return rows


def last_id(path: pathlib.Path | None = None) -> int:
    return max((int(r.get("id", 0)) for r in entries(path)), default=0)


def find(entry_id: int, path: pathlib.Path | None = None) -> dict | None:
    return next((r for r in entries(path) if int(r.get("id", 0)) == entry_id), None)


def veto_close(entry_id: int, path: pathlib.Path | None = None) -> str | None:
    row = find(entry_id, path)
    return row.get("veto_window_close") if row else None


def append(action: str, tier: int, status: str, reasoning: str, files: list[str],
           veto_window_close: str | None = None, *, path: pathlib.Path | None = None,
           now: dt.datetime | None = None) -> dict:
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    if not action.strip():
        raise ValueError("action must not be empty")
    p = _path(path)
    stamp = (now or dt.datetime.now().astimezone()).strftime("%Y-%m-%dT%H:%M:%S%z")
    row = {"id": last_id(p) + 1, "ts": stamp, "tier": int(tier), "status": status,
           "action": action, "reasoning": reasoning, "files": [str(f) for f in files],
           "veto_window_close": veto_window_close, "stephen_reviewed": False}
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="Read the KDesk decision ledger.")
    ap.add_argument("--tail", type=int, default=10)
    a = ap.parse_args()
    for row in entries()[-a.tail:]:
        print(f"{row['id']:>3} T{row['tier']} {row['status']:>11} {row['action'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
