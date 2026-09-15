"""scripts/video/gumroad_covers_ui.py — the token must never reach a repo-tracked file.

verify_via_api used to pass the Gumroad token as a URL query param. urllib3 puts the full
request URL into its exception text, and that text was written straight into a queue card
under marketing/publish-queue/manual/ — a directory git tracks. One network blip during a
cover upload would have committed the token. The token now travels as an Authorization
header, and everything on the failure path goes through session.redact_secrets().
"""
import pathlib
import sys
import types

import gumroad_covers_ui as cv
from browser import session


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _install_fake_requests(monkeypatch, recorder, payload=None):
    fake = types.ModuleType("requests")

    def get(url, **kwargs):
        recorder.append((url, kwargs))
        return _FakeResponse(payload or {"product": {"covers": [{"id": "c1"}],
                                                     "main_cover_id": "c1",
                                                     "thumbnail_url": "https://x/t.png"}})

    fake.get = get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return fake


def test_the_token_is_sent_as_an_authorization_header_not_a_url_param(monkeypatch):
    calls = []
    _install_fake_requests(monkeypatch, calls)
    monkeypatch.setattr(cv, "token", lambda: "abc123SECRETTOKEN")
    cv.verify_via_api("PID==")
    url, kwargs = calls[0]
    assert "access_token" not in url
    assert "abc123SECRETTOKEN" not in url
    assert kwargs["headers"]["Authorization"] == "Bearer abc123SECRETTOKEN"
    assert "access_token" not in str(kwargs.get("params") or {})


def test_verify_via_api_still_reports_the_cover_state(monkeypatch):
    _install_fake_requests(monkeypatch, [])
    monkeypatch.setattr(cv, "token", lambda: "abc123SECRETTOKEN")
    out = cv.verify_via_api("PID==")
    assert "covers=1" in out
    assert "main_is_new=True" in out
    assert "thumb=True" in out


def test_verify_via_api_is_skipped_without_a_product_id():
    assert cv.verify_via_api(None) == ""


def test_a_failure_card_masks_a_token_that_leaked_into_the_exception(tmp_path):
    """The regression the Authorization header alone would not cover."""
    class _Pg:
        def screenshot(self, path):
            pass

    card = session.fail_card(
        tmp_path, _Pg(), kind="gumroad-cover", slug="phxigq", run_name="gumroad-covers",
        title="Set the cover and thumbnail by hand",
        detail=("gumroad_covers_ui.py failed: HTTPSConnectionPool(host='api.gumroad.com') "
                "Max retries exceeded with url: /v2/products/PID?access_token=abc123SECRET"),
        steps=["Open the editor"])
    text = card.read_text()
    assert "abc123SECRET" not in text
    assert "access_token=***" in text


def test_no_inline_gumroad_anchors_survive_in_the_covers_driver():
    src = pathlib.Path(cv.__file__).read_text(encoding="utf-8")
    for literal in ("[role=tablist][aria-label='Product covers']", "[role=dialog]"):
        assert literal not in src, f"{literal!r} should live in selectors_gumroad.py"


def test_the_cover_tile_js_is_built_from_the_selector_constant():
    from browser import selectors_gumroad as S
    js = cv.cover_tile_count_js()
    assert S.COVER_TABS in js
    assert js.count("{") == js.count("}")


def test_the_covers_driver_uses_the_shared_fail_card_helper():
    src = pathlib.Path(cv.__file__).read_text(encoding="utf-8")
    assert "session.fail_card(" in src
    assert "session.write_queue_card(" not in src


# --- fix round 2, item 6: the MutationObserver JS re-typed input[type=file] three times.

def test_file_input_watcher_js_is_built_from_the_selector_constant():
    from browser import selectors_gumroad as S
    js = cv.file_input_watcher_js()
    assert repr(S.FILE_INPUT) in js or S.FILE_INPUT in js
    assert js.count("{") == js.count("}")
    assert js.count("(") == js.count(")")
    assert "window.__fi" in js and "MutationObserver" in js


def test_no_retyped_selector_literals_remain_in_the_covers_driver():
    src = pathlib.Path(cv.__file__).read_text(encoding="utf-8")
    for literal in ("input[type=file]", "[role=tablist][aria-label='Product covers']",
                    "[role=dialog]", '"img"'):
        assert literal not in src, f"{literal!r} should come from selectors_gumroad.py"
