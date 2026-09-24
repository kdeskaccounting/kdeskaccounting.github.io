"""Print each post on TikTok Studio's Content page with its visibility (Everyone / Only me / Friends).

  scripts/video/.venv-tts/bin/python scripts/browser/tiktok_status.py

Read-only; runs through the debug Chrome (ensure_chrome.py). Use it after a post to confirm
TikTok's review has finished ("Only me" while under review, "Everyone" once public).
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
KEYS = ("Everyone", "Only me", "Friends", "Scheduled", "review")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].new_page()
        page.goto("https://www.tiktok.com/tiktokstudio/content", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        if "login" in page.url:
            print("not signed in:", page.url)
            page.close()
            return 1
        lines = [l.strip() for l in page.inner_text("body").splitlines() if l.strip()]
        title = None
        for line in lines:
            if any(k in line for k in KEYS) and title:
                print(f"{line[:12]:<12} | {title[:90]}")
                title = None
            elif len(line) > 30:
                title = line
        page.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
