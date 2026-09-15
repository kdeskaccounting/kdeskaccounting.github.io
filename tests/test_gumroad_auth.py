"""The Gumroad token travels in a header, never in a URL.

Gumroad's v2 API accepts `?access_token=...`, and both weekly scripts used it. A query
string is the worst place to put a credential: it lands in the server's access logs, in any
proxy in between, in a `requests` exception's repr (which is what a queue card or a CI log
would print), and in the shell history of anyone who reproduces the call with curl. The
header form is equally supported and none of that happens. crm_sync.fetch_gumroad already
did it this way; these two are the stragglers.

`requests` is absent from the mandated test environment, so each test injects a fake module
into sys.modules - the same seam tests/test_crm_sync.py uses.
"""
import sys
import types

import pull_gumroad_snapshot as pg
import sync_gumroad_to_mailerlite as sync

TOKEN = "FAKE-GUMROAD-TOKEN"


class Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_requests(monkeypatch, seen, payloads):
    def fake_get(url, headers=None, params=None, timeout=None):
        seen.append({"url": url, "headers": headers or {}, "params": params or {}})
        return Response(payloads[min(len(seen) - 1, len(payloads) - 1)])

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=fake_get))


def _assert_no_token_in_the_url(call):
    assert TOKEN not in call["url"], "the token must not be in the URL"
    assert "access_token" not in call["params"], "nor in the query string"
    assert "access_token" not in call["url"]
    assert call["headers"].get("Authorization") == f"Bearer {TOKEN}"


def test_pull_gumroad_snapshot_authenticates_with_a_header(monkeypatch):
    seen = []
    _fake_requests(monkeypatch, seen, [
        {"products": [{"id": "p1"}]},
        {"sales": [{"email": "buyer@northstar.example", "price": 0}], "next_page_key": None},
    ])
    prods, sales = pg.pull(TOKEN)
    assert [p["id"] for p in prods] == ["p1"]
    assert len(sales) == 1
    assert len(seen) == 2, "one products call, one sales call"
    for call in seen:
        _assert_no_token_in_the_url(call)


def test_pull_still_pages_on_the_page_key(monkeypatch):
    """The token moved to a header; page_key stays a query param, which is what it is."""
    seen = []
    _fake_requests(monkeypatch, seen, [
        {"products": []},
        {"sales": [{"email": "a@northstar.example"}], "next_page_key": "k2"},
        {"sales": [{"email": "b@northstar.example"}], "next_page_key": None},
    ])
    _prods, sales = pg.pull(TOKEN)
    assert len(sales) == 2
    assert seen[2]["params"]["page_key"] == "k2"


def test_sync_gumroad_to_mailerlite_authenticates_with_a_header(monkeypatch):
    seen = []
    _fake_requests(monkeypatch, seen, [
        {"sales": [{"email": "buyer@northstar.example", "product_name": "x",
                    "created_at": "2026-09-11T04:25:17Z"}], "next_page_key": None},
    ])
    monkeypatch.setattr(sync, "gtoken", lambda: TOKEN)
    sales = sync.gumroad_sales(3650)
    assert [s["email"] for s in sales] == ["buyer@northstar.example"]
    for call in seen:
        _assert_no_token_in_the_url(call)


def test_neither_script_mentions_access_token_any_more():
    """The literal is the thing to grep for; leaving one behind is how the other half of a
    two-file fix gets forgotten."""
    import pathlib

    for module in (pg, sync):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert "access_token" not in source.replace("GUMROAD_ACCESS_TOKEN", ""), module.__name__
