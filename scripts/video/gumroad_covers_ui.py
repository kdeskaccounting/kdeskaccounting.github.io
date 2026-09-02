#!/usr/bin/env python3
"""
Upload covers + thumbnails to Gumroad listings through the logged-in debug Chrome (CDP :9222).
The Gumroad API silently ignores cover params, so this drives the product editor UI.
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py [--only slug]
"""
import sys, pathlib, os, requests, warnings; warnings.filterwarnings("ignore")
from playwright.sync_api import sync_playwright
REPO = pathlib.Path(__file__).resolve().parents[2]; IMG = (REPO / "static" / "images" / "products").resolve()
LISTINGS = {  # Gumroad EDITOR permalink (from /products list, not the custom slug) -> (cover, thumb, api product id or None)
    "phxigq": ("asc842-cover.png", "asc842-thumb.png", "Gp9nwTmverZnmQqvQe_afg=="), "gljxc": ("asc842-free-cover.png", "asc842-free-thumb.png", "OYv6bQLI2pyKl7xnr-qzTA=="),
    "mwmwpe": ("asc606-cover.png", "asc606-thumb.png", None), "cjexre": ("asc606-free-cover.png", "asc606-free-thumb.png", "XW7TqzwvQ8MuwsiMOUq-ng=="),
    "xsezh": ("fixed-assets-cover.png", "fixed-assets-thumb.png", "SAuqdvLmzgT_nUKj99lpZw=="), "pdnpy": ("fixed-assets-free-cover.png", "fixed-assets-free-thumb.png", "T9PHkG-s1Hz_tHIlgoyf_A=="),
    "qmgnitm": ("saas-metrics-cover.png", "saas-metrics-thumb.png", "5b3Dn9UXPPDSu_gJs1gVhA=="), "feqoy": ("saas-metrics-free-cover.png", "saas-metrics-free-thumb.png", "oEIj8s_0_Kk9qHDuPT6Y1Q=="),
    "bujdfg": ("runway-cover.png", "runway-thumb.png", "tDj5H9JMTOTNHlr8JLqOWg=="), "onxlfg": ("runway-free-cover.png", "runway-free-thumb.png", "ZkFjfA6mjAV6ogPNTqkJjw=="),
    "sjftml": ("month-end-close-cover.png", "month-end-close-thumb.png", "tvxqT2fwquibDUr1V4rJEg=="),
    "shccc": ("bundle-cover.png", "bundle-thumb.png", "WAKdGcEmy476e-5fWioVsQ=="),
}
SEC = "xpath=//*[self::h2 or self::h3 or self::legend or self::label][normalize-space(.)='{h}']/ancestor::*[self::section or self::fieldset][1]"
def token():
    for l in open(os.path.expanduser("~/kdeskaccountingtemplates/.env")):
        if l.startswith("GUMROAD_ACCESS_TOKEN"): return l.split("=", 1)[1].strip().strip('"\'')
def do_listing(pg, slug, cover, thumb):
    pg.goto(f"https://app.gumroad.com/products/{slug}/edit", wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(2500)
    if "login" in pg.url: raise SystemExit("Not logged in to Gumroad in the debug browser.")
    pg.evaluate("""() => { window.__fi=[]; const mo=new MutationObserver(ms=>ms.forEach(m=>m.addedNodes.forEach(n=>{ if(n.nodeType===1){ if(n.matches&&n.matches('input[type=file]')) window.__fi.push(n); n.querySelectorAll&&n.querySelectorAll('input[type=file]').forEach(i=>window.__fi.push(i)); } }))); mo.observe(document.documentElement,{childList:true,subtree:true}); }""")
    cov = pg.locator(SEC.format(h="Cover")).first; cov.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    tiles = cov.locator("[role=tablist][aria-label='Product covers'] [role=tab]"); before = tiles.count()
    if cov.locator("button[aria-label='Add cover']").count():
        cov.locator("button[aria-label='Add cover']").first.click(); pg.wait_for_timeout(800)
        pg.locator("[role=dialog] button", has_text="Upload images or videos").first.click(); pg.wait_for_timeout(800)
    else:
        cov.locator("button", has_text="Upload images or videos").first.click(); pg.wait_for_timeout(800)
    h = pg.evaluate_handle("() => window.__fi[window.__fi.length-1]")
    if not h.as_element(): raise RuntimeError("no file input created by Upload images or videos")
    h.as_element().set_input_files(str(IMG / cover)); pg.keyboard.press("Escape")
    for _ in range(20):
        pg.wait_for_timeout(1000)
        if tiles.count() > before: break
    if tiles.count() <= before: raise RuntimeError("cover tile did not appear")
    if before > 0:  # drag the new (last) tile to the front so it becomes the main cover
        src = tiles.nth(tiles.count() - 1).bounding_box(); dst = tiles.nth(0).bounding_box()
        pg.mouse.move(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2); pg.mouse.down(); pg.wait_for_timeout(200)
        for i in range(1, 12):
            pg.mouse.move(src["x"] + src["width"] / 2 + (dst["x"] - src["x"]) * i / 11, src["y"] + src["height"] / 2); pg.wait_for_timeout(60)
        pg.mouse.move(dst["x"] + 5, dst["y"] + dst["height"] / 2); pg.wait_for_timeout(200); pg.mouse.up(); pg.wait_for_timeout(800)
    th = pg.locator(SEC.format(h="Thumbnail")).first; th.scroll_into_view_if_needed()
    rm = th.locator("button[aria-label='Remove']")
    if rm.count(): rm.first.click(); pg.wait_for_timeout(700)
    th.locator("input[type=file]").first.set_input_files(str(IMG / thumb))
    for _ in range(15):
        pg.wait_for_timeout(1000)
        if th.locator("img").count(): break
    pg.get_by_role("button", name="Save changes").first.click(); pg.wait_for_timeout(5000)
    alerts = [a for a in pg.locator("[role=alert],[role=status]").all_inner_texts() if a.strip()][:2]
    return before, alerts
def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None; tok = token()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222"); ctx = b.contexts[0]; pg = ctx.new_page()
        for slug, (cover, thumb, pid) in LISTINGS.items():
            if only and slug != only: continue
            if "--skip" in sys.argv and slug in sys.argv[sys.argv.index("--skip") + 1].split(","): continue
            try:
                before, alerts = do_listing(pg, slug, cover, thumb)
                state = ""
                if pid:
                    g = requests.get(f"https://api.gumroad.com/v2/products/{pid}", params={"access_token": tok}).json()["product"]
                    state = f"covers={len(g.get('covers') or [])} main_is_new={(g.get('covers') or [{}])[0].get('id')==g.get('main_cover_id')} thumb={bool(g.get('thumbnail_url'))}"
                print(f"{slug:<30} ok  old_covers={before} {state} {alerts}", flush=True)
            except Exception as e:
                pg.screenshot(path=str(REPO / "scripts/video/build/cdp" / f"fail-{slug}.png")); print(f"{slug:<30} FAILED {str(e)[:140]}", flush=True)
        pg.close()
if __name__ == "__main__": main()
