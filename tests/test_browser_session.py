"""scripts/browser/session.py — per-site preflight, queue cards, trace paths."""
import datetime as dt
import os
import re

import pytest

from browser import session

NOW = dt.datetime(2026, 9, 14, 8, 30, tzinfo=dt.timezone(dt.timedelta(hours=-7)))


def test_sites_cover_every_driven_site_with_dashboard_urls():
    # TikTok joined on 2026-09-15 with the Chrome-driven scheduler (publishers/tiktok_web.py);
    # its own anchors are asserted in tests/test_browser_selectors_tiktok.py.
    assert set(session.SITES) == {"gumroad", "mailerlite", "tiktok"}
    assert session.SITES["gumroad"].dashboard_url == "https://app.gumroad.com/products"
    assert session.SITES["mailerlite"].dashboard_url == "https://dashboard.mailerlite.com/campaigns"
    assert session.SITES["tiktok"].dashboard_url == "https://www.tiktok.com/tiktokstudio"


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


# ============================ fix round 2 ============================

# --- 1. known_secrets() took the value of EVERY KEY=VALUE line in the .env, so ordinary
# config (a product URL, a base path) got masked in queue cards, corrupting the evidence
# Stephen has to act on. Only credential-shaped KEYS contribute a literal.

def _write_env(home, body):
    d = home / "kdeskaccountingtemplates"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".env").write_text(body, encoding="utf-8")


def test_known_secrets_takes_credential_keys_only(tmp_path, monkeypatch):
    _write_env(tmp_path, "GUMROAD_ACCESS_TOKEN=tok_abcdefghijkl\n"
                         "PRODUCT_URL=https://kdeskaccounting.gumroad.com/l/asc842\n")
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    session.known_secrets.cache_clear()
    try:
        secrets = session.known_secrets()
        assert "tok_abcdefghijkl" in secrets
        assert "https://kdeskaccounting.gumroad.com/l/asc842" not in secrets
        masked = session.redact_secrets(
            "failed for PRODUCT_URL=https://kdeskaccounting.gumroad.com/l/asc842")
        assert "kdeskaccounting.gumroad.com/l/asc842" in masked, "config must survive"
    finally:
        session.known_secrets.cache_clear()


def test_known_secrets_matches_key_secret_password_variants(tmp_path, monkeypatch):
    _write_env(tmp_path, "MAILERLITE_API_KEY=key_abcdefghijkl\n"
                         "SOME_SECRET=sec_abcdefghijkl\n"
                         "DB_PASSWORD=pw_abcdefghijkl\n"
                         "BASE_DIR=/Users/someone/projects\n")
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    session.known_secrets.cache_clear()
    try:
        secrets = session.known_secrets()
        assert {"key_abcdefghijkl", "sec_abcdefghijkl", "pw_abcdefghijkl"} <= secrets
        assert "/Users/someone/projects" not in secrets
    finally:
        session.known_secrets.cache_clear()


def test_known_secrets_survives_a_binary_env_file(tmp_path, monkeypatch):
    d = tmp_path / "kdeskaccountingtemplates"
    d.mkdir(parents=True)
    (d / ".env").write_bytes(b"\xff\xfe\x00binary garbage\x00")
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    session.known_secrets.cache_clear()
    try:
        assert isinstance(session.known_secrets(), frozenset)   # must not raise
    finally:
        session.known_secrets.cache_clear()


# --- 3. Both call sites truncated the exception to 300 chars BEFORE redaction, so a token
# straddling the cut left a usable prefix in the card. fail_card redacts first, then trims.

def test_fail_card_redacts_before_truncating_so_a_straddling_token_cannot_survive(
        tmp_path, monkeypatch):
    token = "tok_" + "S" * 40
    monkeypatch.setattr(session, "known_secrets", lambda: frozenset({token}))

    class _Pg:
        def screenshot(self, path):
            pass

    detail = "x" * 290 + token + " trailing context"
    card = session.fail_card(tmp_path, _Pg(), kind="gumroad-cover", slug="s",
                             title="t", detail=detail, steps=["s"],
                             run_name="gumroad-covers")
    text = card.read_text()
    assert token not in text
    for n in (8, 12, 20, 30):
        assert token[:n] not in text, f"a {n}-char prefix of the token survived"


def test_fail_card_still_truncates_a_very_long_detail(tmp_path):
    class _Pg:
        def screenshot(self, path):
            pass

    card = session.fail_card(tmp_path, _Pg(), kind="k", slug="s", title="t",
                             detail="y" * 5000, steps=["s"], run_name="r")
    text = card.read_text()
    assert "y" * 5000 not in text
    assert "truncated" in text
    # the longest run of the filler is capped (counting every "y" would also count the
    # ones pytest puts in tmp_path from this test's own name)
    longest = max((len(m) for m in re.findall(r"y+", text)), default=0)
    assert longest <= 400


# --- 5. Credentials also appear in JSON bodies and colon-separated logs, not just URLs.

def test_redact_secrets_masks_a_quoted_json_credential():
    out = session.redact_secrets('{"api_key": "abc123secretvalue", "page": 2}')
    assert "abc123secretvalue" not in out
    assert "page" in out and "2" in out


def test_redact_secrets_masks_a_bare_colon_credential():
    out = session.redact_secrets("access_token: abc123secretvalue")
    assert "abc123secretvalue" not in out


def test_redact_secrets_masks_single_quoted_and_nested_forms():
    out = session.redact_secrets("headers={'token': 'abc123secretvalue'}")
    assert "abc123secretvalue" not in out


def test_colon_redaction_does_not_eat_ordinary_words_ending_in_key():
    out = session.redact_secrets("monkey: a banana")
    assert "banana" in out


# ============================ fix round 3 ============================

# --- Redaction could not see UPLOAD_POST_KEY: known_secrets() read token FILES only, never
# the environment, and no pattern matched Upload-Post's `Authorization: Apikey <key>` scheme.
# A queue card written by scripts/publishers/ would therefore have carried the key verbatim.

def test_known_secrets_collects_credential_shaped_environment_variables(tmp_path, monkeypatch):
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("UPLOAD_POST_KEY", "up_live_abcdefghijkl")
    session.known_secrets.cache_clear()
    try:
        assert "up_live_abcdefghijkl" in session.known_secrets()
        out = session.redact_secrets("Upload-Post HTTP 401: bad key up_live_abcdefghijkl")
        assert "up_live_abcdefghijkl" not in out
        assert "***" in out
    finally:
        session.known_secrets.cache_clear()


def test_environment_secrets_are_not_cached_so_a_newly_exported_key_is_masked(tmp_path, monkeypatch):
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    session.known_secrets.cache_clear()
    try:
        session.known_secrets()                      # warm whatever cache exists
        monkeypatch.setenv("UPLOAD_POST_KEY", "up_live_exported_later")
        assert "up_live_exported_later" in session.known_secrets()
    finally:
        session.known_secrets.cache_clear()


def test_environment_sweep_ignores_a_path_or_url_valued_variable(tmp_path, monkeypatch):
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("SSH_KEY_PATH", "/Users/someone/.ssh/id_rsa")
    monkeypatch.setenv("TOKEN_ENDPOINT", "https://api.upload-post.com/api/upload")
    session.known_secrets.cache_clear()
    try:
        secrets = session.known_secrets()
        assert "/Users/someone/.ssh/id_rsa" not in secrets
        assert "https://api.upload-post.com/api/upload" not in secrets
        survives = session.redact_secrets("posted to https://api.upload-post.com/api/upload")
        assert "api.upload-post.com/api/upload" in survives, "config must survive"
    finally:
        session.known_secrets.cache_clear()


def test_redact_secrets_masks_an_apikey_authorization_header():
    out = session.redact_secrets("headers={'Authorization': 'Apikey up_live_x'}")
    assert "up_live_x" not in out
    assert "Apikey ***" in out


def test_redact_secrets_masks_an_apikey_scheme_in_a_plain_header_line():
    out = session.redact_secrets("Authorization: Apikey up_live_SECRETVALUE1")
    assert "up_live_SECRETVALUE1" not in out


# ============================ fix round 4 ============================

# --- _CREDENTIAL_KEY matched TOKEN|KEY|SECRET|PASSWORD|PASS ANYWHERE in a name, so
# COMPASS_MODE, MONKEY_NAME and KEYBOARD_LAYOUT were swept as credentials and their values
# masked out of queue cards. Anchor to whole underscore-delimited components.

@pytest.mark.parametrize("name", ["UPLOAD_POST_KEY", "GUMROAD_ACCESS_TOKEN", "MY_PASS",
                                  "MAILERLITE_API_KEY", "SOME_SECRET", "DB_PASSWORD",
                                  "TOKEN_ENDPOINT", "KEY"])
def test_is_credential_name_accepts_a_whole_component(name):
    assert session.is_credential_name(name)


@pytest.mark.parametrize("name", ["COMPASS_MODE", "MONKEY_NAME", "KEYBOARD_LAYOUT",
                                  "PASSAGE", "TOKENIZER_PATH", "BASE_DIR", "PRODUCT_URL"])
def test_is_credential_name_rejects_a_word_that_merely_contains_one(name):
    assert not session.is_credential_name(name)


def test_the_environment_sweep_leaves_an_innocent_lookalike_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("COMPASS_MODE", "north-by-northwest")
    monkeypatch.setenv("MONKEY_NAME", "the one with the cymbals")
    monkeypatch.setenv("UPLOAD_POST_KEY", "up_live_abcdefghijkl")
    session.known_secrets.cache_clear()
    try:
        secrets = session.known_secrets()
        assert "up_live_abcdefghijkl" in secrets
        assert "north-by-northwest" not in secrets
        assert "the one with the cymbals" not in secrets
        survives = session.redact_secrets("failed while heading north-by-northwest")
        assert "north-by-northwest" in survives
    finally:
        session.known_secrets.cache_clear()


# --- Tests read the ambient environment through _env_secrets(), so a developer's or CI's
# real credentials could change what a test masks. conftest strips them for every test.

def test_the_ambient_environment_is_hidden_from_every_test():
    leaked = [n for n in os.environ if session.is_credential_name(n)]
    assert leaked == [], f"credential-named variables visible to tests: {leaked}"


# ============================ ElevenLabs narration key =====================


# --- The ElevenLabs key lives in a token FILE beside MailerLite's and Bing's
# (~/kdesk-analytics/elevenlabs-api-key.txt, 0600), and scripts/video/narrate.py prints
# ElevenLabs error text to stdout. If the sweep does not know the file, a 401 body that
# echoes the key would land in a build log verbatim.

def test_known_secrets_includes_the_elevenlabs_key_file(tmp_path, monkeypatch):
    analytics = tmp_path / "kdesk-analytics"
    analytics.mkdir()
    (analytics / "elevenlabs-api-key.txt").write_text("sk_fake_elevenlabs_0123456789\n")
    monkeypatch.setattr(session.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    session.known_secrets.cache_clear()
    try:
        assert "sk_fake_elevenlabs_0123456789" in session.known_secrets()
        out = session.redact_secrets("ElevenLabs HTTP 401 for xi-api-key "
                                     "sk_fake_elevenlabs_0123456789")
        assert "sk_fake_elevenlabs_0123456789" not in out
        assert "***" in out
    finally:
        session.known_secrets.cache_clear()


def test_the_elevenlabs_environment_variable_is_swept_as_a_credential():
    assert session.is_credential_name("ELEVENLABS_API_KEY")
=======
# --- fail_card wrote every card into publish-queue/manual/ regardless of the driver, so a
# publisher that advertises its own queue dir was pointing at a directory nothing arrived in.
# The subdir is now the caller's, defaulting to "manual" for the login/canary cards.

class _ShotPage:
    def __init__(self):
        self.shots = []

    def screenshot(self, path):
        self.shots.append(path)


def test_fail_card_defaults_to_the_manual_queue(tmp_path):
    card = session.fail_card(tmp_path, _ShotPage(), kind="login", slug="gumroad",
                             title="t", detail="d", steps=["s"], run_name="r")
    assert card.parent == tmp_path / "marketing" / "publish-queue" / "manual"


def test_fail_card_writes_into_the_subdir_the_caller_names(tmp_path):
    card = session.fail_card(tmp_path, _ShotPage(), kind="tiktok_web", slug="day-1",
                             title="t", detail="d", steps=["s"], run_name="r",
                             subdir="tiktok")
    assert card.parent == tmp_path / "marketing" / "publish-queue" / "tiktok"
    assert card.exists()
