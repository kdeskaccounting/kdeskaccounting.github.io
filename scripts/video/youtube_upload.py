#!/usr/bin/env python3
"""
Upload the product walkthrough videos to YouTube through Studio in the logged-in debug Chrome (CDP :9222).
  scripts/video/.venv-tts/bin/python scripts/video/youtube_upload.py [--only slug] [--resume-open]
Writes marketing/video/<slug>/youtube.json with the resulting URL.
"""
import sys, json, pathlib, yaml, time
from playwright.sync_api import sync_playwright
REPO = pathlib.Path(__file__).resolve().parents[2]; B = REPO / "scripts/video/build"; IMG = REPO / "static/images/products"
META = {
 "asc842": ("ASC 842 Lease Accounting Excel Template — Full Walkthrough (JEs, Rollforward, Reconciliation)",
            "Tab-by-tab walkthrough of the KDesk ASC 842 Lease Accounting Workbook on its real sample data: 20 leases, operating and finance, 120-month amortization schedules, a JE Generator with your GL codes, balance sheet rollforward, maturity analysis, and a reconciliation that ties to $0. Pure Excel, no macros, Windows and Mac."),
 "asc606": ("ASC 606 Commission Capitalization Excel Template — Walkthrough (ASC 340-40 Waterfall, JEs)",
            "Tab-by-tab walkthrough of the KDesk ASC 606 Commission Accrual Workbook: 50 deals, three amortization bases (contract term, estimated benefit period, practical expedient), a 60-month amortization waterfall, JE Generator, deferred commission asset rollforward, and a reconciliation that ties to $0. Pure Excel, no macros."),
 "fixed-assets": ("Fixed Asset Depreciation & Rollforward Excel Template — Walkthrough (SL, DDB, SYD, UoP, JEs)",
            "Tab-by-tab walkthrough of the KDesk Fixed Asset Rollforward Workbook: 50 assets, four depreciation methods, 120-month schedules, a JE Generator with QuickBooks / NetSuite / Sage Intacct / Xero presets, disposal log, category rollforward, and a five-way reconciliation (Schedule = JE = Rollforward = Register = GL). Pure Excel, no macros."),
 "saas-metrics": ("SaaS Metrics Dashboard Excel Template — MRR, ARR, NRR, Churn, CAC, LTV (Full Walkthrough)",
            "Tab-by-tab walkthrough of the KDesk SaaS Metrics & ARR Dashboard: seven monthly inputs, 24 months auto-chained, 11 metrics (MRR, ARR, Net New MRR, gross churn, NRR, ARPA, CAC, LTV, LTV:CAC, CAC payback, Magic Number) and a board-ready dashboard that reconciles to recognized revenue. Pure Excel, no macros."),
 "runway": ("Startup Runway Calculator Excel Template — Runway, Cash-Zero Date, Breakeven (Walkthrough)",
            "Tab-by-tab walkthrough of the KDesk Startup Runway Calculator: 12 to 48-month cash forecast from five input tabs, two-rate revenue growth, Base / Optimistic / Pessimistic scenario multipliers, and a dashboard with months of runway, cash-zero date, peak cash and breakeven. Pure Excel, no macros."),
 "month-end-close": ("Free Month-End Close Checklist Excel Template — 42 Tasks, 18 Reconciliations (Walkthrough)",
            "Walkthrough of the free KDesk Month-End Close Checklist + Tie-Out Workbook: a 42-task close calendar in five phases, 18 subledger-to-GL reconciliations with a materiality flag, a JE tracker with a debits = credits check, and a printable sign-off page. Free, pay what you want."),
}
LINKS = {"asc842": ("asc842", "https://kdeskaccounting.gumroad.com/l/gljxc"), "asc606": ("asc606", "https://kdeskaccounting.gumroad.com/l/cjexre"),
         "fixed-assets": ("fixed-assets", "https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward-free"), "saas-metrics": ("saas-metrics", "https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard-free"),
         "runway": ("runway", "https://kdeskaccounting.gumroad.com/l/runway-calculator-free"), "month-end-close": ("month-end-close", "https://kdeskaccounting.gumroad.com/l/month-end-close-checklist")}
def chapters(slug):
    spec = yaml.safe_load(open(REPO / "marketing/video" / slug / "scenes.yaml")); d = json.load(open(B / slug / "audio/durations.json"))
    t = 0.0; out = []
    for i, sc in enumerate(spec["scenes"]):
        name = "Intro" if sc.get("kind") == "title" else ("Get the workbook" if sc.get("kind") == "outro" else sc.get("caption", sc.get("sheet", "")))
        out.append(f"{int(t//60)}:{int(t%60):02d} {name}"); t += max(3.0, float(d.get(str(i), 0)) + 0.7)
    return "\n".join(out)
def description(slug):
    page, free = LINKS[slug]; title, blurb = META[slug]
    return (f"{blurb}\n\nProduct page + free version: https://kdeskaccounting.com/templates/{page}/\nFree download: {free}\n\nChapters:\n{chapters(slug)}\n\n"
            "Built by KDesk Accounting for controllers and finance managers at SaaS companies. Not tax or legal advice.\n"
            "https://kdeskaccounting.com")
def fill(pg, slug):
    dlg = pg.locator("ytcp-uploads-dialog").first
    title = dlg.locator("#textbox[aria-label*='title']").first; title.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(META[slug][0]); pg.wait_for_timeout(500)
    desc = dlg.locator("#textbox[aria-label*='Tell viewers']").first; desc.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(description(slug)); pg.wait_for_timeout(500)
    poster = IMG / f"{slug}-poster.png"
    thumb_inp = dlg.locator("#file-loader, input[type=file][accept*='image']")
    if thumb_inp.count(): thumb_inp.first.set_input_files(str(poster)); pg.wait_for_timeout(3000)
    nk = dlg.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first; nk.scroll_into_view_if_needed(); nk.click(); pg.wait_for_timeout(500)
    for _ in range(3):
        dlg.locator("#next-button").first.click(); pg.wait_for_timeout(1500)
    pub = dlg.locator("tp-yt-paper-radio-button[name='PUBLIC']").first; pub.scroll_into_view_if_needed(); pub.click(); pg.wait_for_timeout(1200)
    got = pg.get_by_role("button", name="Got it")
    if got.count() and got.first.is_visible(): got.first.click(); pg.wait_for_timeout(800)
    # wait for upload/processing to allow publishing (Done button enabled)
    done = dlg.locator("#done-button").first
    for _ in range(120):
        if done.is_enabled(): break
        pg.wait_for_timeout(5000)
    link = dlg.locator("a.ytcp-video-info, #share-url, a[href*='youtu.be'], a[href*='youtube.com/watch']").first
    url = link.get_attribute("href") if link.count() else None
    done.click(); pg.wait_for_timeout(4000)
    return url
def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222"); ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "studio.youtube.com" in x.url), None) or ctx.new_page()
        for slug in META:
            if only and slug != only: continue
            out = REPO / "marketing/video" / slug / "youtube.json"
            if out.exists() and not only: print(slug, "already uploaded:", json.load(open(out)).get("url")); continue
            if not ("--resume-open" in sys.argv and pg.locator("ytcp-uploads-dialog").count()):
                pg.goto("https://studio.youtube.com/channel/UCmurE9-rT0C4NAZiYVR4HBw/videos/upload?d=ud", wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
                if not pg.locator("ytcp-uploads-dialog").count():
                    pg.locator("#upload-icon, ytcp-button#upload-icon, [aria-label='Upload videos']").first.click(); pg.wait_for_timeout(2500)
                pg.locator("ytcp-uploads-dialog input[type=file], input[type=file]").first.set_input_files(str(B / slug / f"{slug}.mp4")); pg.wait_for_timeout(8000)
            url = fill(pg, slug)
            json.dump({"url": url, "title": META[slug][0], "uploaded": time.strftime("%Y-%m-%d %H:%M")}, open(out, "w"), indent=1)
            print(slug, "->", url, flush=True)
            # close any leftover dialog
            close = pg.locator("ytcp-uploads-dialog #close-button, ytcp-uploads-dialog [aria-label='Close']")
            if close.count(): close.first.click(); pg.wait_for_timeout(1500)
if __name__ == "__main__": main()
