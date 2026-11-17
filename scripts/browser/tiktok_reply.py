"""Reply to a comment in TikTok Studio (web) with TRUSTED input, and prove it on a fresh load.

  uv run -q --with websockets python scripts/browser/tiktok_reply.py "<piece of the comment>" "<reply>" \
      [--parent "<piece of the top-level comment, when replying to a reply>"] [--go | --verify]

Without --go it is a dry run: it finds the comment and refuses if our reply is already on the page.
Each phase opens its own new tab in the debug Chrome (port 9222) and closes only that tab; Chrome is never
brought to the front.

Why trusted input: on 2026-11-16 a reply sent with JS click() on Studio's send button showed "View 1 reply" on
the open page but was gone on reload (ParkSheet memory tiktok-web-replies-dont-persist). Clicks here are CDP
Input.dispatchMouseEvent and the text is Input.insertText; that reply landed and survived a fresh load.

  1. check:  fresh load; with --parent, expand that thread's replies first; find the comment; stop if our reply
             text is already on the page (never reply twice).
  2. send:   (--go) trusted click on the comment's Reply, insertText, trusted click on the send button.
  3. verify: (--go, or --verify alone) a NEW tab, fresh load, expand the thread, and look for our text. Only
             this phase's VERIFIED line counts as sent.

Exit codes: 0 dry run OK / VERIFIED · 2 sent but not found on a fresh load · 6 comment not found ·
7 already replied (nothing sent) · 8 no reply box or send button.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import urllib.request

import websockets

STUDIO = "https://www.tiktok.com/tiktokstudio/comment"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


class Tab:
    def __init__(self, url: str):
        req = urllib.request.Request("http://localhost:9222/json/new?" + url, method="PUT")
        self.tab = json.load(urllib.request.urlopen(req))
        self.n = 0

    async def __aenter__(self):
        self.ws = await websockets.connect(self.tab["webSocketDebuggerUrl"], max_size=50_000_000)
        return self

    async def __aexit__(self, *exc):
        await self.ws.close()
        urllib.request.urlopen(f"http://localhost:9222/json/close/{self.tab['id']}")

    async def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        i = self.n
        await self.ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == i:
                return m.get("result", {})

    async def js(self, expr: str):
        r = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    async def tclick(self, el_expr: str):
        """Trusted click at the centre of the element `el_expr` evaluates to, scrolled into view first."""
        r = await self.js("(()=>{const e=%s;if(!e)return null;e.scrollIntoView({block:'center'});"
                          "const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width}})()"
                          % el_expr)
        if not r or not r["w"]:
            return None
        await asyncio.sleep(0.4)
        await self.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"]})
        for t in ("mousePressed", "mouseReleased"):
            await self.call("Input.dispatchMouseEvent",
                            {"type": t, "x": r["x"], "y": r["y"], "button": "left", "clickCount": 1})
        return r


# The smallest ancestor of a leaf containing `t` that holds exactly one leaf reading 'Reply'; stored as window[name].
# Every leaf carrying the text is tried, because a comment can appear twice on the page (2026-11-17: a second copy
# outside the comment list, with no Reply of its own, came first and the old .find() stopped there).
BOX = """((t,name)=>{t=t.toLowerCase();const leaves=[...document.querySelectorAll('*')].filter(e=>e.children.length===0&&(e.innerText||'').trim().toLowerCase().includes(t));
for(const leaf of leaves){let box=leaf;for(let k=0;k<10;k++){box=box.parentElement;if(!box)break;
const r=[...box.querySelectorAll('*')].filter(e=>e.children.length===0&&(e.innerText||'').trim()==='Reply');
if(r.length===1){window[name]=box;window[name+'Reply']=r[0];return box.innerText.slice(0,500)}if(r.length>1)break}}return null})"""
INPUT = ("[...document.querySelectorAll('textarea,[contenteditable=true],input[type=text]')].find(e=>window.__box.contains(e))"
         "||[...document.querySelectorAll('textarea,[contenteditable=true],input[type=text]')]"
         ".find(e=>(e.getAttribute('placeholder')||e.getAttribute('aria-label')||'')==='Reply to comment')")


async def locate(t: Tab, comment: str, parent: str | None) -> str | None:
    """Fresh page: expand the parent's thread if given, then find the comment's box. Returns its text."""
    await asyncio.sleep(12)
    if parent:
        for _ in range(5):
            if await t.js(f"{BOX}({json.dumps(parent)},'__parent')"):
                break
            await asyncio.sleep(3)
        view = ("[...window.__parent.querySelectorAll('*')].find(e=>e.children.length===0&&"
                "/^view \\d+ repl/i.test((e.innerText||'').trim()))")
        print("expand parent thread:", bool(await t.tclick(view)))
        await asyncio.sleep(3)
    for _ in range(8):
        found = await t.js(f"{BOX}({json.dumps(comment)},'__box')")
        if found:
            return found
        await asyncio.sleep(3)
    return None


async def already(t: Tab, reply: str) -> bool:
    return norm(reply)[:40] in norm(await t.js("document.body.innerText") or "")


async def check(comment, reply, parent) -> int:
    async with Tab(STUDIO) as t:
        box = await locate(t, comment, parent)
        print("check:", json.dumps(box)[:400])
        if not box:
            return 6
        if not parent:   # a collapsed thread hides our reply: open it before deciding
            view = ("[...window.__box.querySelectorAll('*')].find(e=>e.children.length===0&&"
                    "/^view \\d+ repl/i.test((e.innerText||'').trim()))")
            if await t.tclick(view):
                print("check: expanded the thread")
                await asyncio.sleep(4)
        if await already(t, reply):
            print("our reply is already on the page: not sending")
            return 7
        return 0


async def send(comment, reply, parent) -> int:
    async with Tab(STUDIO) as t:
        if not await locate(t, comment, parent):
            print("send: comment not found")
            return 6
        print("send: reply click", await t.tclick("window.__boxReply"))
        await asyncio.sleep(2)
        if not await t.tclick(INPUT):
            print("send: no reply input")
            return 8
        await t.call("Input.insertText", {"text": reply})
        await asyncio.sleep(1)
        print("send: typed", repr(await t.js(f"(()=>{{const e={INPUT};return e?(e.innerText||e.value||''):null}})()")))
        tag = await t.js("(()=>{let p=%s;for(let k=0;k<4;k++)p=p.parentElement;const b=[...p.querySelectorAll('button.TUXButton')][0];"
                         "window.__send=b;return b?b.outerHTML.split('>')[0]:null})()" % INPUT)
        if not tag or 'aria-disabled="true"' in tag or " disabled" in tag.replace("aria-disabled", ""):
            print("send: send button missing or disabled:", tag)
            return 8
        print("send: send click", await t.tclick("window.__send"))
        await asyncio.sleep(5)
        return 0


async def verify(comment, reply, parent) -> int:
    async with Tab(STUDIO) as t:
        if not await locate(t, comment, parent):
            print("verify: comment not found")
            return 6
        if not parent:
            view = ("[...window.__box.querySelectorAll('*')].find(e=>e.children.length===0&&"
                    "/^view \\d+ repl/i.test((e.innerText||'').trim()))")
            print("verify: expand", bool(await t.tclick(view)))
            await asyncio.sleep(4)
        ok = await already(t, reply)
        print("VERIFIED" if ok else "NOT FOUND after a fresh load")
        return 0 if ok else 2


async def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    parent = None
    if "--parent" in argv:
        parent = argv[argv.index("--parent") + 1]
        args.remove(parent)
    comment, reply = args[0], args[1]
    if "--verify" in argv:
        return await verify(comment, reply, parent)
    rc = await check(comment, reply, parent)
    if rc or "--go" not in argv:
        print("dry run" if rc == 0 else "stopped")
        return rc
    rc = await send(comment, reply, parent)
    if rc:
        return rc
    await asyncio.sleep(5)
    return await verify(comment, reply, parent)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
