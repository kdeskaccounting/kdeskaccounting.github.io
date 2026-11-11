"""Read TikTok's search suggestions (the autofill dropdown) for each query, from the logged-in debug Chrome.

    uv run -q --with websockets python scripts/browser/tiktok_suggest.py "can you bring food into disney" "disney world rule"
    uv run -q --with websockets python scripts/browser/tiktok_suggest.py --file queries.txt      # one query a line

Prints one JSON object a line: {"q": ..., "sug": [...]} in TikTok's own order (or {"q": ..., "error": "captcha"}
and stops). Read-only: it opens ONE tab of its own (CDP 9222), reloads a light page before each query so the
box is empty, types the query, reads the dropdown, and closes its tab at the end. It never raises a window.
Why (ParkSheet, 2026-11-11): Search is the only TikTok source that has compounded for the channel, and topic
scoring only looked at Google and YouTube suggest. Keep runs modest (tens of queries, ~9 s each).
"""
import argparse, asyncio, json, sys, urllib.request
import websockets

BASE = "http://127.0.0.1:9222"
START = "https://www.tiktok.com/explore"

async def run(queries):
    tab = json.load(urllib.request.urlopen(urllib.request.Request(f"{BASE}/json/new?{START}", method="PUT"), timeout=15))
    try:
        async with websockets.connect(tab["webSocketDebuggerUrl"], max_size=None, open_timeout=15) as ws:
            n = 0
            async def call(method, params=None):
                nonlocal n; n += 1; ident = n
                await ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == ident: return msg.get("result", {})
            async def js(expr):
                return (await call("Runtime.evaluate", {"expression": expr, "returnByValue": True})).get("result", {}).get("value")
            for q in queries:
                await call("Page.navigate", {"url": START})
                await asyncio.sleep(5)
                if await js("!!document.querySelector('[class*=captcha],[id*=captcha]')"):
                    print(json.dumps({"q": q, "error": "captcha"}), flush=True); return 3
                await js("(()=>{const b=document.querySelector('button[data-e2e=nav-search]');if(b)b.click();return !!b})()")
                await asyncio.sleep(1.5)
                if not await js("(()=>{const i=document.querySelector('input[data-e2e=search-user-input]');if(i)i.focus();return !!i})()"):
                    print(json.dumps({"q": q, "error": "no search box"}), flush=True); continue
                await call("Input.insertText", {"text": q})
                await asyncio.sleep(3)
                sug = await js("JSON.stringify([...document.querySelectorAll('h4[class*=H4ItemTitle]')].map(e=>e.innerText.trim()).filter((v,i,a)=>a.indexOf(v)===i).slice(0,10))")
                print(json.dumps({"q": q, "sug": json.loads(sug or "[]")}), flush=True)
            return 0
    finally:
        try: urllib.request.urlopen(f"{BASE}/json/close/{tab['id']}", timeout=10)
        except Exception: pass

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("queries", nargs="*"); p.add_argument("--file")
    a = p.parse_args()
    qs = list(a.queries)
    if a.file: qs += [l.strip() for l in open(a.file) if l.strip()]
    if not qs: p.print_usage(); return 2
    return asyncio.run(run(qs))

if __name__ == "__main__":
    sys.exit(main())
