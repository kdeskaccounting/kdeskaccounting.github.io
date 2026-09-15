#!/usr/bin/env python3
"""HTML cards for the `card` scene kind: a caller's data block straight into a 9:16 frame.

Three templates, all fed by one `data:` block with exactly four keys — `heading`,
`subheading`, `items`, `footer`:

  ranked_list  items: [{rank: int ascending, label: str, value: int|float|""}]   0-8 rows
  countdown    items: [{rank: int descending, label: str, value: int}]           0-8 rows, list order
  changed      items: [{label: str, value: str}]                                 0-5 rows; no rank, and
                                                                                 value is a 60-120
                                                                                 character sentence
                                                                                 that wraps

The row caps are readability limits, not storage limits: rows shrink as they multiply, and past
8 ranked rows (or 5 sentence rows) the type is too small to read on a phone, so `card_html`
raises rather than render something unusable. `changed` note text never falls below 30px on the
1296x2304 canvas.

`ranked_list` renders a rank + label row with no value column when `value` is `""`, and an
empty `items` list renders the heading, subheading and footer over a tasteful empty body
rather than raising — the caller emits an empty list when its source has nothing to report
and a Short still has to render.

Colours come from the spec's optional `brand:` block (`{name, url, accent}` is the usual
three-key form); the defaults are brand-neutral and dark, so the same renderer serves a
second venture without carrying KDesk's palette. Every string from `data`/`brand` is
HTML-escaped, and every brand colour is checked against a hex literal before it lands in the
<style> block, because a brand token is the one value that is interpolated unescaped.

Pure string building — no I/O, stdlib only — so the golden tests run in the plain
`uv run --with pytest` environment.
"""
from __future__ import annotations

import html as _html
import re

TEMPLATES = ("ranked_list", "countdown", "changed")

#: A 9:16 card stays legible down to about this many rank rows; past it the caller must split.
MAX_ITEMS = 8

#: `changed` rows carry a whole sentence each, so they run out of room far sooner.
MAX_CHANGED_ITEMS = 5

#: Floor on a `changed` row's font size, in canvas units (height/100). The note is .9em of it,
#: so 1.45 units keeps note text at 30px or more on the 1296x2304 card.
MIN_CHANGED_ROW_UNITS = 1.45

DEFAULT_BRAND: dict = {
    "name": "Your Brand",
    "url": "example.com",
    "bg": "#101418",
    "bg_alt": "#1B2430",
    "fg": "#FFFFFF",
    "muted": "#AAB6C4",
    "accent": "#F2C14E",
    "accent_fg": "#101418",
    "font": "Carlito, Arial, Helvetica, sans-serif",
}

_COLOUR_TOKENS = ("bg", "bg_alt", "fg", "muted", "accent", "accent_fg")
_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_FONT_STACK = re.compile(r"^[A-Za-z0-9 ,'\-]+$")


# --- brand ----------------------------------------------------------------------------

def _checked_token(key: str, value: object) -> str:
    """Brand tokens are interpolated into CSS unescaped, so validate them as literals."""
    text = str(value)
    if key in _COLOUR_TOKENS and not _HEX.match(text):
        raise ValueError(f"brand token {key!r} must be a hex colour like '#1F3864', got {text!r}")
    if key == "font" and not _FONT_STACK.match(text):
        raise ValueError(f"brand token 'font' must be a plain font stack "
                         f"(letters, digits, spaces, commas, hyphens), got {text!r}")
    return text


def brand_tokens(spec_brand: dict | None) -> dict:
    """`DEFAULT_BRAND` overlaid with the spec's `brand:` block. Unknown keys are an error."""
    tokens = dict(DEFAULT_BRAND)
    for key, value in (spec_brand or {}).items():
        if key not in DEFAULT_BRAND:
            raise KeyError(f"unknown brand token {key!r}; "
                           f"known: {', '.join(sorted(DEFAULT_BRAND))}")
        tokens[key] = _checked_token(key, value)
    return tokens


def is_card(scene: dict) -> bool:
    return scene.get("kind") == "card"


# --- values ---------------------------------------------------------------------------

def _e(value: object) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def _value_text(value: object) -> str:
    """`5` -> '5', `9.4` -> '9.4', `8.0` -> '8', `""`/None -> '' (no value column)."""
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


def _rank_text(template: str, item: dict, index: int, count: int) -> str:
    """The caller supplies the rank; countdown reads `#3 … #1`, ranked_list `1 … N`.

    The fallback follows the template's direction, so a countdown that omits `rank` still
    counts down instead of silently counting up.
    """
    default = count - index if template == "countdown" else index + 1
    rank = item.get("rank", default)
    return f"#{rank}" if template == "countdown" else str(rank)


# --- rows -----------------------------------------------------------------------------

def _rows_ranked(template: str, items: list[dict]) -> str:
    out = []
    for i, item in enumerate(items):
        value = _value_text(item.get("value"))
        cells = (f'<div class="rank">{_e(_rank_text(template, item, i, len(items)))}</div>'
                 f'<div class="label">{_e(item.get("label"))}</div>')
        if value:
            out.append(f'<li class="row">{cells}<div class="value">{_e(value)}</div></li>')
        else:
            out.append(f'<li class="row novalue">{cells}</li>')
    return "\n      ".join(out)


def _rows_changed(items: list[dict]) -> str:
    out = []
    for item in items:
        out.append(f'<li class="row changed"><div class="label">{_e(item.get("label"))}</div>'
                   f'<div class="note">{_e(item.get("value"))}</div></li>')
    return "\n      ".join(out)


# --- layout ---------------------------------------------------------------------------

def _heading_size(heading: str, unit: float) -> float:
    """Step the headline down so a long heading wraps instead of overrunning the card."""
    if len(heading) <= 34:
        return 4.4 * unit
    if len(heading) <= 52:
        return 3.8 * unit
    return 3.3 * unit


def _row_size(template: str, count: int, unit: float) -> float:
    """Rows shrink as they multiply, so 3 rows and 8 rows both fit the same canvas."""
    n = max(count, 1)
    if template == "changed":
        return max(min(2.45, 8.4 / n), MIN_CHANGED_ROW_UNITS) * unit
    return min(3.3, 18.0 / n) * unit


def card_html(template: str, data: dict, brand: dict, width: int = 1296,
              height: int = 2304) -> str:
    if template not in TEMPLATES:
        raise ValueError(f"unknown card template {template!r}; known: {', '.join(TEMPLATES)}")
    items = data.get("items") or []
    if not isinstance(items, list):
        raise TypeError(f"card data.items must be a list, got {type(items).__name__}")
    cap = MAX_CHANGED_ITEMS if template == "changed" else MAX_ITEMS
    if len(items) > cap:
        raise ValueError(f"card template {template!r} holds at most {cap} items, "
                         f"got {len(items)}; split it across two cards")

    heading = str(data.get("heading") or "")
    subheading = str(data.get("subheading") or "")
    unit = height / 100.0
    h1_fs = _heading_size(heading, unit)
    row_fs = _row_size(template, len(items), unit)
    gap = 0.45 * row_fs

    if not items:
        body = '<div class="empty">Nothing to show right now</div>'
    elif template == "changed":
        body = f'<ul class="rows">\n      {_rows_changed(items)}\n    </ul>'
    else:
        body = f'<ul class="rows">\n      {_rows_ranked(template, items)}\n    </ul>'
    sub = f'<p class="sub">{_e(subheading)}</p>' if subheading else ""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden;
  background:radial-gradient(120% 60% at 18% 6%, {brand['bg_alt']} 0%, {brand['bg']} 58%, {brand['bg']} 100%);
  color:{brand['fg']};font-family:{brand['font']};-webkit-font-smoothing:antialiased}}
.card{{width:{width}px;height:{height}px;display:flex;flex-direction:column;
  padding:{4.6 * unit:.0f}px {4.5 * unit:.0f}px}}
.brand{{display:flex;align-items:baseline;justify-content:space-between;gap:{2 * unit:.0f}px;
  font-size:{1.55 * unit:.1f}px;letter-spacing:.07em;text-transform:uppercase;
  margin-bottom:{2.2 * unit:.0f}px}}
.bname{{font-weight:700;color:{brand['fg']}}} .burl{{color:{brand['muted']}}}
h1{{font-size:{h1_fs:.1f}px;line-height:1.06;font-weight:700;letter-spacing:-.01em;
  margin-bottom:{1.0 * unit:.0f}px;display:-webkit-box;-webkit-line-clamp:3;
  -webkit-box-orient:vertical;overflow:hidden}}
.sub{{font-size:{2.05 * unit:.1f}px;line-height:1.25;color:{brand['muted']};
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.rule{{width:{8 * unit:.0f}px;height:{0.45 * unit:.1f}px;border-radius:999px;
  background:{brand['accent']};margin:{2.2 * unit:.0f}px 0}}
.body{{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;
  overflow:hidden}}
.rows{{list-style:none;display:flex;flex-direction:column;gap:{gap:.0f}px}}
.row{{display:flex;align-items:center;gap:{1.1 * gap:.0f}px;font-size:{row_fs:.1f}px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10);
  border-radius:{0.5 * row_fs:.0f}px;padding:{0.55 * row_fs:.0f}px {0.8 * row_fs:.0f}px}}
.rank{{min-width:2.1em;font-size:1em;font-weight:700;color:{brand['accent']};
  font-variant-numeric:tabular-nums}}
.label{{flex:1;font-size:.84em;line-height:1.15;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}}
.value{{font-size:1em;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}}
.row.changed{{flex-direction:column;align-items:stretch;gap:{0.35 * row_fs:.0f}px;
  padding:{0.7 * row_fs:.0f}px {0.8 * row_fs:.0f}px}}
.row.changed .label{{flex:none;font-size:1em;font-weight:700;color:{brand['accent']};
  -webkit-line-clamp:1}}
.note{{font-size:.9em;line-height:1.32;color:{brand['muted']};white-space:normal}}
.empty{{border:{0.25 * unit:.0f}px dashed rgba(255,255,255,.22);border-radius:{1.6 * unit:.0f}px;
  padding:{5 * unit:.0f}px {3 * unit:.0f}px;text-align:center;font-size:{2.4 * unit:.1f}px;
  color:{brand['muted']}}}
.foot{{padding-top:{1.8 * unit:.0f}px;font-size:{1.7 * unit:.1f}px;font-weight:700;
  color:{brand['accent']}}}
</style></head><body>
<div class="card">
  <div class="brand"><span class="bname">{_e(brand['name'])}</span><span class="burl">{_e(brand['url'])}</span></div>
  <h1>{_e(heading)}</h1>
  {sub}
  <div class="rule"></div>
  <div class="body">
    {body}
  </div>
  <div class="foot">{_e(data.get('footer'))}</div>
</div>
</body></html>"""
