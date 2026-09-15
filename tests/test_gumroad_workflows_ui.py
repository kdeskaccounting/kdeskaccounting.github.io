"""scripts/video/gumroad_workflows_ui.py — the JS it injects must be syntactically valid.

Regression test for a live failure on 2026-09-14: the workflow-list reader was built by
concatenating an f-string segment (where `{{` collapses to `{`) with plain segments (where
`}}` stays two literal braces), so every run died with
`Page.evaluate: SyntaxError: Unexpected token '}'` and queued five manual cards.
Playwright is absent here, so the JS is built by a pure function and checked as text.
"""
import sys

import pytest

import gumroad_workflows_ui as wf


def _balanced(js: str, opener: str, closer: str) -> bool:
    depth = 0
    for ch in js:
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def test_workflow_links_js_has_balanced_braces_and_parens():
    js = wf.workflow_links_js()
    assert js.count("{") == js.count("}"), js
    assert _balanced(js, "{", "}"), js
    assert _balanced(js, "(", ")"), js


def test_workflow_links_js_selects_the_workflow_edit_anchors():
    js = wf.workflow_links_js()
    assert 'a[href*="/workflows/"][href$="/edit"]' in js
    assert "href:a.getAttribute('href')" in js
    # the regex literal must survive as \s+, not a doubled backslash
    assert r"replace(/\s+/g,' ')" in js


def test_workflow_links_js_returns_one_object_per_anchor():
    js = wf.workflow_links_js()
    assert js.startswith("() =>")
    assert "map(a=>({" in js
    assert js.rstrip().endswith("}))")


# --- Gumroad rebuilt the workflow list in 2026 as one <table> per workflow whose <caption>
# carries the name; the edit anchor now sits in a text-less <div>. closest() returns the
# NEAREST ancestor matching any selector in the list, so a bare 'div' in that list wins and
# yields ''. Verified live 2026-09-14: all 7 workflows returned text:'' and read_state()
# matched none of them - a non-check run would have created five DUPLICATE workflows.

def test_row_container_selector_excludes_the_bare_div_that_swallowed_the_name():
    from browser import selectors_gumroad as S
    parts = {p.strip() for p in S.WORKFLOW_ROW_CONTAINER.split(",")}
    assert "table" in parts, "the workflow name lives in the table's caption"
    assert "div" not in parts, "a bare div is the nearest ancestor and has no text"
    assert "li" not in parts, "li is also nearer than the table in the current markup"


def test_workflow_links_js_reads_text_from_the_row_container_constant():
    from browser import selectors_gumroad as S
    js = wf.workflow_links_js()
    assert f"closest('{S.WORKFLOW_ROW_CONTAINER}')" in js
    assert "closest('tr,li,section,div')" not in js


# --- The editor hydrates after domcontentloaded, so reading inner_text('body') straight
# after goto() races it. On 2026-09-14 two identical --check runs disagreed about asc842's
# product filter (False then True) with no write in between; build() turns filter_ok=False
# into a live save, so a raced read costs an unnecessary write to Gumroad.

def test_body_contains_js_is_a_predicate_over_the_rendered_body_text():
    js = wf.body_contains_js()
    assert js.startswith("t =>")
    assert "document.body" in js
    assert "innerText" in js
    assert ".includes(t)" in js


def test_body_contains_js_tolerates_a_body_that_is_not_there_yet():
    js = wf.body_contains_js()
    assert "?." in js or "||" in js, "must not throw before the body exists"


# --- PRODUCT must only name listings that actually exist on Gumroad. Verified live
# 2026-09-14: PRODUCT["fixed-assets"] still said "Free 5-Asset Fixed Asset Depreciation
# Workbook (Excel)" while the listing had been renamed to "Free Fixed Asset Register +
# Depreciation Schedule (Excel, 5 Assets)", so --check reported filter=False forever and a
# live run would have retyped a filter that was already correct, clicking an option that no
# longer exists. tests/fixtures/gumroad_product_names.json is the captured listing set;
# re-capture it and update PRODUCT in the same commit whenever Stephen renames a listing.

import json
import pathlib

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "gumroad_product_names.json"


def _live_names() -> set:
    return set(json.loads(FIXTURE.read_text(encoding="utf-8"))["names"])


def test_the_fixture_captures_the_current_listing_names():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["captured"] == "2026-09-14"
    assert len(data["names"]) == 14
    assert "Free Fixed Asset Register + Depreciation Schedule (Excel, 5 Assets)" in data["names"]


def test_every_product_name_is_a_current_gumroad_listing():
    assert wf.product_mismatches(_live_names()) == []


def test_fixed_assets_points_at_the_renamed_listing():
    assert wf.PRODUCT["fixed-assets"] == (
        "Free Fixed Asset Register + Depreciation Schedule (Excel, 5 Assets)")
    # the stale 2026-09 name must not come back
    assert "5-Asset Fixed Asset Depreciation" not in wf.PRODUCT["fixed-assets"]


def test_product_mismatches_names_the_offending_slug_and_value():
    stale = {n for n in _live_names() if n != wf.PRODUCT["fixed-assets"]}
    assert wf.product_mismatches(stale) == [
        ("fixed-assets", "Free Fixed Asset Register + Depreciation Schedule (Excel, 5 Assets)")]


def test_product_mismatches_reports_every_slug_when_the_scrape_returns_nothing():
    assert len(wf.product_mismatches(set())) == len(wf.PRODUCT)


def test_product_names_js_reads_the_listing_name_from_each_row():
    js = wf.product_names_js()
    assert js.startswith("() =>")
    assert "table tbody tr" in js
    assert "split('\\n')[0]" in js
    assert _balanced(js, "{", "}") and _balanced(js, "(", ")")


# ============================ fix round 1 ============================

# --- 2. Markup drift must never reach the create branch. If the scrape returns rows but
# every row's text is empty, the workflow names are simply unreadable - which is exactly
# what happened on 2026-09-14. read_state() would report wf=None and build() would create a
# duplicate of a workflow that already exists. Fail loudly instead.

def test_scraped_rows_pass_through_when_at_least_one_row_has_text():
    rows = [{"href": "/workflows/a/edit", "text": ""},
            {"href": "/workflows/b/edit", "text": "Free → full: ASC 606"}]
    assert wf.check_scrape_sane(rows) == rows


def test_no_rows_at_all_is_an_empty_workflow_list_not_drift():
    assert wf.check_scrape_sane([]) == []


def test_rows_with_every_text_empty_raise_rather_than_creating_duplicates():
    rows = [{"href": "/workflows/a/edit", "text": ""},
            {"href": "/workflows/b/edit", "text": "   "}]
    with pytest.raises(wf.WorkflowScrapeError) as e:
        wf.check_scrape_sane(rows)
    msg = str(e.value)
    assert "2" in msg
    assert "duplicate" in msg.lower()


# --- 3. The PRODUCT guard must run before ANY write, not only under --check. A stale name
# makes build() retype a filter and click an option that no longer exists.

def test_mismatch_lines_are_empty_when_every_product_name_is_live():
    assert wf.mismatch_lines(_live_names()) == []


def test_mismatch_lines_name_the_slug_and_the_stale_value():
    stale = {n for n in _live_names() if n != wf.PRODUCT["runway"]}
    lines = wf.mismatch_lines(stale)
    assert len(lines) == 1
    assert "runway" in lines[0]
    assert "PRODUCT MISMATCH" in lines[0]
    assert wf.PRODUCT["runway"] in lines[0]


def test_mismatch_lines_fail_closed_when_the_scrape_reads_nothing():
    lines = wf.mismatch_lines([])
    assert len(lines) == 1
    assert "PRODUCT MISMATCH" in lines[0]


def test_build_is_never_reached_when_a_product_name_is_stale(monkeypatch, capsys):
    """A write run must abort on mismatch, before build() touches anything."""
    import contextlib as _ctx

    @_ctx.contextmanager
    def fake_open_page(*_a, **_k):
        yield object()

    def boom(*_a, **_k):
        raise AssertionError("build() must not run when PRODUCT is stale")

    monkeypatch.setattr(wf.session, "open_page", fake_open_page)
    monkeypatch.setattr(wf, "live_product_names", lambda _pg: ["something else entirely"])
    monkeypatch.setattr(wf, "build", boom)
    monkeypatch.setattr(sys, "argv", ["gumroad_workflows_ui.py"])   # a real write run
    rc = wf.main()
    assert rc == 1
    assert "PRODUCT MISMATCH" in capsys.readouterr().out


def test_a_clean_product_list_lets_a_write_run_proceed(monkeypatch, capsys):
    import contextlib as _ctx
    seen = []

    @_ctx.contextmanager
    def fake_open_page(*_a, **_k):
        yield object()

    monkeypatch.setattr(wf.session, "open_page", fake_open_page)
    monkeypatch.setattr(wf, "live_product_names", lambda _pg: sorted(_live_names()))
    monkeypatch.setattr(wf, "build", lambda pg, slug, check_only=False: seen.append(slug) or "ok")
    monkeypatch.setattr(sys, "argv", ["gumroad_workflows_ui.py", "--only", "runway"])
    rc = wf.main()
    assert rc == 0
    assert seen == ["runway"]


# --- 4. The delete loop compared against a count re-read AFTER the click, and clicked the
# confirm button without waiting for it. Capture before, wait for confirm, assert the drop.

class _FakeLocator:
    def __init__(self, page, key):
        self.page, self.key = page, key
        self.first = self

    def count(self):
        return self.page.counts[self.key]

    def click(self, **_kw):
        self.page.events.append(f"click:{self.key}")
        if self.key == "confirm":
            self.page.counts["delete"] = max(0, self.page.counts["delete"] - 1)


class _FakePage:
    def __init__(self, n):
        self.counts = {"delete": n, "confirm": 1}
        self.events = []
        self.expects = []

    def locator(self, sel):
        return _FakeLocator(self, "delete")

    def get_by_role(self, _role, name=None):
        return _FakeLocator(self, "confirm")


def _fake_expect(page):
    class _Assert:
        def __init__(self, loc):
            self.loc = loc

        def to_be_visible(self, timeout=None):
            page.expects.append(("visible", self.loc.key))

        def to_have_count(self, n, timeout=None):
            page.expects.append(("count", self.loc.key, n))
            assert self.loc.count() == n, f"expected {n}, got {self.loc.count()}"
    return _Assert


def test_delete_loop_waits_for_the_confirm_dialog_before_clicking_it():
    pg = _FakePage(1)
    wf.delete_all_emails(pg, _fake_expect(pg))
    assert pg.events == ["click:delete", "click:confirm"]
    # the confirm button is asserted visible before it is clicked
    assert pg.expects[0] == ("visible", "confirm")


def test_delete_loop_asserts_the_count_dropped_to_the_captured_value_minus_one():
    pg = _FakePage(3)
    assert wf.delete_all_emails(pg, _fake_expect(pg)) == 3
    counts = [e for e in pg.expects if e[0] == "count"]
    assert [c[2] for c in counts] == [2, 1, 0]
    assert pg.counts["delete"] == 0


def test_delete_loop_does_nothing_when_there_are_no_emails():
    pg = _FakePage(0)
    assert wf.delete_all_emails(pg, _fake_expect(pg)) == 0
    assert pg.events == []


# --- 5. Site-specific anchors belong in selectors_gumroad.py (Chrome rule 6).

def test_no_inline_gumroad_anchors_survive_in_the_workflows_driver():
    src = pathlib.Path(wf.__file__).read_text(encoding="utf-8")
    for literal in ("button[aria-label='Delete']", "Yes, delete", "Create email", "Add email",
                    'name="Publish"', 'name="Unpublish"', "Save and continue"):
        assert literal not in src, f"{literal!r} should live in selectors_gumroad.py"


def test_the_moved_selectors_all_exist():
    from browser import selectors_gumroad as S
    for attr in ("WORKFLOW_DELETE_BUTTON", "WORKFLOW_CONFIRM_DELETE", "WORKFLOW_CREATE_EMAIL",
                 "WORKFLOW_ADD_EMAIL", "WORKFLOW_PUBLISH_BUTTON", "WORKFLOW_UNPUBLISH_BUTTON",
                 "WORKFLOW_SAVE_CONTINUE", "WORKFLOW_TRIGGER_PURCHASE",
                 "WORKFLOW_DELAY_UNIT_SELECT", "WORKFLOW_DELAY_UNIT_LABEL",
                 "SAVE_RESPONSE_WORKFLOWS", "SAVE_RESPONSE_PRODUCTS"):
        assert getattr(S, attr), attr


def test_the_unused_save_response_fragments_constant_is_gone():
    from browser import selectors_gumroad as S
    assert not hasattr(S, "SAVE_RESPONSE_FRAGMENTS")


def test_the_dead_alerts_helper_is_gone():
    assert not hasattr(wf, "alerts")


def test_workflows_json_is_read_without_leaking_a_file_handle():
    src = pathlib.Path(wf.__file__).read_text(encoding="utf-8")
    assert "json.load(open(" not in src
    assert "read_text(" in src


# ============================ fix round 2 ============================

# --- 2. The pre-write PRODUCT guard navigates (goto + wait_for_selector), so it can time
# out. It sat OUTSIDE the try/except: a timeout there produced a raw traceback, no queue
# card and no ledger line - the exact "silent failure" the spec forbids.

class _ShotPage:
    def __init__(self):
        self.shots = []

    def screenshot(self, path):
        self.shots.append(path)


def _fake_open_page(page):
    import contextlib as _ctx

    @_ctx.contextmanager
    def _cm(*_a, **_k):
        yield page
    return _cm


def test_a_timeout_in_the_product_guard_writes_a_card_instead_of_a_traceback(
        tmp_path, monkeypatch, capsys):
    page = _ShotPage()

    def timeout(*_a, **_k):
        raise TimeoutError("Timeout 30000ms exceeded waiting for table tbody tr")

    monkeypatch.setattr(wf, "REPO", tmp_path)
    monkeypatch.setattr(wf.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(wf, "live_product_names", timeout)
    monkeypatch.setattr(wf, "build", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("build() must not run after the guard failed")))
    monkeypatch.setattr(sys, "argv", ["gumroad_workflows_ui.py"])

    rc = wf.main()

    assert rc == 1
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1, "a failure must leave exactly one queue card"
    body = cards[0].read_text()
    assert "Timeout 30000ms exceeded" in body
    assert page.shots, "a screenshot should accompany the card"
    assert "FAILED" in capsys.readouterr().out


def test_the_product_guard_failure_card_names_the_preflight_not_a_slug(tmp_path, monkeypatch):
    page = _ShotPage()
    monkeypatch.setattr(wf, "REPO", tmp_path)
    monkeypatch.setattr(wf.session, "open_page", _fake_open_page(page))
    monkeypatch.setattr(wf, "live_product_names",
                        lambda _pg: (_ for _ in ()).throw(TimeoutError("boom")))
    monkeypatch.setattr(sys, "argv", ["gumroad_workflows_ui.py"])
    wf.main()
    card = next((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert "preflight" in card.name


# --- 6. JS built from the selector constants, not from re-typed literals.

def test_email_state_js_is_built_from_the_selector_constants():
    from browser import selectors_gumroad as S
    js = wf.email_state_js()
    for const in (S.WORKFLOW_SUBJECT_INPUT, S.WORKFLOW_BODY_EDITOR, S.WORKFLOW_DELAY_INPUT):
        assert const in js, const
    assert js.count("{") == js.count("}")
    assert _balanced(js, "{", "}") and _balanced(js, "(", ")")


def test_email_state_js_returns_the_same_three_fields_as_before():
    js = wf.email_state_js()
    assert "subj:" in js and "delay:" in js and "body:" in js
    assert js.startswith("() =>")


def test_no_retyped_selector_literals_remain_in_the_workflows_driver():
    src = pathlib.Path(wf.__file__).read_text(encoding="utf-8")
    for literal in ('input[placeholder=\\"Subject\\"]', "[contenteditable=true]",
                    'input[placeholder=\\"0\\"]', "button[aria-label='Delete']",
                    "Yes, delete", "Create email", "Add email", "Save and continue"):
        assert literal not in src, f"{literal!r} should come from selectors_gumroad.py"
