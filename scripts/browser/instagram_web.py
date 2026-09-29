"""Post a ParkSheet Short as an Instagram Reel through instagram.com in the debug Chrome.

  scripts/video/.venv-tts/bin/python scripts/browser/instagram_web.py --asset day-1.mp4 --meta day-1.json [--go]

Why: the Chrome extension cannot open instagram.com, Upload-Post's free tier is spent, and
Stephen ruled (2026-09-29) that Instagram is posted by hand from the daily session until
Upload-Post Basic is bought. Playwright over CDP against Stephen's logged-in debug Chrome is
the same path that set the bio on 2026-09-23.

Flow (verified 2026-09-29): Create -> Post -> "Create new post" dialog with one
`input[type=file]` (accept includes video/mp4) -> Next (crop) -> Next (edit) -> caption box
(`[aria-label="Add a caption..."]`) -> Share -> "Your reel has been shared." Without --go the
script stops after filling the caption and closes the dialog (Discard) so nothing is posted.

Idempotency: the profile grid is read first; if the newest reel's alt/caption starts with the
meta title, the script reports "already posted" and does nothing. Never retries a Share.
Session-only; never an Actions job; no credentials are read or typed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
HANDLE = "park.sheet"
SHOTS = pathlib.Path(__file__).resolve().parent / "runs" / "instagram-web"


def caption_of(meta: dict) -> str:
    return str(meta.get("description") or meta.get("title") or "").strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--asset", type=pathlib.Path, required=True)
    ap.add_argument("--meta", type=pathlib.Path, required=True)
    ap.add_argument("--go", action="store_true", help="really click Share")
    args = ap.parse_args(argv)
    meta = json.loads(args.meta.read_text())
    title = str(meta["title"]).strip()
    caption = caption_of(meta)
    SHOTS.mkdir(parents=True, exist_ok=True)
    tag = args.asset.stem

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP, timeout=30_000)
        page = browser.contexts[0].new_page()
        try:
            page.goto(f"https://www.instagram.com/{HANDLE}/", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            if "/accounts/login" in page.url:
                print("not signed in to Instagram in the debug Chrome"); return 1
            before = page.locator("main a[href*='/reel/'], main a[href*='/p/']").count()
            print("profile posts before:", before)
            first = page.locator("main a[href*='/reel/'], main a[href*='/p/']").first
            first_alt = (first.locator("img").first.get_attribute("alt") or "") if first.count() else ""
            if title[:40].lower() in first_alt.lower():
                print("already posted:", page.url); return 0

            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.locator("svg[aria-label='New post'], svg[aria-label='Create']").first.click()
            page.wait_for_timeout(1500)
            page.get_by_text("Post", exact=True).first.click()
            page.wait_for_timeout(2500)
            dlg = page.locator("[role=dialog]").last
            dlg.locator("input[type=file]").first.set_input_files(str(args.asset))
            page.wait_for_timeout(6000)
            page.screenshot(path=str(SHOTS / f"{tag}-1-loaded.png"))
            for step in ("crop", "edit"):
                ok = page.get_by_role("button", name="OK", exact=True)
                if ok.count():  # "Video posts are now shared as reels" notice
                    ok.first.click(); page.wait_for_timeout(1000)
                nxt = page.locator("[role=dialog]").last.get_by_role("button", name="Next", exact=True).first
                nxt.wait_for(state="visible", timeout=60_000)
                nxt.click(); page.wait_for_timeout(3000)
                page.screenshot(path=str(SHOTS / f"{tag}-2-{step}.png"))
            # verified 2026-09-29: the placeholder reads "Add a caption..." on the New reel step
            box = page.locator("[aria-label='Add a caption...'], [aria-label='Write a caption...'], [role=dialog] div[contenteditable='true']").first
            box.wait_for(state="visible", timeout=30_000)
            box.click()
            for i, line in enumerate(caption.split("\n")):
                page.keyboard.type(line, delay=1)
                if i < caption.count("\n"):
                    page.keyboard.press("Enter")
            page.wait_for_timeout(800)
            got = box.inner_text()
            print("caption chars typed:", len(got), "of", len(caption))
            page.screenshot(path=str(SHOTS / f"{tag}-3-caption.png"))
            if not args.go:
                print("dry run: stopping before Share")
                page.keyboard.press("Escape"); page.wait_for_timeout(800)
                d = page.get_by_role("button", name="Discard", exact=True)
                if d.count(): d.first.click()
                return 0
            # verified 2026-09-29: "Share" is a link-styled control top-right of the New reel dialog
            share = page.locator("[role=dialog]").last.get_by_text("Share", exact=True).first
            share.click()
            print("Share clicked")
            shared = page.get_by_text("has been shared", exact=False).first
            try:
                shared.wait_for(state="visible", timeout=180_000)
                print("instagram says:", shared.inner_text())
            except Exception:
                page.screenshot(path=str(SHOTS / f"{tag}-4-after-share.png"))
                print("no 'shared' confirmation seen within 3 min; NOT retrying -- check the profile by hand")
                return 2
            page.goto(f"https://www.instagram.com/{HANDLE}/", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            after = page.locator("main a[href*='/reel/'], main a[href*='/p/']")
            print("profile posts after:", after.count())
            href = after.first.get_attribute("href") if after.count() else None
            print("newest:", f"https://www.instagram.com{href}" if href else "n/a")
            return 0 if after.count() > before else 2
        finally:
            page.close()


if __name__ == "__main__":
    sys.exit(main())
