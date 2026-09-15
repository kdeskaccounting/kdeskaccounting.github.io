#!/usr/bin/env python3
"""
Upload covers + thumbnails to Gumroad listings through the logged-in debug Chrome (CDP :9222).
The Gumroad API silently ignores cover params, so this drives the product editor UI.

  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py [--only slug] [--skip a,b]
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check      # read-only
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --dry-run    # plan only

Behaviour is unchanged from the 2026-09-02 version; the browser lifecycle, login preflight,
condition waits (no wait_for_timeout), tracing and queue cards come from scripts/browser/.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from browser import selectors_gumroad as S  # noqa: E402
from browser import session  # noqa: E402

IMG = (REPO / "static" / "images" / "products").resolve()
LISTINGS = {  # Gumroad EDITOR permalink -> (cover, thumb, api product id or None)
    "phxigq": ("asc842-cover.png", "asc842-thumb.png", "Gp9nwTmverZnmQqvQe_afg=="),
    "gljxc": ("asc842-free-cover.png", "asc842-free-thumb.png", "OYv6bQLI2pyKl7xnr-qzTA=="),
    "mwmwpe": ("asc606-cover.png", "asc606-thumb.png", None),
    "cjexre": ("asc606-free-cover.png", "asc606-free-thumb.png", "XW7TqzwvQ8MuwsiMOUq-ng=="),
    "xsezh": ("fixed-assets-cover.png", "fixed-assets-thumb.png", "SAuqdvLmzgT_nUKj99lpZw=="),
    "pdnpy": ("fixed-assets-free-cover.png", "fixed-assets-free-thumb.png", "T9PHkG-s1Hz_tHIlgoyf_A=="),
    "qmgnitm": ("saas-metrics-cover.png", "saas-metrics-thumb.png", "5b3Dn9UXPPDSu_gJs1gVhA=="),
    "feqoy": ("saas-metrics-free-cover.png", "saas-metrics-free-thumb.png", "oEIj8s_0_Kk9qHDuPT6Y1Q=="),
    "bujdfg": ("runway-cover.png", "runway-thumb.png", "tDj5H9JMTOTNHlr8JLqOWg=="),
    "onxlfg": ("runway-free-cover.png", "runway-free-thumb.png", "ZkFjfA6mjAV6ogPNTqkJjw=="),
    "sjftml": ("month-end-close-cover.png", "month-end-close-thumb.png", "tvxqT2fwquibDUr1V4rJEg=="),
    "shccc": ("bundle-cover.png", "bundle-thumb.png", "WAKdGcEmy476e-5fWioVsQ=="),
}


def token() -> str:
    env = pathlib.Path(os.path.expanduser("~/kdeskaccountingtemplates/.env"))
    for line in env.read_text().splitlines():
        if line.startswith("GUMROAD_ACCESS_TOKEN"):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"No GUMROAD_ACCESS_TOKEN in {env}")


def file_input_watcher_js() -> str:
    """JS: record every file input the editor adds to the DOM.

    Gumroad creates the input only after the upload button is clicked, so it is watched
    for rather than polled. Built from the selector constant (spec Chrome rule 6); plain
    concatenation keeps the JS braces literal, with no f-string escaping to get wrong.
    """
    sel = repr(S.FILE_INPUT)
    return ("() => { window.__fi=[]; const mo=new MutationObserver(ms=>ms.forEach(m=>m.addedNodes"
            ".forEach(n=>{ if(n.nodeType===1){ if(n.matches&&n.matches(" + sel + "))"
            " window.__fi.push(n); n.querySelectorAll&&n.querySelectorAll(" + sel + ")"
            ".forEach(i=>window.__fi.push(i)); } }))); mo.observe(document.documentElement,"
            "{childList:true,subtree:true}); }")


def cover_tile_count_js() -> str:
    """JS predicate: has a new cover tile appeared since there were `n` of them?"""
    return f"n => document.querySelectorAll({S.COVER_TABS!r}).length > n"


def open_editor(pg, slug: str):
    from playwright.sync_api import expect
    pg.goto(S.EDITOR_URL.format(slug=slug), wait_until="domcontentloaded", timeout=60_000)
    status = session.classify("gumroad", S.EDITOR_URL.format(slug=slug), pg.url)
    if not status.ok:
        raise SystemExit(session.report(status, repo=REPO) and f"gumroad preflight: {status.detail}")
    cover = pg.locator(S.SECTION.format(heading=S.COVER_HEADING)).first
    expect(cover).to_be_visible(timeout=30_000)
    return cover


def check_listing(pg, slug: str) -> str:
    """Read-only: assert the two anchors this driver depends on still resolve."""
    from playwright.sync_api import expect
    cover = open_editor(pg, slug)
    thumb = pg.locator(S.SECTION.format(heading=S.THUMBNAIL_HEADING)).first
    expect(thumb).to_be_visible(timeout=30_000)
    tabs = cover.locator(S.COVER_TABS).count()
    return f"cover section ok (tiles={tabs}) · thumbnail section ok"


def do_listing(pg, slug: str, cover_png: str, thumb_png: str):
    from playwright.sync_api import expect
    cov = open_editor(pg, slug)
    pg.evaluate(file_input_watcher_js())
    cov.scroll_into_view_if_needed()
    tiles = cov.locator(S.COVER_TABS)
    before = tiles.count()
    if cov.locator(S.ADD_COVER_BUTTON).count():
        cov.locator(S.ADD_COVER_BUTTON).first.click()
        dialog = pg.locator(S.DIALOG)
        expect(dialog).to_be_visible(timeout=15_000)
        dialog.locator("button", has_text=S.UPLOAD_BUTTON_TEXT).first.click()
    else:
        cov.locator("button", has_text=S.UPLOAD_BUTTON_TEXT).first.click()
    pg.wait_for_function("() => window.__fi && window.__fi.length > 0", timeout=15_000)
    handle = pg.evaluate_handle("() => window.__fi[window.__fi.length-1]")
    element = handle.as_element()
    if element is None:
        raise RuntimeError(f"no file input created by {S.UPLOAD_BUTTON_TEXT!r}")
    element.set_input_files(str(IMG / cover_png))
    pg.keyboard.press("Escape")
    pg.wait_for_function(cover_tile_count_js(), arg=before, timeout=120_000)
    if before > 0:  # drag the new (last) tile to the front so it becomes the main cover
        src = tiles.nth(tiles.count() - 1).bounding_box()
        dst = tiles.nth(0).bounding_box()
        pg.mouse.move(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2)
        pg.mouse.down()
        for i in range(1, 12):
            pg.mouse.move(src["x"] + src["width"] / 2 + (dst["x"] - src["x"]) * i / 11,
                          src["y"] + src["height"] / 2)
        pg.mouse.move(dst["x"] + 5, dst["y"] + dst["height"] / 2)
        pg.mouse.up()
        expect(tiles.nth(0)).to_be_visible(timeout=15_000)
    th = pg.locator(S.SECTION.format(heading=S.THUMBNAIL_HEADING)).first
    th.scroll_into_view_if_needed()
    rm = th.locator(S.THUMBNAIL_REMOVE_BUTTON)
    if rm.count():
        rm.first.click()
        expect(th.locator(S.IMAGE)).to_have_count(0, timeout=15_000)
    th.locator(S.FILE_INPUT).first.set_input_files(str(IMG / thumb_png))
    expect(th.locator(S.IMAGE).first).to_be_visible(timeout=120_000)
    with pg.expect_response(
            lambda r: S.SAVE_RESPONSE_PRODUCTS in r.url and r.request.method in ("PUT", "POST"),
            timeout=60_000):
        pg.get_by_role("button", name=S.SAVE_BUTTON).first.click()
    alerts = [a for a in pg.locator(S.ALERTS).all_inner_texts() if a.strip()][:2]
    return before, alerts


def verify_via_api(pid: str | None) -> str:
    """Confirm through the API that Gumroad kept the cover and thumbnail.

    The token goes in an Authorization header, never a query param: a failed request
    raises with the full URL in its message, and that message is written into a queue card
    under marketing/publish-queue/ — which git tracks.
    """
    if not pid:
        return ""
    import requests
    g = requests.get(f"https://api.gumroad.com/v2/products/{pid}",
                     headers={"Authorization": f"Bearer {token()}"},
                     timeout=30).json()["product"]
    covers = g.get("covers") or []
    return (f"covers={len(covers)} "
            f"main_is_new={(covers[0].get('id') if covers else None) == g.get('main_cover_id')} "
            f"thumb={bool(g.get('thumbnail_url'))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--skip", default="")
    ap.add_argument("--check", action="store_true", help="read-only anchor assertion; changes nothing")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; open nothing")
    a = ap.parse_args()
    skip = {s for s in a.skip.split(",") if s}
    targets = [(s, v) for s, v in LISTINGS.items() if (not a.only or s == a.only) and s not in skip]
    if a.dry_run:
        for slug, (cover, thumb, _pid) in targets:
            print(f"(dry-run) {slug:<10} cover={cover} thumb={thumb}")
        return 0
    rc = 0
    with session.open_page("gumroad-covers", repo=REPO) as pg:
        for slug, (cover, thumb, pid) in targets:
            try:
                if a.check:
                    print(session.redact_secrets(f"{slug:<10} CHECK {check_listing(pg, slug)}"), flush=True)
                    continue
                before, alerts = do_listing(pg, slug, cover, thumb)
                print(session.redact_secrets(
                    f"{slug:<10} ok  old_covers={before} {verify_via_api(pid)} {alerts}"),
                    flush=True)
            except Exception as exc:  # noqa: BLE001 — one retry max, then a queue card (rule 7)
                rc = 1
                card = session.fail_card(
                    REPO, pg, kind="gumroad-cover", slug=slug, run_name="gumroad-covers",
                    title=f"Set the cover and thumbnail on Gumroad listing {slug} by hand",
                    detail=f"gumroad_covers_ui.py failed: {exc}",   # full text: fail_card redacts, then trims
                    steps=[f"Open {S.EDITOR_URL.format(slug=slug)}",
                           f"Cover → {S.UPLOAD_BUTTON_TEXT} → static/images/products/{cover}",
                           "Drag the new tile to the first position",
                           f"Thumbnail → replace with static/images/products/{thumb}",
                           S.SAVE_BUTTON])
                print(f"{slug:<10} FAILED {session.redact_secrets(str(exc))[:120]} "
                      f"-> {card.relative_to(REPO)}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
