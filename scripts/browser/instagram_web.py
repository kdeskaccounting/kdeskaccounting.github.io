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

Verification (fixed 2026-10-06): the profile grid renders only 12 tiles on load, so a tile count
stops rising once the account has more than 12 posts (13 on 2026-10-06 -> false exit 2 on a live
reel). The post is confirmed by (a) the header's "N posts" figure rising, or (b) the newest grid
tile being new and its alt text matching the title/caption. The tile count is only a fallback for
when neither the header count nor the newest tile can be read. If Instagram said "shared" but
nothing confirms it, the exit message says the reel is probably live and must be checked by hand.

Exit codes: 0 posted (or already posted / dry run), 1 not signed in, 2 not confirmed -- check
the profile by hand and do NOT re-run with --go.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

CDP = "http://127.0.0.1:9222"
HANDLE = "park.sheet"
SHOTS = pathlib.Path(__file__).resolve().parent / "runs" / "instagram-web"


TILES = "main a[href*='/reel/'], main a[href*='/p/']"
_COUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)\s+posts?\b", re.IGNORECASE)


def caption_of(meta: dict) -> str:
    return str(meta.get("description") or meta.get("title") or "").strip()


def parse_post_count(text: str | None) -> int | None:
    """The exact number in "13 posts" / "1,234 posts" / "1 post" (header or og:description).

    Abbreviated figures ("1.2K posts") are rounded by Instagram and cannot show a +1, so they
    parse as None, as does text with no posts figure.
    """
    m = _COUNT.search(text or "")
    return int(m.group(1).replace(",", "")) if m else None


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).lower()


def matches_post(alt: str | None, title: str, caption: str = "") -> bool:
    """True if a grid tile's alt text is this post: it contains the title's or caption's opening."""
    a = _norm(alt)
    if not a:
        return False
    needles = [_norm(title)[:40], _norm(caption)[:60]]
    return any(n and n in a for n in needles)


def verify(*, before_count: int | None, after_count: int | None,
           before_href: str | None, after_href: str | None, after_alt: str | None,
           title: str, caption: str, before_tiles: int, after_tiles: int) -> tuple[bool, str]:
    """After the "shared" toast: does the profile confirm the new post? (confirmed, message)."""
    if before_count is not None and after_count is not None and after_count > before_count:
        return True, f"header post count {before_count} -> {after_count}"
    new_tile = bool(after_href) and after_href != before_href
    if new_tile and matches_post(after_alt, title, caption):
        return True, f"newest tile {after_href} matches the caption"
    if (before_count is None or after_count is None) and after_tiles > before_tiles:
        return True, f"grid tiles {before_tiles} -> {after_tiles} (header count unreadable)"
    seen = (f"header {before_count} -> {after_count}; newest tile "
            f"{'new but caption does not match' if new_tile else 'unchanged or unreadable'}")
    return False, ("Instagram showed 'Your reel has been shared.' but the profile did not confirm "
                   f"it ({seen}). The reel is PROBABLY LIVE: open https://www.instagram.com/{HANDLE}/ "
                   "and check by hand. Do NOT re-run with --go (it would risk a duplicate).")


def read_post_count(page) -> int | None:
    """The header's "N posts" figure, else the og/meta description's "N Posts"."""
    try:
        n = parse_post_count(page.locator("header").first.inner_text(timeout=5000))
        if n is not None:
            return n
    except Exception as e:  # noqa: BLE001 -- fall through to the meta description
        print("header count unreadable:", type(e).__name__)
    try:
        return parse_post_count(page.evaluate(
            "() => { const m = document.querySelector('meta[property=\"og:description\"], "
            "meta[name=description]'); return m ? m.content : '' }"))
    except Exception:  # noqa: BLE001 -- unreadable means "no count", never a crash after Share
        return None


def read_newest(page) -> tuple[str | None, str]:
    """(href, alt) of the first grid tile; (None, "") if the grid is empty or unreadable."""
    first = page.locator(TILES).first
    if not first.count():
        return None, ""
    img = first.locator("img").first
    alt = (img.get_attribute("alt") or "") if img.count() else ""
    return first.get_attribute("href"), alt


# Overlays seen on instagram.com that swallow the Create click. Only "not now"/close-style
# buttons inside a dialog are pressed; nothing that changes a setting or posts anything.
DISMISS = ("Not Now", "Not now", "Close")


def dismiss_overlays(page) -> None:
    for _ in range(3):
        dlg = page.locator("[role=dialog]")
        if not dlg.count():
            return
        for name in DISMISS:
            b = dlg.last.get_by_role("button", name=name, exact=True)
            if b.count():
                print("dismissing overlay:", name)
                b.first.click(); page.wait_for_timeout(1000)
                break
        else:
            page.keyboard.press("Escape"); page.wait_for_timeout(1000)


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

    # lazy import: the test suite has no Playwright
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP, timeout=30_000)
        page = browser.contexts[0].new_page()
        try:
            page.goto(f"https://www.instagram.com/{HANDLE}/", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            if "/accounts/login" in page.url:
                print("not signed in to Instagram in the debug Chrome"); return 1
            before_count = read_post_count(page)
            before_tiles = page.locator(TILES).count()
            before_href, first_alt = read_newest(page)
            print("profile posts before:", before_count, f"(header; {before_tiles} grid tiles)")
            if matches_post(first_alt, title):
                print("already posted:", f"https://www.instagram.com{before_href}"); return 0

            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            dismiss_overlays(page)  # e.g. "Turn on Notifications" -> Not Now
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
            ok, why = False, ""
            for attempt in range(3):  # the profile can lag the toast; re-read, never re-share
                page.goto(f"https://www.instagram.com/{HANDLE}/", wait_until="domcontentloaded")
                page.wait_for_timeout(6000 + 4000 * attempt)
                after_count = read_post_count(page)
                after_href, after_alt = read_newest(page)
                ok, why = verify(before_count=before_count, after_count=after_count,
                                 before_href=before_href, after_href=after_href, after_alt=after_alt,
                                 title=title, caption=caption, before_tiles=before_tiles,
                                 after_tiles=page.locator(TILES).count())
                print("profile posts after:", after_count, "| newest:",
                      f"https://www.instagram.com{after_href}" if after_href else "n/a")
                if ok:
                    break
            if ok:
                print("confirmed:", why); return 0
            page.screenshot(path=str(SHOTS / f"{tag}-5-profile-unconfirmed.png"))
            print(why)
            return 2
        finally:
            page.close()


if __name__ == "__main__":
    sys.exit(main())
