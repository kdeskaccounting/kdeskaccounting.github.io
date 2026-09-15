#!/usr/bin/env python3
"""Send the drafted re-engagement email to the 14 downloaders the nurture skipped.

The COPY comes from marketing/email-sequences/re-engage-2026-09.md — this script never
writes copy. The RECIPIENTS do not: that file is tracked in a public repo, so its table
carries `<redacted:XXXXXXXX>` markers only. The real rows (subscriber id, address, product
and every merge value) live in the private store, mode 0600, outside the repo:

    ~/kdesk-analytics/private/re-engage-2026-09-recipients.json

One message per recipient through `gws gmail users messages send` as santiagokdesk@gmail.com,
two seconds apart, one ledger line each. A recipient whose merge fields cannot be filled gets
a queue card instead of a half-rendered email.

  python3 scripts/sales/send_reengage.py --dry-run              # render every email, send none
  python3 scripts/sales/send_reengage.py [--veto-entry 69] [--limit 2] [--recipients PATH]

Re-running is safe: anyone the ledger already records a send for is skipped, so a run that
died at recipient 7 resumes rather than emailing the first six a second time (--resend
overrides, deliberately).

Refuses to send unless the named ledger entry exists, is a T2 act-with-veto-window entry,
was not vetoed, and its veto_window_close has passed. Entry 69 (the T1-loosening decision)
closes 2026-09-16T12:00:00-0700, so a live run before then refuses and sends nothing. Confirm
which entry carries the window first:  python3 scripts/ledger.py --tail 5

PRIVACY (this repo is public — see CLAUDE.md "Privacy"): the address exists in exactly one
place, the MIME envelope handed to gws. Everything else — stdout, the queue cards under
marketing/publish-queue/, the ledger line — carries the 8-hex salted digest prefix instead,
the same marker the tracked draft uses, so a row stays joinable to the private store without
naming anyone. scrub() is the one choke point that guarantees it.

Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import time
from email.message import EmailMessage

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402
import privacy  # noqa: E402  (the salted digest; never an address in a tracked file)
from browser import session  # noqa: E402  (redact_secrets + the queue-card writers)

LEDGER_PATH = ledger.DEFAULT_PATH
SOURCE = REPO / "marketing" / "email-sequences" / "re-engage-2026-09.md"
# Personal data lives outside the repo, 0700/0600, and is never synced to git.
RECIPIENTS_PATH = (pathlib.Path.home() / "kdesk-analytics" / "private"
                   / "re-engage-2026-09-recipients.json")
SENDER = "santiagokdesk@gmail.com"
SENDER_NAME = "KDesk Accounting"
GAP_SECONDS = 2.0
VETO_ENTRY_DEFAULT = 69
VETO_TIER = 2
MERGE_FIELDS = ("product_name", "page_url", "paid_url", "price", "free_cap")
MERGE_RE = re.compile(r"\{\$([a-z_]+)\}")
ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# A base64/base64url MIME body (what rfc822() produces) is one long run of these characters
# with no spaces or punctuation. gws stderr can echo the --json payload it was given, which
# is exactly that: a request containing the encoded message, address and all. This catches
# it even though it never matches ADDRESS_RE (base64 has no '@').
B64_RE = re.compile(r"[A-Za-z0-9_-]{40,}")
CONSECUTIVE_FAILURE_LIMIT = 3
# The exact opening of every ledger line this script writes, and the pattern that reads them
# back. Matching a fixed sentence rather than the word "re-engagement" keeps prose in some
# other entry from ever being mistaken for evidence that a person was emailed.
CAMPAIGN = "2026-09 re-engagement"
SENT_PREFIX = f"Sent the {CAMPAIGN} email to "
SENT_RE = re.compile(re.escape(SENT_PREFIX) + r"(<redacted:[0-9a-f]{8}>)")
GWS_BIN = shutil.which("gws") or "/opt/homebrew/bin/gws"


class RecipientsError(RuntimeError):
    """The private recipient store is missing, unreadable or not what this script expects.

    Always fatal: a send that cannot read its own recipient list must stop, not improvise.
    """


@dataclasses.dataclass(frozen=True)
class Recipient:
    subscriber_id: str
    email: str
    product: str
    merge_fields: dict = dataclasses.field(default_factory=dict)


# --------------------------------------------------------------------------- pseudonymisation

def digest(email: str) -> str:
    """First 8 hex of the salted SHA-256 — the marker the tracked draft's table uses."""
    return privacy.email_hash(email)[:8]


def marker(email: str) -> str:
    return f"<redacted:{digest(email)}>"


def scrub(text: object) -> str:
    """Mask credentials, then replace every address that is not KDesk's own with its marker.

    The one choke point. Everything that leaves this script other than the MIME envelope —
    stdout, stderr, a queue card, a ledger line — goes through here, including text this
    script did not write (a `gws` stderr tail can echo the request it failed on). Applying
    it to strings that hold no address costs nothing; forgetting it once publishes a
    customer's address to a public repo forever.
    """
    def swap(match: re.Match) -> str:
        address = match.group(0)
        return address if address.lower() == SENDER else marker(address)

    masked = session.redact_secrets(text)
    # Elide long base64-shaped runs BEFORE the address swap: a raw MIME body never contains
    # '@' (base64url's alphabet doesn't have one), so ADDRESS_RE alone would let it straight
    # through, undecoded but perfectly decodable by anyone who copies it out of the card.
    masked = B64_RE.sub("<b64 elided>", masked)
    return ADDRESS_RE.sub(swap, masked)


# ------------------------------------------------------------------------------- the copy only

def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{heading}.*?$\n(.*?)(?=^##\s|\Z)", re.S | re.M)
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def parse(markdown: str) -> tuple[str, str]:
    """Return (subject, body). Deliberately NOT recipients.

    The plan's draft returned a third element read out of the `## Recipients` table. That
    table is now redaction markers (the file is tracked in a public repo), so parsing it
    would yield `<redacted:…>` where an address belongs and the send would address nobody.
    Recipients come from load_recipients() and the private store instead.
    """
    subject = _section(markdown, "Subject").strip()
    body = _section(markdown, "Body")
    if not subject:
        raise ValueError(f"{SOURCE.name}: no '## Subject' section")
    if not body:
        raise ValueError(f"{SOURCE.name}: no '## Body' section")
    return subject, body


# ----------------------------------------------------------------------- the private recipients

def load_recipients(path: pathlib.Path | None = None) -> list[Recipient]:
    """Read the 0600 private store. Raises RecipientsError — never guesses, never sends."""
    store = pathlib.Path(path) if path is not None else RECIPIENTS_PATH
    try:
        text = store.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipientsError(
            f"cannot read the private recipient store {store} "
            f"({exc.strerror or exc}). The 14 rows live outside the repo, mode 0600; "
            f"pass --recipients PATH if it lives somewhere else on this machine.") from exc
    mode = stat.S_IMODE(store.stat().st_mode)
    if mode & 0o077:
        # Warn, never chmod: silently widening or narrowing a file Stephen owns is worse
        # than telling him. Personal data readable by the group or the world is a finding.
        print(f"WARNING: {store} is mode {mode:04o}, not 0600 — this file holds personal "
              f"data; run: chmod 600 {store}", file=sys.stderr)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecipientsError(f"{store} is not valid JSON: {exc}") from exc
    rows = payload.get("recipients") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RecipientsError(f"{store} has no non-empty 'recipients' list")
    out: list[Recipient] = []
    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise RecipientsError(f"{store}: recipient #{position} is not an object")
        address = str(row.get("email") or "").strip().lower()
        if "@" not in address:
            # Never echo the value - it may be a malformed address, which is still personal.
            raise RecipientsError(f"{store}: recipient #{position} has no usable 'email'")
        fields = row.get("merge_fields") or {}
        out.append(Recipient(subscriber_id=str(row.get("subscriber_id") or ""),
                             email=address,
                             product=str(row.get("product") or ""),
                             merge_fields=dict(fields) if isinstance(fields, dict) else {}))
    return out


def merge_fields_for(recipient: Recipient) -> dict:
    """The merge values for one recipient, from the private store.

    The plan's draft re-read these from MailerLite over HTTP. The store now carries them
    (it was built from that same MailerLite pull), so the send is deterministic, offline and
    has one source of truth instead of two that can disagree mid-campaign. A field the store
    does not hold comes back empty, which render() turns into a queue card.
    """
    stored = recipient.merge_fields or {}
    return {key: stored.get(key, "") for key in MERGE_FIELDS}


def render(template: str, fields: dict) -> str:
    """Substitute every `{$key}`; raise KeyError naming every field it could not fill."""
    missing = sorted({name for name in MERGE_RE.findall(template) if not fields.get(name)})
    if missing:
        raise KeyError(f"unfilled merge fields: {', '.join(missing)}")
    return MERGE_RE.sub(lambda m: str(fields[m.group(1)]), template)


def rfc822(to: str, subject: str, body: str, sender: str = SENDER) -> str:
    """base64url of the MIME message — the one place the address legitimately appears."""
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = sender if "<" in sender else f"{SENDER_NAME} <{sender}>"
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")


# ------------------------------------------------------------------------------------ the gate

def _parse_iso(value: str) -> dt.datetime:
    """Parse an ISO-8601 stamp, including the ledger's colon-free ±HHMM offset.

    ledger.append() stamps with %z, which renders as `-0700`. datetime.fromisoformat only
    learned to read that in 3.11, and the runbook drives these scripts with the system
    python3 — 3.9.6 on this Mac. Without this the gate refused every entry as "unparseable":
    fail-closed, so nothing was ever sent wrongly, but for the wrong reason, and it would
    have gone on refusing after the window actually shut.
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


def veto_ok(close_iso: str | None, now: dt.datetime) -> tuple[bool, str]:
    """Has the veto window closed? The reason is a verb phrase; the caller names the entry."""
    if not close_iso:
        return False, "has no veto_window_close — nothing authorises this send"
    try:
        closes = _parse_iso(close_iso)
    except ValueError:
        return False, f"has an unparseable veto_window_close {close_iso!r}"
    if closes.tzinfo is None:
        # A stamp with no offset is read in the reader's own zone rather than crashing the
        # comparison; the ledger always writes one, so this only covers a hand-edited row.
        closes = closes.replace(tzinfo=now.tzinfo)
    if now.tzinfo is None and closes.tzinfo is not None:
        # A naive `now` can't be compared against an aware `closes` (TypeError). Refuse
        # rather than guess which offset the caller meant - a wrong guess here is the
        # difference between "refused" and "sent".
        return False, (f"the caller passed a timezone-naive 'now', which cannot be compared "
                       f"against veto_window_close {close_iso} — refusing rather than "
                       f"assuming an offset")
    if now < closes:
        return False, (f"has a veto window that closes {close_iso}; it is "
                       f"{now.isoformat(timespec='minutes')}")
    return True, f"veto window closed {close_iso}"


def veto_gate(entry: dict | None, now: dt.datetime,
              entry_id: int = VETO_ENTRY_DEFAULT) -> tuple[bool, str]:
    """Every condition that authorises an autonomous send, in one place.

    Four ways to fail and they are not interchangeable: an entry that does not exist yet, an
    entry of the wrong tier (a T0 note authorises nothing), an entry Stephen actually vetoed,
    and a window that has not closed. The status check is the one that matters most: a vetoed
    decision whose window has since elapsed would otherwise read as permission.
    """
    if entry is None:
        return False, (f"does not exist yet — the T{VETO_TIER} entry that authorises this "
                       f"send has not been written. Run `python3 scripts/ledger.py --tail 5` "
                       f"and pass --veto-entry with the id that carries the window")
    try:
        tier = int(entry.get("tier", -1))
    except (TypeError, ValueError):
        tier = -1
    if tier != VETO_TIER:
        return False, (f"is tier {entry.get('tier')!r}, not a T{VETO_TIER} "
                       f"act-with-veto-window entry — it authorises no send")
    if str(entry.get("status", "")).strip().lower() == "vetoed":
        return False, ("was VETOED — Stephen said no. An elapsed window does not turn a veto "
                       "into permission; this send must not happen")
    return veto_ok(entry.get("veto_window_close"), now)


# ----------------------------------------------------------------------------------- the seams

def _gws(argv: list[str], body: dict | None = None) -> dict:
    """The one send seam. Tests monkeypatch this; nothing else shells out.

    Only the FIRST LINE of stderr ever leaves this function. gws stderr on a failure can
    echo the request it choked on - including the --json body, which for a send is the
    base64url MIME envelope with the recipient's address inside it. A multi-line echo of
    "here is the request that failed" must never become "here is the request that failed,
    address and all" in a card this repo tracks.
    """
    cmd = [GWS_BIN, *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        lines = (proc.stderr or "").strip().splitlines()
        reason = lines[0] if lines else "(gws produced no stderr)"
        raise RuntimeError(f"gws {' '.join(argv[:4])} failed: {reason}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _sleep(seconds: float) -> None:
    """The pacing seam, so tests assert the gap without waiting it out."""
    time.sleep(seconds)


# ------------------------------------------------------------------------------------ the send

def card_markdown(recipient: Recipient, detail: str,
                  now: dt.datetime | None = None) -> str:
    """A paste-ready card for one recipient. Carries the marker, never the address."""
    return scrub(session.queue_card_markdown(
        kind="email",
        title=f"Send the {CAMPAIGN} email to {marker(recipient.email)} by hand",
        why=(f"send_reengage.py could not render it: {detail}. This recipient "
             f"({recipient.subscriber_id}) took the free {recipient.product}. The address is "
             f"in the private store, keyed by this marker — it is deliberately not in this "
             f"card, which git tracks."),
        steps=[f"Look {marker(recipient.email)} up in {RECIPIENTS_PATH} "
               f"(match on redaction_id / subscriber_id)",
               f"Open {SOURCE.relative_to(REPO)} and copy the subject and body verbatim",
               f"Fill {', '.join(MERGE_FIELDS)} for '{recipient.product}' by hand",
               f"Send it from {SENDER}, then add a ledger line: "
               f"python3 scripts/ledger.py --tail 5 shows the format"],
        now=now))


def _queue(repo: pathlib.Path, recipient: Recipient, detail: str) -> pathlib.Path:
    return session.write_queue_card(repo, "manual", f"reengage-{digest(recipient.email)}",
                                    card_markdown(recipient, detail))


def unlogged_card_markdown(recipient: Recipient, subject: str, detail: str,
                           now: dt.datetime | None = None) -> str:
    """A loud card for the one failure worse than a failed send: a send that worked but was
    never recorded.

    Without a ledger line, a resumed run has no way to know this recipient was already
    emailed and would send them a second copy. A lock or permission error on the ledger file
    must not be allowed to quietly turn into a duplicate email later.
    """
    return scrub(session.queue_card_markdown(
        kind="email",
        title=f"SENT but NOT LOGGED — do not resend {marker(recipient.email)}",
        why=(f"send_reengage.py delivered this email but ledger.append() then failed: "
             f"{detail}. Subject: {subject}. This recipient ({recipient.subscriber_id}) took "
             f"the free {recipient.product}. Until a ledger line exists for this marker, a "
             f"resumed run will not know they were already emailed and will send it again."),
        steps=["Confirm the send actually went out (check the Sent folder for "
               f"{SENDER} around this time)",
               f"Add a ledger line by hand for {marker(recipient.email)} — "
               f"python3 scripts/ledger.py --tail 5 shows the format; the action text must "
               f"start with '{SENT_PREFIX}{marker(recipient.email)}' so already_sent() finds it",
               "Do not re-run send_reengage.py for this recipient until that line exists"],
        now=now))


def _queue_unlogged(repo: pathlib.Path, recipient: Recipient, subject: str,
                    detail: str) -> pathlib.Path:
    return session.write_queue_card(
        repo, "manual", f"reengage-UNLOGGED-{digest(recipient.email)}",
        unlogged_card_markdown(recipient, subject, detail))


def systemic_failure_card_markdown(pending: list[tuple[Recipient, str]],
                                   remaining: list[Recipient],
                                   now: dt.datetime | None = None) -> str:
    """One card for a run stopped after CONSECUTIVE_FAILURE_LIMIT gws failures in a row —
    not one per recipient, and not one per failure either.

    Three sends to gws failing back to back almost never means three broken recipients; it
    means gws itself is down (expired auth, a quota, a network blip). Filing a card per
    failure — or per remaining, never-attempted recipient — would be noise on top of the
    outage. `pending` holds every recipient in the failing streak (their individual cards
    were deliberately withheld until it was clear whether the streak would resolve or grow
    into this); `remaining` holds everyone after them who was never attempted at all.
    """
    failing = [recipient for recipient, _detail in pending]
    unsent = failing + remaining
    last_detail = pending[-1][1] if pending else "(no detail recorded)"
    markers = ", ".join(marker(r.email) for r in unsent)
    return scrub(session.queue_card_markdown(
        kind="email",
        title=f"STOPPED the {CAMPAIGN} send — {CONSECUTIVE_FAILURE_LIMIT} consecutive gws "
              f"failures",
        why=(f"send_reengage.py stopped after {CONSECUTIVE_FAILURE_LIMIT} sends to gws failed "
             f"in a row. Most recent error: {last_detail}. That pattern almost always means "
             f"gws itself is broken (auth, quota, network) rather than a problem with any one "
             f"recipient, so the run stopped instead of grinding through the rest and filing "
             f"one card per person. {len(unsent)} recipient(s) were not sent: {markers}."),
        steps=["Run `gws gmail users getProfile --params '{\"userId\":\"me\"}'` to confirm "
               "gws/auth is healthy",
               "Fix whatever gws reported, then re-run send_reengage.py — the ledger's "
               "duplicate-send guard skips anyone already emailed"],
        now=now))


def _queue_systemic(repo: pathlib.Path, pending: list[tuple[Recipient, str]],
                    remaining: list[Recipient]) -> pathlib.Path:
    anchor = pending[-1][0] if pending else remaining[0]
    return session.write_queue_card(
        repo, "manual", f"reengage-SYSTEMIC-{digest(anchor.email)}",
        systemic_failure_card_markdown(pending, remaining))


def already_sent(path: pathlib.Path | None = None) -> set[str]:
    """Markers this campaign has already logged a send for.

    The ledger is the only durable record of who has been emailed, so it is also the only
    thing that can stop a resumed run from emailing the first half of the list twice. A
    partial run is the normal failure here — a dead network at recipient 7 — and "send it
    again" is not a recoverable mistake on a real customer's inbox.
    """
    return {match.group(1) for row in ledger.entries(path if path is not None else LEDGER_PATH)
            for match in SENT_RE.finditer(str(row.get("action") or ""))}


def _log(recipient: Recipient, subject: str) -> None:
    ledger.append(
        action=scrub(
            f"{SENT_PREFIX}{marker(recipient.email)} (recipient "
            f"{recipient.subscriber_id}, took the free {recipient.product}) from "
            f"{SENDER}. Subject: {subject}. Copy verbatim from "
            f"{SOURCE.relative_to(REPO)}; recipient and merge fields from the private store "
            f"(~/kdesk-analytics/private/, 0600). The address is not recorded here: this "
            f"ledger is tracked in a public repo."),
        tier=1, status="executed",
        reasoning=("Decision 35 activated the free→paid automation as 'new subscribers only', "
                   "so these downloaders never received any email. The send is gated on the "
                   f"T{VETO_TIER} veto window in ledger entry {VETO_ENTRY_DEFAULT}."),
        files=[str(SOURCE.relative_to(REPO))],
        path=LEDGER_PATH)


def send_all(markdown: str, recipients: list[Recipient], *, dry_run: bool,
             repo: pathlib.Path | None, limit: int | None = None,
             resend: bool = False) -> tuple[int, int]:
    """Render and send one email per recipient. Returns (sent, failed).

    `markdown` is the copy; `recipients` is the private list. A failure is never fatal to the
    campaign and never silent: it becomes a queue card and a non-zero exit, and the next
    recipient still gets their email — unless CONSECUTIVE_FAILURE_LIMIT consecutive sends to
    gws fail, which reads as gws itself being down rather than any one recipient's data, and
    stops the run with a single card instead of grinding through the rest. Anyone the ledger
    already records a send for is skipped (counted as neither sent nor failed) unless
    `resend` says otherwise.
    """
    subject_template, body_template = parse(markdown)
    done = set() if resend else already_sent()
    sent = failed = duplicate = 0
    # Failures to gws itself are buffered, not queued immediately: a card per failure would
    # mean 1, 2, 3, 4... individual cards while gws is down, when what happened is ONE
    # outage. A card is written for a buffered failure only once we know how the streak
    # resolves - broken by a later success (flushed individually below), or grown to
    # CONSECUTIVE_FAILURE_LIMIT (consolidated into one systemic card and the run stops).
    pending_gws_failures: list[tuple[Recipient, str]] = []
    stopped_early = False
    sliced = recipients[:limit]

    def _flush_pending_individually() -> None:
        if repo is None:
            pending_gws_failures.clear()
            return
        for pf_recipient, pf_detail in pending_gws_failures:
            card = _queue(repo, pf_recipient, pf_detail)
            print(f"       queued -> {card.relative_to(repo)}", file=sys.stderr)
        pending_gws_failures.clear()

    for idx, recipient in enumerate(sliced):
        tag = marker(recipient.email)
        if tag in done:
            duplicate += 1
            print(f"  skip {tag} — the ledger already records this send")
            continue
        try:
            fields = merge_fields_for(recipient)
            subject = render(subject_template, fields)
            body = render(body_template, fields)
        except KeyError as exc:
            failed += 1
            detail = exc.args[0] if exc.args else str(exc)
            print(f"  SKIP {tag} {scrub(detail)}")
            if dry_run:
                # --dry-run performs zero writes, cards included.
                print("       (dry-run: would queue a manual card)")
            elif repo is not None:
                card = _queue(repo, recipient, str(detail))
                print(f"       queued -> {card.relative_to(repo)}")
            continue
        if dry_run:
            sent += 1
            print(f"\n--- would send to {tag} (recipient id {recipient.subscriber_id})")
            print(f"Subject: {scrub(subject)}\n{scrub(body)}")
            continue
        try:
            _gws(["gmail", "users", "messages", "send", "--params",
                  json.dumps({"userId": "me"})],
                 {"raw": rfc822(recipient.email, subject, body)})
        except Exception as exc:  # noqa: BLE001 - one dead send must not end the campaign
            failed += 1
            detail = f"{type(exc).__name__}: {exc}"
            print(f"  FAIL {tag} {scrub(detail)}", file=sys.stderr)
            pending_gws_failures.append((recipient, detail))
            if len(pending_gws_failures) >= CONSECUTIVE_FAILURE_LIMIT:
                remaining = sliced[idx + 1:]
                failed += len(remaining)
                print(f"  STOPPING: {CONSECUTIVE_FAILURE_LIMIT} consecutive gws failures — "
                      f"this looks systemic (auth/quota/network), not a per-recipient "
                      f"problem; {len(pending_gws_failures) + len(remaining)} recipient(s) "
                      f"not sent", file=sys.stderr)
                if repo is not None:
                    card = _queue_systemic(repo, pending_gws_failures, remaining)
                    print(f"       queued -> {card.relative_to(repo)}", file=sys.stderr)
                pending_gws_failures.clear()
                stopped_early = True
                break
            continue
        # A success breaks the streak: any buffered failures were isolated, not systemic,
        # so they get their own cards now that we know they weren't the start of an outage.
        _flush_pending_individually()
        sent += 1
        print(f"  sent {tag}")
        try:
            _log(recipient, subject)
        except Exception as exc:  # noqa: BLE001 - a delivered email must never be dropped
            failed += 1
            detail = f"{type(exc).__name__}: {exc}"
            print(f"  SENT but NOT LOGGED — do not resend {tag}: {scrub(detail)}",
                  file=sys.stderr)
            if repo is not None:
                card = _queue_unlogged(repo, recipient, subject, detail)
                print(f"       queued -> {card.relative_to(repo)}", file=sys.stderr)
        # Paced, not blasted: 14 identical messages from one mailbox in one second is what a
        # spam filter is built to notice. No gap after the last recipient — there is nothing
        # left to pace against.
        if idx != len(sliced) - 1:
            _sleep(GAP_SECONDS)
    if not stopped_early:
        # The list ended with an unresolved streak below the threshold (1 or 2 failures) -
        # each still gets its own card, just as it would have before buffering existed.
        _flush_pending_individually()
    if duplicate:
        print(f"  ({duplicate} already in the ledger, not sent again — pass --resend to "
              f"override)")
    return sent, failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Send the 2026-09 re-engagement email.")
    ap.add_argument("--dry-run", action="store_true",
                    help="render every email to stdout (markers, never addresses); send none")
    ap.add_argument("--veto-entry", type=int, default=VETO_ENTRY_DEFAULT,
                    help="ledger id of the T2 entry whose veto window authorises the send")
    ap.add_argument("--limit", type=int, help="stop after N recipients")
    ap.add_argument("--recipients", type=pathlib.Path, default=None,
                    help=f"private recipient JSON (default: {RECIPIENTS_PATH})")
    ap.add_argument("--resend", action="store_true",
                    help="email people the ledger already records a send for (off by default)")
    a = ap.parse_args(argv)
    try:
        markdown = SOURCE.read_text(encoding="utf-8")
        parse(markdown)                       # fail before the gate if the copy is not there
    except (OSError, ValueError) as exc:
        print(f"REFUSING: {scrub(exc).rstrip('.')}; nothing sent", file=sys.stderr)
        return 2
    if not a.dry_run:
        # The gate runs BEFORE the private store is opened: a refused run must not even read
        # the address list, let alone hold it in memory.
        ok, why = veto_gate(ledger.find(a.veto_entry, LEDGER_PATH),
                            dt.datetime.now().astimezone(), a.veto_entry)
        if not ok:
            print(f"REFUSING: ledger entry {a.veto_entry} {why}", file=sys.stderr)
            return 2
        print(f"ledger entry {a.veto_entry}: {why}")
    try:
        recipients = load_recipients(a.recipients)
    except RecipientsError as exc:
        print(f"REFUSING: {scrub(exc).rstrip('.')}; nothing sent", file=sys.stderr)
        return 2
    if a.resend:
        print("--resend: the duplicate-send guard is OFF; people already in the ledger will "
              "be emailed again", file=sys.stderr)
    sent, failed = send_all(markdown, recipients, dry_run=a.dry_run,
                            repo=None if a.dry_run else REPO, limit=a.limit,
                            resend=a.resend)
    if a.dry_run:
        print(f"\n(dry-run) {sent} rendered, {failed} could not be filled — nothing sent")
    else:
        print(f"{sent} sent, {failed} queued")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
