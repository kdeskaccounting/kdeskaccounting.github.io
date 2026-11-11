"""Dump TikTok Studio's Inspiration page for the logged-in account: US trending topics, and the Recommended lists.

    uv run -q --with websockets python scripts/browser/tiktok_inspiration.py --out /path/2026-11-15.json

Read-only. Opens ONE tab of its own in the debug Chrome (CDP 9222), reads
`tiktokstudio/inspiration` (Trending -> Topics, region United States) and
`tiktokstudio/inspiration/recommended` (Similar posts, Followers viewed, Similar creators), writes JSON,
closes its tab. It never raises a window.
Why (ParkSheet, 2026-11-11): the weekly scout gets TikTok's own trend list as an extra lane, and the
"similar posts" list shows what TikTok thinks the account is (on 2026-11-11: prank videos, not parks).
"""
import argparse, asyncio, datetime, json, sys, urllib.request
import websockets

BASE = "http://127.0.0.1:9222"
JS_PICK_US = """(async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const find=t=>[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.innerText||'').trim()===t);
let us=find('United States');if(!us){const a=find('All regions');if(a){a.click();await sleep(1200)}us=find('United States')}
if(!us)return 'All regions';us.scrollIntoView({block:'center'});us.click();await sleep(5000);return 'United States'})()"""
JS_TOPICS = """JSON.stringify([...document.querySelectorAll('[data-tt*=TrendingTopicList_FlexRow]')]
.filter(r=>!r.parentElement.closest('[data-tt*=TrendingTopicList_FlexRow]'))
.map(r=>r.innerText.split('\\n').map(s=>s.trim()).filter(Boolean).slice(0,4)).filter(a=>/^\\d+$/.test(a[0])))"""
JS_CLICK = "(t)=>{const e=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.innerText||'').trim()===t);if(!e)return false;e.click();return true}"
JS_LINES = """JSON.stringify(document.body.innerText.split('\\n').map(s=>s.trim()).filter(Boolean))"""

async def run(out_path):
    tab = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{BASE}/json/new?https://www.tiktok.com/tiktokstudio/inspiration", method="PUT"), timeout=15))
    try:
        async with websockets.connect(tab["webSocketDebuggerUrl"], max_size=None, open_timeout=15) as ws:
            n = 0
            async def js(expr):
                nonlocal n; n += 1; ident = n
                await ws.send(json.dumps({"id": ident, "method": "Runtime.evaluate",
                                          "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == ident: return msg.get("result", {}).get("result", {}).get("value")
            await asyncio.sleep(9)
            region = await js(JS_PICK_US)
            topics = [{"rank": int(a[0]), "topic": a[1], "views": a[2] if len(a) > 2 else "", "trend": a[3] if len(a) > 3 else ""}
                      for a in json.loads(await js(JS_TOPICS) or "[]")]
            await js("(location.href='https://www.tiktok.com/tiktokstudio/inspiration/recommended','')")
            await asyncio.sleep(8)
            recommended = {}
            for name in ("Similar posts", "Followers viewed", "Similar creators"):
                await js(f"({JS_CLICK})({json.dumps(name)})")
                await asyncio.sleep(5)
                lines = json.loads(await js(JS_LINES) or "[]")
                start = max((i for i, l in enumerate(lines) if l == "Similar creators"), default=-1) + 1
                body = [l for l in lines[start:] if len(l) > 12][:25]   # captions and names, not the view counts
                recommended[name.lower().replace(" ", "_")] = body
            doc = {"read_at": datetime.datetime.now().astimezone().isoformat(timespec="minutes"), "region": region,
                   "trending_topics": topics, "recommended": recommended}
            text = json.dumps(doc, indent=1, ensure_ascii=False)
            if out_path:
                with open(out_path, "w") as fh: fh.write(text + "\n")
                print(f"wrote {out_path}: {len(topics)} topics ({region}); recommended lists: "
                      + ", ".join(f"{k} {len(v)}" for k, v in recommended.items()))
            else:
                print(text)
            return 0 if topics else 3
    finally:
        try: urllib.request.urlopen(f"{BASE}/json/close/{tab['id']}", timeout=10)
        except Exception: pass

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", help="write the JSON here (default: print it)")
    return asyncio.run(run(p.parse_args().out))

if __name__ == "__main__":
    sys.exit(main())
