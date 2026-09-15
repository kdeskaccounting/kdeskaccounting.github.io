"""No private handle may live in a tracked file. This repo is PUBLIC.

The sibling guard (tests/test_no_third_party_emails.py) keeps addresses out. This one keeps
out the thing that leads to them: a Google **file handle** — a spreadsheet, document or Drive
folder id. The private "KDesk CRM" sheet holds every customer address KDesk has, and its id is
the whole access story: anyone the sheet is shared with, or any future misconfiguration of its
sharing, needs only the id. The same is true of a Doc handle and of a Drive folder handle,
which names a container rather than one file.

It got in exactly the way these things do. `crm_sync.py` interpolated the id into its ledger
line; the ledger is tracked; `digest.py` re-emits recent ledger lines into
`$GITHUB_STEP_SUMMARY`, which is a public workflow log. One `f"({sheet_id})"` published a
private handle twice.

The shape: a Google file id is a run of `[A-Za-z0-9_-]` mixing upper, lower and digits.
Requiring all three classes is what keeps this off `# ----------` rules and
`def test_a_very_long_function_name_like_this_one()`. Adjacency is what keeps it off base64
fixtures that have nothing to do with Drive, and the adjacency sets the floor: 40 characters
near the word "sheet" (a noun is weak evidence, so length carries it), 33 next to a Google
document/spreadsheet/folder URL (the URL states outright that the token opens a private
file, and a Drive folder id is commonly 33 characters).

Handles already committed were redacted in place to `<redacted-doc:XXXXXXXX>` markers
(`privacy.handle_hash`, case-sensitive because a Drive id is), originals in the private
redaction map — ledger entries 79 and 80.

Failures report paths and counts, never the token: a CI log is as public as the repo.
"""
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# The base64url alphabet, carrying at least one lowercase, one uppercase and one digit. Two
# floors, because the evidence that a token is a handle differs:
#
#   40 chars near the word "sheet" — a bare id with only a noun for context, so the length is
#     doing the work. A Sheets id is 44; 40 is the floor scripts/gws.py elides at.
#   33 chars next to a Google URL — docs.google.com/document/d/<id>, /folders/<id>. The URL
#     says outright that the token is a Drive handle, so a shorter one is still a handle: a
#     Drive folder id is commonly 33. Below 33 lies real prose, so it stays the floor.
def _token(floor: int) -> "re.Pattern":
    return re.compile(r"(?=[A-Za-z0-9_-]*[a-z])(?=[A-Za-z0-9_-]*[A-Z])"
                      r"(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{%d,}" % floor)


SHEET_ID = _token(40)
GOOGLE_HANDLE = _token(33)
NEAR = re.compile(r"sheet", re.I)          # covers "sheet", "Sheets", "spreadsheetId"
# A Google URL naming a document, a spreadsheet or a folder. Any of these next to a token is
# an explicit statement that the token opens a private file.
GOOGLE_URL = re.compile(r"docs\.google\.com|drive\.google\.com|document/d|spreadsheets/d|/folders/",
                        re.I)
CONTEXT = 100                              # characters either side that count as "adjacent"

# Tokens allowed by literal. Empty on purpose: a fixture that needs an id-shaped string
# should build it from parts (see test_the_pattern_recognises_an_id_shaped_token below) so
# the guard keeps guarding. Every entry added here needs a reason in a comment.
ALLOWED_TOKENS: frozenset = frozenset()

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".xlsx", ".zip",
                 ".mp4", ".mov", ".woff", ".woff2", ".ttf", ".eot")

# Fixtures, assembled from parts on purpose: this file is tracked and therefore scanned by
# its own test below, so a handle written as one literal would make the guard fail on its
# own source. HANDLE_33 is the length of a Drive folder id; HANDLE_45 clears the bare floor.
HANDLE_33 = "1AbC2dEf3GhI4jKl5" + "MnO6pQr7StU8vWx9"
HANDLE_45 = "1A" + "bQ7z_x-9" * 5 + "2yK"


def _tracked_files() -> list[pathlib.Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        pytest.skip("not a git checkout, nothing to scan")
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [ROOT / name for name in names if name]


def sheet_ids_in(text: str) -> list[str]:
    """Every id-shaped token close enough to something that says it opens a private file.

    Two rules, checked longest-floor-first so a token is reported once: 40+ characters near
    the word "sheet", or 33+ characters near a Google document/spreadsheet/folder URL.
    """
    found, seen = [], set()
    for pattern, near in ((SHEET_ID, NEAR), (GOOGLE_HANDLE, GOOGLE_URL)):
        for match in pattern.finditer(text):
            token = match.group(0)
            if token in ALLOWED_TOKENS or (match.start(), token) in seen:
                continue
            window = text[max(0, match.start() - CONTEXT):match.end() + CONTEXT]
            if near.search(window):
                seen.add((match.start(), token))
                found.append(token)
    return found


def offenders() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = sheet_ids_in(text)
        if hits:
            found[str(path.relative_to(ROOT))] = len(hits)
    return found


def test_no_tracked_file_carries_a_google_handle():
    found = offenders()
    # Paths and counts only - never the token. A CI log is as public as the repo.
    assert not found, (
        "Google file-id-shaped tokens (a spreadsheet, document or Drive folder handle) found "
        f"in tracked files ({sum(found.values())} across {len(found)} files): "
        + ", ".join(f"{p} ({n})" for p, n in sorted(found.items()))
        + ". The CRM sheet's id belongs in ~/kdesk-analytics/crm-sheet-id.txt (0600); any "
          "other handle belongs in ~/kdesk-analytics/private/redaction-map-2026-09-14.json "
          "with a <redacted-doc:XXXXXXXX> marker left behind (privacy.handle_hash). Refer to "
          "a private file by title in anything tracked."
    )


def test_the_pattern_recognises_an_id_shaped_token():
    """Built from parts, so this file does not trip its own scan."""
    fake = HANDLE_45
    assert len(fake) >= 40
    assert sheet_ids_in(f"the KDesk CRM sheet ({fake})") == [fake]
    assert sheet_ids_in(f"spreadsheetId={fake}") == [fake]


def test_the_pattern_ignores_long_runs_that_are_not_ids():
    """The false positives that would make this guard unusable, and are therefore excluded:
    a comment rule, a long snake_case name, and a long word - none mix all three classes."""
    rule = "# " + "-" * 60
    assert sheet_ids_in(f"# Sheet builders\n{rule}") == []
    assert sheet_ids_in("def test_the_sheet_upsert_is_idempotent_across_two_runs(): pass") == []
    assert sheet_ids_in("SHEETSHEETSHEET" * 4) == []


def test_an_id_far_from_the_word_sheet_is_not_this_guards_business():
    """Scoped deliberately: a long opaque token with no sheet context is some other file's
    concern (a video id, a base64 fixture). Widening this to every long run would make the
    guard fire on things it cannot judge, and a guard that cries wolf gets deleted."""
    fake = HANDLE_45
    assert sheet_ids_in(f"an opaque blob {fake} with no context") == []


def test_a_drive_handle_next_to_a_google_url_is_caught_below_the_bare_token_floor():
    """A 33-character Drive folder id has no "sheet" next to it and is under the 40-char
    floor, so the original rule let it straight through - which is how three of them stayed
    in tracked files. The URL beside it is the evidence that it opens a private file."""
    handle = HANDLE_33
    assert len(handle) == 33
    assert sheet_ids_in(f"https://drive.google.com/drive/folders/{handle}") == [handle]
    assert sheet_ids_in(f"https://docs.google.com/document/d/{handle}/edit") == [handle]
    assert sheet_ids_in(f"see docs.google.com — the doc is {handle}") == [handle]
    # The same token with no Google URL anywhere near it is under the bare-token floor.
    assert sheet_ids_in(f"an opaque blob {handle} in a sheet of results") == []


def test_the_bare_token_floor_is_still_40_near_the_word_sheet():
    """Only the Google-URL rule drops to 33. A 33-character token near the word "sheet" is
    not enough evidence on its own - that floor is where real prose and hyphenated slugs
    start turning up."""
    short, long = HANDLE_33, HANDLE_45
    assert sheet_ids_in(f"the KDesk CRM sheet ({short})") == []
    assert sheet_ids_in(f"the KDesk CRM sheet ({long})") == [long]


def test_a_token_is_reported_once_even_when_both_rules_match():
    handle = HANDLE_45
    assert sheet_ids_in(
        f"the sheet at https://docs.google.com/spreadsheets/d/{handle}/edit") == [handle]


def test_the_guard_and_the_scrubber_agree_on_what_a_handle_is():
    """Two implementations of the same rule, kept independent (a production module must not
    import from tests/) and therefore able to drift. This is what notices."""
    import gws

    short, long = HANDLE_33, HANDLE_45
    for sample in (f"https://docs.google.com/document/d/{short}/edit",
                   f"https://drive.google.com/drive/folders/{short}",
                   f"the KDesk CRM sheet ({long})"):
        assert sheet_ids_in(sample), sample
        assert short not in gws.scrub(sample) and long not in gws.scrub(sample), sample
    # And neither fires on a short token with no Google context.
    plain = f"build id {short} finished"
    assert sheet_ids_in(plain) == []
    assert short in gws.scrub(plain)


def test_the_allowlist_stays_empty_or_justified():
    assert len(ALLOWED_TOKENS) <= 2, "justify every literal; build fixtures from parts instead"


def test_the_scan_is_repo_wide():
    scanned = {str(p.relative_to(ROOT)) for p in _tracked_files()}
    assert len(scanned) > 250, "expected the whole repo, not a subtree"
    for expected in ("decisions/decisions.jsonl", "scripts/sales/crm_sync.py", "CLAUDE.md"):
        assert expected in scanned, expected


def test_the_scrubber_would_elide_such_a_token_before_it_reached_a_log():
    """The guard catches what is already committed; scripts/gws.scrub is what stops the next
    one reaching a queue card or a public CI step summary. Both, or neither is enough."""
    import gws

    fake = HANDLE_45
    assert fake not in gws.scrub(f"KDesk CRM ({fake})")
