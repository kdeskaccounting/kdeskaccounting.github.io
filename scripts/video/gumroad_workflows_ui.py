#!/usr/bin/env python3
"""Create + publish the free->paid follow-up workflows on Gumroad (UI via CDP :9222).
Copy from marketing/email-sequences/workflows.json.

  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py [--only slug]
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check    # read-only
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --dry-run  # plan only

Declarative and idempotent: read the live state, apply only what is missing, re-read and
assert. Re-running with nothing to do prints the verified state and changes nothing.
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from browser import selectors_gumroad as S  # noqa: E402
from browser import session  # noqa: E402

W = json.loads((REPO / "marketing/email-sequences/workflows.json").read_text(encoding="utf-8"))
PRODUCT = {
    "asc842": "ASC 842 Lease Accounting Workbook — Free Excel Template (3-Lease Version)",
    "asc606": "ASC 606 Commission Accrual Workbook — Free Excel Template (5-Deal Version)",
    # Renamed on Gumroad; the old "Free 5-Asset Fixed Asset Depreciation Workbook (Excel)"
    # no longer exists. Kept in step with tests/fixtures/gumroad_product_names.json.
    "fixed-assets": "Free Fixed Asset Register + Depreciation Schedule (Excel, 5 Assets)",
    "saas-metrics": "SaaS Metrics & ARR Dashboard — FREE 6-Month Excel Template",
    "runway": "Startup Runway Calculator — Free Excel Template (12-Month)",
}
NAME = {
    "asc842": "Free → full: ASC 842 (3-email follow-up)",
    "asc606": "Free → full: ASC 606 (3-email follow-up)",
    "fixed-assets": "Free → full: Fixed Assets (3-email follow-up)",
    "saas-metrics": "Free → full: SaaS Metrics (3-email follow-up)",
    "runway": "Free → full: Runway (3-email follow-up)",
}
JS_STATE = (
    "() => [...document.querySelectorAll('input[placeholder=\"Subject\"]')].map(s=>{let n=s;"
    " for(let i=0;i<12;i++){ n=n.parentElement; if(n.querySelector('[contenteditable=true]')"
    "&&n.querySelector('input[placeholder=\"0\"]')) break;}"
    " const ce=n.querySelector('[contenteditable=true]');"
    " return {subj:s.value.slice(0,16), delay:n.querySelector('input[placeholder=\"0\"]').value,"
    " body:(ce?ce.innerText:'').trim().length}})")
DELAY_LABELS = ("0 days after purchase", "3 days after purchase", "7 days after purchase")


def block(pg, i):
    s = pg.locator(S.WORKFLOW_SUBJECT_INPUT).nth(i)
    return s, s.locator(S.WORKFLOW_BLOCK_FOR_SUBJECT)


def type_body(pg, blk, text):
    from playwright.sync_api import expect
    body = blk.locator(S.WORKFLOW_BODY_EDITOR).first
    body.scroll_into_view_if_needed()
    body.click()
    expect(body).to_be_focused(timeout=10_000)
    for line in text.split("\n"):
        pg.keyboard.type(line)
        pg.keyboard.press("Enter")


def goto(pg, url):
    from playwright.sync_api import expect
    pg.goto(url, wait_until="domcontentloaded", timeout=60_000)
    status = session.classify("gumroad", url, pg.url)
    if not status.ok:
        session.report(status, repo=REPO)
        raise SystemExit(f"gumroad preflight: {status.detail}")
    expect(pg.locator("body")).to_be_visible(timeout=30_000)


def product_names_js() -> str:
    """JS that reads every listing name off the products table.

    The name is the first line of the row's first non-empty cell; the remainder of that
    cell is the public /l/ URL.
    """
    return (f"() => [...document.querySelectorAll('{S.PRODUCT_ROWS}')].map(r => {{"
            f" const c = [...r.querySelectorAll('td,th')]"
            f".map(x => (x.innerText||'').trim()).find(Boolean) || '';"
            f" return c.split('\\n')[0].trim(); }}).filter(Boolean)")


def product_mismatches(live_names) -> list:
    """(slug, name) for every PRODUCT entry that is not a current Gumroad listing.

    A stale name is not cosmetic: read_state() reports filter=False for that slug forever,
    and build() reacts by retyping the filter and clicking an option that no longer exists.
    An empty `live_names` (the scrape found nothing) deliberately reports every slug rather
    than passing silently - fail closed.
    """
    live = set(live_names)
    return [(slug, name) for slug, name in sorted(PRODUCT.items()) if name not in live]


def mismatch_lines(live_names, slugs=None) -> list:
    """One named PRODUCT MISMATCH line per stale entry; empty when every name is live.

    Runs before any write, not just under --check: a stale name makes build() retype the
    product filter and click an option that no longer exists.
    """
    names = list(live_names)
    if not names:
        return [f"{'products':<13} PRODUCT MISMATCH could not read any listing name from "
                f"{S.PRODUCTS_URL} — cannot verify PRODUCT, so refusing to guess"]
    wanted = set(slugs) if slugs is not None else None
    return [f"{slug:<13} PRODUCT MISMATCH {name!r} is not one of the {len(names)} live "
            f"Gumroad listings — fix PRODUCT['{slug}'] and re-capture "
            f"tests/fixtures/gumroad_product_names.json"
            for slug, name in product_mismatches(names)
            if wanted is None or slug in wanted]


def live_product_names(pg) -> list:
    """Read-only: the listing names currently on the Gumroad products page."""
    goto(pg, S.PRODUCTS_URL)
    pg.wait_for_selector(S.PRODUCT_ROWS, state="attached", timeout=30_000)
    return pg.evaluate(product_names_js())


def workflow_links_js() -> str:
    """The JS that reads the workflow list: [{href, text}] for every edit anchor.

    Every segment is an f-string so the `{{` / `}}` escaping is uniform. Mixing an
    f-string segment with plain ones silently leaves `}}` as two literal braces, which
    is what broke this reader on 2026-09-14 (SyntaxError: Unexpected token '}').
    """
    return (f"() => [...document.querySelectorAll('{S.WORKFLOW_LINKS}')].map(a=>({{"
            f"href:a.getAttribute('href'),"
            f"text:(a.closest('{S.WORKFLOW_ROW_CONTAINER}')?.innerText||'')"
            f".replace(/\\s+/g,' ').slice(0,120)}}))")


class WorkflowScrapeError(RuntimeError):
    """The workflow list rendered, but its names could not be read.

    Distinct from "there are no workflows": rows exist, so the markup drifted. Treating
    that as an empty list is what makes build() create duplicates of workflows that are
    already there, so it is raised rather than returned.
    """


def check_scrape_sane(rows) -> list:
    """Pass the scraped rows through, or refuse when every one of them is nameless."""
    if rows and not any((r.get("text") or "").strip() for r in rows):
        raise WorkflowScrapeError(
            f"read {len(rows)} workflow rows from {S.WORKFLOWS_URL} but every one had an "
            f"empty name, so no workflow can be recognised. Gumroad's list markup has "
            f"changed: fix selectors_gumroad.WORKFLOW_ROW_CONTAINER. Refusing to continue, "
            f"because treating this as 'no workflows exist' would create a duplicate of "
            f"every workflow.")
    return rows


def existing(pg):
    goto(pg, S.WORKFLOWS_URL)
    pg.wait_for_selector(S.WORKFLOW_LINKS, state="attached", timeout=30_000)
    return check_scrape_sane(pg.evaluate(workflow_links_js()))


def body_contains_js() -> str:
    """JS predicate: is `t` present in the rendered body text yet?"""
    return "t => (document.body?.innerText || '').includes(t)"


def has_text(pg, needle: str, timeout: int = 15_000) -> bool:
    """Wait for `needle` to appear in the body; False only once it genuinely never does.

    The editor hydrates after domcontentloaded, so a bare inner_text() read races it.
    Waiting on the condition makes a False mean "absent", not "not rendered yet" - which
    matters because build() turns filter_ok=False into a live save.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    try:
        pg.wait_for_function(body_contains_js(), arg=needle, timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


def read_state(pg, slug):
    """Live state for one workflow: id, product filter, subjects present, delays, published."""
    wf = next((e["href"].split("/")[2] for e in existing(pg) if NAME[slug][:22] in e["text"]), None)
    if wf is None:
        return {"wf": None, "filter_ok": False, "emails": 0, "delays": 0, "published": False}
    goto(pg, S.WORKFLOW_EDIT_URL.format(wf=wf))
    filter_ok = has_text(pg, PRODUCT[slug][:20])
    goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=wf))
    has_text(pg, W[slug][0]["subject"])  # let the email list hydrate before counting it
    text = pg.inner_text("body")
    return {"wf": wf, "filter_ok": filter_ok,
            "emails": sum(1 for e in W[slug] if e["subject"] in text),
            "delays": sum(1 for d in DELAY_LABELS if d in text),
            "published": pg.get_by_role("button", name=S.WORKFLOW_UNPUBLISH_BUTTON).count() > 0}


def save(pg):
    from playwright.sync_api import expect
    with pg.expect_response(
            lambda r: S.SAVE_RESPONSE_WORKFLOWS in r.url and r.request.method in ("PUT", "POST"),
            timeout=60_000):
        pg.get_by_role("button", name=S.SAVE_BUTTON).first.click(force=True)
    expect(pg.locator(S.ALERTS).first).to_be_visible(timeout=30_000)


def delete_all_emails(pg, expect_fn, tries: int = 8) -> int:
    """Remove every existing email block; returns how many were deleted.

    The count is captured BEFORE the click - re-reading it afterwards raced the deletion
    and compared against a number that had already dropped, so the assertion passed
    whatever happened. The confirmation button is waited for rather than probed with
    count(), which reads 0 while the dialog is still animating in and silently skips it.
    """
    deleted = 0
    for _ in range(tries):
        buttons = pg.locator(S.WORKFLOW_DELETE_BUTTON)
        before = buttons.count()
        if not before:
            break
        buttons.first.click(force=True)
        confirm = pg.get_by_role("button", name=S.WORKFLOW_CONFIRM_DELETE).first
        expect_fn(confirm).to_be_visible(timeout=15_000)
        confirm.click(force=True)
        expect_fn(pg.locator(S.WORKFLOW_DELETE_BUTTON)).to_have_count(before - 1, timeout=15_000)
        deleted += 1
    return deleted


def apply_emails(pg, slug):
    from playwright.sync_api import expect
    emails = W[slug]
    delete_all_emails(pg, expect)
    pg.get_by_role("button", name=S.WORKFLOW_CREATE_EMAIL).first.click(force=True)
    expect(pg.locator(S.WORKFLOW_SUBJECT_INPUT)).to_have_count(1, timeout=30_000)
    for n in (2, 3):
        pg.get_by_role("button", name=S.WORKFLOW_ADD_EMAIL).last.click(force=True)
        expect(pg.locator(S.WORKFLOW_SUBJECT_INPUT)).to_have_count(n, timeout=30_000)
    for i, e in enumerate(emails):
        s, blk = block(pg, i)
        delay = blk.locator(S.WORKFLOW_DELAY_INPUT).first
        delay.click()
        pg.keyboard.press("Meta+A")
        pg.keyboard.type(str(e["delay_days"]))
        blk.locator(S.WORKFLOW_DELAY_UNIT_SELECT).first.select_option(
            label=S.WORKFLOW_DELAY_UNIT_LABEL)
        s.click()
        s.fill(e["subject"])
        type_body(pg, blk, e["body"])
    for i, e in enumerate(emails):
        if pg.evaluate(JS_STATE)[i]["body"] < 50:
            _s, blk = block(pg, i)
            type_body(pg, blk, e["body"])
    save(pg)


def build(pg, slug, check_only=False):
    from playwright.sync_api import expect
    state = read_state(pg, slug)
    if check_only:
        return (f"wf={str(state['wf'])[:10]} filter={state['filter_ok']} "
                f"emails={state['emails']}/3 delays={state['delays']}/3 "
                f"published={state['published']}")
    if state["wf"] is None:
        goto(pg, S.WORKFLOW_NEW_URL)
        pg.locator(S.WORKFLOW_NAME_INPUT).fill(NAME[slug])
        pg.get_by_text(S.WORKFLOW_TRIGGER_PURCHASE, exact=True).first.click()
        pg.locator(S.WORKFLOW_BOUGHT_INPUT).click()
        pg.keyboard.type(PRODUCT[slug][:24])
        option = pg.get_by_text(PRODUCT[slug], exact=True).first
        expect(option).to_be_visible(timeout=15_000)
        option.click()
        with pg.expect_navigation(timeout=60_000):
            pg.get_by_role("button", name=S.WORKFLOW_SAVE_CONTINUE).first.click(force=True)
        state = read_state(pg, slug)
    if state["wf"] is None:
        # Never format a URL with "None". If the workflow still cannot be found after the
        # create branch ran, something is wrong upstream and another pass would create yet
        # another duplicate.
        raise WorkflowScrapeError(
            f"workflow for {slug!r} could not be found after creating it — refusing to "
            f"continue, because re-running this branch would create another duplicate. "
            f"Check {S.WORKFLOWS_URL} by hand.")
    if not state["filter_ok"]:
        goto(pg, S.WORKFLOW_EDIT_URL.format(wf=state["wf"]))
        pg.locator(S.WORKFLOW_BOUGHT_INPUT).click()
        pg.keyboard.type(PRODUCT[slug][:24])
        option = pg.get_by_text(PRODUCT[slug], exact=True).first
        expect(option).to_be_visible(timeout=15_000)
        option.click()
        save(pg)
        state = read_state(pg, slug)
    if state["emails"] < 3:
        goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=state["wf"]))
        apply_emails(pg, slug)
        state = read_state(pg, slug)
    if state["emails"] == 3 and state["delays"] == 3 and state["filter_ok"] and not state["published"]:
        goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=state["wf"]))
        with pg.expect_response(lambda r: S.SAVE_RESPONSE_WORKFLOWS in r.url, timeout=60_000):
            pg.get_by_role("button", name=S.WORKFLOW_PUBLISH_BUTTON).first.click(force=True)
        state = read_state(pg, slug)
    return (f"wf={str(state['wf'])[:10]} filter={state['filter_ok']} "
            f"emails={state['emails']}/3 delays={state['delays']}/3 published={state['published']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--check", action="store_true", help="read-only state report; changes nothing")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; open nothing")
    a = ap.parse_args()
    slugs = [s for s in W if not a.only or s == a.only]
    if a.dry_run:
        for slug in slugs:
            print(f"(dry-run) {slug:<13} would ensure '{NAME[slug]}' has "
                  f"{len(W[slug])} emails filtered to {PRODUCT[slug][:40]}…")
        return 0
    rc = 0
    with session.open_page("gumroad-workflows", repo=REPO) as pg:
        # Verify PRODUCT against the live listings before anything is written. Read-only.
        stale = mismatch_lines(live_product_names(pg), slugs)
        for line in stale:
            print(line, flush=True)
        if stale:
            rc = 1
            if not a.check:
                # A write run stops here: build() would retype a filter from a name that
                # no longer exists. --check keeps going, because reporting state is the
                # whole point of the canary.
                print("aborted before any write — fix PRODUCT, then re-run", flush=True)
                return rc
        for slug in slugs:
            try:
                print(session.redact_secrets(f"{slug:<13} {build(pg, slug, check_only=a.check)}"),
                      flush=True)
            except Exception as exc:  # noqa: BLE001
                rc = 1
                card = session.fail_card(
                    REPO, pg, kind="gumroad-workflow", slug=slug, run_name="gumroad-workflows",
                    title=f"Finish the free→paid workflow for {slug} in the Gumroad editor",
                    detail=f"gumroad_workflows_ui.py failed: {str(exc)[:300]}",
                    steps=[f"Open {S.WORKFLOWS_URL}",
                           f"Open or create '{NAME[slug]}' filtered to '{PRODUCT[slug]}'",
                           "Paste the three emails from marketing/email-sequences/workflows.json "
                           f"under key '{slug}' with delays 0/3/7 days after purchase",
                           "Save changes, then Publish"])
                print(f"{slug:<13} FAILED {session.redact_secrets(str(exc))[:120]} "
                      f"-> {card.relative_to(REPO)}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
