#!/usr/bin/env python3
"""
Make a stand-in "raw human recording" from an existing TTS build, to smoke-test
human_voice.py end to end before a real read exists.

  scripts/video/.venv-tts/bin/python scripts/video/human_voice_standin.py \
      --audio scripts/video/build/<slug>/audio --out /tmp/standin.wav \
      [--retake 3] [--false-start 2] [--split-pause 5]

What it does to the TTS scenes, so the pipeline has something to cut:
  * 5 s of room tone first (pink noise ~-58 dBFS + 60 Hz hum ~-64 dBFS, under everything)
  * scene --false-start: the first ~55 % of it, a 0.9 s pause, then the whole sentence
  * scene --retake: read twice in full, the FIRST take slowed to 0.85x so the two differ;
    the pipeline must keep the second (normal-speed) one
  * scene --split-pause: a 1.1 s pause between its two sentences
  * the gaps between scenes vary 0.45-1.4 s (the trimmer brings them to ~0.3 s)
  * level: speech peaks around -12 dBFS, as the recording sheet asks; mono 48 kHz 24-bit

A JSON beside the WAV records where everything was put, for checking the cut.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import human_voice as H  # noqa: E402

GAPS = [0.55, 1.4, 0.45, 0.9, 0.7, 1.2, 0.5, 0.8, 0.6, 1.0]


def main(argv=None) -> int:
    import numpy as np
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--audio", required=True, help="a TTS build's audio directory")
    ap.add_argument("--out", required=True)
    ap.add_argument("--retake", type=int, default=3)
    ap.add_argument("--false-start", type=int, default=2)
    ap.add_argument("--split-pause", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(argv)
    audio_dir = pathlib.Path(a.audio)
    sr = H.SR
    rng = np.random.default_rng(a.seed)
    scenes = sorted(audio_dir.glob("scene_[0-9][0-9].wav"))

    def trimmed(path, tempo=1.0):
        x = H.load_audio(path)
        if tempo != 1.0:
            raw = subprocess.run([H.FFMPEG, "-v", "error", "-i", str(path), "-af",
                                  f"atempo={tempo}", "-ac", "1", "-ar", str(sr), "-f", "f32le",
                                  "-"], capture_output=True, check=True).stdout
            x = np.frombuffer(raw, np.float32).copy()
        idx = np.nonzero(np.abs(x) > 0.01)[0]
        return x[idx[0]:idx[-1] + 1] if len(idx) else x

    def silence(seconds):
        return np.zeros(int(seconds * sr), np.float32)

    parts, log, t = [silence(5.0)], [], 5.0
    for k, path in enumerate(scenes):
        idx = int(path.stem.split("_")[1])
        clip = trimmed(path)
        if idx == a.false_start:
            head = clip[:int(len(clip) * 0.55)]
            head[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr), dtype=np.float32)
            parts += [head, silence(0.9)]
            log.append({"scene": idx, "what": "false start", "start": t,
                        "end": t + len(head) / sr})
            t += len(head) / sr + 0.9
        if idx == a.retake:
            slow = trimmed(path, 0.85)
            parts += [slow, silence(1.2)]
            log.append({"scene": idx, "what": "first take (0.85x, must be CUT)", "start": t,
                        "end": t + len(slow) / sr})
            t += len(slow) / sr + 1.2
        if idx == a.split_pause:
            words = json.loads(path.with_name(path.stem + ".words.json").read_text())
            ends = [w for w in words if w["text"].endswith(("?", ".", "!"))]
            if len(ends) > 1:
                lead = np.nonzero(np.abs(H.load_audio(path)) > 0.01)[0][0] / sr
                cut = int((ends[0]["end"] + 0.05 - lead) * sr)
                clip = np.concatenate([clip[:cut], silence(1.1), clip[cut:]])
                log.append({"scene": idx, "what": "1.1 s pause between its sentences"})
        log.append({"scene": idx, "what": "kept take", "start": t, "end": t + len(clip) / sr,
                    "seconds": len(clip) / sr})
        gap = GAPS[k % len(GAPS)]
        parts += [clip, silence(gap)]
        t += len(clip) / sr + gap
    parts.append(silence(1.5))
    voice = np.concatenate(parts)
    voice *= (10 ** (-12 / 20)) / max(np.max(np.abs(voice)), 1e-9)
    n = len(voice)
    white = rng.standard_normal(n).astype(np.float32)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    spectrum[1:] /= np.sqrt(freqs[1:])
    pink = np.fft.irfft(spectrum, n).astype(np.float32)
    pink *= (10 ** (-58 / 20)) / np.sqrt(np.mean(pink ** 2))
    hum = (10 ** (-64 / 20)) * np.sqrt(2) * np.sin(2 * np.pi * 60 * np.arange(n) / sr)
    out = (voice + pink + hum.astype(np.float32)).astype(np.float32)
    H.save_audio(a.out, out, subtype="PCM_24")
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(log, indent=1))
    print(f"wrote {a.out} ({n / sr:.1f}s) and {pathlib.Path(a.out).with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
