#!/usr/bin/env python3
"""
Driver: scene spec (YAML) -> preset workbook -> LibreOffice recalc -> PNG frames -> Kokoro narration -> mp4.

  scripts/video/.venv-tts/bin/python scripts/video/build_video.py --spec marketing/video/asc842/scenes.yaml
  options: --frames-only (no TTS/ffmpeg), --skip-recalc (reuse build/<slug>/recalc/src.xlsx), --scenes 3,7
"""
import argparse, json, pathlib, shutil, subprocess, sys, yaml, openpyxl
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import render_sheets as R

SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
VENV_PY = HERE / ".venv-tts" / "bin" / "python"

def recalc(src: pathlib.Path, outdir: pathlib.Path) -> pathlib.Path:
    outdir.mkdir(parents=True, exist_ok=True)
    subprocess.run([SOFFICE, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(outdir), str(src)],
                   check=True, capture_output=True, timeout=600)
    out = outdir / src.name
    if not out.exists(): raise SystemExit(f"LibreOffice did not produce {out}")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--skip-recalc", action="store_true")
    ap.add_argument("--scenes", help="comma-separated scene indexes to (re)render")
    a = ap.parse_args()
    spec = yaml.safe_load(open(a.spec)); slug = spec["slug"]
    build = HERE / "build" / slug; frames = build / "frames"; frames.mkdir(parents=True, exist_ok=True)
    src = pathlib.Path(spec["source"]).expanduser()
    if not src.is_absolute(): src = REPO / src
    staged = build / "src.xlsx"
    if not a.skip_recalc or not (build / "recalc" / "src.xlsx").exists():
        shutil.copy(src, staged)
        presets = spec.get("presets") or {}
        if presets:
            wb = openpyxl.load_workbook(staged)
            for sheet, cells in presets.items():
                for addr, val in cells.items():
                    wb[sheet][addr] = val
            wb.save(staged)
        rec = recalc(staged, build / "recalc")
        print(f"recalc ok -> {rec}")
    rec = build / "recalc" / "src.xlsx"
    wbv = openpyxl.load_workbook(rec, data_only=True); wbf = openpyxl.load_workbook(rec)
    only = {int(x) for x in a.scenes.split(",")} if a.scenes else None
    fj = frames / "focus.json"; focus = json.load(open(fj)) if fj.exists() else {}
    wbname = spec.get("workbook_name", src.name)
    for i, sc in enumerate(spec["scenes"]):
        if only is not None and i not in only: continue
        out = frames / f"scene_{i:02d}.png"; kind = sc.get("kind", "sheet")
        if kind in ("title", "outro"):
            focus[str(i)] = R.render_card(kind, out, sc.get("heading", spec.get("title", "")), sc.get("sub", ""),
                                          sc.get("lines", []), sc.get("price", ""), sc.get("url", ""), sc.get("badge", ""))
        else:
            focus[str(i)] = R.render_sheet(wbv, wbf, sc["sheet"], sc["range"], out, tuple(sc.get("highlight", [])),
                                           float(sc.get("zoom", 1.0)), sc.get("caption", ""), wbname)
        print(f"scene {i:02d}: {kind:<6} {sc.get('sheet','')} {sc.get('range','')} -> {out.name} focus={focus[str(i)]}", flush=True)
    json.dump(focus, open(fj, "w"), indent=1)
    if a.frames_only: return
    subprocess.run([str(VENV_PY), str(HERE / "narrate.py"), "--spec", a.spec, "--out", str(build / "audio")], check=True)
    final = build / f"{slug}.mp4"
    subprocess.run([sys.executable, str(HERE / "assemble.py"), "--build", str(build), "--out", str(final)], check=True)

if __name__ == "__main__":
    main()
