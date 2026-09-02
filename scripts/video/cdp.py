#!/usr/bin/env python3
"""Drive the debug Chrome (--remote-debugging-port=9222) with Playwright over CDP.
  cdp.py pages | open <url> | shot <url> <out.png> [full] | text <url> | eval <url> <js>
Reuses the browser's default context (logged-in sessions)."""
import sys, json
from playwright.sync_api import sync_playwright
CDP = "http://localhost:9222"
def main():
    cmd, *args = sys.argv[1:]
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP); ctx = b.contexts[0]
        if cmd == "pages":
            for pg in ctx.pages: print(pg.url[:100], "|", pg.title()[:60])
            return
        url = args[0]
        pg = next((x for x in ctx.pages if x.url.split("#")[0] == url.split("#")[0]), None) or ctx.new_page()
        if pg.url.split("#")[0] != url.split("#")[0]: pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(1500)
        if cmd == "open": print(pg.url, "|", pg.title())
        elif cmd == "shot": pg.screenshot(path=args[1], full_page=(len(args) > 2)); print("saved", args[1], pg.url)
        elif cmd == "text": print(pg.inner_text("body")[:6000])
        elif cmd == "eval": print(json.dumps(pg.evaluate(args[1]))[:4000])
if __name__ == "__main__": main()
