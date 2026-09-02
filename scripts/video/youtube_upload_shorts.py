#!/usr/bin/env python3
"""
Upload the 9:16 Shorts (scripts/video/build/<slug>/<slug>-short.mp4) through YouTube Studio in the logged-in debug Chrome (CDP :9222).
Title/description come from marketing/video/<slug>/short.json; the resulting URL is written back into that file.
  scripts/video/.venv-tts/bin/python scripts/video/youtube_upload_shorts.py [--only slug]
"""
import sys, json, pathlib, time
from playwright.sync_api import sync_playwright
REPO = pathlib.Path(__file__).resolve().parents[2]; B = REPO / "scripts/video/build"; MV = REPO / "marketing/video"
SLUGS = ["asc842", "asc606", "fixed-assets", "saas-metrics", "runway", "month-end-close"]
UPLOAD = "https://studio.youtube.com/channel/UCmurE9-rT0C4NAZiYVR4HBw/videos/upload?d=ud"
TAIL = "\n\nBuilt by KDesk Accounting for controllers and finance managers at SaaS companies. Not tax or legal advice.\nhttps://kdeskaccounting.com"

def fill(pg, title, desc):
    dlg = pg.locator("ytcp-uploads-dialog").first
    t = dlg.locator("#textbox[aria-label*='title']").first; t.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(title); pg.wait_for_timeout(500)
    d = dlg.locator("#textbox[aria-label*='Tell viewers']").first; d.click(); pg.keyboard.press("Meta+A"); pg.keyboard.type(desc); pg.wait_for_timeout(500)
    nk = dlg.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first; nk.scroll_into_view_if_needed(); nk.click(); pg.wait_for_timeout(500)
    for _ in range(3):
        dlg.locator("#next-button").first.click(); pg.wait_for_timeout(1500)
    pub = dlg.locator("tp-yt-paper-radio-button[name='PUBLIC']").first; pub.scroll_into_view_if_needed(); pub.click(); pg.wait_for_timeout(1200)
    got = pg.get_by_role("button", name="Got it")
    if got.count() and got.first.is_visible(): got.first.click(); pg.wait_for_timeout(800)
    done = dlg.locator("#done-button").first
    for _ in range(120):
        if done.is_enabled(): break
        pg.wait_for_timeout(5000)
    link = dlg.locator("a.ytcp-video-info, #share-url, a[href*='youtu.be'], a[href*='youtube.com/watch'], a[href*='youtube.com/shorts']").first
    url = link.get_attribute("href") if link.count() else None
    done.click(); pg.wait_for_timeout(4000)
    return url

def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222"); ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "studio.youtube.com" in x.url), None) or ctx.new_page()
        for slug in SLUGS:
            if only and slug != only: continue
            meta_p = MV / slug / "short.json"; meta = json.load(open(meta_p))
            if meta.get("url") and not only: print(slug, "already uploaded:", meta["url"]); continue
            mp4 = B / slug / f"{slug}-short.mp4"; assert mp4.exists(), mp4
            pg.goto(UPLOAD, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            if not pg.locator("ytcp-uploads-dialog").count():
                pg.locator("#upload-icon, ytcp-button#upload-icon, [aria-label='Upload videos']").first.click(); pg.wait_for_timeout(2500)
            pg.locator("ytcp-uploads-dialog input[type=file], input[type=file]").first.set_input_files(str(mp4)); pg.wait_for_timeout(8000)
            url = fill(pg, meta["title"], meta["description"] + TAIL)
            meta.update({"url": url, "uploaded": time.strftime("%Y-%m-%d %H:%M")}); json.dump(meta, open(meta_p, "w"), indent=1)
            print(slug, "->", url, flush=True)
            close = pg.locator("ytcp-uploads-dialog #close-button, ytcp-uploads-dialog [aria-label='Close']")
            if close.count(): close.first.click(); pg.wait_for_timeout(1500)
if __name__ == "__main__": main()
