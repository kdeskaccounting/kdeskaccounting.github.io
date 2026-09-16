#!/usr/bin/env python3
"""Regenerate the media-demo's two placeholder assets. Synthetic — nothing is licensed.

    python3 marketing/video/media-demo/assets/generate.py

Both are 16:9 on purpose: the `media` kind has to scale-and-crop a landscape source to fill
a 9:16 frame, and a demo that shipped 9:16 sources would never exercise that. They are
committed (tests/test_media.py guards the size cap) so the demo spec renders on a clean
checkout with no download step, and they are ffmpeg's own synthetic sources so there is no
imagery to credit — the demo's `credit:` lines are there to exercise the credit plate, not
because these frames need attribution.
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent

#: Committed placeholders stay small; the real thing is a link to a release, not a blob.
MAX_BYTES = 300_000

STILL = HERE / "placeholder-still.jpg"
CLIP = HERE / "placeholder-clip.mp4"


def run(args):
    proc = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(args)}\n{proc.stderr[-1500:]}")


def main() -> int:
    # A dusk sky over warm ground: enough tonal range to show whether the plates stay legible.
    run(["-f", "lavfi",
         "-i", "gradients=s=1920x1080:c0=0x1B3B6F:c1=0x2E75B6:c2=0xB07A2A:c3=0x3A2A18:"
               "n=4:x0=180:y0=0:x1=1740:y1=1080:d=1",
         "-frames:v", "1", "-q:v", "6", str(STILL)])
    # Three seconds of slow drift, so `clip` has something that visibly moves and something
    # short enough that a longer narration has to loop it.
    run(["-f", "lavfi",
         "-i", "gradients=s=1920x1080:c0=0x11202E:c1=0x2E75B6:c2=0x8B5A2B:n=3:"
               "speed=0.012:d=3",
         "-t", "3", "-r", "30", "-c:v", "libx264", "-preset", "slow", "-crf", "34",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(CLIP)])
    ok = True
    for path in (STILL, CLIP):
        size = path.stat().st_size
        print(f"{path.name}: {size:,} bytes")
        if size > MAX_BYTES:
            print(f"  TOO BIG: over the {MAX_BYTES:,} byte cap", file=sys.stderr)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
