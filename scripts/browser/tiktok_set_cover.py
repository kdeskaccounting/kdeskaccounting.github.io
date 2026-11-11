"""Set a posted TikTok's cover to one frame of the video, through TikTok Studio's edit page.

    uv run -q --with websockets python scripts/browser/tiktok_set_cover.py \
        --post 7706940290698923294 --seconds 2.2 --duration 32.2            # dry run: select, report, cancel
    ... --go                                                                # save the cover
    ... --shot /tmp/cover.png                                               # screenshot the editor after selecting

Why (ParkSheet, 2026-11-11): a v6 Short opens on a 180 ms zoom blur, and TikTok's default cover is
frame 0, so every new post showed a smear on the profile grid. Studio lets a cover be changed
"once a day and within the first 7 days of posting"; this picks a sharp frame a couple of seconds
in (or 0.8 s on a claim-strip build, where the strip is the title).

How: opens `tiktokstudio/upload/post/<id>` in a NEW tab of the debug Chrome (CDP 9222), clicks
"Edit cover", clicks the frame strip at seconds/duration of its width (the strip maps position to
time linearly), checks the editor's own mm:ss label against the request, then with --go saves the
cover and the post edit. It never brings a window to the front and closes only the tab it opened.

Exit codes: 0 done (or dry run ok) · 2 usage · 3 cover not editable (locked today, older than
7 days, or the page did not load) · 4 the editor's time label is not the requested second ·
5 saved but not confirmed.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import urllib.request

import websockets

BASE = "http://127.0.0.1:9222"
EDIT_URL = "https://www.tiktok.com/tiktokstudio/upload/post/{post}?from=creator_center"

JS_HAS_EDIT = """(()=>{const e=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.innerText||'').trim()==='Edit cover');
if(!e)return false;e.scrollIntoView({block:'center',inline:'center'});return true})()"""
JS_CLICK_EDIT = """(()=>{const e=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.innerText||'').trim()==='Edit cover');
if(!e)return false;e.click();return true})()"""
JS_STRIP = """(()=>{const c=document.querySelector('[class*=FramePicker__canvas]');if(!c)return null;
const r=c.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()"""
JS_LABEL = """(()=>{const l=[...document.querySelectorAll('*')].filter(e=>e.children.length===0&&/^\\d\\d:\\d\\d$/.test((e.innerText||'').trim()));
return l.length?l[0].innerText.trim():null})()"""
JS_MODAL_BUTTON = """(name)=>{const b=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()===name&&b.getBoundingClientRect().y<120);
if(b.length!==1)return 'found '+b.length;b[0].click();return 'ok'}"""
JS_MODAL_OPEN = "!!document.querySelector('[class*=FramePicker__canvas]')"
JS_PAGE_SAVE = """(()=>{const b=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()==='Save');
if(b.length!==1)return 'found '+b.length;if(b[0].disabled)return 'disabled';b[0].scrollIntoView({block:'center'});b[0].click();return 'ok'})()"""


class Tab:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        ident = self.n
        await self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == ident:
                return msg.get("result", {})

    async def js(self, expression: str):
        res = await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True,
                                                   "awaitPromise": True})
        return res.get("result", {}).get("value")

    async def click(self, x: float, y: float) -> None:
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            params = {"type": kind, "x": x, "y": y}
            if kind != "mouseMoved":
                params.update(button="left", clickCount=1)
            await self.call("Input.dispatchMouseEvent", params)

    async def wait(self, expression: str, seconds: float, want=True) -> bool:
        for _ in range(int(seconds * 2)):
            if (await self.js(expression)) == want:
                return True
            await asyncio.sleep(0.5)
        return False


def label_seconds(label: str | None) -> int | None:
    if not label:
        return None
    minutes, _, secs = label.partition(":")
    return int(minutes) * 60 + int(secs)


async def run(args) -> int:
    frac = min(max(args.seconds / args.duration, 0.0), 0.98)
    req = urllib.request.Request(f"{BASE}/json/new?{EDIT_URL.format(post=args.post)}", method="PUT")
    target = json.load(urllib.request.urlopen(req, timeout=15))
    try:
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=15) as ws:
            tab = Tab(ws)
            if not await tab.wait(JS_HAS_EDIT, 30):
                print("not editable: no 'Edit cover' on the edit page (not loaded, or the post is too old)")
                return 3
            await asyncio.sleep(1.0)
            await tab.js(JS_CLICK_EDIT)
            if not await tab.wait(JS_MODAL_OPEN, 12):
                print("not editable: the cover editor did not open (covers can be edited once a day, "
                      "within 7 days of posting)")
                return 3
            await asyncio.sleep(1.5)
            strip = await tab.js(JS_STRIP)
            y = strip["y"] + strip["h"] / 2
            # The first click only wakes the picker (the selector appears at 0:00), and a click
            # inside the selector box is ignored. So: wake it, park it at the far end, then pick.
            far = strip["x"] + strip["w"] * (0.97 if frac < 0.5 else 0.03)
            label = got = None
            for _attempt in range(2):
                await tab.click(far, y)
                await asyncio.sleep(1.0)
                await tab.click(far, y)
                await asyncio.sleep(1.0)
                await tab.click(strip["x"] + strip["w"] * frac, y)
                await asyncio.sleep(2.0)
                label = await tab.js(JS_LABEL)
                got = label_seconds(label)
                if got is not None and abs(got - args.seconds) <= 1.5:
                    break
            print(f"selected {label} for a request of {args.seconds:.1f} s of {args.duration:.1f} s")
            if args.shot:
                shot = await tab.call("Page.captureScreenshot", {"format": "png"})
                with open(args.shot, "wb") as handle:
                    handle.write(base64.b64decode(shot["data"]))
                print("screenshot:", args.shot)
            if got is None or abs(got - args.seconds) > 1.5:
                await tab.js(f"({JS_MODAL_BUTTON})('Cancel')")
                print("the editor's time is not the requested second; nothing saved")
                return 4
            if not args.go:
                await tab.js(f"({JS_MODAL_BUTTON})('Cancel')")
                print("dry run: nothing saved (pass --go to save)")
                return 0
            said = await tab.js(f"({JS_MODAL_BUTTON})('Save')")
            if said != "ok" or not await tab.wait(JS_MODAL_OPEN, 15, want=False):
                print(f"cover editor Save did not complete ({said}); nothing saved")
                return 5
            await asyncio.sleep(1.5)
            said = await tab.js(JS_PAGE_SAVE)
            if said != "ok":
                print(f"post Save: {said}; the cover was chosen but the post edit was not saved")
                return 5
            if not await tab.wait("location.pathname.startsWith('/tiktokstudio/content')", 25):
                print("post Save clicked, but Studio did not return to the posts list; check the post by hand")
                return 5
            print(f"cover saved: post {args.post} at {label}")
            return 0
    finally:
        try:
            urllib.request.urlopen(f"{BASE}/json/close/{target['id']}", timeout=10)
        except Exception as exc:   # the tab is ours either way; say so and move on
            print("could not close the tab this script opened:", type(exc).__name__)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--post", required=True, help="TikTok post id")
    parser.add_argument("--seconds", required=True, type=float, help="the frame to use, in seconds")
    parser.add_argument("--duration", required=True, type=float, help="the video's length in seconds (ffprobe)")
    parser.add_argument("--go", action="store_true", help="save; without it this is a dry run")
    parser.add_argument("--shot", help="write a PNG of the editor after selecting")
    args = parser.parse_args(argv)
    if not args.post.isdigit() or args.duration <= 0 or not 0 <= args.seconds < args.duration:
        parser.print_usage()
        return 2
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
