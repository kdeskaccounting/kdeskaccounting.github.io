#!/usr/bin/env python3
"""Link-preview (Open Graph) images in the site's brand: 1200x627 PNGs in static/images/og/.

    /usr/bin/python3 scripts/make_og_images.py            # all cards
    /usr/bin/python3 scripts/make_og_images.py asc842     # one card

A page uses a card through front matter (`images: ["/images/og/<slug>.png"]`); hugo.toml's
`params.images` is the fallback for every other page. Renders with headless Chrome, which must be
able to reach Google Fonts. After a card changes, LinkedIn keeps its old copy until the page URL is
run through https://www.linkedin.com/post-inspector/.

The figures on the cards are computed here, so they always add up: a 60-month lease at 5,000 a
month, 5.0% a year, payments at the end of each month.
"""
import html
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "static" / "images" / "og"
LOGO = (REPO / "static" / "images" / "brand" / "kdesk-logo-nav.svg").as_uri()
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1200, 627


def schedule(payment=5000.0, months=60, annual=0.05, rows=5):
    r = annual / 12
    bal = payment * (1 - (1 + r) ** -months) / r
    out = [("Open", "", "", bal)]
    for m in range(1, rows + 1):
        interest = round(bal * r, 2)
        bal = round(bal + interest - payment, 2)
        out.append((str(m), interest, payment, bal))
    return out


def money(x):
    return "" if x == "" else f"{x:,.2f}"


def lease_sheet():
    rows = "".join(
        f"<tr><td class=l>{m}</td><td>{money(i)}</td><td>{money(p)}</td><td>{money(b)}</td></tr>"
        for m, i, p, b in schedule())
    return ("<div class=cap><b>Lease schedule</b><span>60 months · IBR 5.0%</span></div>"
            "<table><tr><th class=l>Month</th><th>Interest</th><th>Payment</th><th>Liability</th></tr>"
            f"{rows}</table>")


def tieout_sheet():
    end = schedule(rows=1)[-1][3]
    return ("<div class=cap><b>Tie-out</b><span>month 1</span></div>"
            "<table class=two>"
            f"<tr><td class=l>Lease schedule, ending liability</td><td>{money(end)}</td></tr>"
            f"<tr><td class=l>General ledger, lease liability</td><td>{money(end)}</td></tr>"
            f"<tr class=tot><td class=l>Difference</td><td>{money(0.0)}</td></tr></table>")


CARDS = {
    "asc842": dict(
        eyebrow="ASC 842 · Excel workbook",
        title="Lease accounting without enterprise software",
        sub="Up to 20 leases. Escalating rent, free rent, journal entries and a rollforward.",
        foot="$249 one-time · no subscription",
        sheet=lease_sheet),
    "default": dict(
        eyebrow="Excel templates · technical accounting",
        title="Excel templates that tie to the GL",
        sub="Leases, commissions, fixed assets, SaaS metrics and month-end close.",
        foot="One-time purchase · no macros",
        sheet=tieout_sheet),
}

CSS = """
*{box-sizing:border-box} html,body{margin:0;width:1200px;height:627px;overflow:hidden}
body{background:#F3F5F1;color:#0F1E33;font-family:"IBM Plex Sans",system-ui,sans-serif;position:relative;
  -webkit-font-smoothing:antialiased}
.band{position:absolute;left:0;top:0;width:100%;height:12px;background:#0E1B2E}
.logo{position:absolute;left:64px;top:60px;height:58px}
.left{position:absolute;left:64px;top:176px;width:570px}
.eyebrow{font:500 17px/1 "IBM Plex Mono",monospace;letter-spacing:.11em;text-transform:uppercase;color:#1F4E8C}
h1{font:400 61px/1.05 "Newsreader",Georgia,serif;letter-spacing:-.012em;margin:20px 0 0}
.sub{font:400 23px/1.42 "IBM Plex Sans",sans-serif;color:#4F5A67;margin-top:22px;max-width:540px}
.foot{position:absolute;left:64px;bottom:50px;font:500 19px/1 "IBM Plex Mono",monospace;color:#0F1E33}
.url{position:absolute;right:56px;bottom:50px;font:400 19px/1 "IBM Plex Mono",monospace;color:#4F5A67}
.sheet{position:absolute;right:56px;top:128px;width:452px;background:#fff;border:1px solid #B4C5AF;
  padding:24px 26px 20px}
.cap{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:14px;border-bottom:2px solid #0F1E33}
.cap b{font:500 25px/1 "Newsreader",Georgia,serif}
.cap span{font:400 14px/1 "IBM Plex Mono",monospace;color:#4F5A67}
table{border-collapse:collapse;width:100%;font:400 17px/1 "IBM Plex Mono",monospace}
th{font:500 12.5px/1 "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:#4F5A67;
  text-align:right;padding:14px 0 10px}
td{text-align:right;padding:11px 0;border-top:1px solid #D3DDD0;white-space:nowrap}
.l{text-align:left}
table.two td{padding:17px 0;font-size:16.5px} table.two tr:first-child td{border-top:0}
table.two .l{font:400 16.5px/1.2 "IBM Plex Sans",sans-serif;color:#0F1E33}
tr.tot td{border-top:2px solid #0F1E33;font-weight:500}
"""

FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500"
         "&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=block")


def page(card):
    e = html.escape
    return (f'<!doctype html><html><head><meta charset="utf-8"><link href="{FONTS}" rel="stylesheet">'
            f"<style>{CSS}</style></head><body><div class=band></div>"
            f'<img class=logo src="{LOGO}" alt="">'
            f'<div class=left><div class=eyebrow>{e(card["eyebrow"])}</div><h1>{e(card["title"])}</h1>'
            f'<div class=sub>{e(card["sub"])}</div></div>'
            f'<div class=sheet>{card["sheet"]()}</div>'
            f'<div class=foot>{e(card["foot"])}</div><div class=url>kdeskaccounting.com</div></body></html>')


def render(slug):
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / f"{slug}.html"
        src.write_text(page(CARDS[slug]), encoding="utf-8")
        dest = OUT / f"{slug}.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--window-size={W},{H}",
                        "--virtual-time-budget=8000", f"--screenshot={dest}", src.as_uri()],
                       check=True, capture_output=True)
    print("wrote", dest.relative_to(REPO))


if __name__ == "__main__":
    for s in (sys.argv[1:] or list(CARDS)):
        render(s)
