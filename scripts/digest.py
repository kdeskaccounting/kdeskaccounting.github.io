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
one — every free-text field is passed through `browser.session.redact_secrets` (known secrets:
tokens, bearer/apikey headers) and then through an address-pattern scrub that swaps anything
shaped like an email for the `<redacted:XXXXXXXX>` marker (scripts/privacy.email_hash), the same
convention the rest of the repo uses for pseudonymising addresses.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from email.message import EmailMessage

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402
import privacy  # noqa: E402
from browser import session  # noqa: E402

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

# Same shape as tests/test_no_third_party_emails.py's EMAIL pattern — kept independent (a
# production module must not import from tests/) but deliberately identical.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _scrub(text: str) -> str:
    """Mask known secrets, then swap any email-shaped address for a `<redacted:XXXXXXXX>`.

    No exception for KDesk's own or Stephen's own address: the digest can land in a public
    CI step summary, and this is the one seam every section funnels through before it
    becomes "the digest" (compose() below returns the result), so it is the one place that
    has to hold the line.
    """
    masked = session.redact_secrets(text)
    return _EMAIL.sub(lambda m: f"<redacted:{privacy.email_hash(m.group(0))[:8]}>", masked)


@dataclasses.dataclass(frozen=True)
class Section:
    heading: str
    lines: list[str]

    def render(self) -> str:
        body = "\n".join(self.lines) if self.lines else "_(nothing)_"
        return f"{self.heading}\n\n{body}\n"


def recent_entries(entries: list[dict], now: dt.datetime, hours: int = 24) -> list[dict]:
    cutoff = now - dt.timedelta(hours=hours)
    out = []
    for row in entries:
        try:
            stamp = dt.datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if stamp >= cutoff:
            out.append(row)
    return out


def _parse_iso(value: str) -> dt.datetime:
    """Parse an ISO-8601 stamp, including the ledger's colon-free ±HHMM offset.

    ledger.append() stamps with %z, which renders as `-0700`. datetime.fromisoformat only
    learned to read that in 3.11, and this script has to run under the system python3
    (3.9.6 on this Mac) as well as under `uv run`'s newer interpreter — identical fix and
    rationale as scripts/sales/send_reengage.py._parse_iso, which hit the same bug first.
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


def open_veto_windows(entries: list[dict], now: dt.datetime) -> list[dict]:
    out = []
    for row in entries:
        close = row.get("veto_window_close")
        if not close:
            continue
        try:
            closes = _parse_iso(close)
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
    path = pathlib.Path(path)
    if not path.exists() or not keys:
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
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
            cards: list[pathlib.Path], deltas: dict) -> str:
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
    return _scrub(md)


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
    cmd = ["gws", *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"gws send failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


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
