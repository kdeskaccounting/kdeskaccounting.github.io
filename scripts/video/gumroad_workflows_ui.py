#!/usr/bin/env python3
"""Create + publish the free->paid follow-up workflows on Gumroad (UI via CDP :9222). Copy from marketing/email-sequences/workflows.json.
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py [--only slug]"""
import sys, json, pathlib, time
from playwright.sync_api import sync_playwright
REPO = pathlib.Path(__file__).resolve().parents[2]; W = json.load(open(REPO / "marketing/email-sequences/workflows.json"))
PRODUCT = {"asc842": "ASC 842 Lease Accounting Workbook — Free Excel Template (3-Lease Version)",
           "asc606": "ASC 606 Commission Accrual Workbook — Free Excel Template (5-Deal Version)",
           "fixed-assets": "Free 5-Asset Fixed Asset Depreciation Workbook (Excel)",
           "saas-metrics": "SaaS Metrics & ARR Dashboard — FREE 6-Month Excel Template",
           "runway": "Startup Runway Calculator — Free Excel Template (12-Month)"}
NAME = {"asc842": "Free → full: ASC 842 (3-email follow-up)", "asc606": "Free → full: ASC 606 (3-email follow-up)", "fixed-assets": "Free → full: Fixed Assets (3-email follow-up)",
        "saas-metrics": "Free → full: SaaS Metrics (3-email follow-up)", "runway": "Free → full: Runway (3-email follow-up)"}
JS_STATE = "() => [...document.querySelectorAll('input[placeholder=\"Subject\"]')].map(s=>{let n=s; for(let i=0;i<12;i++){ n=n.parentElement; if(n.querySelector('[contenteditable=true]')&&n.querySelector('input[placeholder=\"0\"]')) break;} const ce=n.querySelector('[contenteditable=true]'); return {subj:s.value.slice(0,16), delay:n.querySelector('input[placeholder=\"0\"]').value, body:(ce?ce.innerText:'').trim().length}})"
def alerts(pg): return [a for a in pg.locator("[role=alert],[role=status]").all_inner_texts() if a.strip()][:2]
def block(pg, i):
    s = pg.locator("input[placeholder='Subject']").nth(i); return s, s.locator("xpath=ancestor::*[.//input[@placeholder='0']][1]")
def type_body(pg, blk, text):
    body = blk.locator("[contenteditable=true]").first; body.scroll_into_view_if_needed(); body.click(); pg.wait_for_timeout(250)
    for line in text.split("\n"): pg.keyboard.type(line); pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
def existing(pg):
    pg.goto("https://app.gumroad.com/workflows", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    return pg.evaluate("() => [...document.querySelectorAll('a[href*=\"/workflows/\"][href$=\"/edit\"]')].map(a=>({href:a.getAttribute('href'), text:(a.closest('tr,li,section,div')?.innerText||'').replace(/\\s+/g,' ').slice(0,120)}))")
def build(pg, slug):
    emails = W[slug]
    wf = next((e["href"].split("/")[2] for e in existing(pg) if NAME[slug][:22] in e["text"]), None)
    if not wf:
        pg.goto("https://app.gumroad.com/workflows/new", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.locator("#name").fill(NAME[slug]); pg.get_by_text("Purchase", exact=True).first.click(); pg.wait_for_timeout(300)
        pg.locator("#bought").click(); pg.keyboard.type(PRODUCT[slug][:24]); pg.wait_for_timeout(1200)
        pg.get_by_text(PRODUCT[slug], exact=True).first.click(); pg.wait_for_timeout(800)
        pg.get_by_role("button", name="Save and continue").first.click(force=True); pg.wait_for_timeout(3500)
        wf = pg.url.split("/workflows/")[1].split("/")[0]
    pg.goto(f"https://app.gumroad.com/workflows/{wf}/edit", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    if PRODUCT[slug][:20] not in pg.inner_text("body"):
        pg.locator("#bought").click(); pg.keyboard.type(PRODUCT[slug][:24]); pg.wait_for_timeout(1200)
        pg.get_by_text(PRODUCT[slug], exact=True).first.click(); pg.wait_for_timeout(800)
        pg.get_by_role("button", name="Save changes").first.click(force=True); pg.wait_for_timeout(3500)
        pg.goto(f"https://app.gumroad.com/workflows/{wf}/edit", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    ok_filter = PRODUCT[slug][:20] in pg.inner_text("body")
    pg.goto(f"https://app.gumroad.com/workflows/{wf}/emails", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    t = pg.inner_text("body")
    if sum(1 for e in emails if e["subject"] in t) < 3:
        for _ in range(8):
            d = pg.locator("button[aria-label='Delete']")
            if not d.count(): break
            d.first.click(force=True); pg.wait_for_timeout(600)
            c = pg.get_by_role("button", name="Yes, delete")
            if c.count(): c.first.click(force=True); pg.wait_for_timeout(600)
        pg.get_by_role("button", name="Create email").first.click(force=True); pg.wait_for_timeout(1200)
        for _ in range(2): pg.get_by_role("button", name="Add email").last.click(force=True); pg.wait_for_timeout(1200)
        for i, e in enumerate(emails):
            s, blk = block(pg, i); d = blk.locator("input[placeholder='0']").first; d.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(str(e["delay_days"]))
            blk.locator("select").first.select_option(label="days after purchase"); s.click(); s.fill(e["subject"]); pg.wait_for_timeout(200); type_body(pg, blk, e["body"])
        st = pg.evaluate(JS_STATE)
        for i, e in enumerate(emails):
            if st[i]["body"] < 50: s, blk = block(pg, i); type_body(pg, blk, e["body"])
        pg.wait_for_timeout(1500)
        for attempt in range(3):
            pg.get_by_role("button", name="Save changes").first.click(force=True); pg.wait_for_timeout(4500); a = alerts(pg)
            if any("saved" in x.lower() for x in a): break
            pg.wait_for_timeout(2000)
        pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(3500); t = pg.inner_text("body")
        # fix delays after reload (the delay input sometimes drops on the middle editor)
        for i in range(pg.get_by_role("button", name="Edit").count()): pg.get_by_role("button", name="Edit").nth(i).click(force=True); pg.wait_for_timeout(500)
        st = pg.evaluate(JS_STATE); changed = False
        for i, x in enumerate(st):
            idx = next((k for k, e in enumerate(emails) if e["subject"][:16] == x["subj"]), None)
            if idx is not None and x["delay"] != str(emails[idx]["delay_days"]):
                s, blk = block(pg, i); d = blk.locator("input[placeholder='0']").first; d.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(str(emails[idx]["delay_days"])); blk.locator("select").first.select_option(label="days after purchase"); changed = True
        if changed:
            pg.wait_for_timeout(800); pg.get_by_role("button", name="Save changes").first.click(force=True); pg.wait_for_timeout(4500)
        pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(3500); t = pg.inner_text("body")
    n = sum(1 for e in emails if e["subject"] in t); delays = [m for m in ["0 days after purchase", "3 days after purchase", "7 days after purchase"] if m in t]
    published = pg.get_by_role("button", name="Unpublish").count() > 0
    if n == 3 and len(delays) == 3 and ok_filter and not published:
        pg.get_by_role("button", name="Publish").first.click(force=True); pg.wait_for_timeout(4500)
        pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(3000); published = pg.get_by_role("button", name="Unpublish").count() > 0
    print(f"{slug:<13} wf={wf[:10]} filter={ok_filter} emails={n}/3 delays={len(delays)}/3 published={published}", flush=True)
def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222"); ctx = b.contexts[0]; pg = ctx.new_page()
        for slug in W:
            if only and slug != only: continue
            try: build(pg, slug)
            except Exception as e:
                pg.screenshot(path=str(REPO / "scripts/video/build/cdp" / f"wf-fail-{slug}.png")); print(f"{slug:<13} FAILED {str(e)[:140]}", flush=True)
        pg.close()
if __name__ == "__main__": main()
