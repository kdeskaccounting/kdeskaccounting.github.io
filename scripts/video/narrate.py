#!/usr/bin/env python3
"""
Synthesize per-scene narration WAVs with Kokoro TTS (local, no API keys).
Run with the pipeline venv:  scripts/video/.venv-tts/bin/python scripts/video/narrate.py --spec ... --out ...
Caches by (voice, speed, text) hash so re-runs only synthesize changed scenes.
"""
import os, sys, json, hashlib, pathlib, argparse
HERE = pathlib.Path(__file__).resolve().parent
# spaCy (inside Kokoro's G2P) auto-installs its English model via `uv pip`; it needs to see the venv.
os.environ.setdefault("VIRTUAL_ENV", str(HERE / ".venv-tts"))
import yaml, numpy as np, soundfile as sf

SR = 24000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--voice"); ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    spec = yaml.safe_load(open(a.spec)); voice = a.voice or spec.get("voice", "am_michael")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from kokoro import KPipeline
    pipe = None
    durations = {}
    for i, sc in enumerate(spec["scenes"]):
        text = " ".join((sc.get("narration") or "").split())
        wav, meta = out / f"scene_{i:02d}.wav", out / f"scene_{i:02d}.json"
        if not text:
            durations[i] = 0.0; continue
        h = hashlib.sha1(f"{voice}|{a.speed}|{text}".encode()).hexdigest()
        if wav.exists() and meta.exists() and json.load(open(meta)).get("hash") == h:
            durations[i] = json.load(open(meta))["seconds"]; print(f"scene {i:02d}: cached {durations[i]:.1f}s"); continue
        if pipe is None:
            pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        chunks = [audio for _, _, audio in pipe(text, voice=voice, speed=a.speed)]
        audio = np.concatenate(chunks).astype(np.float32)
        idx = np.where(np.abs(audio) > 0.01)[0]
        if len(idx):
            audio = audio[max(0, idx[0] - int(0.1 * SR)): idx[-1] + int(0.25 * SR)]
        audio = np.concatenate([np.zeros(int(0.3 * SR), dtype=np.float32), audio])
        sf.write(wav, audio, SR)
        sec = len(audio) / SR; durations[i] = sec
        json.dump({"hash": h, "seconds": sec, "voice": voice, "text": text}, open(meta, "w"))
        print(f"scene {i:02d}: {sec:.1f}s  peak={float(np.abs(audio).max()):.2f}", flush=True)
    json.dump(durations, open(out / "durations.json", "w"), indent=1)

if __name__ == "__main__":
    main()
