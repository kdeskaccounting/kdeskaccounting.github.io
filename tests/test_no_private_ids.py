"""No private handle may live in a tracked file. This repo is PUBLIC.

The sibling guard (tests/test_no_third_party_emails.py) keeps addresses out. This one keeps
out the thing that leads to them: a Google **spreadsheet id**. The private "KDesk CRM" sheet
holds every customer address KDesk has, and its id is the whole access story — anyone the
sheet is shared with, or any future misconfiguration of its sharing, needs only the id.

It got in exactly the way these things do. `crm_sync.py` interpolated the id into its ledger
line; the ledger is tracked; `digest.py` re-emits recent ledger lines into
`$GITHUB_STEP_SUMMARY`, which is a public workflow log. One `f"({sheet_id})"` published a
private handle twice.

The shape: a Google file id is a 40+ character run of `[A-Za-z0-9_-]` mixing upper, lower
and digits. Requiring all three classes is what keeps this off `# ----------` rules and
`def test_a_very_long_function_name_like_this_one()`. Adjacency to the word "sheet" is what
keeps it off base64 fixtures that have nothing to do with Drive.

Failures report paths and counts, never the token: a CI log is as public as the repo.
"""
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 40+ of the base64url alphabet, carrying at least one lowercase, one uppercase and one
# digit. A real Drive/Sheets id is 44 of these; 40 is the floor scripts/gws.py elides at.
SHEET_ID = re.compile(r"(?=[A-Za-z0-9_-]*[a-z])(?=[A-Za-z0-9_-]*[A-Z])"
                      r"(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{40,}")
NEAR = re.compile(r"sheet", re.I)          # covers "sheet", "Sheets", "spreadsheetId"
CONTEXT = 100                              # characters either side that count as "adjacent"

# Tokens allowed by literal. Empty on purpose: a fixture that needs an id-shaped string
# should build it from parts (see test_the_pattern_recognises_an_id_shaped_token below) so
# the guard keeps guarding. Every entry added here needs a reason in a comment.
ALLOWED_TOKENS: frozenset = frozenset()

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".xlsx", ".zip",
                 ".mp4", ".mov", ".woff", ".woff2", ".ttf", ".eot")


def _tracked_files() -> list[pathlib.Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        pytest.skip("not a git checkout, nothing to scan")
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [ROOT / name for name in names if name]


def sheet_ids_in(text: str) -> list[str]:
    """Every id-shaped token that sits within CONTEXT characters of the word "sheet"."""
    found = []
    for match in SHEET_ID.finditer(text):
        if match.group(0) in ALLOWED_TOKENS:
            continue
        window = text[max(0, match.start() - CONTEXT):match.end() + CONTEXT]
        if NEAR.search(window):
            found.append(match.group(0))
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


def test_no_tracked_file_carries_a_google_sheet_id():
    found = offenders()
    # Paths and counts only - never the token. A CI log is as public as the repo.
    assert not found, (
        "Google Sheet-id-shaped tokens found in tracked files "
        f"({sum(found.values())} across {len(found)} files): "
        + ", ".join(f"{p} ({n})" for p, n in sorted(found.items()))
        + ". The id belongs in ~/kdesk-analytics/crm-sheet-id.txt (0600); refer to the sheet "
          "by title in anything tracked."
    )


def test_the_pattern_recognises_an_id_shaped_token():
    """Built from parts, so this file does not trip its own scan."""
    fake = "1A" + "bQ7z_x-9" * 5 + "2yK"
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
    fake = "1A" + "bQ7z_x-9" * 5 + "2yK"
    assert sheet_ids_in(f"an opaque blob {fake} with no context") == []


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

    fake = "1A" + "bQ7z_x-9" * 5 + "2yK"
    assert fake not in gws.scrub(f"KDesk CRM ({fake})")
