#!/usr/bin/env python3
"""Schedule a week of Shorts onto TikTok, one per day — the Saturday batch's one command.

  python3 scripts/publishers/schedule_week.py --week 2026-W39 \
      --assets-dir ~/parksheet/release/2026-W39                    # dry run: the DEFAULT
  python3 scripts/publishers/schedule_week.py --week 2026-W39 \
      --assets-dir ~/parksheet/release/2026-W39 --start-day 1 --hour 14:00 --go

The render batch leaves `day-1.mp4 … day-7.mp4` with a `day-N.json` beside each. This maps
day N onto the Nth day of the week (shifted by `--start-day`) at `--hour` **America/
Los_Angeles**, and hands each to the TikTok Studio driver, which skips any day already on
the posts list. Re-running the same week is therefore a no-op that prints the state.

Exit codes, because the batch branches on them:

  0  every day is scheduled (or was already)
  1  at least one day queued a card for Stephen; the rest still ran
  2  the batch itself is wrong — bad week, an mp4 with no meta, an empty directory, or the
     autonomy veto window is still open — and nothing was attempted

**Nothing reaches TikTok without `--go`.** A bare invocation prints the plan and opens no
browser, because a forgotten flag must not be able to schedule a week of posts to a live
brand account.

This is a **semi-supervised, Mac-only step** (spec Chrome rule 1): it drives a logged-in
browser, so it never belongs in a GitHub Actions schedule. Stdlib only at import time.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import zoneinfo

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402

from browser.session import redact_secrets  # noqa: E402
from publishers import publish  # noqa: E402  (the veto gate, shared, not re-implemented)
from publishers import tiktok_web  # noqa: E402
from publishers.base import REPO, PublishResult  # noqa: E402

# Stephen's own timezone, and the one TikTok Studio's form shows him. Hard-coded rather than
# read from the machine: a batch run over SSH from anywhere else must still schedule 14:00
# Pacific, not 14:00 wherever the shell happens to think it is.
TZ_NAME = "America/Los_Angeles"
DEFAULT_HOUR = "14:00"
DAY_FILE = re.compile(r"^day-(\d+)$")
WEEK = re.compile(r"^(\d{4})-W(\d{2})$")


class PlanError(ValueError):
    """The batch cannot be planned: bad week, bad hour, missing or unpaired assets."""


def tz() -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(TZ_NAME)


def week_start(week: str) -> dt.date:
    """'2026-W39' → the Monday of that ISO week."""
    match = WEEK.match(str(week or "").strip())
    if not match:
        raise PlanError(f"--week {week!r} must look like 2026-W39 (ISO year and week)")
    year, number = int(match.group(1)), int(match.group(2))
    try:
        return dt.date.fromisocalendar(year, number, 1)
    except ValueError as exc:
        raise PlanError(f"--week {week!r} is not a real ISO week: {exc}") from exc


def parse_hour(text: str) -> tuple[int, int]:
    """'14:00' → (14, 0). Twenty-four hour, so 2 p.m. can never read as 2 a.m."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(text or "").strip())
    if not match:
        raise PlanError(f"--hour {text!r} must look like 14:00 (24-hour, local Pacific)")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise PlanError(f"--hour {text!r} is not a real time of day")
    return hour, minute


def slot_for(monday: dt.date, start_day: int, n: int, hour: tuple[int, int]) -> dt.datetime:
    """The instant day `n` posts: the week's Monday, plus the start-day and day offsets.

    Adding days to a date rather than juggling weekday numbers is what makes `--start-day 3`
    with seven days run Wednesday → the following Tuesday instead of wrapping back to Monday.
    The zone is attached last, so the offset is whatever Los Angeles is actually on that day
    (-07:00 in September, -08:00 in November) rather than whatever it is today.
    """
    day = monday + dt.timedelta(days=(int(start_day) - 1) + (int(n) - 1))
    return dt.datetime(day.year, day.month, day.day, hour[0], hour[1], tzinfo=tz())


def discover(assets_dir: pathlib.Path) -> list[tuple[int, pathlib.Path, pathlib.Path]]:
    """[(n, mp4, json)] for every day-N.mp4 in the directory, in numeric order.

    Numeric, not lexical: sorted() puts day-10 between day-1 and day-2, which would schedule
    the week in the wrong order and is invisible until a batch has ten days in it.
    """
    assets_dir = pathlib.Path(assets_dir)
    if not assets_dir.is_dir():
        raise PlanError(f"--assets-dir {assets_dir} is not a directory")
    found = []
    for mp4 in assets_dir.glob("day-*.mp4"):
        match = DAY_FILE.match(mp4.stem)
        if match:
            found.append((int(match.group(1)), mp4, mp4.with_suffix(".json")))
    if not found:
        raise PlanError(f"no day-N.mp4 files in {assets_dir}")
    missing = [str(meta.name) for _n, _mp4, meta in found if not meta.exists()]
    if missing:
        raise PlanError(
            f"{len(missing)} video(s) in {assets_dir} have no meta beside them "
            f"({', '.join(sorted(missing))}). Refusing to schedule part of a week: a batch "
            f"this incomplete means the render step did not finish.")
    return sorted(found)


def load_meta(path: pathlib.Path) -> dict:
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"{path.name} could not be read as JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise PlanError(f"{path.name} must be a JSON object, got {type(meta).__name__}")
    return meta


def plan(assets_dir: pathlib.Path, week: str, start_day: int, hour: str) -> list[dict]:
    """Every day of the batch, resolved. Pure apart from reading the directory."""
    monday = week_start(week)
    at = parse_hour(hour)
    rows = []
    for n, mp4, meta_path in discover(assets_dir):
        when = slot_for(monday, start_day, n, at)
        meta = load_meta(meta_path)
        rows.append({"n": n, "asset": mp4, "when": when,
                     "meta": {**meta, "schedule_at": when.isoformat()}})
    return rows


def outcome(result: PublishResult) -> str:
    """ok / skip / QUEUED — `skip` is the idempotent 'it was already there' answer."""
    if not result.ok:
        return "QUEUED"
    return "skip" if "already scheduled" in (result.detail or "") else "ok"


def summary_lines(rows: list[dict]) -> list[str]:
    """The table printed at the end — one line per day, wide enough to scan, not to parse."""
    out = [f"{'day':<7} {'when':<21} {'status':<7} {'detail'}",
           f"{'-' * 7} {'-' * 21} {'-' * 7} {'-' * 40}"]
    for row in rows:
        when = row["when"]
        target = row.get("url") or row.get("queued_path") or ""
        detail = " ".join(str(row.get("detail", "")).split())[:70]
        out.append(f"day-{row['n']:<3} {when.strftime('%a %Y-%m-%d %H:%M'):<21} "
                   f"{row['status']:<7} {target or detail}")
    return out


def ledger_action(row: dict, result: PublishResult) -> str:
    """The ledger line. The caption never appears past its 40-character key.

    decisions/decisions.jsonl is tracked in a public repo and the daily digest re-emits it
    into a public workflow log, so the rule is the same one the privacy pass established:
    enough to audit the action, never the content.
    """
    key = tiktok_web.caption_key(tiktok_web.caption_of(row["meta"]))
    return (f"Scheduled {row['asset'].name} on tiktok_web for "
            f"{row['when'].isoformat()} (caption key {key!r}): "
            f"{result.url or 'QUEUED ' + str(result.queued_path)}. {result.detail}")


def main(argv: list[str] | None = None, *, repo: pathlib.Path | None = None,
         publisher=None, now: dt.datetime | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Schedule a week of day-N.mp4 Shorts onto TikTok, one per day.")
    ap.add_argument("--week", required=True, help="ISO week, e.g. 2026-W39")
    ap.add_argument("--assets-dir", required=True, type=pathlib.Path,
                    help="directory holding day-N.mp4 and day-N.json")
    ap.add_argument("--start-day", type=int, default=1,
                    help="which day of the week day-1 lands on (1=Monday, default 1)")
    ap.add_argument("--hour", default=DEFAULT_HOUR,
                    help=f"local {TZ_NAME} time of day, 24-hour (default {DEFAULT_HOUR})")
    # Dry run is the DEFAULT and --go is the deliberate act. This command schedules a week
    # of posts to a live brand account through a browser; that must not happen because
    # someone forgot a flag, or pasted a line from the runbook with the tail cut off.
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="the default: print the plan, open no browser, write nothing")
    mode.add_argument("--go", action="store_true",
                      help="actually schedule — the only way anything reaches TikTok")
    a = ap.parse_args(argv)
    dry_run = not a.go
    repo = pathlib.Path(repo) if repo is not None else REPO

    try:
        rows = plan(a.assets_dir, a.week, a.start_day, a.hour)
    except PlanError as exc:
        print(f"REFUSING: {redact_secrets(exc)}", file=sys.stderr)
        return 2

    # The same T2 gate publish.py uses, from the same helper — a second copy of the rule is
    # how the two drift apart. --dry-run writes nothing, so it stays ungated.
    if not dry_run:
        ok, why = publish.veto_gate(now)
        if not ok:
            print(f"REFUSING: ledger entry {publish.VETO_ENTRY} {why}. Nothing was "
                  f"scheduled. Re-run with --dry-run to see the week's plan.", file=sys.stderr)
            return 2

    pub = publisher if publisher is not None else tiktok_web.TikTokWebPublisher(repo=repo)
    rc = 0
    for row in rows:
        try:
            result = pub.publish(row["asset"], row["meta"], dry_run)
        except Exception as exc:  # noqa: BLE001 — a driver that cannot even queue is fatal
            print(redact_secrets(f"day-{row['n']} FAILED {type(exc).__name__}: {exc}"),
                  file=sys.stderr)
            row.update(status="ERROR", detail=f"{type(exc).__name__}: {exc}")
            rc = 2
            continue
        row.update(status=outcome(result), detail=result.detail,
                   url=result.url, queued_path=result.queued_path)
        if dry_run:
            continue
        if not result.ok:
            rc = max(rc, 1)
        if row["status"] != "skip":
            # A skip changed nothing on TikTok, so it records nothing. Everything else —
            # a schedule or a queued card — is an action and gets its line.
            ledger.append(
                action=redact_secrets(ledger_action(row, result)),
                tier=1, status="executed",
                reasoning=("T1 auto-publish after the fact-check gate (2026-09-14 autonomy "
                           "decision), scheduled by hand on the Mac through TikTok Studio: "
                           "Upload-Post reaches TikTok only on its paid plan."),
                files=[str(result.queued_path)] if result.queued_path else [])
    for line in summary_lines(rows):
        print(redact_secrets(line))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
