"""Reply to a viewer's comment on a YouTube video as the signed-in channel, through the debug Chrome.

  scripts/video/.venv-tts/bin/python scripts/browser/youtube_reply_comment.py --video=VIDEO_ID \
      --comment "a unique piece of the viewer's comment" --text "our reply" [--dry-run]

Same session rules as youtube_pin_comment.py (whose ensure_channel it reuses): Studio is put on
S.CHANNEL_NAME (Park Detective) first and switched back afterwards; another Google account is refused (exit 5).
Playwright clicks and types with real input events (CDP Input.*), which is what a reply needs: TikTok Studio
ignored JS click() on its send button (ParkSheet memory tiktok-web-replies-dont-persist), so nothing here clicks
through page JS.

  1. opens the watch page and scrolls to the comments; finds the ONE thread whose top comment contains --comment
  2. expands its replies; if one already starts with our text's first 40 characters, stops (never replies twice)
  3. unless --dry-run: clicks the thread's Reply, types the text, clicks the reply dialog's Reply button
  4. reloads the page in the same tab, finds the thread again, expands its replies and looks for our text.
     Only this fresh-load check counts as sent.

Exit codes: 0 sent and seen after a reload (or --dry-run found the comment with no reply of ours) ·
2 submitted but not seen after the reload · 5 refused: wrong Google account (nothing posted) ·
6 comment not found, or more than one thread matched · 7 already replied (nothing posted).
No YouTube Data API is used.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))   # scripts/
from browser import studio_channel  # noqa: E402
from browser.youtube_pin_comment import CDP, ensure_channel  # noqa: E402

SHOTS = pathlib.Path(__file__).resolve().parent / "runs" / "youtube-reply"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", required=True, help="YouTube video id (pass as --video=<id>: an id can start with '-')")
    ap.add_argument("--comment", required=True, help="a unique piece of the viewer's top-level comment text")
    ap.add_argument("--text", required=True, help="the reply (one line)")
    ap.add_argument("--dry-run", action="store_true", help="find the comment and check for our reply; post nothing")
    args = ap.parse_args(argv)
    SHOTS.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright  # lazy: absent in the test env

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        found: dict = {}
        try:
            try:
                ensure_channel(page, found)
            except studio_channel.ChannelRefused as exc:
                print(f"REFUSED: {exc}. Nothing posted.")
                return 5
            return reply(page, args.video, args.comment, args.text.strip(), args.dry_run)
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001 - the tab may already be gone
                pass
            studio_channel.restore_in_new_tab(ctx, found.get("original"), label="youtube_reply_comment")


def _open_comments(page, video: str) -> None:
    page.goto(f"https://www.youtube.com/watch?v={video}", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    for _ in range(6):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(600)
    page.wait_for_selector("ytd-comments#comments ytd-comment-thread-renderer", timeout=30_000)


def _thread(page, comment: str):
    """The single thread whose top-level comment contains `comment`, or None (printing why)."""
    threads = page.locator("ytd-comment-thread-renderer").filter(
        has=page.locator("#comment #content-text", has_text=comment))
    n = threads.count()
    if n != 1:
        print(f"threads matching {comment!r}: {n} (need exactly 1)")
        return None
    return threads.first


def _reply_texts(page, thread) -> list[str]:
    """Expand the thread's replies (if any) and return their texts."""
    # Two "N replies" buttons exist (2026-11-17): #more-replies (hidden in the current layout) and
    # #more-replies-sub-thread (the visible one). Click whichever is visible.
    for sel in ("#more-replies-sub-thread button", "#more-replies button"):
        more = thread.locator(f"ytd-comment-replies-renderer {sel}")
        if more.count() and more.first.is_visible():
            more.first.click()
            page.wait_for_timeout(3000)
            break
    return [t.strip() for t in thread.locator("ytd-comment-replies-renderer #content-text").all_inner_texts()]


def norm(s: str) -> str:
    """Letters, digits and single spaces only. YouTube draws an emoji as an <img>, so a reply's inner text
    has no emoji in it: '👀' in our text would make a raw prefix match miss our own reply (2026-11-17)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def reply(page, video: str, comment: str, text: str, dry_run: bool) -> int:
    key = norm(text)[:40]
    _open_comments(page, video)
    thread = _thread(page, comment)
    if thread is None:
        return 6
    print("comment:", thread.locator("#comment #content-text").first.inner_text()[:200])
    existing = _reply_texts(page, thread)
    print("replies already there:", len(existing))
    if any(norm(r).startswith(key) for r in existing):
        print("already replied with this text: nothing posted")
        return 7
    if dry_run:
        print("dry run: would reply", repr(text))
        return 0
    thread.locator("#reply-button-end button, #reply-button-end ytd-button-renderer").first.click()
    page.wait_for_timeout(1200)
    dialog = thread.locator("ytd-comment-reply-dialog-renderer").first
    editor = dialog.locator("#contenteditable-root").first
    editor.wait_for(state="visible", timeout=15_000)
    editor.click()
    page.keyboard.type(text, delay=1)
    page.wait_for_timeout(800)
    print("composer chars:", len(editor.inner_text()))
    dialog.locator("#submit-button button, #submit-button").first.click()
    page.wait_for_timeout(5000)
    page.screenshot(path=str(SHOTS / f"{video}-after-submit.png"))
    # the only proof that counts: a fresh load
    _open_comments(page, video)
    thread = _thread(page, comment)
    seen = thread is not None and any(norm(r).startswith(key) for r in _reply_texts(page, thread))
    print("reply seen after reload:", seen)
    if not seen:
        page.screenshot(path=str(SHOTS / f"{video}-after-reload.png"))
    return 0 if seen else 2


if __name__ == "__main__":
    sys.exit(main())
