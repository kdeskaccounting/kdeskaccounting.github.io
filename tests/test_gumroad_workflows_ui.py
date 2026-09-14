"""scripts/video/gumroad_workflows_ui.py — the JS it injects must be syntactically valid.

Regression test for a live failure on 2026-09-14: the workflow-list reader was built by
concatenating an f-string segment (where `{{` collapses to `{`) with plain segments (where
`}}` stays two literal braces), so every run died with
`Page.evaluate: SyntaxError: Unexpected token '}'` and queued five manual cards.
Playwright is absent here, so the JS is built by a pure function and checked as text.
"""
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
