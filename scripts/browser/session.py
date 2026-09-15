#!/usr/bin/env python3
"""Connect to the debug Chrome, preflight each site, fail closed with a queue card.

  python3 scripts/browser/session.py --check gumroad mailerlite
  python3 scripts/browser/session.py --check gumroad --dry-run   # prints the plan, opens nothing

Rules implemented (spec "Chrome automation"): scripts own the lifecycle (ensure_chrome);
preflight per site and fail closed; condition waits only; tracing on by default under
scripts/browser/runs/<date>/<name>-<HHMMSS>/trace.zip; a failure writes
marketing/publish-queue/manual/<date>-<slug>.md and logs one ledger line.

Playwright is imported lazily inside open_page() so this module stays importable with
the standard library alone (the test environment has no playwright).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import functools
import os
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402  (scripts/ledger.py)

REPO = pathlib.Path(__file__).resolve().parents[2]
CDP_URL = "http://localhost:9222"


@dataclasses.dataclass(frozen=True)
class Site:
    name: str
    dashboard_url: str
    login_marker: str
    anchor_description: str
    # Hosts the site may legitimately redirect to and still be the logged-in dashboard.
    # An explicit allow-list, never a suffix match: 'evilgumroad.com' must stay unexpected.
    alt_hosts: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class SiteStatus:
    site: str
    ok: bool
    requested_url: str
    final_url: str
    detail: str


SITES: dict[str, Site] = {
    # Gumroad moved the dashboard to the apex host in 2026; app.gumroad.com still 301s
    # there, so both are the same logged-in dashboard (verified live 2026-09-14).
    "gumroad": Site("gumroad", "https://app.gumroad.com/products", "/login",
                    "the products table", alt_hosts=("gumroad.com",)),
    "mailerlite": Site("mailerlite", "https://dashboard.mailerlite.com/campaigns", "/login",
                       "the campaigns list"),
}


def classify(site: str, requested_url: str, final_url: str) -> SiteStatus:
    cfg = SITES[site]
    want_host = urllib.parse.urlsplit(cfg.dashboard_url).netloc
    got = urllib.parse.urlsplit(final_url)
    if got.netloc != want_host and got.netloc not in cfg.alt_hosts:
        return SiteStatus(site, False, requested_url, final_url,
                          f"unexpected host {got.netloc!r} (wanted {want_host!r})")
    if cfg.login_marker in got.path:
        return SiteStatus(site, False, requested_url, final_url,
                          f"not logged in — redirected to {got.path}")
    return SiteStatus(site, True, requested_url, final_url,
                      f"logged in — {cfg.anchor_description} reachable at {got.path}")


# Anything shaped like a credential in a URL, a header, or a key=value pair. The exception
# text from a failed HTTPS call embeds the full URL, so a token passed as a query param
# would otherwise land verbatim in a queue card under marketing/publish-queue/ - which is
# tracked by git. Redaction is belt-and-braces: drivers also send tokens as headers.
_SECRET_PARAM = re.compile(
    r"\b(access_token|refresh_token|api_key|apikey|password|secret|token|key)=[^&\s\"'<>]+",
    re.IGNORECASE)
# Authorization schemes whose value is the credential itself. Upload-Post uses
# `Authorization: Apikey <UPLOAD_POST_KEY>`, so `Bearer` alone left that key in the clear.
_AUTH_SCHEME = re.compile(r"\b(Bearer|Apikey)\s+[^\s\"'<>]+", re.IGNORECASE)
# The same credentials also turn up in JSON bodies and colon-separated logs:
#   {"api_key": "…"}   headers={'token': '…'}   access_token: …
_SECRET_COLON = re.compile(
    r"([\"']?)\b(access_token|refresh_token|api_key|apikey|password|secret|token|key)\b\1"
    r"\s*:\s*([\"']?)[^\s,;}\]\"']+\3",
    re.IGNORECASE)
# Shorter than this and a "secret" would mask ordinary words; a real token is far longer.
_MIN_SECRET_LEN = 8
# .env holds configuration as well as credentials. Only these key shapes contribute a
# literal to mask - masking a product URL or a base path would corrupt the very evidence
# a queue card exists to carry.
_CREDENTIAL_KEY = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|PASS)", re.IGNORECASE)


def _env_secrets() -> frozenset:
    """Credential values exported into this process's environment.

    Deliberately NOT cached: UPLOAD_POST_KEY (and anything else) can be exported after the
    first redaction, and a stale cache would leave it in the clear. Values shaped like
    configuration rather than a credential - a path, a URL - are skipped for the same
    reason the .env sweep looks at key names only: masking a base path or an endpoint
    would corrupt the very evidence a queue card exists to carry.
    """
    found: set[str] = set()
    for name, value in os.environ.items():
        value = (value or "").strip()
        if not _CREDENTIAL_KEY.search(name) or len(value) < _MIN_SECRET_LEN:
            continue
        if value.startswith(("/", "~", ".")) or "://" in value:
            continue
        found.add(value)
    return frozenset(found)


@functools.lru_cache(maxsize=1)
def _file_secrets() -> frozenset:
    """Literal token values in the token FILES on this machine. Cached: they rarely change."""
    found: set[str] = set()
    home = pathlib.Path.home()
    env_file = home / "kdeskaccountingtemplates" / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            if _CREDENTIAL_KEY.search(key):
                found.add(value.strip().strip("\"'"))
    except (OSError, UnicodeDecodeError):
        pass
    for plain in (home / "kdesk-analytics" / "mailerlite-token.txt",
                  home / "kdesk-analytics" / "bing-api-key.txt"):
        try:
            found.add(plain.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeDecodeError):
            pass
    return frozenset(s for s in found if len(s) >= _MIN_SECRET_LEN)


def known_secrets() -> frozenset:
    """Literal token values on this machine, so they can be masked wherever they surface.

    Never raises and never logs: a missing or unreadable token file just means there is
    one less literal to mask. The values are held in memory only, never written anywhere.
    """
    return _file_secrets() | _env_secrets()


# Callers (and tests) drop the token-file cache through known_secrets.cache_clear(); the
# environment half is read live every time, so there is nothing else to invalidate.
known_secrets.cache_clear = _file_secrets.cache_clear


def redact_secrets(text, *, secrets=None) -> str:
    """Mask credentials in `text` before it reaches a card, the ledger, stdout or a path.

    Masks known literal token values plus anything shaped like `access_token=…`,
    `Bearer …` or `Apikey …`. Idempotent, so it is safe to apply more than once.
    """
    if text is None:
        return ""
    out = str(text)
    for secret in (known_secrets() if secrets is None else secrets):
        if secret and len(str(secret).strip()) >= _MIN_SECRET_LEN:
            out = out.replace(str(secret), "***")
    out = _SECRET_PARAM.sub(r"\1=***", out)
    out = _SECRET_COLON.sub(r"\1\2\1: \3***\3", out)
    return _AUTH_SCHEME.sub(r"\1 ***", out)


def queue_card_markdown(kind: str, title: str, why: str, steps: list[str],
                        now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now().astimezone()
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    return (f"# {kind} — {title}\n\n"
            f"Written {now.strftime('%Y-%m-%d %H:%M %z')} by scripts/browser/session.py\n\n"
            f"## Why\n\n{why}\n\n"
            f"## Do this\n\n{numbered}\n")


def write_queue_card(repo: pathlib.Path, subdir: str, slug: str, body: str,
                     now: dt.datetime | None = None) -> pathlib.Path:
    now = now or dt.datetime.now().astimezone()
    folder = pathlib.Path(repo) / "marketing" / "publish-queue" / subdir
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{now.strftime('%Y-%m-%d')}-{slug}"
    path = folder / f"{stem}.md"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}.md"
        n += 1
    path.write_text(body, encoding="utf-8")
    return path


def trace_dir(repo: pathlib.Path, name: str, now: dt.datetime | None = None) -> pathlib.Path:
    now = now or dt.datetime.now().astimezone()
    d = (pathlib.Path(repo) / "scripts" / "browser" / "runs"
         / now.strftime("%Y-%m-%d") / f"{name}-{now.strftime('%H%M%S')}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def trace_path(directory: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(directory) / "trace.zip"


def fail_card(repo: pathlib.Path, page, *, kind: str, slug: str, title: str, detail: str,
              steps: list[str], run_name: str, limit: int = 400) -> pathlib.Path:
    """Turn a driver failure into a screenshot plus a paste-ready queue card.

    The single place a failure becomes a card, so redaction happens once rather than being
    re-implemented (and eventually forgotten) in each driver. Everything that lands on
    disk - the card body, the title, the steps and the screenshot path - is masked first.
    A screenshot failure never hides the original error.

    Pass the FULL exception text: `detail` is redacted and only then truncated to `limit`.
    Truncating first would cut a token in half and leave a usable prefix in a file that
    git tracks, which is exactly what the callers used to do with str(exc)[:300].
    """
    safe_slug = redact_secrets(slug).replace("/", "-")
    out = trace_dir(repo, f"{run_name}-fail-{safe_slug}")
    shot = out / "fail.png"
    try:
        page.screenshot(path=str(shot))
        where = f"\n\nScreenshot: {redact_secrets(shot)}"
    except Exception:  # noqa: BLE001 - a dead page must not mask the real failure
        where = "\n\n(no screenshot: the page was not available)"
    safe_detail = redact_secrets(detail)          # redact first...
    if len(safe_detail) > limit:                  # ...then trim the already-safe text
        safe_detail = safe_detail[:limit] + " […truncated]"
    body = queue_card_markdown(
        kind=kind,
        title=redact_secrets(title),
        why=safe_detail + where,
        steps=[redact_secrets(s) for s in steps])
    return write_queue_card(repo, "manual", f"{kind}-{safe_slug}", body)


@contextlib.contextmanager
def open_page(name: str, *, repo: pathlib.Path = REPO, tracing: bool = True):
    """Yield a Page on the logged-in debug Chrome, with a trace.zip per run."""
    from playwright.sync_api import sync_playwright  # lazy: absent in the test env

    from browser import ensure_chrome

    ensure_chrome.ensure()
    out = trace_dir(repo, name)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        if tracing:
            ctx.tracing.start(name=name, screenshots=True, snapshots=True)
        page = ctx.new_page()
        try:
            yield page
        finally:
            if tracing:
                ctx.tracing.stop(path=str(trace_path(out)))
                print(f"trace: {trace_path(out)}", file=sys.stderr)
            page.close()


def check(site: str, *, page=None) -> SiteStatus:
    """Open the site dashboard and report whether the profile is still logged in."""
    cfg = SITES[site]
    if page is not None:
        page.goto(cfg.dashboard_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_load_state("domcontentloaded")
        return classify(site, cfg.dashboard_url, page.url)
    with open_page(f"check-{site}") as pg:
        pg.goto(cfg.dashboard_url, wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_load_state("domcontentloaded")
        return classify(site, cfg.dashboard_url, pg.url)


def report(status: SiteStatus, *, repo: pathlib.Path = REPO, dry_run: bool = False) -> int:
    """Print one line; on failure write a queue card and a ledger entry. Returns an exit code."""
    mark = "OK  " if status.ok else "FAIL"
    print(f"{mark} {status.site:<11} {redact_secrets(status.detail)}")
    if status.ok or dry_run:
        return 0 if status.ok else 1
    cfg = SITES[status.site]
    body = queue_card_markdown(
        kind="login",
        title=f"Log in to {status.site} in the debug Chrome",
        why=redact_secrets(
            f"`python3 scripts/browser/session.py --check {status.site}` requested "
            f"{status.requested_url} and landed on {status.final_url}."),
        steps=["Run: python3 scripts/browser/ensure_chrome.py",
               f"In the window that opens, sign in to {status.site} "
               f"({cfg.dashboard_url}) — the profile keeps the session afterwards",
               f"Re-run: python3 scripts/browser/session.py --check {status.site}"])
    card = write_queue_card(repo, "manual", f"login-{status.site}", body)
    ledger.append(
        action=redact_secrets(
            f"Browser preflight failed for {status.site}: {status.detail}. "
            f"Wrote the manual queue card {card.relative_to(repo)}; no driver ran."),
        tier=0, status="executed",
        reasoning="Fail closed rather than retry blindly (spec Chrome rule 3).",
        files=[str(card.relative_to(repo))])
    print(f"     queued -> {card.relative_to(repo)}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Check the debug Chrome's login state per site.")
    ap.add_argument("--check", nargs="+", choices=sorted(SITES), required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be checked; open nothing, write nothing")
    a = ap.parse_args()
    if a.dry_run:
        for site in a.check:
            print(f"(dry-run) would open {SITES[site].dashboard_url} and assert "
                  f"{SITES[site].anchor_description}")
        return 0
    rc = 0
    for site in a.check:
        rc |= report(check(site))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
