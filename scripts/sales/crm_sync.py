#!/usr/bin/env python3
"""Build and upsert the private "KDesk CRM" Google Sheet from Gumroad + MailerLite + the
append-only JSONL trackers. Never in the public repo — the sheet lives in Drive, owned by
santiagokdesk@gmail.com, and only its id is stored locally.

  python3 scripts/sales/crm_sync.py --dry-run     # print the counts, write nothing
  python3 scripts/sales/crm_sync.py               # create-or-upsert, then log to the ledger

Row (tab "People"): email · first_seen · source · domain · is_business · interest · stage ·
mrr · last_touch · next_action. Upserts are keyed on the lowercased email, so re-running is
idempotent: a run with nothing to change makes zero write calls.

Customer addresses are the point of this script and also its one hazard. They go into the
private sheet and nowhere else: main() prints counts and non-identifying breakdowns only,
the ledger line carries counts only, and a failure card carries counts only. sync() will
print a per-person diff when a caller asks for one (show_emails=True, which the tests use
with fixture data), but the CLI never asks.

Transport is the `gws` CLI, which carries its own santiagokdesk credentials
(~/.config/gws/). That binary is local to the Mac, so live runs happen on the Mac; CI runs
--dry-run only. Sheet id: ~/kdesk-analytics/crm-sheet-id.txt (mode 0600, never committed).
requests is imported lazily so this module is importable with the standard library alone.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Iterable

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import gws  # noqa: E402  (the one gws seam + the one scrubber; see scripts/gws.py)
import ledger  # noqa: E402
import privacy  # noqa: E402  (the tracked sync log stores digests, never addresses)
from pull_gumroad_snapshot import is_business  # noqa: E402  (single definition of the rule)

SHEET_TITLE = "KDesk CRM"
SHEET_ID_FILE = pathlib.Path.home() / "kdesk-analytics" / "crm-sheet-id.txt"
MAILERLITE_TOKEN_FILE = pathlib.Path.home() / "kdesk-analytics" / "mailerlite-token.txt"
TABS = ("People", "Events", "Pipeline", "Scoreboard")
COLUMNS = ("email", "first_seen", "source", "domain", "is_business", "interest",
           "stage", "mrr", "last_touch", "next_action")
# Who owns which cell. Machine columns are recomputed from the APIs on every run and
# overwritten without asking. Human columns are Stephen's: read them, never clobber them.
# email is the key and first_seen only ever moves backwards, so neither is in either list.
MACHINE_COLUMNS = ("source", "domain", "is_business", "interest", "stage", "mrr", "last_touch")
HUMAN_COLUMNS = ("next_action",)
LAST_COL = chr(ord("A") + len(COLUMNS) - 1)          # "J"
SOURCE_RANK = {"gumroad-paid": 3, "gumroad-free": 2, "calculator": 2, "mailerlite": 1, "": 0}
PAID_CENTS = 1                                        # any non-zero price is a purchase
MAX_PAGES = 200                                       # paging guard on both public APIs
ROW_CAP = 2000                                        # how far read_people looks down the tab
GWS_TIMEOUT = 180                                     # a 2000-row read is not a quick call
GWS_ACCOUNT = "santiagokdesk@gmail.com"               # whose credentials `gws` carries


@dataclasses.dataclass
class Person:
    email: str
    first_seen: str = ""
    source: str = ""
    domain: str = ""
    is_business: str = "FALSE"
    interest: str = ""
    stage: str = "lead"
    mrr: str = "0"
    last_touch: str = ""
    next_action: str = ""
    # Provenance, not a column: True when the person told us the interest themselves (a
    # MailerLite field) rather than us inferring it from the product they downloaded. It
    # never reaches a row, so it is excluded from equality too - two Persons are the same
    # person when their ten cells match.
    interest_declared: bool = dataclasses.field(default=False, compare=False, repr=False)

    def as_row(self) -> list[str]:
        return [str(getattr(self, c)) for c in COLUMNS]

    @classmethod
    def from_row(cls, row: list[str]) -> "Person":
        padded = list(row) + [""] * (len(COLUMNS) - len(row))
        return cls(**dict(zip(COLUMNS, padded[:len(COLUMNS)])))


def a1(tab: str, row: int) -> str:
    return f"{tab}!A{row}:{LAST_COL}{row}"


def _date(value: str) -> str:
    """Normalise every timestamp shape these APIs return to YYYY-MM-DD."""
    text = (value or "").strip().replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        return dt.datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return text[:10]


def _person(email: str, **kw) -> Person:
    email = (email or "").strip().lower()
    domain = email.rsplit("@", 1)[1] if "@" in email else ""
    return Person(email=email, domain=domain,
                  is_business="TRUE" if is_business(email) else "FALSE", **kw)


def from_gumroad(sales: list[dict]) -> dict[str, Person]:
    out: dict[str, Person] = {}
    for sale in sorted(sales, key=lambda s: s.get("created_at", "")):
        email = (sale.get("email") or "").strip().lower()
        if not email:
            continue
        day = _date(sale.get("created_at", ""))
        paid = int(sale.get("price", 0) or 0) >= PAID_CENTS
        person = out.get(email) or _person(email, first_seen=day)
        person.last_touch = day
        if paid or person.source != "gumroad-paid":
            person.source = "gumroad-paid" if paid else (person.source or "gumroad-free")
        if paid:
            person.stage = "customer"
        # Inferred, not declared: the product they took is our best guess at their interest.
        person.interest = person.interest or str(sale.get("product_name", ""))[:60]
        out[email] = person
    return out


def from_mailerlite(subscribers: list[dict]) -> dict[str, Person]:
    out: dict[str, Person] = {}
    for sub in subscribers:
        email = (sub.get("email") or "").strip().lower()
        if not email:
            continue
        day = _date(sub.get("subscribed_at") or sub.get("created_at") or "")
        person = _person(email, first_seen=day, source="mailerlite")
        person.last_touch = day
        person.interest = str((sub.get("fields") or {}).get("interest") or "")
        person.interest_declared = bool(person.interest)   # they picked this themselves
        out[email] = person
    return out


def from_seo_tracking(repo: pathlib.Path,
                     known_emails: "Iterable[str]" = ()) -> dict[str, Person]:
    """The append-only sync log is the record of who took a free file and when.

    That log lives in a PUBLIC repo, so it stores a salted digest instead of the address
    (scripts/privacy.py). A digest cannot be turned back into an address, but it can be
    matched against addresses we already hold from the live Gumroad/MailerLite pulls - pass
    those as `known_emails` and a hash-only row still enriches its person. A digest we
    cannot resolve is skipped: there is no key to file it under. Rows written before
    containment still carry a plaintext `email` and are read as-is.
    """
    out: dict[str, Person] = {}
    path = pathlib.Path(repo) / "marketing" / "seo-tracking" / "mailerlite-sync.jsonl"
    if not path.exists():
        return out
    by_hash = privacy.hash_index(known_emails)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        email = (row.get("email") or "").strip().lower()
        if not email and row.get("email_sha256"):
            email = by_hash.get(row["email_sha256"], "")
        if not email:
            continue
        day = _date(row.get("gumroad_sale", ""))
        person = _person(email, first_seen=day, source="gumroad-free")
        person.last_touch = _date(row.get("synced_at", "")) or day
        person.interest = str(row.get("product", ""))
        out[email] = person
    return out


def merge(*sources: dict[str, Person]) -> dict[str, Person]:
    merged: dict[str, Person] = {}
    for source in sources:
        for email, person in source.items():
            current = merged.get(email)
            if current is None:
                merged[email] = dataclasses.replace(person)
                continue
            if SOURCE_RANK.get(person.source, 0) > SOURCE_RANK.get(current.source, 0):
                current.source = person.source
            if person.first_seen and (not current.first_seen or person.first_seen < current.first_seen):
                current.first_seen = person.first_seen
            if person.last_touch and person.last_touch > current.last_touch:
                current.last_touch = person.last_touch
            # An interest the person declared beats one we inferred from a product name;
            # otherwise the first non-empty one stands.
            if person.interest and ((person.interest_declared and not current.interest_declared)
                                    or not current.interest):
                current.interest = person.interest
                current.interest_declared = person.interest_declared
            if person.stage == "customer":
                current.stage = "customer"
    return merged


def apply_to(existing: Person, wanted: Person) -> Person:
    """The row we actually want in the sheet: machine columns refreshed, human columns kept.

    Writing `wanted` wholesale would silently erase whatever Stephen typed into
    next_action - the sheet is a working CRM, not a read-only export, so a column a human
    owns is read and preserved rather than recomputed.
    """
    merged = dataclasses.replace(existing)
    for column in MACHINE_COLUMNS:
        setattr(merged, column, getattr(wanted, column))
    for column in HUMAN_COLUMNS:
        if not str(getattr(existing, column, "")).strip():
            setattr(merged, column, getattr(wanted, column))
    merged.email = existing.email or wanted.email
    # first_seen is the earliest we have ever seen this person; it never moves forward, so a
    # sale that has aged out of the API window cannot reset it.
    if wanted.first_seen and (not existing.first_seen or wanted.first_seen < existing.first_seen):
        merged.first_seen = wanted.first_seen
    return merged


def diff(existing_rows: list[list[str]], wanted: dict[str, Person]):
    """Return (updates, appends). updates are (1-based sheet row, Person)."""
    index: dict[str, tuple[int, Person]] = {}
    for offset, row in enumerate(existing_rows[1:], start=2):   # row 1 is the header
        if row and row[0].strip():
            index[row[0].strip().lower()] = (offset, Person.from_row(row))
    updates, appends = [], []
    for email, person in wanted.items():
        found = index.get(email)
        if found is None:
            appends.append(person)
            continue
        target = apply_to(found[1], person)
        if found[1].as_row() != target.as_row():
            updates.append((found[0], target))
    return updates, appends


def _gws(argv: list[str], body: dict | None = None) -> dict:
    """The one subprocess seam. Tests monkeypatch this; nothing else shells out.

    The implementation lives in scripts/gws.py, which keeps only the FIRST LINE of stderr in
    any error it raises. That is not tidiness: gws echoes the request it choked on, and for
    this script that request is the --json body of a Sheets upsert - People rows, i.e.
    customer addresses. This copy used to carry `proc.stderr[:400]` into a queue card that a
    PUBLIC repo tracks.
    """
    return gws.run_json(argv, body, timeout=GWS_TIMEOUT)


def _create_body() -> dict:
    """The whole spreadsheet in one request: four tabs, with the People header already in A1.

    One call rather than create-then-write-the-header, so a sheet never exists in a
    half-built state and ensure_sheet() has exactly one side effect to reason about.
    """
    sheets = []
    for tab in TABS:
        sheet: dict = {"properties": {"title": tab}}
        if tab == "People":
            sheet["data"] = [{"startRow": 0, "startColumn": 0, "rowData": [
                {"values": [{"userEnteredValue": {"stringValue": c}} for c in COLUMNS]}]}]
        sheets.append(sheet)
    return {"properties": {"title": SHEET_TITLE}, "sheets": sheets}


def _record_sheet_id(sheet_id: str) -> None:
    """Write the id 0600 from the start - it is a private handle, not repo content."""
    SHEET_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(SHEET_ID_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(sheet_id + "\n")
    os.chmod(SHEET_ID_FILE, 0o600)


def recorded_sheet_id() -> str | None:
    """The id we have already recorded, or None. Blank counts as absent.

    ensure_sheet() and main() both need this answer and must agree: when they disagreed, a
    blank file made ensure_sheet return the dry-run placeholder while main went on to call
    gws with that placeholder as a spreadsheet id.
    """
    try:
        value = SHEET_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def ensure_sheet(dry_run: bool) -> str:
    recorded = recorded_sheet_id()
    if recorded:
        return recorded
    if dry_run:
        return "(would create a new spreadsheet)"
    created = _gws(["sheets", "spreadsheets", "create"], _create_body())
    sheet_id = created["spreadsheetId"]
    _record_sheet_id(sheet_id)
    return sheet_id


def read_people(sheet_id: str) -> list[list[str]]:
    payload = _gws(["sheets", "spreadsheets", "values", "get", "--params",
                    json.dumps({"spreadsheetId": sheet_id,
                                "range": f"People!A1:{LAST_COL}{ROW_CAP}"})])
    rows = payload.get("values", [])
    if len(rows) >= ROW_CAP:
        # Everyone past the cap would look absent and be appended a second time. A silent
        # duplicate in a CRM is worse than a stop, so this becomes a queued failure.
        raise RuntimeError(
            f"People tab has reached the {ROW_CAP}-row read cap; widen ROW_CAP in "
            f"scripts/sales/crm_sync.py before syncing again, or the upsert would duplicate "
            f"every person below row {ROW_CAP}.")
    return rows


def _breakdown(people: list[Person]) -> str:
    """A non-identifying summary of a batch - counts by source, plus how many are business."""
    by_source: dict[str, int] = {}
    for person in people:
        by_source[person.source or "(none)"] = by_source.get(person.source or "(none)", 0) + 1
    parts = " · ".join(f"{k} {v}" for k, v in sorted(by_source.items()))
    business = sum(1 for p in people if p.is_business == "TRUE")
    return f"{parts or '(none)'} — business domains {business}/{len(people)}"


def sync(sheet_id: str, wanted: dict[str, Person], existing: list[list[str]], dry_run: bool,
         show_emails: bool = False) -> tuple[int, int]:
    updates, appends = diff(existing, wanted)
    if show_emails:
        for _row, person in updates:
            print(f"  ~ {person.email:<40} {person.source:<13} {person.stage}")
        for person in appends:
            print(f"  + {person.email:<40} {person.source:<13} {person.stage}")
    else:
        # The CLI path. Addresses stay in the sheet; stdout gets counts and shape only.
        print(f"  ~ update  {_breakdown([p for _r, p in updates])}")
        print(f"  + append  {_breakdown(appends)}")
    print(f"{len(updates)} to update, {len(appends)} to append")
    if dry_run or not (updates or appends):
        return len(updates), len(appends)
    if updates:
        _gws(["sheets", "spreadsheets", "values", "batchUpdate", "--params",
              json.dumps({"spreadsheetId": sheet_id})],
             {"valueInputOption": "RAW",
              "data": [{"range": a1("People", row), "values": [person.as_row()]}
                       for row, person in updates]})
    if appends:
        _gws(["sheets", "spreadsheets", "values", "append", "--params",
              json.dumps({"spreadsheetId": sheet_id, "range": "People!A1",
                          "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})],
             {"values": [person.as_row() for person in appends]})
    return len(updates), len(appends)


def card_body(detail: str, now: dt.datetime | None = None) -> str:
    """The card text. Carries no addresses - this card lives in the public repo.

    `detail` is machine text: a gws stderr line, a KeyError repr, a socket error. Any of
    those can quote the request that produced it, so it goes through gws.scrub(), which
    masks credentials, elides base64-shaped runs (a MIME body or a spreadsheet id) and
    swaps every remaining address for its salted marker. Only KDesk's own account is kept,
    and only because step 1 below asks a human to check that it is still signed in.
    """
    now = now or dt.datetime.now().astimezone()
    return (
        f"# CRM sync — needs one manual step\n\n"
        f"Queued {now.strftime('%Y-%m-%d %H:%M %z')} by scripts/sales/crm_sync.py\n\n"
        f"## Why it is here\n\n{gws.scrub(detail)}\n\n"
        f"## The remaining manual step\n\n"
        f"1. Confirm the `gws` CLI is still signed in as {GWS_ACCOUNT}:\n"
        f"   `gws gmail users getProfile --params '{{\"userId\":\"me\"}}'`\n"
        f"2. If that fails, or the error above is a scope error, re-consent once:\n"
        f"   `gws auth login -s gmail,drive,calendar,docs,sheets,slides`\n"
        f"3. Re-run `python3 scripts/sales/crm_sync.py`. The upsert is keyed on email, so\n"
        f"   re-running is safe — it will only write what is still missing.\n\n"
        f"## Privacy\n\nNo customer addresses appear in this card; they exist only in the\n"
        f"private \"{SHEET_TITLE}\" sheet.\n")


def queue_card(detail: str, repo: pathlib.Path | None = None,
               now: dt.datetime | None = None) -> pathlib.Path:
    """Queues, not silent failures: a paste-ready card with the exact remaining manual step."""
    now = now or dt.datetime.now().astimezone()
    root = pathlib.Path(repo or REPO) / "marketing" / "publish-queue" / "manual"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"crm-sync-{now.strftime('%Y-%m-%d-%H%M')}.md"
    path.write_text(card_body(detail, now), encoding="utf-8")
    return path


def fetch_gumroad() -> list[dict]:
    """Read-only pull of every sale. The token goes in the Authorization header, never a URL."""
    import requests
    from pull_gumroad_snapshot import token
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/json"}
    sales: list[dict] = []
    key = None
    for _page in range(MAX_PAGES):
        params = {"page_key": key} if key else {}
        r = requests.get("https://api.gumroad.com/v2/sales", headers=headers, params=params,
                         timeout=30)
        r.raise_for_status()
        payload = r.json()
        sales += payload.get("sales", [])
        nxt = payload.get("next_page_key")
        if not nxt or nxt == key:
            return sales
        key = nxt
    return sales


def fetch_mailerlite() -> list[dict]:
    """Read-only pull of every subscriber."""
    import requests
    token = MAILERLITE_TOKEN_FILE.read_text(encoding="utf-8").strip()
    out: list[dict] = []
    cursor = None
    for _page in range(MAX_PAGES):
        params: dict = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = requests.get("https://connect.mailerlite.com/api/subscribers",
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                         params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        out += payload.get("data", [])
        nxt = (payload.get("meta") or {}).get("next_cursor")
        if not nxt or nxt == cursor:
            return out
        cursor = nxt
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync the private KDesk CRM sheet.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        subscribers = from_mailerlite(fetch_mailerlite())
        buyers = from_gumroad(fetch_gumroad())
        # The tracker is hash-only, so it is read last: the addresses just pulled are what
        # its digests are matched against.
        tracked = from_seo_tracking(REPO, known_emails=set(subscribers) | set(buyers))
        wanted = merge(tracked, subscribers, buyers)
        sheet_id = ensure_sheet(a.dry_run)
        existing = [] if a.dry_run and recorded_sheet_id() is None else read_people(sheet_id)
        print(f"{SHEET_TITLE} ({sheet_id}) — {len(wanted)} people "
              f"from Gumroad + MailerLite + trackers")
        updated, appended = sync(sheet_id, wanted, existing, a.dry_run)
    except Exception as exc:  # noqa: BLE001
        # A traceback out of a scheduled job is a silent failure: nobody reads it. Everything
        # that can go wrong above (a gws non-zero exit, a timeout, a malformed JSON reply, a
        # missing key in one, a dead socket) becomes the same visible thing - a card with the
        # manual step and a non-zero exit. ledger.append stays outside this block: a lost
        # audit entry must be loud, not queued.
        detail = f"`crm_sync.py` could not finish: {type(exc).__name__}: {exc}"
        if a.dry_run:
            # --dry-run performs zero writes, and that includes the card. On Actions, where
            # the tokens are absent, writing one would dirty the checkout on every run.
            print(card_body(detail), file=sys.stderr)
            print("(--dry-run: card printed, not written)", file=sys.stderr)
            return 1
        card = queue_card(detail)
        print(f"queued -> {card.relative_to(REPO)}", file=sys.stderr)
        return 1
    if a.dry_run or not (updated or appended):
        return 0
    ledger.append(
        action=(f"CRM sync: updated {updated} and appended {appended} rows on the private "
                f"'{SHEET_TITLE}' Google Sheet ({sheet_id}) from Gumroad sales, MailerLite "
                f"subscribers and marketing/seo-tracking/mailerlite-sync.jsonl. "
                f"{len(wanted)} people total; keyed on lowercased email, so the run is "
                f"idempotent. No addresses left the private sheet."),
        tier=0, status="executed",
        reasoning="Track 3: the CRM is a private sheet, never the public repo.",
        files=[])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
