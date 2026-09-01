#!/usr/bin/env python3
"""
Covers, thumbnails and video posters built from REAL rendered sheets.
  scripts/video/.venv-tts/bin/python scripts/video/make_covers.py --spec marketing/video/asc842/scenes.yaml
Outputs (static/images/products/): <slug>-cover.png 1280x720, <slug>-thumb.png 600x600,
<slug>-poster.png 1920x1080, <slug>-free-cover.png, <slug>-free-thumb.png.
Requires the spec's `cover:` block and a recalculated workbook at scripts/video/build/<slug>/recalc/src.xlsx
(run build_video.py --frames-only first, or this script recalcs the source itself).
"""
import argparse, pathlib, sys, html, yaml, openpyxl, subprocess, shutil
HERE = pathlib.Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); import render_sheets as R
from build_video import recalc
OUT = REPO / "static" / "images" / "products"
NAVY, BLUE = "#1F3864", "#2E75B6"

def cover_html(c, shots, free, w=1280, h=720, zoom=1.0):
    checks = "".join(f"<li>{html.escape(x)}</li>" for x in c.get("checks", []))
    ribbon = '<div class="ribbon">FREE</div>' if free else ""
    sub = html.escape(c.get("free_label", "Free version")) if free else "Excel template · one-time purchase"
    price = ('<div class="price">$0 <span>free download</span></div>' if free
             else f'<div class="price">{html.escape(c["price"])} <span>one-time · no subscription</span></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{R.BASE_CSS}
html,body{{width:{w}px;height:{h}px;zoom:{zoom}}}
body{{background:radial-gradient(900px 600px at 15% 0%,#2E75B6 0%,{NAVY} 45%,#0d1a33 100%);font-family:Carlito,Arial,sans-serif;color:#fff;position:relative}}
.brand{{position:absolute;left:56px;top:44px;font-size:22px;color:#dbe7f7}} .brand i{{background:#fff;width:20px;height:20px}}
.left{{position:absolute;left:56px;top:120px;width:520px}}
.badge{{display:inline-block;background:rgba(255,255,255,.14);border:1.5px solid rgba(255,255,255,.4);border-radius:999px;padding:6px 16px;font-size:19px;letter-spacing:1px;margin-bottom:18px}}
h1{{font-size:56px;line-height:1.02;margin:0 0 8px;letter-spacing:-.5px}}
.sub{{font-size:24px;color:#cfe0f5;margin:0 0 22px}}
ul{{margin:0 0 26px;padding:0;list-style:none;font-size:22px;line-height:1.5;color:#eef4fb}}
ul li::before{{content:'✓';color:#7ee08a;font-weight:700;margin-right:10px}}
.price{{font-size:40px;font-weight:700}} .price span{{font-size:18px;font-weight:400;color:#cfe0f5;margin-left:8px}}
.shot{{position:absolute;border-radius:10px;overflow:hidden;box-shadow:0 30px 70px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.15);background:#fff}}
.shot img{{display:block;width:100%}}
.s1{{left:610px;top:92px;width:760px;transform:perspective(1600px) rotateY(-9deg) rotateX(2deg);transform-origin:left center}}
.s2{{left:680px;top:36px;width:640px;opacity:.55;transform:perspective(1600px) rotateY(-9deg) rotateX(2deg) translateZ(-120px);transform-origin:left center;filter:blur(.3px)}}
.ribbon{{position:absolute;right:-70px;top:34px;width:300px;transform:rotate(35deg);background:#2e9d4a;color:#fff;text-align:center;font-weight:700;font-size:26px;letter-spacing:3px;padding:8px 0;box-shadow:0 6px 18px rgba(0,0,0,.4)}}
.foot{{position:absolute;left:56px;bottom:34px;font-size:18px;color:#a9bcd8}}
</style></head><body>
<div class="brand"><i></i>KDesk Accounting</div>
<div class="left"><div class="badge">{html.escape(c["standard"])}</div><h1>{html.escape(c["name"])}</h1><p class="sub">{sub}</p><ul>{checks}</ul>{price}</div>
<div class="shot s2"><img src="file://{shots[1]}"></div>
<div class="shot s1"><img src="file://{shots[0]}"></div>
{ribbon}
<div class="foot">Pure Excel · No macros · Windows &amp; Mac · kdeskaccounting.com</div>
</body></html>"""

def thumb_html(c, shot, free, size=600):
    ribbon = '<div class="ribbon">FREE</div>' if free else ""
    price = html.escape(c.get("free_label", "Free version")) if free else f'{html.escape(c["price"])} · one-time'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{R.BASE_CSS}
html,body{{width:{size}px;height:{size}px}}
body{{background:{NAVY};font-family:Carlito,Arial,sans-serif;color:#fff;position:relative;overflow:hidden}}
.shot{{position:absolute;left:0;top:0;width:{size}px;height:{int(size*0.6)}px;overflow:hidden;background:#fff}}
.shot img{{position:absolute;left:0px;top:-52px;width:{int(size*1.55)}px;box-shadow:0 10px 30px rgba(0,0,0,.4)}}
.shot::after{{content:'';position:absolute;left:0;right:0;bottom:0;height:90px;background:linear-gradient(to bottom,rgba(31,56,100,0),{NAVY})}}
.panel{{position:absolute;left:0;right:0;bottom:0;height:{int(size*0.44)}px;padding:22px 34px 0;background:linear-gradient(to bottom,{NAVY},#0f2242)}}
.std{{font-size:64px;font-weight:700;line-height:1;letter-spacing:-1px}}
.name{{font-size:30px;color:#dbe7f7;margin:8px 0 16px;line-height:1.15}}
.pill{{display:inline-block;background:#ffd966;color:{NAVY};font-weight:700;font-size:24px;padding:6px 18px;border-radius:999px}}
.brand{{position:absolute;right:26px;bottom:20px;font-size:18px;color:#a9bcd8}} .brand i{{width:16px;height:16px;background:#fff}}
.ribbon{{position:absolute;right:-70px;top:30px;width:260px;transform:rotate(35deg);background:#2e9d4a;color:#fff;text-align:center;font-weight:700;font-size:24px;letter-spacing:3px;padding:7px 0;box-shadow:0 6px 18px rgba(0,0,0,.4)}}
</style></head><body>
<div class="shot"><img src="file://{shot}"></div>
<div class="panel"><div class="std">{html.escape(c["standard"])}</div><div class="name">{html.escape(c["name"])}</div><div class="pill">{price}</div></div>
<div class="brand"><i></i>KDesk</div>{ribbon}
</body></html>"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); a = ap.parse_args()
    spec = yaml.safe_load(open(a.spec)); slug = spec["slug"]; c = spec["cover"]
    build = HERE / "build" / slug; shots_dir = build / "cover-shots"; shots_dir.mkdir(parents=True, exist_ok=True)
    rec = build / "recalc" / "src.xlsx"
    if not rec.exists():
        src = pathlib.Path(spec["source"]).expanduser(); staged = build / "src.xlsx"; build.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, staged)
        if spec.get("presets"):
            wb = openpyxl.load_workbook(staged)
            for sh, cells in spec["presets"].items():
                for addr, val in cells.items(): wb[sh][addr] = val
            wb.save(staged)
        rec = recalc(staged, build / "recalc")
    wbv = openpyxl.load_workbook(rec, data_only=True); wbf = openpyxl.load_workbook(rec)
    name = spec.get("workbook_name", "Workbook.xlsx")
    shots = []
    for key in ("hero", "second", "thumb"):
        sh = c[key]; png = shots_dir / f"{key}.png"
        R.render_sheet(wbv, wbf, sh["sheet"], sh["range"], png, tuple(sh.get("highlight", [])), float(sh.get("zoom", 1.0)),
                       "", name, show_caption=False)
        shots.append(png.resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    for free in (False, True):
        tag = "-free" if free else ""
        hp = shots_dir / f"cover{tag}.html"; hp.write_text(cover_html(c, shots, free)); R.screenshot(hp, OUT / f"{slug}{tag}-cover.png", 1280, 720)
        hp = shots_dir / f"thumb{tag}.html"; hp.write_text(thumb_html(c, shots[2], free)); R.screenshot(hp, OUT / f"{slug}{tag}-thumb.png", 600, 600)
        if not free:
            hp = shots_dir / "poster.html"; hp.write_text(cover_html(c, shots, False, 1280, 720, 1.5)); R.screenshot(hp, OUT / f"{slug}-poster.png", 1920, 1080)
    print("covers ->", sorted(p.name for p in OUT.glob(f"{slug}*")))

if __name__ == "__main__":
    main()
