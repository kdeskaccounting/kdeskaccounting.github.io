#!/usr/bin/env python3
"""The one `gws` subprocess seam, and the one scrubber every message passes through.

Three scripts drive the `gws` CLI (crm_sync, digest, send_reengage) and each had grown its
own private `_gws`. Only send_reengage's had learned the rule that matters, and the rule is
not obvious: **`gws` echoes the request it choked on**, so its stderr on a failure can
contain the `--json` body it was handed. For a Sheets upsert that body is a block of People
rows — customer addresses — and for a Gmail send it is the base64url MIME envelope with the
recipient inside. crm_sync's copy pasted `proc.stderr[:400]` into a queue card that this
PUBLIC repo tracks. That is a leak, not an error message.

So there are exactly two rules here and both are enforced in one place:

1. `run()` keeps **only the first line** of stderr in the error it raises. The first line is
   the reason ("quota exceeded", "invalid_grant"); everything after it is the echo.
2. `scrub()` is the choke point for any text that becomes a card, a ledger line, stdout or a
   CI step summary: known credentials are masked, base64-shaped runs of 40+ characters are
   elided (a MIME body has no `@`, so the address pattern alone would let it through
   undecoded but perfectly decodable — and a Google spreadsheet id is exactly that shape),
   id-shaped runs of 33+ characters next to a Google document/Drive URL are elided too (a
   Drive folder id is commonly 33, under the bare floor, and the URL is what says the token
   opens a private file), and anything still shaped like an address becomes
   `<redacted:XXXXXXXX>`, the salted marker from scripts/privacy.py that the rest of the
   repo uses.

Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Iterable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import privacy  # noqa: E402  (the salted digest; never an address in a tracked file)
from browser import session  # noqa: E402  (redact_secrets: the known-credential half)

GWS_BIN = shutil.which("gws") or "/opt/homebrew/bin/gws"

ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# A base64/base64url blob, a bearer-ish opaque token and a Google spreadsheet id are all the
# same shape: one long unbroken run of these characters. 40 is below the 44 of a sheet id and
# far below a MIME body, and above any English word or hyphenated path segment in this repo.
B64_RE = re.compile(r"[A-Za-z0-9_-]{40,}")
B64_PLACEHOLDER = "<b64 elided>"
# A Drive folder id is commonly 33 characters - under the floor above, and with no "sheet"
# next to it nothing else marks it as a handle. What does mark it is the URL it sits in: a
# Google document/spreadsheet/folder link says outright that the token opens a private file.
# So the floor drops to 33, but only inside that window; eliding every 33-character run
# everywhere would swallow commit shas, build ids and slugs out of ordinary messages.
GOOGLE_URL_RE = re.compile(
    r"docs\.google\.com|drive\.google\.com|document/d|spreadsheets/d|/folders/", re.I)
GOOGLE_HANDLE_RE = re.compile(r"(?=[A-Za-z0-9_-]*[a-z])(?=[A-Za-z0-9_-]*[A-Z])"
                              r"(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{33,}")
GOOGLE_WINDOW = 100          # characters either side of the token that count as "adjacent"
# How much of argv may appear in an error. The verb ("sheets spreadsheets values append") is
# useful; the tail is `--params {"spreadsheetId": ...}`, a private handle.
ARGV_WORDS_IN_ERROR = 4


class GwsError(RuntimeError):
    """A `gws` invocation exited non-zero. Carries the first stderr line and nothing else.

    A RuntimeError subclass on purpose: callers already catch RuntimeError from the private
    copies this replaces, and their `except Exception` queue-card paths are unchanged.
    """


def run(argv: list[str], body: dict | None = None, *, timeout: float) -> str:
    """Run `gws <argv>` (with `--json <body>` when given) and return stdout verbatim.

    `timeout` is keyword-only and required: every caller has a different sensible ceiling
    (a Gmail send is not a 2000-row Sheets read), and a silent default is how one of them
    ends up hanging a scheduled job forever.

    Raises GwsError on a non-zero exit, with ONLY the first line of stderr. See the module
    docstring for why that is not a nicety.
    """
    cmd = [GWS_BIN, *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        lines = (proc.stderr or "").strip().splitlines()
        reason = lines[0].strip() if lines and lines[0].strip() else "(gws produced no stderr)"
        raise GwsError(f"gws {' '.join(argv[:ARGV_WORDS_IN_ERROR])} failed: {reason}")
    return proc.stdout


def run_json(argv: list[str], body: dict | None = None, *, timeout: float) -> dict:
    """run(), decoded. An empty stdout is an empty dict, not a JSONDecodeError."""
    out = run(argv, body, timeout=timeout).strip()
    return json.loads(out) if out else {}


def _elide_google_handles(text: str) -> str:
    """Elide id-shaped runs of 33+ characters that sit next to a Google document URL.

    Written as a scan rather than one regex because the evidence and the token are two
    separate things: the URL can precede the token (the usual case) or follow it in prose
    ("the doc is <id> - see docs.google.com"). Replacing from the end keeps the offsets of
    the matches still to be processed valid.
    """
    if not GOOGLE_URL_RE.search(text):
        return text
    out = text
    for match in reversed(list(GOOGLE_HANDLE_RE.finditer(text))):
        window = text[max(0, match.start() - GOOGLE_WINDOW):match.end() + GOOGLE_WINDOW]
        if GOOGLE_URL_RE.search(window):
            out = out[:match.start()] + B64_PLACEHOLDER + out[match.end():]
    return out


def marker(email: str) -> str:
    """`<redacted:XXXXXXXX>` — the first 8 hex of the salted digest, the repo's convention."""
    return f"<redacted:{privacy.email_hash(email)[:8]}>"


def scrub(text: object, *, extra_secrets: Iterable[str] = (),
          keep: Iterable[str] = ()) -> str:
    """Mask credentials, elide long opaque runs, then pseudonymise every address left.

    Order matters. redact_secrets first, so a token is masked as a token rather than elided
    as an anonymous blob. Base64 elision second, because a raw MIME body (or a spreadsheet
    id) never contains `@` and ADDRESS_RE would otherwise let it through intact. The address
    swap last, on what remains.

    `keep` is an explicit allow-list of literal addresses — KDesk's own published sender,
    typically, which a human needs to see in a card to check which account failed. It is
    empty by default: the strict behaviour is the one that belongs in a public CI log.
    """
    if text is None:
        return ""
    out = session.redact_secrets(text)
    extras = [str(s) for s in extra_secrets if str(s).strip()]
    if extras:
        out = session.redact_secrets(out, secrets=extras)
    out = B64_RE.sub(B64_PLACEHOLDER, out)
    out = _elide_google_handles(out)
    kept = {str(k).strip().lower() for k in keep if str(k).strip()}

    def swap(match: "re.Match") -> str:
        address = match.group(0)
        return address if address.lower() in kept else marker(address)

    return ADDRESS_RE.sub(swap, out)
