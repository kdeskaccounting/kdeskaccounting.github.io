#!/usr/bin/env python3
"""Append-only decision ledger for KDesk autonomous actions.

Every live side effect in this repo writes exactly one line to decisions/decisions.jsonl.
Schema (fixed, matching entries 1-68; status also covers pending_veto, used by entries
69-70 for T2 act-with-veto-window actions): id, ts, tier, status, action, reasoning, files,
veto_window_close, stephen_reviewed.

Two optional fields, written only when given, let a LATER row answer an earlier T2 window
by id — the only way to do it in an append-only file: `approves: [69, 70]` (Stephen said
yes; only on a row whose status is "approved" or "executed") and `vetoes: [69]` (he said
no). The gate below reads them, and the LAST such row in file order wins, so an approval can
be taken back by a later veto. Entry #85 approves 69 and 70.

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
STATUSES = ("executed", "in_progress", "planned", "approved", "pending_veto", "vetoed")
VETO_TIER = 2                     # "act, with a veto window" — the only tier a gate can open
# A later row may answer an earlier T2 window by id, in `approves` / `vetoes`. An approval
# only counts from a row that records something that actually happened — Stephen said yes —
# so these are the statuses that may carry `approves`. A veto counts from any status: a stop
# is never ignored on a technicality.
APPROVAL_STATUSES = ("approved", "executed")


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


def _norm_ids(value: object, field: str) -> list[int]:
    """Validate an `approves`/`vetoes` value: a list of plain ints, or raise naming the field.

    Deliberately strict on the way in. A bare `approves=69`, a stringified `"69"` or a float
    would all read as "approves nothing" to the gate below, which fails open in the one
    direction that matters — so they are rejected where they are written, not tolerated where
    they are read.
    """
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of ints, got {value!r}")
    ids: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"{field} must be a list of ints, got {value!r}")
        ids.append(int(item))
    return ids


def answered_ids(row: dict, field: str) -> list[int]:
    """The ids `row` answers in `field` ("approves"/"vetoes"), tolerating a hand-written row.

    The reader is lenient where the writer is strict: a row someone typed by hand may carry
    `"approves": "69"` or a null, and that must not crash a gate. Anything unreadable simply
    answers no ids.
    """
    value = row.get(field)
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value if isinstance(v, int) and not isinstance(v, bool)]
    if isinstance(value, int) and not isinstance(value, bool):
        return [int(value)]
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


# --------------------------------------------------------------------------- the T2 gate
#
# T2 is "act, with a veto window": the decision is written, Stephen gets a stated number of
# hours to say no, and the action happens only after that window closes unvetoed. Two scripts
# act on the same T2 decision (#69, the marketing-autonomy loosening): send_reengage.py sends
# email under it and publishers/publish.py posts under it. The gate lives here so there is one
# answer to "may I act yet", and one place that gets the awkward case right: a decision
# Stephen actually vetoed, whose window has since elapsed, must read as NO, not as permission.


def veto_ok(close_iso: str | None, now: dt.datetime) -> tuple[bool, str]:
    """Has the veto window closed? The reason is a verb phrase; the caller names the entry."""
    if not close_iso:
        return False, "has no veto_window_close — nothing authorises this action"
    try:
        closes = parse_ts(close_iso)
    except ValueError:
        return False, f"has an unparseable veto_window_close {close_iso!r}"
    if closes.tzinfo is None:
        # A stamp with no offset is read in the reader's own zone rather than crashing the
        # comparison; append() always writes one, so this only covers a hand-edited row.
        closes = closes.replace(tzinfo=now.tzinfo)
    if now.tzinfo is None and closes.tzinfo is not None:
        # A naive `now` cannot be compared against an aware `closes` (TypeError). Refuse
        # rather than guess which offset the caller meant - a wrong guess here is the
        # difference between "refused" and "published".
        return False, (f"the caller passed a timezone-naive 'now', which cannot be compared "
                       f"against veto_window_close {close_iso} — refusing rather than "
                       f"assuming an offset")
    if now < closes:
        return False, (f"has a veto window that closes {close_iso}; it is "
                       f"{now.isoformat(timespec='minutes')}")
    return True, f"veto window closed {close_iso}"


def veto_gate(entry: dict | None, now: dt.datetime,
              entry_id: int = 0) -> tuple[bool, str]:
    """Every condition that authorises an autonomous action under a T2 window, in one place.

    Four ways to fail and they are not interchangeable: an entry that does not exist yet, an
    entry of the wrong tier (a T0 note authorises nothing), an entry Stephen actually vetoed,
    and a window that has not closed. The status check is the one that matters most: a vetoed
    decision whose window has since elapsed would otherwise read as permission.
    """
    if entry is None:
        return False, (f"does not exist yet — the T{VETO_TIER} entry that authorises this "
                       f"action has not been written. Run `python3 scripts/ledger.py "
                       f"--tail 5` and check which id carries the window")
    try:
        tier = int(entry.get("tier", -1))
    except (TypeError, ValueError):
        tier = -1
    if tier != VETO_TIER:
        return False, (f"is tier {entry.get('tier')!r}, not a T{VETO_TIER} "
                       f"act-with-veto-window entry — it authorises no action")
    if str(entry.get("status", "")).strip().lower() == "vetoed":
        return False, ("was VETOED — Stephen said no. An elapsed window does not turn a veto "
                       "into permission; this action must not happen")
    return veto_ok(entry.get("veto_window_close"), now)


def t2_window_open(entry_id: int, now: dt.datetime,
                   *, path: pathlib.Path | None = None) -> tuple[bool, str]:
    """(may_act, why) for the T2 entry `entry_id` — the form callers actually want.

    "Open" means the authorisation is open for acting: the entry exists, is T2, was not
    vetoed, and its window has closed. The reason is a verb phrase to be printed after
    "ledger entry <id> …", so it reads the same from every caller.
    """
    return veto_gate(find(entry_id, path), now, entry_id)


def append(action: str, tier: int, status: str, reasoning: str, files: list[str],
           veto_window_close: str | None = None, *, path: pathlib.Path | None = None,
           now: dt.datetime | None = None, approves: list[int] | None = None,
           vetoes: list[int] | None = None) -> dict:
    """Write one line. `approves`/`vetoes` name earlier entry ids this row answers for.

    Both are omitted from the row entirely unless given, so the eight fixed fields are still
    exactly what entries 1-84 carry. `approves` may only be written on a row whose status is
    one of APPROVAL_STATUSES — it records Stephen having said yes, not a plan to ask him.
    """
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    if not action.strip():
        raise ValueError("action must not be empty")
    extra: dict[str, list[int]] = {}
    if approves is not None:
        if status not in APPROVAL_STATUSES:
            raise ValueError(f"approves may only be written on a row whose status is one of "
                             f"{APPROVAL_STATUSES}, got {status!r}")
        extra["approves"] = _norm_ids(approves, "approves")
    if vetoes is not None:
        extra["vetoes"] = _norm_ids(vetoes, "vetoes")
    p = _path(path)
    stamp = (now or dt.datetime.now().astimezone()).strftime("%Y-%m-%dT%H:%M:%S%z")
    with _locked(p):
        row = {"id": last_id(p) + 1, "ts": stamp, "tier": int(tier), "status": status,
               "action": action, "reasoning": reasoning, "files": [str(f) for f in files],
               "veto_window_close": veto_window_close, "stephen_reviewed": False, **extra}
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
