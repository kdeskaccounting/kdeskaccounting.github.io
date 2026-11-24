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
                   callouts: make_short's own list -- sticker, badge, text, arrow, circle and
                             hoot, every key callouts.py reads (+ `at`, `seconds`, `label`),
                   fx: the Shorts verdict washes/grades (grammar.py)
  landscape.chapter_sfx: {src: 'bundle:whoosh', gain_db: -16, lead: 0.2} (default) | null

  * beats cut the picture inside one scene (seconds rescaled to the real narration exactly as
    make_short.beat_spans does); `in:` starts a clip at an in-point (scene or beat);
  * a chapter card slides in at the scene's start, where the captions are not (lower-left and
    clear of the Earth Studio zone over Earth footage), and chapters.json records its start;
  * callouts land on their word (words.json) with the Shorts' eases, holds and sounds, drawn
    with PIL at the Short's pixel sizes (scripts/video/longform_overlay.py); Hoot sits beside
    the captions and climbs over them; nothing covers an Earth Studio attribution zone;
  * `fx:` verdict washes tint the picture under the graphics, with on_verdict's buzzer/ding;
  * the bed is looped to the episode's length with crossfaded seams and mixed by
    make_short.audio_steps (gain from the row's measured lufs, sidechain duck, alimiter,
    loudnorm to audio.master); the one-shots (callout sfx via audio.sfx.events or on_tag,
    verdict sounds, the chapter whoosh) are thinned and laid over it on one bus, un-ducked.

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


def caption_layout(text: str, position: str = "lower-third", w: int = W, h: int = H) -> tuple:
    """(lines, line widths, line height, box (x0, y0, x1, y1)) of one cue: caption_png's
    geometry, and what a Hoot on a 16:9 scene is kept clear of."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(CAPTION_FONT), CAPTION_PX)
    lines = wrap_caption(text)
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    line_h = int(CAPTION_PX * 1.22)
    widths = [d.textbbox((0, 0), ln, font=font, stroke_width=2)[2] for ln in lines]
    box_w, box_h = max(widths) + 56, line_h * len(lines) + 28
    x0 = (w - box_w) // 2
    y0 = int(h * CAPTION_MARGIN) if position == "top" else int(h * (1 - CAPTION_MARGIN)) - box_h
    return lines, widths, line_h, (x0, y0, x0 + box_w, y0 + box_h)


def caption_png(text: str, out: pathlib.Path, position: str = "lower-third",
                w: int = W, h: int = H) -> pathlib.Path:
    """A full-frame transparent PNG with the cue in a soft dark box (no drawtext here)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(CAPTION_FONT), CAPTION_PX)
    lines, widths, line_h, (x0, y0, x1, y1) = caption_layout(text, position, w, h)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=(0, 0, 0, 150))
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
                         spec_brand: dict | None = None, lf=None, spec: dict | None = None) -> list:
    """One `kind: media` scene rendered from its source(s) at 1920x1080: beats, verdict washes,
    callouts (longform_overlay: stickers, badges, stamps, arrows, circles, Hoot), chapter card,
    sentence captions. Returns its sound events, [{at, role, kind}] on the scene clock, kind
    callout (role = the sfx name) | verdict (role verdict_good|bad) | chapter."""
    import illustrate
    import longform
    import longform_overlay
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

    cues = caption_cues(words, dur) if lf.captions_on else []

    def cue_position(a: float, b: float) -> str:
        return "top" if earth_zones_in(a, b) else lf.caption_position

    def captions_in(a: float, b: float) -> list:
        return [caption_layout(t, cue_position(c0, c1))[3] for (t, c0, c1) in cues
                if longform.windows_overlap(a, b, c0, c1)]

    # The picture's own grade first: the verdict washes (fx:) and the blur behind a Hoot that
    # asks for it (grammar.window_steps, as the Shorts lay them), under every graphic.
    events = []
    verdicts = longform_overlay.verdict_windows(scene, words, dur, where)
    calls = longform_overlay.check(scene.get("callouts"), where, spec, spec_path)
    layers = longform_overlay.build_layers(
        calls, illustrate.word_rows(words), dur, cuts, lf.callout_s,
        work / f"scene_{i:02d}_callouts", where, captions_in, earth_zones_in)
    windows = [w for _v, w in verdicts] + longform_overlay.blur_windows(layers, dur)
    if windows:
        import grammar
        w_steps, stage = grammar.window_steps(stage, windows)
        steps.extend(w_steps)
    events += [{"at": w.t0, "role": f"verdict_{v}", "kind": "verdict"} for v, w in verdicts]
    # Callouts: under the chapter card and the captions, over the picture.
    l_args, l_steps, stage, n_in = longform_overlay.layer_steps(layers, stage, n_in)
    args += l_args
    steps += l_steps
    events += [{"at": L.t0, "role": L.sfx, "kind": "callout"} for L in layers if L.sfx]
    if layers:
        print(f"scene {i:02d}: callouts " + ", ".join(
            f"{L.callout} {L.t0:.2f}-{L.t1:.2f}s" for L in layers), flush=True)

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
        events.append({"at": 0.0, "role": "chapter", "kind": "chapter"})
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


def landscape_final(lst: pathlib.Path, out: str, mix, events, runtime: float,
                    work: pathlib.Path, lf, spec: dict | None = None, spec_path=None) -> None:
    """Join the parts (video stream-copied) and finish the sound.

    The one-shots (callout sfx, verdict sounds, the chapter whoosh) are placed and thinned by
    longform_overlay.placements and rendered onto one bus WAV. With a bed: the bed looped to
    `runtime` with crossfaded seams (longform.render_bed_loop), then make_short.audio_steps --
    the Shorts' own mix: gain target - lufs, fades, sidechain duck under the voice, the bus laid
    over it un-ducked as one event at 0 s, alimiter, loudnorm to audio.master. Without a bed:
    voice + bus, alimiter, the master loudnorm (no bus: the narration alone, as before).
    """
    import dataclasses as _dc
    import longform
    import longform_overlay
    import make_short
    snd = longform_overlay.chapter_sound((spec or {}).get("landscape"),
                                         lambda src: longform_overlay.resolve_sound(src, spec_path))
    rows, notes = longform_overlay.placements(
        mix, [e for e in events if e.get("kind") == "callout"],
        [e for e in events if e.get("kind") == "verdict"],
        [e for e in events if e.get("kind") == "chapter"], snd)
    for note in notes:
        print(f"note: {note}", flush=True)
    bus = longform_overlay.render_bus(rows, runtime, work / "sfx-bus.wav")
    print(f"sfx: {len(rows)} one-shot(s) on the bus ("
          + ", ".join(f"{r['role']} {r['at']:.2f}s" for r in rows) + ")", flush=True)
    master = mix.master if mix is not None else make_short.Master()
    if mix is None or mix.bed is None:
        if bus is None:
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-c:v", "copy", "-af", make_short.loudnorm_filter(master), *LANDSCAPE_AUDIO,
                 "-movflags", "+faststart", out])
            return
        fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
             "-i", str(bus), "-filter_complex",
             f"[0:a]{fmt}[vox];[1:a]{fmt}[bus];[vox][bus]amix=inputs=2:normalize=0,"
             f"alimiter=limit=0.97,{make_short.loudnorm_filter(master)}[aout]",
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy", *LANDSCAPE_AUDIO,
             "-movflags", "+faststart", out])
        return
    bed = longform.render_bed_loop(mix.bed.src, runtime, lf.bed_crossfade, work / "bed-loop.wav",
                                   lf.bed_loop_in)
    bus_events = []
    mixed = mix
    if bus is not None:
        mixed = _dc.replace(mix, sfx=make_short.Sfx(
            src="", events=(make_short.SfxEvent(role="bus", src=str(bus), gain_db=0.0),)))
        bus_events = [{"at": 0.0, "role": "bus"}]
    ev_args, ev_indexes = make_short.event_inputs(mixed, bus_events, 2)
    steps = make_short.audio_steps(mixed, runtime=runtime, cuts=[], bed_index=1, sfx_indexes=[],
                                   events=bus_events, event_indexes=ev_indexes)
    print(f"bed: {pathlib.Path(mix.bed.src).name} looped to {runtime:.1f}s "
          f"({lf.bed_crossfade:g}s crossfades), {make_short.bed_gain_db(mix.bed.target_lufs, mix.bed.lufs):+g} dB, "
          f"ducked; master {make_short.loudnorm_filter(mix.master)}", flush=True)
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
                                          spec_brand=(spec or {}).get("brand"), lf=lf, spec=spec)
            events += [{**e, "at": round(start + e["at"], 3)} for e in sounds]
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
        landscape_final(lst, a.out, mix, events, start, b, lf, spec, a.spec)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", a.out])
    print(f"final: {a.out}  {dur_of(a.out):.1f}s  {pathlib.Path(a.out).stat().st_size/1e6:.1f} MB")

if __name__ == "__main__":
    main()
