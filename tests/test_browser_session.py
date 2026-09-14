"""scripts/browser/session.py — per-site preflight, queue cards, trace paths."""
import datetime as dt

import pytest

from browser import session

NOW = dt.datetime(2026, 9, 14, 8, 30, tzinfo=dt.timezone(dt.timedelta(hours=-7)))


def test_sites_cover_gumroad_and_mailerlite_with_dashboard_urls():
    assert set(session.SITES) == {"gumroad", "mailerlite"}
    assert session.SITES["gumroad"].dashboard_url == "https://app.gumroad.com/products"
    assert session.SITES["mailerlite"].dashboard_url == "https://dashboard.mailerlite.com/campaigns"


def test_classify_is_ok_when_the_dashboard_url_holds():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://app.gumroad.com/products")
    assert s.ok is True
    assert s.site == "gumroad"
    assert "logged in" in s.detail


def test_classify_detects_a_redirect_to_the_login_page():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://app.gumroad.com/login?next=%2Fproducts")
    assert s.ok is False
    assert "not logged in" in s.detail
    assert s.final_url.endswith("%2Fproducts")


def test_classify_detects_the_mailerlite_signin_redirect():
    s = session.classify("mailerlite", "https://dashboard.mailerlite.com/campaigns",
                         "https://dashboard.mailerlite.com/login")
    assert s.ok is False


def test_classify_flags_an_unexpected_host_rather_than_calling_it_ok():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://accounts.google.com/signin/oauth")
    assert s.ok is False
    assert "unexpected" in s.detail


def test_classify_rejects_an_unknown_site_name():
    with pytest.raises(KeyError):
        session.classify("linkedin", "a", "b")


def test_queue_card_markdown_is_paste_ready_and_dated():
    card = session.queue_card_markdown(
        kind="login",
        title="Log in to Gumroad in the debug Chrome",
        why="session.py --check gumroad was redirected to https://app.gumroad.com/login",
        steps=["Run: python3 scripts/browser/ensure_chrome.py",
               "In the window that opens, sign in to Gumroad",
               "Re-run: python3 scripts/browser/session.py --check gumroad"],
        now=NOW)
    assert card.startswith("# login — Log in to Gumroad in the debug Chrome\n")
    assert "2026-09-14 08:30 -0700" in card
    assert "## Why\n" in card and "## Do this\n" in card
    assert "1. Run: python3 scripts/browser/ensure_chrome.py" in card
    assert "3. Re-run: python3 scripts/browser/session.py --check gumroad" in card


def test_write_queue_card_lands_under_the_dated_manual_folder(tmp_path):
    p = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# body\n", NOW)
    assert p == tmp_path / "marketing" / "publish-queue" / "manual" / "2026-09-14-login-gumroad.md"
    assert p.read_text() == "# body\n"


def test_write_queue_card_never_overwrites_an_existing_card(tmp_path):
    first = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# one\n", NOW)
    second = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# two\n", NOW)
    assert first.read_text() == "# one\n"
    assert second.name == "2026-09-14-login-gumroad-2.md"
    assert second.read_text() == "# two\n"


def test_trace_dir_is_one_folder_per_run_under_the_date(tmp_path):
    d = session.trace_dir(tmp_path, "gumroad-covers", NOW)
    assert d == tmp_path / "scripts" / "browser" / "runs" / "2026-09-14" / "gumroad-covers-083000"
    assert d.is_dir()
    assert session.trace_path(d) == d / "trace.zip"


# --- Gumroad moved its dashboard from app.gumroad.com to the apex gumroad.com (verified
# live 2026-09-14: app.gumroad.com/products 301s to gumroad.com/products, title "Products",
# session still logged in). classify() must not read that migration as a lost session, but
# must still reject a genuinely foreign host. Alternate hosts are an explicit per-site
# allow-list, never a fuzzy suffix match.

def test_classify_accepts_the_declared_alternate_host_after_a_site_migration():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://gumroad.com/products")
    assert s.ok is True
    assert "logged in" in s.detail


def test_classify_still_rejects_the_login_page_on_the_alternate_host():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://gumroad.com/login?next=%2Fproducts")
    assert s.ok is False
    assert "not logged in" in s.detail


def test_alternate_hosts_are_an_explicit_allow_list_not_a_suffix_match():
    assert session.SITES["gumroad"].alt_hosts == ("gumroad.com",)
    assert session.SITES["mailerlite"].alt_hosts == ()
    # a lookalike that merely ends with the same string is not accepted
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://evilgumroad.com/products")
    assert s.ok is False
    assert "unexpected" in s.detail


# --- Secret redaction. gumroad_covers_ui.verify_via_api used to pass the Gumroad token as
# a URL query param; urllib3 puts the full URL in its exception text, and that text is
# written verbatim into marketing/publish-queue/manual/ - which is NOT gitignored. One
# network blip would have committed the token. Nothing reaches a card, a ledger entry,
# stdout or a screenshot path without going through redact_secrets() first.

def test_redact_secrets_masks_an_access_token_query_param():
    out = session.redact_secrets("HTTPSConnectionPool ... /v2/products/x?access_token=abc123 (Caused by ...)")
    assert "access_token=***" in out
    assert "abc123" not in out


def test_redact_secrets_masks_a_known_literal_token_anywhere_in_the_text():
    out = session.redact_secrets("boom: tok_live_SECRET99 leaked", secrets={"tok_live_SECRET99"})
    assert "tok_live_SECRET99" not in out
    assert "***" in out


def test_redact_secrets_masks_a_bearer_header_echoed_into_an_error():
    out = session.redact_secrets("headers={'Authorization': 'Bearer abc123'}")
    assert "abc123" not in out


def test_redact_secrets_masks_every_occurrence_and_is_idempotent():
    once = session.redact_secrets("a?access_token=AAA&b access_token=BBB")
    assert "AAA" not in once and "BBB" not in once
    assert session.redact_secrets(once) == once


def test_redact_secrets_handles_empty_and_non_string_input():
    assert session.redact_secrets("") == ""
    assert session.redact_secrets(None) == ""
    assert "123" in session.redact_secrets(123) or session.redact_secrets(123) == "123"


def test_redact_secrets_ignores_a_blank_or_tiny_secret_so_it_cannot_mask_everything():
    # a short/empty secret would otherwise turn the whole message into asterisks
    out = session.redact_secrets("a real message", secrets={"", " ", "a"})
    assert out == "a real message"


def test_known_secrets_never_raises_even_when_the_token_files_are_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    session.known_secrets.cache_clear()
    assert isinstance(session.known_secrets(), frozenset)
    session.known_secrets.cache_clear()


# --- fail_card(): the one place a driver failure becomes a queue card, so redaction has a
# single choke point instead of being re-implemented in each driver.

class _FakePage:
    def __init__(self, fail=False):
        self.shots = []
        self._fail = fail

    def screenshot(self, path):
        if self._fail:
            raise RuntimeError("page is closed")
        self.shots.append(path)


def test_fail_card_writes_a_card_with_the_secret_masked(tmp_path):
    pg = _FakePage()
    card = session.fail_card(
        tmp_path, pg, kind="gumroad-cover", slug="phxigq",
        title="Set the cover by hand",
        detail="requests failed: /v2/products/x?access_token=abc123",
        steps=["Open the editor"], run_name="gumroad-covers")
    text = card.read_text()
    assert "access_token=***" in text
    assert "abc123" not in text
    assert card.parent == tmp_path / "marketing" / "publish-queue" / "manual"
    assert "gumroad-cover-phxigq" in card.name


def test_fail_card_takes_a_screenshot_under_the_run_folder(tmp_path):
    pg = _FakePage()
    session.fail_card(tmp_path, pg, kind="gumroad-workflow", slug="asc842", title="t",
                      detail="d", steps=["s"], run_name="gumroad-workflows")
    assert len(pg.shots) == 1
    assert pg.shots[0].endswith("fail.png")
    assert "gumroad-workflows-fail-asc842" in pg.shots[0]


def test_fail_card_still_writes_the_card_when_the_screenshot_fails(tmp_path):
    card = session.fail_card(tmp_path, _FakePage(fail=True), kind="gumroad-workflow",
                             slug="asc842", title="t", detail="the real failure",
                             steps=["s"], run_name="gumroad-workflows")
    assert "the real failure" in card.read_text()


def test_fail_card_masks_a_secret_that_appears_in_the_steps_or_title(tmp_path):
    card = session.fail_card(
        tmp_path, _FakePage(), kind="gumroad-cover", slug="x",
        title="token access_token=abc123", detail="d",
        steps=["curl 'https://api.gumroad.com/v2/products?access_token=abc123'"],
        run_name="gumroad-covers")
    assert "abc123" not in card.read_text()
