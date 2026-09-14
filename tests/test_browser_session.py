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
