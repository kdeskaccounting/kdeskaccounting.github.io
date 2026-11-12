"""Read a TikTok post's early retention (the share of viewers still watching at 1, 2 and 3 seconds) from TikTok
Studio's per-post retention chart.

    uv run -q --with websockets python scripts/browser/tiktok_hold.py --post 7703636637946891550
    -> {"post": "...", "hold": {"1": 85.0, "2": 69.0, "3": 59.0}, "stopped_at": "0:02"}

Why (ParkSheet, 2026-11-11): Stephen set every test to aim at the hook first: YouTube's stayed-to-watch, and on TikTok
"the TikTok equivalent". Studio has no single number for it, but its "Retention rate" chart shows, on hover, the
share still watching at each whole second ("0:03 / 59%"). The 3-second hold is the TikTok hook metric.

How: opens `tiktokstudio/analytics/<id>` in a NEW tab of the debug Chrome (CDP 9222), scrolls the chart into view,
moves the mouse across its canvas (mouseMoved only, no clicks) and reads the tooltip's "m:ss" and "NN%" pairs. It
never brings a window to the front and closes only the tab it opened. Read-only.

Exit codes: 0 read · 2 usage · 3 the page or the chart did not load · 4 the chart showed no 1-3 s points.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.request

import websockets

BASE = "http://127.0.0.1:9222"
URL = "https://www.tiktok.com/tiktokstudio/analytics/{post}"

JS_SCROLL = """(()=>{const t=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.innerText||'').trim()==='Retention rate');
if(!t)return false;t.scrollIntoView({block:'start'});return true})()"""
# The retention chart is the small canvas below the video preview (the larger one above is the views trend).
JS_CHART = """(()=>{const c=[...document.querySelectorAll('canvas')].map(e=>e.getBoundingClientRect())
.filter(b=>b.width>200&&b.height<120&&b.y>0);if(!c.length)return null;const b=c[0];return {x:b.x,y:b.y,w:b.width,h:b.height}})()"""
JS_STOPPED = """(()=>{const m=(document.body.innerText||'').match(/stopped watching at (\\d+:\\d\\d)/);return m?m[1]:null})()"""
# Every leaf "m:ss" and "NN%" with its position; the tooltip pair is the one near the cursor.
JS_LABELS = """(()=>{const out=[];for(const e of document.querySelectorAll('*')){if(e.children.length)continue;
const t=(e.innerText||'').trim();if(/^\\d+:\\d\\d$/.test(t)||/^[<\\d.]+%$/.test(t)){const b=e.getBoundingClientRect();
out.push([t,b.x,b.y])}}return out})()"""


def pair_near(labels: list, x: float, y: float) -> tuple[int, float] | None:
    """The (second, percent) of the tooltip: the time label nearest the cursor, and the percent just below it."""
    times = [(t, lx, ly) for t, lx, ly in labels if ":" in t and abs(ly - y) < 80 and abs(lx - x) < 80]
    if not times:
        return None
    t, lx, ly = min(times, key=lambda r: abs(r[1] - x) + abs(r[2] - y))
    pcts = [(p, px, py) for p, px, py in labels if p.endswith("%") and 0 < py - ly < 40 and abs(px - lx) < 40]
    if not pcts:
        return None
    minutes, secs = t.split(":")
    value = pcts[0][0].rstrip("%").lstrip("<")
    try:
        return int(minutes) * 60 + int(secs), float(value)
    except ValueError:
        return None


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
        res = await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return res.get("result", {}).get("value")


async def run(post: str, seconds: tuple[int, ...]) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}/json/new?{URL.format(post=post)}", method="PUT")
    target = json.load(urllib.request.urlopen(req, timeout=15))
    try:
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=15) as ws:
            tab = Tab(ws)
            for _ in range(30):
                if await tab.js(JS_SCROLL):
                    break
                await asyncio.sleep(0.5)
            else:
                return 3, {"post": post, "error": "no 'Retention rate' section"}
            await asyncio.sleep(1.5)
            chart = await tab.js(JS_CHART)
            if not chart:
                return 3, {"post": post, "error": "no retention chart"}
            y = chart["y"] + chart["h"] * 0.4
            hold: dict[int, float] = {}
            # Sweep the first third of the chart in small steps: early seconds sit close together.
            steps = 60
            for i in range(steps + 1):
                x = chart["x"] + 1 + chart["w"] * 0.35 * i / steps
                await tab.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
                await asyncio.sleep(0.12)
                found = pair_near(await tab.js(JS_LABELS) or [], x, y)
                if found and found[0] in seconds and found[0] not in hold:
                    hold[found[0]] = found[1]
                if all(s in hold for s in seconds):
                    break
            stopped = await tab.js(JS_STOPPED)
            out = {"post": post, "hold": {str(k): hold[k] for k in sorted(hold)}, "stopped_at": stopped}
            return (0 if hold else 4), out
    finally:
        try:
            urllib.request.urlopen(f"{BASE}/json/close/{target['id']}", timeout=10)
        except Exception as exc:  # the tab is ours either way
            print("could not close the tab this script opened:", type(exc).__name__, file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--post", required=True, help="TikTok post id")
    ap.add_argument("--seconds", default="1,2,3", help="whole seconds to read (default 1,2,3)")
    args = ap.parse_args(argv)
    if not args.post.isdigit() or not re.fullmatch(r"\d+(,\d+)*", args.seconds):
        ap.print_usage()
        return 2
    code, out = asyncio.run(run(args.post, tuple(int(s) for s in args.seconds.split(","))))
    print(json.dumps(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
