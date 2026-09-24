"""Post a comment on a YouTube video as the signed-in channel and pin it, through the debug Chrome.

  scripts/video/.venv-tts/bin/python scripts/browser/youtube_pin_comment.py --video VIDEO_ID --text-file comment.txt

Needs Stephen's Chrome running with --remote-debugging-port=9222 (scripts/browser/ensure_chrome.py)
and the brand channel selected in that profile. The script:

  1. opens the watch page and scrolls to the comments
  2. if a comment starting with the text's first line already exists, skips posting
  3. otherwise types the text (Shift+Enter between lines), clicks Comment, and dismisses
     YouTube's one-time "Remember that anyone can see what you write" notice, which swallows
     the first submit on a new channel and has to be answered with Got it before re-submitting
  4. opens the comment's action menu and clicks Pin, then reloads and looks for "Pinned by"

Exit codes: 0 pinned (or already pinned) · 2 comment did not post · 3 pin blocked because the
channel has not verified a phone number (Studio > Settings > Channel > Feature eligibility >
Intermediate features) — the comment stays up, unpinned · 4 pin clicked but badge not seen.
No YouTube Data API is used (uploads via the API are barred; comments are kept off it too).
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
SHOTS = pathlib.Path(__file__).resolve().parent / "runs" / "youtube-pin"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", required=True, help="YouTube video id")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="comment text; use \\n for line breaks")
    group.add_argument("--text-file", type=pathlib.Path)
    args = ap.parse_args(argv)
    text = args.text_file.read_text().strip() if args.text_file else args.text.replace("\\n", "\n")
    lines = text.split("\n")
    first = lines[0][:60]
    SHOTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].new_page()
        page.goto(f"https://www.youtube.com/watch?v={args.video}", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        for _ in range(6):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(600)
        page.wait_for_selector("ytd-comments#comments", timeout=30_000)
        threads = page.locator("ytd-comment-thread-renderer").filter(has_text=first)
        print("existing threads with our text:", threads.count())
        if not threads.count():
            box = page.locator("ytd-comments #simplebox-placeholder, ytd-comments #placeholder-area").first
            box.wait_for(state="visible", timeout=30_000)
            box.click()
            page.wait_for_timeout(800)
            editor = page.locator("ytd-comments #contenteditable-root").first
            editor.click()
            for i, line in enumerate(lines):
                page.keyboard.type(line, delay=1)
                if i < len(lines) - 1:
                    page.keyboard.press("Shift+Enter")
            page.wait_for_timeout(800)
            print("composer chars:", len(editor.inner_text()))
            submit = page.locator("ytd-comment-simplebox-renderer").get_by_role("button", name="Comment", exact=True)
            submit.first.click()
            page.wait_for_timeout(2500)
            got_it = page.get_by_role("button", name="Got it", exact=True)
            if got_it.count():
                print("first-comment notice: dismissing and re-submitting")
                got_it.first.click()
                page.wait_for_timeout(1000)
                if editor.inner_text().strip():
                    page.locator("ytd-comment-simplebox-renderer").get_by_role(
                        "button", name="Comment", exact=True).first.click()
            page.wait_for_timeout(5000)
            page.screenshot(path=str(SHOTS / f"{args.video}-after-submit.png"))
            threads = page.locator("ytd-comment-thread-renderer").filter(has_text=first)
            print("threads after posting:", threads.count())
            if not threads.count():
                page.close()
                return 2
        thread = threads.first
        if "Pinned by" in (thread.inner_text() or ""):
            print("already pinned")
            page.close()
            return 0
        thread.hover()
        thread.locator("#action-menu button, ytd-menu-renderer yt-icon-button button").first.click()
        page.wait_for_timeout(1200)
        pin = page.get_by_role("menuitem", name="Pin", exact=False)
        if not pin.count():
            pin = page.locator("ytd-menu-popup-renderer").get_by_text("Pin", exact=True)
        if not pin.count():
            print("no Pin item in the comment menu (is the brand channel the signed-in channel?)")
            page.close()
            return 4
        pin.first.click()
        page.wait_for_timeout(1500)
        if page.get_by_text("verify your phone number", exact=False).count():
            print("PIN BLOCKED: channel needs phone verification "
                  "(Studio > Settings > Channel > Feature eligibility > Intermediate features). Comment is up, unpinned.")
            page.get_by_role("button", name="Cancel", exact=True).first.click()
            page.close()
            return 3
        confirm = page.get_by_role("button", name="Pin", exact=True)
        if confirm.count():
            confirm.first.click()
            page.wait_for_timeout(2500)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        for _ in range(6):
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(600)
        t = page.locator("ytd-comment-thread-renderer").filter(has_text=first)
        pinned = t.count() and "Pinned by" in (t.first.inner_text() or "")
        print("pinned badge after reload:", bool(pinned))
        page.close()
        return 0 if pinned else 4


if __name__ == "__main__":
    sys.exit(main())
