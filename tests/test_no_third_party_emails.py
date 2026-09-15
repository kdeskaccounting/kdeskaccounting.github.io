"""No third-party email address may live in a tracked file. This repo is PUBLIC.

The leak this guards against already happened once (ledger entries 76-77): a sync-state file
and five content files carried real customer and outreach addresses into
github.com/kdeskaccounting/kdeskaccounting.github.io. Containment is only worth anything if
the next address cannot get in, so this test scans every tracked text file and fails on any
address that is not KDesk's own or a documentation placeholder.

To store a real person, put them in the private store (~/kdesk-analytics/private/, 0600) and
leave a `<redacted:XXXXXXXX>` marker in the repo - the first 8 hex of the salted digest from
scripts/privacy.py, which keeps the row joinable without naming anyone.

Failures deliberately report paths and counts, never the addresses: a CI log is as public as
the repo.
"""
import pathlib
import re
import subprocess

import pytest

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SCANNED_DIRS = ("marketing", "decisions", "content", "scripts", "tests")
ROOT = pathlib.Path(__file__).resolve().parents[1]

# KDesk's own published contact details. Stephen's business address is meant to be findable.
OWN_MARKERS = ("santiagokdesk@", "@kdeskaccounting.com", "@kdesk.com", "kdeskaccounting.gumroad.com")

# RFC 2606 / RFC 6761 reserved names, which can never belong to a real person.
RESERVED_DOMAINS = ("example.com", "example.net", "example.org")
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")

# Exact synthetic fixtures that must sit on a real consumer domain because the code under
# test classifies addresses BY that domain. Kept to an explicit, reviewed minimum - allowing
# freemail domains wholesale would defeat this test, since most real customers use them.
ALLOWED_LITERALS = {
    "a@gmail.com",   # tests/test_crm_sync.py: the free-mail person, must be is_business FALSE
}

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".xlsx", ".zip",
                 ".mp4", ".mov", ".woff", ".woff2", ".ttf")


def _tracked_files() -> list[pathlib.Path]:
    result = subprocess.run(["git", "ls-files", *SCANNED_DIRS],
                            cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip("not a git checkout, nothing to scan")
    return [ROOT / line for line in result.stdout.split() if line]


def is_allowed(address: str) -> bool:
    low = address.lower()
    if low in ALLOWED_LITERALS:
        return True
    if any(marker in low for marker in OWN_MARKERS):
        return True
    domain = low.rsplit("@", 1)[1]
    return domain in RESERVED_DOMAINS or domain.endswith(RESERVED_SUFFIXES)


def test_no_tracked_file_carries_a_third_party_address():
    offenders: dict[str, int] = {}
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        bad = {a.lower() for a in EMAIL.findall(text) if not is_allowed(a)}
        if bad:
            offenders[str(path.relative_to(ROOT))] = len(bad)
    # Paths and counts only - never the addresses. A CI log is as public as the repo.
    assert not offenders, (
        "third-party email addresses found in tracked files "
        f"({sum(offenders.values())} distinct across {len(offenders)} files): "
        + ", ".join(f"{p} ({n})" for p, n in sorted(offenders.items()))
        + ". Move them to ~/kdesk-analytics/private/ and leave a <redacted:XXXXXXXX> marker."
    )


def test_the_allowlist_itself_stays_narrow():
    """A growing allowlist is how this guard quietly stops guarding."""
    assert len(ALLOWED_LITERALS) <= 3, "justify every literal; prefer a reserved domain"
    assert all("@" in a and a == a.lower() for a in ALLOWED_LITERALS)


def test_a_real_address_is_not_allowed_and_kdesk_and_reserved_ones_are():
    """Addresses are assembled from parts on purpose.

    This file is itself tracked and therefore scanned by the test above, so writing the
    negative cases as literals would make the guard fail on its own source. Joining around
    `AT` keeps no address-shaped text at rest in the repo while still exercising the real
    classifier.
    """
    at = "@"
    assert not is_allowed(f"someone{at}a-company-we-do-not-own.com")
    assert not is_allowed(f"person{at}gmail.com")      # freemail is NOT wholesale-allowed
    assert is_allowed(f"santiagokdesk{at}gmail.com")
    assert is_allowed(f"hello{at}kdeskaccounting.com")
    assert is_allowed(f"buyer{at}northstar.example")
    assert is_allowed(f"someone{at}example.com")


def test_the_guard_scans_its_own_source():
    """The regression that just bit: the guard was written, run while still untracked, and
    passed - then failed the moment `git add` brought it into `git ls-files`."""
    assert pathlib.Path(__file__).resolve() in {p.resolve() for p in _tracked_files()}
