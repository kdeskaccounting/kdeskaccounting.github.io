import re
#!/usr/bin/env python3
"""
Assemble scene PNGs (2400x1350) + scene WAVs into a 1080p30 mp4 with ffmpeg.
Per scene: slow zoompan toward the scene's focus point, video fade in/out, audio pad.
Final: concat (stream copy) + loudnorm + faststart. This ffmpeg build has no drawtext,
so all text is already baked into the PNGs by render_sheets.py.

LANDSCAPE MEDIA (opt-in, ParkSheet long-form spike 2026-11-23). Given `--spec` and a spec with a
top-level `landscape:` mapping, a `kind: media` scene is rendered from its SOURCE instead of from
the poster PNG build_video screenshots for it:

  landscape:
    captions: {style: sentence, position: lower-third}   # or {enabled: false}
    join: cut              # hard cuts; anything else keeps the 0.35 s fade in/out per scene
    scene_pad: 0.35        # silence after each scene's last word (default 0.7, as before)

  * footage plays (`motion: clip`, looped at the input if short) instead of freezing on frame 0;
    a still gets media.py's kenburns (or the scene's `motion: hold`);
  * fill: a source narrower than LANDSCAPE_BLUR_RATIO (portrait or square-ish) is shown WHOLE over a
    blurred copy of itself (media.blur_fill_steps), anything wider is cover-cropped on the scene's
    `focus`; a scene's own `fill:` wins. An Earth Studio scene (media.is_earth_studio) is always
    shown whole, because cover-cropping a portrait export to 16:9 cuts its burned-in attribution,
    and on the brand ground rather than over a blurred, darkened copy of itself (no grade);
  * captions: one cue per sentence (a sentence over two 44-character lines splits at a comma, else
    at the most balanced word break that doesn't end on "the"/"into"/...), drawn
    with PIL as full-frame transparent PNGs from the scene's `scene_NN.words.json` and overlaid
    for the cue's span, in the lower third; on an Earth Studio scene they move to the top so the
    attribution is never covered.

LONG-FORM EXTRAS (2026-11-23, Park Detective episode 1; all of it under the same `landscape:`
opt-in, documented key by key, with defaults and refusals, in scripts/video/longform.py):

  landscape: {captions, join, scene_pad, chapter_card_s: 2.5, callout_s: 3.0,
              max_picture_s: 12.0, bed_crossfade: 3.0, bed_loop_in: 0}   # unknown keys refused
  audio: {bed: 'pool:<id>' | rotate | {src, lufs, ...}, duck, master: {lufs, tp, lra},
          sfx: {events: {...}}}                            # make_short.audio_settings rules
  per media scene: in, beats: [{src, seconds, in?, fill?, focus?, motion?, crop?, credit?}],
                   chapter: {number, title, kicker?},
                   callouts: [{type: sticker, src, when|at, anchor, size?, seconds?, label?,
                               labels?, enter_from?, offset_ms?, sfx?}]

  * beats cut the picture inside one scene (seconds rescaled to the real narration exactly as
    make_short.beat_spans does); `in:` starts a clip at an in-point (scene or beat);
  * a chapter card slides in at the scene's start, where the captions are not (lower-left and
    clear of the Earth Studio zone over Earth footage), and chapters.json records its start;
  * sticker callouts land on their word (words.json), slide in from the nearest edge and never
    cover an Earth Studio attribution zone;
  * the bed is looped to the episode's length with crossfaded seams and mixed by
    make_short.audio_steps (gain from the row's measured lufs, sidechain duck, alimiter,
    loudnorm to audio.master); callout `sfx:` rides the same mix.

Without `--spec`, or with no `landscape:` block, every byte of the old behaviour is unchanged.
"""
import subprocess, json, pathlib, argparse, math, sys
FPS, W, H = 30, 1920, 1080

#: A source whose width/height is below this is shown whole over blur on a 16:9 canvas.
#: 1.3 keeps 4:3 stills (1.33) cropping and pillarboxes 1:1, 3:4 and 9:16.
LANDSCAPE_BLUR_RATIO = 1.3
CAPTION_FONT = pathlib.Path(__file__).resolve().parent / "fonts" / "Carlito-Bold.ttf"
CAPTION_PX = 54            # at 1080 high: TV-readable, about 2.6 cm on a 50" screen
CAPTION_MAX_CHARS = 44     # per line; two lines at most, so a cue is at most 88 characters
CAPTION_MARGIN = 0.08      # of H: inside the 90% title-safe area


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")

def dur_of(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)

SCENE_PNG = re.compile(r"^scene_(\d+)\.png$")


def scene_frames(frames_dir: pathlib.Path) -> list[pathlib.Path]:
    """The full-frame scene stills, in index order — and nothing else.

    A `kind: media` scene leaves its layers beside the still (scene_00-credit.png,
    scene_00-overlay.png, scene_00-poster.png); a bare ``scene_*.png`` glob swept those in
    and crashed on ``int("00-credit")``. Only ``scene_NN.png`` is a scene.
    """
    return sorted((f for f in frames_dir.glob("scene_*.png") if SCENE_PNG.match(f.name)),
                  key=lambda f: int(SCENE_PNG.match(f.name).group(1)))


# --- landscape media (opt-in) -------------------------------------------------------------

def landscape_opts(spec: dict | None) -> dict | None:
    """The spec's `landscape:` mapping, or None (the old path)."""
    opts = (spec or {}).get("landscape")
    return opts if isinstance(opts, dict) else None


def landscape_fill(scene: dict, src_w: int | None, src_h: int | None, earth: bool) -> str:
    """'blur' (whole picture over a blurred copy) or 'crop' (cover on `focus`)."""
    if earth:
        return "blur"
    if scene.get("fill"):
        return str(scene["fill"])
    if not src_w or not src_h:
        return "crop"
    return "blur" if src_w / src_h < LANDSCAPE_BLUR_RATIO else "crop"


#: A chunk never ENDS on one of these when a long sentence has to be split without a comma.
FUNCTION_WORDS = frozenset("a an the and or but to of in into on at for from with by your my his her "
                           "their its our that this these those is are was were be".split())


def _chunk_text(ws: list) -> str:
    return " ".join(str(w["text"]).strip() for w in ws)


def split_long(ws: list, max_chars: int = 2 * CAPTION_MAX_CHARS) -> list:
    """Split one sentence's words into cues of at most `max_chars` (two lines).

    The break goes after a comma/colon/semicolon if the sentence has one (the one that balances
    the halves best), else at the most balanced word boundary that doesn't strand a function
    word ("...costume into" / "a Disney World park").
    """
    if len(ws) < 2 or len(_chunk_text(ws)) <= max_chars:
        return [ws]
    ks = [k for k in range(1, len(ws)) if str(ws[k - 1]["text"]).strip()[-1:] in ",:;"]
    if not ks:
        ks = [k for k in range(1, len(ws))
              if str(ws[k - 1]["text"]).strip().strip(".,;:!?\"'").lower() not in FUNCTION_WORDS]
    if not ks:
        ks = list(range(1, len(ws)))
    k = min(ks, key=lambda k: abs(len(_chunk_text(ws[:k])) - len(_chunk_text(ws[k:]))))
    return split_long(ws[:k], max_chars) + split_long(ws[k:], max_chars)


def caption_cues(words: list, scene_dur: float, max_chars: int = 2 * CAPTION_MAX_CHARS) -> list:
    """[(text, start, end)]: one cue per sentence; a sentence over two lines is split (split_long).

    A cue runs from its first word to the next cue's first word (the last cue to its last word
    + 0.5 s, inside the scene), so the band never blinks off mid-thought.
    """
    sentences, cur = [], []
    for w in words or []:
        t = str(w.get("text", "")).strip()
        if not t:
            continue
        cur.append(w)
        if t[-1:] in ".?!" or t.endswith(('."', '?"', '!"')):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    groups = [chunk for s in sentences for chunk in split_long(s, max_chars)]
    cues = []
    for i, g in enumerate(groups):
        start = float(g[0]["start"])
        end = float(groups[i + 1][0]["start"]) if i + 1 < len(groups) else min(
            scene_dur, float(g[-1]["end"]) + 0.5)
        cues.append((" ".join(str(w["text"]).strip() for w in g), start, max(end, start + 0.3)))
    return cues


def wrap_caption(text: str, max_chars: int = CAPTION_MAX_CHARS) -> list:
    """One line, or two balanced lines."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    best, best_cost = None, None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        cost = abs(len(a) - len(b))
        if best_cost is None or cost < best_cost:
            best, best_cost = [a, b], cost
    return best or [text]


def caption_png(text: str, out: pathlib.Path, position: str = "lower-third",
                w: int = W, h: int = H) -> pathlib.Path:
    """A full-frame transparent PNG with the cue in a soft dark box (no drawtext here)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(CAPTION_FONT), CAPTION_PX)
    lines = wrap_caption(text)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line_h = int(CAPTION_PX * 1.22)
    widths = [d.textbbox((0, 0), ln, font=font, stroke_width=2)[2] for ln in lines]
    box_w, box_h = max(widths) + 56, line_h * len(lines) + 28
    x0 = (w - box_w) // 2
    y0 = int(h * CAPTION_MARGIN) if position == "top" else int(h * (1 - CAPTION_MARGIN)) - box_h
    d.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), radius=14, fill=(0, 0, 0, 150))
    for i, ln in enumerate(lines):
        lw = widths[i]
        d.text(((w - lw) // 2, y0 + 14 + i * line_h), ln, font=font, fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 255))
    img.save(out)
    return out


#: What every beat chain agrees on before the `concat` filter joins them (make_short.BEAT_TAIL,
#: spelled here so this module keeps importing with the standard library alone): limited range,
#: yuv420p, square pixels. concat refuses a mixed pixel format or SAR outright, and a still
#: (full range) cut against footage (limited) would otherwise flip its blacks at the cut.
BEAT_TAIL = "scale=in_range=auto:out_range=tv,format=yuv420p,setsar=1,"


def source_args(motion: str, in_s: float, src) -> list:
    """One picture's ffmpeg input: looped at the input if `clip`, sought to its in-point."""
    import media
    return ((list(media.CLIP_INPUT_ARGS) if motion == "clip" else [])
            + (["-ss", f"{float(in_s):.3f}"] if in_s else []) + ["-i", str(src)])


def picture_steps(src_label: str, out_label: str, motion: str, dur: float, size, fill, focus,
                  crop, earth: bool, bg: str) -> list:
    """The chains that turn one source into `dur` seconds of 1920x1080 at `[out_label]`."""
    import media
    if earth:
        # Earth Studio footage is shown whole and untouched: no blurred, darkened copy of it
        # beside itself (that copy would be a grade of Earth footage), just the brand ground.
        return [f"[{src_label}]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={bg},"
                f"{media.motion_chain(motion, dur, W, H, FPS)}[{out_label}]"]
    fill = landscape_fill({"fill": fill} if fill else {}, *(size or (None, None)), earth=False)
    return media.ffmpeg_video_steps(motion, dur, W, H, FPS, src_w=size[0] if size else None,
                                    src_h=size[1] if size else None, src_label=src_label,
                                    out_label=out_label, fill=fill, focus=tuple(focus),
                                    crop=crop or None)


def landscape_media_part(scene: dict, spec_path: str, wav: pathlib.Path, dur: float, out: pathlib.Path,
                         opts: dict, work: pathlib.Path, i: int, crf: int,
                         spec_brand: dict | None = None, lf=None) -> list:
    """One `kind: media` scene rendered from its source(s) at 1920x1080, with its beats, callouts,
    chapter card and sentence captions. Returns the callouts' sounds, [{at, role}] scene-local."""
    import illustrate
    import longform
    import media
    lf = lf or longform.options({"landscape": opts})
    where = f"scene {i}"
    bg = str(((spec_brand or {}).get("bg")) or "#101418")
    pics = longform.scene_pictures(scene, spec_path, lf.max_picture_s, where)
    args, steps, pictures = [], [], []          # pictures: (start, end, earth, size)
    if pics[0]["beat"] is not None:
        spans = longform.beat_spans([p["beat"] for p in pics], dur, lf.max_picture_s)
        t = 0.0
        for k, (p, span) in enumerate(zip(pics, spans)):
            size = probe_size(p["src"])
            chains = picture_steps(f"{k}:v", f"b{k}", p["motion"], span, size, p["fill"],
                                   p["focus"], p["crop"], p["earth"], bg)
            trim = f"trim=duration={span:.3f},setpts=PTS-STARTPTS"
            # Every beat ends the same way, whatever its motion (make_short.beat_steps): `clip`
            # already ends on this trim, so the normalisation is spliced in front of it.
            body = chains[-1].removesuffix(f"[b{k}]").removesuffix(trim).rstrip(",")
            chains[-1] = f"{body},{BEAT_TAIL}{trim}[b{k}]"
            steps += chains
            args += source_args(p["motion"], p["in"], p["src"])
            pictures.append((t, t + span, p["earth"], size))
            t += span
        steps.append("".join(f"[b{k}]" for k in range(len(pics)))
                     + f"concat=n={len(pics)}:v=1:a=0[m0]")
        cuts = longform.cut_times(spans)
        n_in = len(pics)
    else:
        p = pics[0]
        size = probe_size(p["src"])
        earth = media.is_earth_studio(scene)
        steps = picture_steps("0:v", "m0", p["motion"], dur, size,
                              landscape_fill(scene, *(size or (None, None)), earth=earth),
                              tuple(scene.get("focus") or (0.5, 0.5)), scene.get("crop"),
                              earth, bg)
        args = source_args(p["motion"], p["in"], p["src"])
        pictures.append((0.0, dur, earth, size))
        cuts = []
        n_in = 1
    audio_index = None
    if wav.exists():
        args += ["-i", str(wav)]
        audio_index = n_in
        n_in += 1
    stage = "m0"
    wj = wav.with_suffix(".words.json")
    words = json.loads(wj.read_text()) if wj.exists() else []

    def earth_zones_in(a: float, b: float) -> list:
        return [z for (p0, p1, e, sz) in pictures if e and longform.windows_overlap(a, b, p0, p1)
                for z in longform.earth_zones(sz)]

    # Callouts: under the chapter card and the captions, over the picture.
    events = []
    for k, c in enumerate(longform.resolve_callouts(scene, spec_path, where)):
        tag = f"{where} callouts[{k}]"
        t0, t1 = longform.callout_window(c, illustrate.word_rows(words), dur, cuts,
                                         lf.callout_s, tag)
        png, sw, sh = longform.sticker_png(c, work / f"scene_{i:02d}_stk{k:02d}.png")
        box = longform.sticker_box(c["anchor"], sw, sh)
        if longform.overlaps_any(box, earth_zones_in(t0, t1)):
            raise SystemExit(f"{tag}: the sticker would cover the Earth Studio attribution zone; "
                             f"move its anchor up or left, or make it smaller")
        args += ["-i", str(png)]
        steps.append(f"[{stage}][{n_in}:v]{longform.sticker_overlay(box, c['enter_from'], t0, t1)}"
                     f"[k{k}]")
        stage = f"k{k}"
        n_in += 1
        if c["sfx"]:
            events.append({"at": t0, "role": c["sfx"]})
    cues = caption_cues(words, dur) if lf.captions_on else []

    def cue_position(a: float, b: float) -> str:
        return "top" if earth_zones_in(a, b) else lf.caption_position

    chapter = longform.chapter_of(scene, where)
    if chapter:
        c1 = min(lf.chapter_card_s, dur)
        earth_under = bool(earth_zones_in(0.0, c1))
        captions_top = lf.caption_position == "top" or any(
            cue_position(a, b) == "top" for (_t, a, b) in cues
            if longform.windows_overlap(a, b, 0.0, c1))
        place = longform.chapter_placement(earth_under, captions_top)
        png, cw, ch = longform.chapter_png(chapter, spec_brand,
                                           work / f"scene_{i:02d}_chapter.png", place["max_w"])
        x, y = longform.chapter_origin(place, cw, ch)
        if longform.overlaps_any((x, y, x + cw, y + ch), earth_zones_in(0.0, c1)):
            raise SystemExit(f"{where}: the chapter card would cover the Earth Studio "
                             f"attribution zone (shorten the title)")
        args += ["-i", str(png)]
        steps.append(f"[{stage}][{n_in}:v]{longform.chapter_overlay(x, y, cw, 0.0, c1)}[ch]")
        stage = "ch"
        n_in += 1
    for k, (text, a, b) in enumerate(cues):
        png = caption_png(text, work / f"scene_{i:02d}_cap{k:02d}.png", cue_position(a, b))
        args += ["-i", str(png)]
        steps.append(f"[{stage}][{n_in}:v]overlay=x=0:y=0:format=auto:"
                     f"enable='between(t,{a:.3f},{b:.3f})'[c{k}]")
        stage = f"c{k}"
        n_in += 1
    fade = "" if lf.join == "cut" else (
        f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, dur - 0.35):.3f}:d=0.35,")
    steps.append(f"[{stage}]scale={W}:{H}:flags=lanczos:out_range=tv,{fade}format=yuv420p[v]")
    if audio_index is None:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_index = n_in
        steps.append(f"[{audio_index}:a]anull[a]")
    else:
        steps.append(f"[{audio_index}:a]apad=pad_dur=3,afade=t=in:d=0.05,"
                     "aformat=sample_rates=48000:channel_layouts=stereo[a]")
    run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(steps),
         "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium",
         "-crf", str(crf), "-r", str(FPS), "-color_range", "tv", "-c:a", "aac", "-b:a", "128k", str(out)])
    return events


def probe_size(p):
    """(width, height) of a media file's first video stream, or None."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0:s=x", str(p)],
                         capture_output=True, text=True).stdout
    for line in (out or "").splitlines():
        parts = line.strip().split("x")
        if len(parts) == 2 and all(q.isdigit() and int(q) for q in parts):
            return int(parts[0]), int(parts[1])
    return None


#: The long-form master's audio: 48 kHz (loudnorm resamples to 192 kHz internally and the AAC
#: encoder would otherwise pick 96 kHz; make_short.OUT_SAMPLE_RATE says the same) at a bitrate
#: for a 15-minute episode rather than a 30-second Short.
LANDSCAPE_AUDIO = ("-c:a", "aac", "-b:a", "192k", "-ar", "48000")


def kept_events(mix, events) -> tuple:
    """(events whose role `audio.sfx.events` has a file for, the roles it has not)."""
    roles = {e.role for e in (mix.sfx.events if mix is not None and mix.sfx is not None else ())}
    kept = [e for e in events if e["role"] in roles]
    return kept, sorted({e["role"] for e in events} - roles)


def landscape_final(lst: pathlib.Path, out: str, mix, events, runtime: float,
                    work: pathlib.Path, lf) -> None:
    """Join the parts (video stream-copied) and finish the sound.

    No `audio:` bed: the narration through the master loudnorm, as the old path did. With a
    bed: the bed looped to `runtime` with crossfaded seams (longform.render_bed_loop), then
    make_short.audio_steps -- the Shorts' own mix: gain target - lufs, fades, sidechain duck
    under the voice, the callouts' `sfx:` events, alimiter, loudnorm to audio.master.
    """
    import longform
    import make_short
    if mix is None or mix.bed is None:
        master = mix.master if mix is not None else make_short.Master()
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
             "-c:v", "copy", "-af", make_short.loudnorm_filter(master), *LANDSCAPE_AUDIO,
             "-movflags", "+faststart", out])
        return
    bed = longform.render_bed_loop(mix.bed.src, runtime, lf.bed_crossfade, work / "bed-loop.wav",
                                   lf.bed_loop_in)
    kept, missing = kept_events(mix, events)
    if missing:
        print(f"note: callout sfx {', '.join(missing)} skipped: audio.sfx.events has no file for "
              f"{'it' if len(missing) == 1 else 'them'}", flush=True)
    ev_args, ev_indexes = make_short.event_inputs(mix, kept, 2)
    steps = make_short.audio_steps(mix, runtime=runtime, cuts=[], bed_index=1, sfx_indexes=[],
                                   events=kept, event_indexes=ev_indexes)
    print(f"bed: {pathlib.Path(mix.bed.src).name} looped to {runtime:.1f}s "
          f"({lf.bed_crossfade:g}s crossfades), {make_short.bed_gain_db(mix.bed.target_lufs, mix.bed.lufs):+g} dB, "
          f"ducked; {len(kept)} callout sound(s); master {make_short.loudnorm_filter(mix.master)}",
          flush=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-i", str(bed), *ev_args, "-filter_complex", ";".join(steps), "-map", "0:v",
         "-map", "[aout]", "-c:v", "copy", *LANDSCAPE_AUDIO, "-movflags", "+faststart", out])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--crf", type=int, default=27)
    ap.add_argument("--spec", help="the scenes.yaml; only read when it carries a `landscape:` block")
    a = ap.parse_args(); b = pathlib.Path(a.build)
    spec = None
    if a.spec:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import specload
        spec = specload.load(a.spec)
    opts = landscape_opts(spec)
    lf = mix = None
    if opts is not None:
        import longform
        lf = longform.options(spec)
        longform.normalise_spec(spec)
        mix = longform.audio_mix(spec, a.spec)       # refuses a bad audio block before rendering
    pad = lf.scene_pad if lf is not None else 0.7
    frames = scene_frames(b / "frames")
    scenes_dir = b / "scenes"; scenes_dir.mkdir(exist_ok=True)
    fj = b / "frames" / "focus.json"
    focus = json.load(open(fj)) if fj.exists() else {}
    parts = []
    start, events, marks = 0.0, [], []     # landscape only: the finished timeline
    for png in frames:
        i = int(png.stem.split("_")[1]); wav = b / "audio" / f"scene_{i:02d}.wav"
        adur = dur_of(wav) if wav.exists() else 0.0
        dur = max(3.0, adur + pad); n = math.ceil(dur * FPS)
        out = scenes_dir / f"scene_{i:02d}.mp4"
        scene = (spec or {}).get("scenes", [{}])[i] if spec else {}
        if opts is not None and (scene or {}).get("kind") == "media":
            sounds = landscape_media_part(scene, a.spec, wav, dur, out, opts, scenes_dir, i, a.crf,
                                          spec_brand=(spec or {}).get("brand"), lf=lf)
            events += [{"at": round(start + e["at"], 3), "role": e["role"]} for e in sounds]
            chapter = longform.chapter_of(scene, f"scene {i}")
            if chapter:
                marks.append({"scene": i, "start": start, **chapter})
            start += dur_of(out)
            parts.append(out); print(f"scene {i:02d}: {dur:5.1f}s -> {out.name} (landscape media)", flush=True)
            continue
        f = focus.get(str(i), {}); fx = f.get("fx", 0.5); fy = f.get("fy", 0.5); static = f.get("static", False)
        zmax = 1.0 if static else 1.10; dz = 0.0 if static else (zmax - 1.0) / n
        vf = (f"scale=2400:1350:flags=lanczos,"
              f"zoompan=z='min(zoom+{dz:.7f},{zmax})':x='iw*{fx:.4f}-(iw/zoom)*{fx:.4f}':y='ih*{fy:.4f}-(ih/zoom)*{fy:.4f}'"
              f":d={n}:s={W}x{H}:fps={FPS},"
              f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, dur-0.35):.3f}:d=0.35,format=yuv420p")
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
        if opts is not None:
            start += dur_of(out)
    lst = b / "concat.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    if opts is not None:
        longform.write_chapters(b / "chapters.json", marks)
        for m in marks:
            print(f"chapter {longform.timestamp(m['start'])} {m['kicker']} {m['title']}".replace("  ", " "))
        landscape_final(lst, a.out, mix, events, start, b, lf)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", a.out])
    print(f"final: {a.out}  {dur_of(a.out):.1f}s  {pathlib.Path(a.out).stat().st_size/1e6:.1f} MB")

if __name__ == "__main__":
    main()
