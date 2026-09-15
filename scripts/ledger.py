#!/usr/bin/env python3
"""Append-only decision ledger for KDesk autonomous actions.

Every live side effect in this repo writes exactly one line to decisions/decisions.jsonl.
Schema (fixed, matching entries 1-68; status also covers pending_veto, used by entries
69-70 for T2 act-with-veto-window actions): id, ts, tier, status, action, reasoning, files,
veto_window_close, stephen_reviewed.

  python3 scripts/ledger.py --tail 5
Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as dt
import fcntl
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PATH = REPO / "decisions" / "decisions.jsonl"
TIERS = (0, 1, 2, 3)
STATUSES = ("executed", "in_progress", "planned", "pending_veto", "vetoed")


class LedgerError(ValueError):
    """Raised when a ledger file contains a line that is not valid JSON.

    This is an audit log: a malformed line is never silently skipped.
    """


def _path(path: pathlib.Path | None) -> pathlib.Path:
    return pathlib.Path(path) if path is not None else DEFAULT_PATH


@contextlib.contextmanager
def _locked(path: pathlib.Path):
    """Hold an exclusive advisory lock on `<path>.lock` for the duration of the block.

    Guards the read-last-id + write-line sequence in append() so two concurrent
    processes/threads can never compute the same next id. Creates the sidecar lock
    file (and the ledger's parent directory) if missing. Stdlib-only (fcntl).
    """
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


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
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LedgerError(f"{p}:{lineno}: not valid JSON") from exc
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


def parse_ts(value: str) -> dt.datetime:
    """Parse an ISO-8601 stamp, including the ledger's own colon-free ±HHMM offset.

    append() below stamps with %z, which renders as `-0700`. datetime.fromisoformat only
    learned to read that shape in 3.11, and scripts in this repo are driven by both the
    system python3 (3.9.6 on this Mac) and `uv run`'s newer interpreter, so both must parse
    a ledger timestamp identically. This used to be a private `_parse_iso` duplicated in
    scripts/digest.py and scripts/sales/send_reengage.py (both hit the same bug
    independently); it lives here once now and both import it.

    Also accepts a trailing 'Z'/'z' (UTC) and a bare offset-less stamp (returned naive,
    same as fromisoformat). Raises ValueError for anything else.
    """
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        pass
    match = re.search(r"([+-])(\d{2})(\d{2})$", text)
    if not match:
        raise ValueError(f"unparseable timestamp {value!r}")
    return dt.datetime.fromisoformat(
        f"{text[:match.start()]}{match.group(1)}{match.group(2)}:{match.group(3)}")


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
    with _locked(p):
        row = {"id": last_id(p) + 1, "ts": stamp, "tier": int(tier), "status": status,
               "action": action, "reasoning": reasoning, "files": [str(f) for f in files],
               "veto_window_close": veto_window_close, "stephen_reviewed": False}
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
