# Mobile dark-mode contrast audit — 2026-05-12

**Trigger:** Stephen flagged the calculator page on iOS Safari (dark mode) where the body copy "Instant estimates for commission capitalization (ASC 606) and lease accounting (ASC 842)..." is barely legible — dark navy text on a washed-out translucent gradient.

**Root cause:** The site has a proper dark-mode token override in `assets/css/extended/custom.css` starting at line 956 (`[data-theme="dark"]` block — `--kd-navy` becomes `#e2e8f0` light, `--kd-text` becomes `#d4d8dd`, etc.). The calculator layout at `layouts/calculator/single.html` was built with **hardcoded hex + RGBA values** that bypass these tokens entirely.

## Offenders

### `layouts/calculator/single.html` (the primary issue)

| Line | Problem | Fix |
|---|---|---|
| 14-15 | `radial-gradient` + `linear-gradient` use hardcoded RGBA from light palette: `rgba(46,117,182,0.10)`, `rgba(214,228,240,0.55)`, `rgba(255,242,204,0.32)` | Replace with `var(--kd-blue)` / `var(--kd-ltblue)` / `var(--kd-yellow)` |
| 16 | `border: 1px solid rgba(31,56,100,0.08)` (hardcoded navy outline) | Replace with `var(--kd-border)` |
| 18 | `box-shadow: 0 18px 40px rgba(31,56,100,0.08)` | Replace with `var(--kd-shadow)` |
| 23 | `.calc-hero h1 { color: #1F3864 }` — light-mode navy hardcoded | `color: var(--kd-navy)` |
| 27 | `.calc-hero p { color: #5a6a7e }` — light-mode muted hardcoded | `color: var(--kd-muted)` |
| 38 | `.calc-eyebrow { background: rgba(255,255,255,0.88) }` — bright white pill on dark bg | Use semi-transparent neutral OR `var(--kd-ltblue)` |
| 39 | `.calc-eyebrow { color: #1F3864 }` | `color: var(--kd-navy)` |
| 70, 72, 82 | `border-color: rgba(31,56,100,0.08)` + `box-shadow` repeats | Replace with `var(--kd-border)` / `var(--kd-shadow)` |
| 153 | `.calc-panel { background: linear-gradient(180deg, rgba(214,228,240,0.38), rgba(255,255,255,1)) }` — opaque white bottom of gradient = blinding in dark mode | Replace stops with `var(--kd-ltblue)` / `var(--kd-bg-light)` |
| 201 | `.calc-cta { background: linear-gradient(135deg, rgba(214,228,240,0.42), rgba(255,242,204,0.30)) }` | Replace with token-based gradient |
| 220, 221 | `.calc-cta a:hover { background: #172b4c }` and `.note { color: #5a6a7e }` | `var(--kd-blue-dk)` and `var(--kd-muted)` |

**Approach:** wholesale find-replace of hex/RGBA → CSS variable references across the entire `<style>` block in the calculator layout. The site already has the token system; the calculator just doesn't use it.

## Non-issues (verified intentional)

- `layouts/templates/single.html:156` — inline `color: #fff !important` inside `.kd-bottom-cta` (the dark navy CTA strip at the bottom of template pages). Always-dark section by design; white text correct in both modes.
- `assets/css/extended/custom.css` lines 191 (`color: #fff` inside `.kd-trust`), 368 (`.kd-bottom-cta h2 { color: #fff }`) — same pattern. These are deliberately-dark sections.
- Posts and homepage use `var(--kd-*)` correctly. PaperMod theme handles its own dark mode.

## Fix priority

P1 — affects every visitor who uses dark mode on mobile (probably 40-60% of Safari iOS users default to dark). Calculator is the strongest free lead magnet, so first impressions matter.

Estimated fix: 20 minutes of targeted edits to the calculator's `<style>` block. Test in both modes via the theme toggle in the header.
