"""Mute audio/video in every open tab of the debug Chrome (CDP 9222). Run: uv run -q --with websockets python scripts/browser/mute_tabs.py
Stephen 2026-11-02: mute the browser before any ParkSheet work. The launcher also passes --mute-audio on (re)launch."""
import json, urllib.request, asyncio, websockets
JS = """(()=>{const m=e=>{try{e.muted=true;e.volume=0}catch(_){}};document.querySelectorAll('video,audio').forEach(m);
if(!window.__psMute){window.__psMute=1;new MutationObserver(()=>document.querySelectorAll('video,audio').forEach(m)).observe(document.documentElement,{childList:true,subtree:true});
const p=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){m(this);return p.apply(this,arguments)};}return 'ok'})()"""
async def run():
    tabs=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list",timeout=10))
    for t in tabs:
        if t.get("type")!="page" or "webSocketDebuggerUrl" not in t: continue
        try:
            async with websockets.connect(t["webSocketDebuggerUrl"],max_size=None,open_timeout=10) as ws:
                await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":JS}}))
                await asyncio.wait_for(ws.recv(),10)
                print("muted",t["url"][:70])
        except Exception as e: print("skip",t["url"][:50],type(e).__name__)
asyncio.run(run())
