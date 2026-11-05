#!/usr/bin/env python3
"""Download the renderer's bundled SFX set (sfx/manifest.json) BY HAND, sha256-checked.

    scripts/video/.venv-tts/bin/python scripts/video/sfx/fetch.py [--dry-run] [--force]

The .wav files are gitignored (public repo; the Mixkit licence does not allow redistributing
the sounds as stand-alone files), so a fresh checkout runs this once. Never called by the
renderer: a missing file refuses the render and names this script. Polite: one request per
file, a named User-Agent, nothing re-downloaded that is already present and correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
UA = "KDesk-renderer-sfx-fetch/1.0 (by-hand; github.com/kdeskaccounting)"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan(manifest: dict, folder: pathlib.Path, force: bool = False) -> list:
    """(name, row, path) for every sound that is missing or wrong. Pure apart from reads."""
    todo = []
    for name, row in sorted(manifest["sounds"].items()):
        path = folder / row["file"]
        if not force and path.is_file() and sha256(path.read_bytes()) == row["sha256"]:
            continue
        todo.append((name, row, path))
    return todo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print what would be fetched")
    ap.add_argument("--force", action="store_true", help="re-fetch even correct files")
    a = ap.parse_args(argv)
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    todo = plan(manifest, HERE, a.force)
    if not todo:
        print("sfx: every bundled sound is present and matches its sha256")
        return 0
    bad = 0
    for name, row, path in todo:
        if a.dry_run:
            print(f"would fetch {name}: {row['download_url']} -> {path.name}")
            continue
        req = urllib.request.Request(row["download_url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if sha256(data) != row["sha256"]:
            print(f"REFUSED {name}: sha256 {sha256(data)} != manifest {row['sha256']} "
                  f"(the upstream file changed; review it and update the manifest by hand)",
                  file=sys.stderr)
            bad += 1
            continue
        path.write_bytes(data)
        print(f"fetched {name}: {path.name} ({len(data)} bytes, sha256 ok)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
