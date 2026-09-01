#!/usr/bin/env python3
"""
Assemble scene PNGs (2400x1350) + scene WAVs into a 1080p30 mp4 with ffmpeg.
Per scene: slow zoompan toward the scene's focus point, video fade in/out, audio pad.
Final: concat (stream copy) + loudnorm + faststart. This ffmpeg build has no drawtext,
so all text is already baked into the PNGs by render_sheets.py.
"""
import subprocess, json, pathlib, argparse, math
FPS, W, H = 30, 1920, 1080

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")

def dur_of(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--crf", type=int, default=27)
    a = ap.parse_args(); b = pathlib.Path(a.build)
    frames = sorted((b / "frames").glob("scene_*.png"))
    scenes_dir = b / "scenes"; scenes_dir.mkdir(exist_ok=True)
    fj = b / "frames" / "focus.json"
    focus = json.load(open(fj)) if fj.exists() else {}
    parts = []
    for png in frames:
        i = int(png.stem.split("_")[1]); wav = b / "audio" / f"scene_{i:02d}.wav"
        adur = dur_of(wav) if wav.exists() else 0.0
        dur = max(3.0, adur + 0.7); n = math.ceil(dur * FPS)
        f = focus.get(str(i), {}); fx = f.get("fx", 0.5); fy = f.get("fy", 0.5); static = f.get("static", False)
        zmax = 1.0 if static else 1.10; dz = 0.0 if static else (zmax - 1.0) / n
        vf = (f"scale=2400:1350:flags=lanczos,"
              f"zoompan=z='min(zoom+{dz:.7f},{zmax})':x='iw*{fx:.4f}-(iw/zoom)*{fx:.4f}':y='ih*{fy:.4f}-(ih/zoom)*{fy:.4f}'"
              f":d={n}:s={W}x{H}:fps={FPS},"
              f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, dur-0.35):.3f}:d=0.35,format=yuv420p")
        out = scenes_dir / f"scene_{i:02d}.mp4"
        base = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png)]
        if wav.exists():
            cmd = base + ["-i", str(wav), "-filter_complex",
                          f"[0:v]{vf}[v];[1:a]apad=pad_dur=3,afade=t=in:d=0.05,aformat=sample_rates=48000:channel_layouts=stereo[a]",
                          "-map", "[v]", "-map", "[a]"]
        else:
            cmd = base + ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", f"[0:v]{vf}[v]",
                          "-map", "[v]", "-map", "1:a"]
        cmd += ["-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-r", str(FPS),
                "-c:a", "aac", "-b:a", "128k", str(out)]
        run(cmd); parts.append(out); print(f"scene {i:02d}: {dur:5.1f}s -> {out.name}", flush=True)
    lst = b / "concat.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", a.out])
    print(f"final: {a.out}  {dur_of(a.out):.1f}s  {pathlib.Path(a.out).stat().st_size/1e6:.1f} MB")

if __name__ == "__main__":
    main()
