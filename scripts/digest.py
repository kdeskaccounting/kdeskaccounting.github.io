#!/usr/bin/env python3
"""The daily digest: what published, what is queued for Stephen, what moved, what is open.

  python3 scripts/digest.py                       # print the markdown
  python3 scripts/digest.py --send                # + email it to Stephen via gws
  python3 scripts/digest.py --vault               # + append it to today's ~/CommandCenter note
  python3 scripts/digest.py --send --vault --dry-run   # compose only, no send, no write
  python3 scripts/digest.py --out "$GITHUB_STEP_SUMMARY"

Sections: ledger entries in the last 24 h · queue cards outstanding · snapshot deltas from the
JSONL trackers · open veto windows. Appending to the vault is idempotent — a second run the
same day replaces its own "## KDesk digest" section rather than stacking another copy.

Privacy: this repo is PUBLIC and `--out "$GITHUB_STEP_SUMMARY"` can land the digest in a public
CI log. compose() therefore never returns an email address — not even a KDesk-own or Stephen-own
one — and never a private handle: every free-text field goes through `gws.scrub` (scripts/gws.py),
which masks known secrets, elides base64-shaped runs of 40+ characters (a MIME body, an opaque
token, or a Google spreadsheet id — the private CRM sheet's handle is exactly 44 of them) and
swaps anything shaped like an address for the `<redacted:XXXXXXXX>` marker, the same convention
the rest of the repo uses for pseudonymising addresses.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import pathlib
import re
import sys
from email.message import EmailMessage
from typing import Callable

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import gws  # noqa: E402  (the one gws seam + the one scrubber; see scripts/gws.py)
import ledger  # noqa: E402

VAULT_ROOT = pathlib.Path.home() / "CommandCenter"
VAULT_HEADING = "## KDesk digest"
SENDER = "santiagokdesk@gmail.com"
RECIPIENT = "santiagokdesk@gmail.com"
TRACKING = REPO / "marketing" / "seo-tracking"
SNAPSHOTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gumroad-snapshots.jsonl", ("all_time.paid_full_price", "all_time.download_events",
                                 "all_time.unique_people", "all_time.revenue_usd")),
    # Real field names as written by scripts/pull_youtube_snapshot.py — confirmed against the
    # last two rows of the tracked file, not the draft plan's guessed "totals.views"/
    # "totals.subscribers" (that path never exists, so it was a permanent no-op).
    ("youtube-snapshots.jsonl", ("subscribers", "total_views", "shorts_views", "longform_views")),
    # ga4-/gsc-snapshots.jsonl are both written by scripts/pull_seo_snapshot.py; keys below
    # match its actual output dict, confirmed against the last two rows of each tracked file.
    ("ga4-snapshots.jsonl", ("active_users_7d", "sessions_7d", "users_30d", "key_events_7d")),
    ("gsc-snapshots.jsonl", ("totals.clicks", "totals.impressions", "totals.ctr_pct",
                             "totals.avg_position")),
    # bing-snapshots.jsonl: scripts/pull_bing_snapshot.py has never been run in this checkout
    # (no ~/kdesk-analytics/bing-api-key.txt yet), so no real file exists to read keys from
    # or drift-test against. Its schema would be ("totals.clicks", "totals.impressions",
    # "totals.ctr_pct") per pull_bing_snapshot.py's pull() — add a SNAPSHOTS entry for it
    # once a real snapshot lands so the drift test below can cover it too.
    ("mailerlite-sync.jsonl", ()),
)

GWS_TIMEOUT = 120


def _scrub(text: str) -> str:
    """The repo-wide scrubber, with no address kept.

    gws.scrub() masks known secrets, elides base64-shaped runs of 40+ characters and swaps
    every remaining address for a `<redacted:XXXXXXXX>` marker. `keep` is deliberately
    empty: no exception for KDesk's own or Stephen's own address, because the digest can
    land in a public CI step summary, and this is the one seam every section funnels
    through before it becomes "the digest" (compose() below returns the result).

    The base64 rule is load-bearing here for a second reason: a Google spreadsheet id is a
    44-character run of exactly those characters, so the private CRM sheet's handle is
    elided along with anything else that long and opaque.
    """
    return gws.scrub(text)


@dataclasses.dataclass(frozen=True)
class Section:
    heading: str
    lines: list[str]

    def render(self) -> str:
        body = "\n".join(self.lines) if self.lines else "_(nothing)_"
        return f"{self.heading}\n\n{body}\n"


def recent_entries(entries: list[dict], now: dt.datetime, hours: int = 24) -> list[dict]:
    """The ledger rows stamped within the last `hours`.

    ledger.parse_ts, not a local strptime: the format string this used ("%Y-%m-%dT%H:%M:%S%z")
    rejects a stamp with fractional seconds or minute precision, and a rejected row did not
    fail loudly - it silently vanished from the digest. The shared parser is also the one
    open_veto_windows() below already uses, so a row cannot be readable in one section of
    the same digest and invisible in another.

    A row whose stamp cannot be parsed, or cannot be compared (a naive stamp against an
    aware `now`), is skipped rather than raised: one bad row in an append-only log a
    scheduled job writes to every day must not take the whole digest down.
    """
    cutoff = now - dt.timedelta(hours=hours)
    out = []
    for row in entries:
        try:
            stamp = ledger.parse_ts(row["ts"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            if stamp >= cutoff:
                out.append(row)
        except TypeError:
            continue          # naive vs aware: refuse the comparison rather than guess
    return out


def open_veto_windows(entries: list[dict], now: dt.datetime) -> list[dict]:
    """The windows still waiting on Stephen: unelapsed, and not already answered by him.

    "Answered" is a later entry whose `approves` or `vetoes` names this id — the same signal
    scripts/ledger.py's gate reads. A window he approved early (#85 did that for #69 and #70)
    is not open, whatever its clock says, and listing it as open at 07:30 asks him for an
    answer he has already given.
    """
    out = []
    for row in entries:
        close = row.get("veto_window_close")
        if not close:
            continue
        if ledger.answer(int(row.get("id", 0) or 0), entries) is not None:
            continue
        try:
            closes = ledger.parse_ts(close)
        except ValueError:
            continue
        if closes.tzinfo is None:
            closes = closes.replace(tzinfo=now.tzinfo)
        if now.tzinfo is None and closes.tzinfo is not None:
            continue  # naive now vs aware close: refuse the comparison rather than guess
        if closes > now:
            out.append(row)
    return out


def queue_cards(repo: pathlib.Path) -> list[pathlib.Path]:
    root = pathlib.Path(repo) / "marketing" / "publish-queue"
    return sorted(root.rglob("*.md")) if root.exists() else []


def _dig(row: dict, dotted: str):
    node = row
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, (int, float)) else None


def snapshot_delta(path: pathlib.Path, keys: tuple[str, ...]) -> dict:
    """Last row minus the previous row for each dotted key.

    A malformed line is skipped with a note on stderr rather than raising: one bad row in a
    tracker a scheduled job appends to every day must not take the whole digest down with it.
    Skipping means "not there" for every purpose below, same as a file that never had a
    second row — 0 parseable rows returns {}; exactly 1 reports the value with no delta.
    """
    path = pathlib.Path(path)
    if not path.exists() or not keys:
        return {}
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"digest: skipping malformed JSON in {path} (line {lineno}): {exc}",
                 file=sys.stderr)
    if not rows:
        return {}
    last, previous = rows[-1], (rows[-2] if len(rows) > 1 else None)
    out = {}
    for key in keys:
        now_value = _dig(last, key)
        if now_value is None:
            continue
        if previous is None:
            out[key] = (now_value, None)
            continue
        before = _dig(previous, key)
        out[key] = (now_value, None if before is None else round(float(now_value) - float(before), 2))
    return out


def _fmt_delta(delta) -> str:
    if delta is None:
        return "(first row)"
    if delta == 0:
        return "±0"
    return f"{'+' if delta > 0 else ''}{delta:g}"


def compose(now: dt.datetime, recent: list[dict], veto: list[dict],
            cards: list[pathlib.Path], deltas: dict, *,
            redact: Callable[[str], str] = _scrub) -> str:
    """Compose the digest markdown. Pure: no filesystem or subprocess I/O of its own — the
    default `redact=_scrub` is the one call that can touch the salt file (privacy.email_hash),
    so pass `redact=lambda text: text` in a test that wants compose() to touch nothing at all.
    """
    shipped = Section("### Shipped in the last 24 h",
                      [f"- **{r['id']}** T{r['tier']} {r['action'][:220]}" for r in recent]
                      or ["Nothing logged in the last 24 h."])
    waiting = Section("### Waiting on Stephen",
                      [f"- `{p.parent.name}/{p.name}`" for p in cards] or ["Queue is empty."])
    windows = Section("### Open veto windows",
                      [f"- **{r['id']}** closes {r['veto_window_close']} — {r['action'][:160]}"
                       for r in veto] or ["No open veto windows."])
    number_lines = []
    for filename, values in deltas.items():
        for key, (value, delta) in values.items():
            number_lines.append(f"- `{filename}` **{key}** = {value} ({_fmt_delta(delta)})")
    numbers = Section("### Numbers", number_lines or ["No snapshot rows yet."])
    parts = "\n".join(s.render() for s in (shipped, waiting, windows, numbers))
    md = f"{VAULT_HEADING} — {now.strftime('%Y-%m-%d')}\n\n{parts}"
    return redact(md)


def vault_path(now: dt.datetime, *, root: pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(root or VAULT_ROOT) / "01-Daily" / f"{now.strftime('%Y-%m-%d')}.md"


def _render_daily_template(text: str, now: dt.datetime) -> str:
    """Fill the vault's Obsidian date placeholders the same way _meta/scripts/daily-briefing.sh
    does: `{{date:YYYY-MM-DD}}` -> ISO date, `{{date:dddd, MMMM D, YYYY}}` -> the long form."""
    long_form = f"{now.strftime('%A')}, {now.strftime('%B')} {now.day}, {now.strftime('%Y')}"
    return (text.replace("{{date:YYYY-MM-DD}}", now.strftime("%Y-%m-%d"))
                .replace("{{date:dddd, MMMM D, YYYY}}", long_form))


def append_to_vault(markdown: str, now: dt.datetime, *, root: pathlib.Path | None = None) -> pathlib.Path:
    path = vault_path(now, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = markdown if markdown.endswith("\n") else markdown + "\n"
    if not path.exists():
        template_path = pathlib.Path(root or VAULT_ROOT) / "_Templates" / "Daily.md"
        try:
            base = _render_daily_template(template_path.read_text(encoding="utf-8"), now).rstrip("\n")
        except OSError:
            base = ""
        content = f"{base}\n\n{body}" if base else body
        path.write_text(content, encoding="utf-8")
        return path
    existing = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(VAULT_HEADING)}.*?$\n.*?(?=^## (?!KDesk digest)|\Z)",
                         re.S | re.M)
    if pattern.search(existing):
        path.write_text(pattern.sub(lambda _m: body + "\n", existing, count=1), encoding="utf-8")
    else:
        path.write_text(existing.rstrip("\n") + "\n\n" + body, encoding="utf-8")
    return path


def _gws(argv: list[str], body: dict | None = None) -> dict:
    """The one send seam. Tests monkeypatch this; nothing else shells out.

    scripts/gws.py keeps only the first line of stderr, so a gws failure that echoes the
    --json body it choked on (here: the base64url MIME envelope of the digest) cannot carry
    that echo into a traceback the workflow log prints.
    """
    return gws.run_json(argv, body, timeout=GWS_TIMEOUT)


def send(markdown: str, now: dt.datetime) -> dict:
    msg = EmailMessage()
    msg["To"] = RECIPIENT
    msg["From"] = f"KDesk digest <{SENDER}>"
    msg["Subject"] = f"KDesk digest — {now.strftime('%Y-%m-%d')}"
    msg.set_content(markdown)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
    return _gws(["gmail", "users", "messages", "send", "--params", json.dumps({"userId": "me"})],
                {"raw": raw})


def main() -> int:
    ap = argparse.ArgumentParser(description="Compose (and optionally send) the daily digest.")
    ap.add_argument("--send", action="store_true", help="email it to Stephen via gws")
    ap.add_argument("--vault", action="store_true",
                    help="append it to ~/CommandCenter/01-Daily/YYYY-MM-DD.md (local only)")
    ap.add_argument("--out", type=pathlib.Path, help="also write the markdown to this file")
    ap.add_argument("--dry-run", action="store_true", help="compose only; never send or write")
    a = ap.parse_args()
    now = dt.datetime.now().astimezone()
    entries = ledger.entries()
    deltas = {name: snapshot_delta(TRACKING / name, keys) for name, keys in SNAPSHOTS}
    deltas = {name: values for name, values in deltas.items() if values}
    markdown = compose(now, recent_entries(entries, now), open_veto_windows(entries, now),
                       queue_cards(REPO), deltas)
    print(markdown)
    if a.dry_run:
        return 0
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    if a.vault:
        print(f"vault -> {append_to_vault(markdown, now)}", file=sys.stderr)
    if a.send:
        send(markdown, now)
        print("emailed to " + RECIPIENT, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
