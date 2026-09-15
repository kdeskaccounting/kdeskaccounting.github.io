"""No third-party email address may live in ANY tracked file. This repo is PUBLIC.

The leak this guards against already happened three times (ledger 76, 77, 78): a sync-state
file, five content files, and the plan document itself carried real customer and outreach
addresses into github.com/kdeskaccounting/kdeskaccounting.github.io. Containment is only
worth anything if the next address cannot get in, so this scans every tracked text file in
the repo - not a hand-listed set of directories, because the third leak was in a directory
the earlier version of this test did not look at.

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
ROOT = pathlib.Path(__file__).resolve().parents[1]

# Domains KDesk owns. Matched on the address's domain part exactly (or as a parent of it) -
# never as a substring, or "x@kdeskaccounting.com.attacker.example" would pass.
OWN_DOMAINS = ("kdeskaccounting.com", "kdesk.com", "kdeskaccounting.gumroad.com")

# RFC 2606 / RFC 6761 reserved names, which can never belong to a real person.
RESERVED_DOMAINS = ("example.com", "example.net", "example.org")
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")

# Exact addresses allowed by literal. Every one needs a reason; a creeping allowlist is how
# this guard would quietly stop guarding. Note that freemail is NEVER allowed wholesale -
# most real customers are on it - so each freemail entry here is individually justified.
ALLOWED_LITERALS = {
    "santiagokdesk@gmail.com",  # KDesk's own published business address
    "smichels1@gmail.com",      # Stephen's own personal address - his, not a third party
    "you@company.com",          # form placeholder, layouts/partials/email_capture.html + rsu-calculator
    "noreply@anthropic.com",    # not a person: the documented Co-Authored-By commit trailer
    "a@gmail.com",              # synthetic fixture; must be freemail to test is_business FALSE
}

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".xlsx", ".zip",
                 ".mp4", ".mov", ".woff", ".woff2", ".ttf", ".eot", ".svg")


def _tracked_files() -> list[pathlib.Path]:
    """Every tracked path, NUL-separated - a filename may legally contain whitespace."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode != 0:
        pytest.skip("not a git checkout, nothing to scan")
    names = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [ROOT / name for name in names if name]


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[1].lower()


def is_allowed(address: str) -> bool:
    low = address.lower()
    if low in ALLOWED_LITERALS:
        return True
    domain = domain_of(low)
    if domain in OWN_DOMAINS or any(domain.endswith(f".{own}") for own in OWN_DOMAINS):
        return True
    return domain in RESERVED_DOMAINS or domain.endswith(RESERVED_SUFFIXES)


def offenders() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        bad = {a.lower() for a in EMAIL.findall(text) if not is_allowed(a)}
        if bad:
            found[str(path.relative_to(ROOT))] = len(bad)
    return found


def test_no_tracked_file_anywhere_carries_a_third_party_address():
    found = offenders()
    # Paths and counts only - never the addresses. A CI log is as public as the repo.
    assert not found, (
        "third-party email addresses found in tracked files "
        f"({sum(found.values())} distinct across {len(found)} files): "
        + ", ".join(f"{p} ({n})" for p, n in sorted(found.items()))
        + ". Move them to ~/kdesk-analytics/private/ and leave a <redacted:XXXXXXXX> marker."
    )


def test_the_scan_really_is_repo_wide():
    """The third leak sat in docs/, which the directory-listed version of this test skipped."""
    scanned = {str(p.relative_to(ROOT)) for p in _tracked_files()}
    assert len(scanned) > 250, "expected the whole repo, not a subtree"
    for expected in ("CLAUDE.md",
                     "docs/superpowers/plans/2026-09-14-kdesk-automation-phase1.md",
                     "layouts/partials/email_capture.html",
                     "scripts/sales/crm_sync.py"):
        assert expected in scanned, expected


def test_the_allowlist_itself_stays_narrow():
    assert len(ALLOWED_LITERALS) <= 6, "justify every literal; prefer a reserved domain"
    assert all("@" in a and a == a.lower() for a in ALLOWED_LITERALS)


def test_own_domains_match_the_domain_exactly_not_as_a_substring():
    """A substring check let an attacker-controlled domain impersonate ours."""
    at = "@"
    assert is_allowed(f"hello{at}kdeskaccounting.com")
    assert is_allowed(f"hello{at}mail.kdeskaccounting.com")      # a real subdomain of ours
    assert not is_allowed(f"hello{at}kdeskaccounting.com.attacker.example.org.co")
    assert not is_allowed(f"hello{at}notkdeskaccounting.com")
    assert not is_allowed(f"santiagokdesk{at}attacker-example.org.co")


def test_a_real_address_is_not_allowed_and_kdesk_and_reserved_ones_are():
    """Addresses are assembled from parts on purpose.

    This file is itself tracked and therefore scanned by the test above, so writing the
    negative cases as literals would make the guard fail on its own source.
    """
    at = "@"
    assert not is_allowed(f"someone{at}a-company-we-do-not-own.com")
    assert not is_allowed(f"person{at}gmail.com")      # freemail is NOT wholesale-allowed
    assert is_allowed(f"santiagokdesk{at}gmail.com")
    assert is_allowed(f"buyer{at}northstar.example")
    assert is_allowed(f"someone{at}example.com")


def test_the_guard_scans_its_own_source():
    """The regression that bit once: the guard was written, run while still untracked, and
    passed - then failed the moment `git add` brought it into `git ls-files`."""
    assert pathlib.Path(__file__).resolve() in {p.resolve() for p in _tracked_files()}
