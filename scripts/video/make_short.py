#!/usr/bin/env python3
"""
Vertical YouTube Short (1080x1920, 30 fps, <= 59 s) composed from the existing walkthrough assets:
scene PNGs + narration WAVs + the `short:` block in marketing/video/<slug>/scenes.yaml.
  scripts/video/.venv-tts/bin/python scripts/video/make_short.py --slug asc842
  scripts/video/.venv-tts/bin/python scripts/video/make_short.py --spec /abs/path/scenes.yaml
Output: scripts/video/build/<slug>/<slug>-short.mp4 (+ short-review/*.png sample frames).
  --slug reads marketing/video/<slug>/scenes.yaml in this repo; --spec takes a scenes.yaml
  anywhere on disk (its `slug:` key names the build directory), which is how a second venture
  renders a card-only Short through this pipeline.
  --variant NAME renders the block under `shorts: {NAME: …}` instead → <slug>-short-NAME.mp4
  --captions / --no-captions override the spec's top-level `captions:` block (default: off)
All text is rendered into PNGs via HTML (this ffmpeg has no drawtext).

Word-timed ("karaoke") captions, when a spec asks for them, are burned into the TOP of the
frame in the pass that already joins the parts — that concat was a stream copy, so this is
the Short's only re-encode, loudnorm and all, rather than a second one. The rules and the
band's geometry live in scripts/video/captions.py; the per-word timings come from the
`scene_NN.words.json` narrate.py writes beside each WAV. An opt-in `short.plate:` block puts
one more transparent PNG — the hook plate — into that same pass as input 1, over the first
seconds of the Short, and drops the cues it covers.
"""
import argparse, dataclasses, html, json, math, pathlib, subprocess, sys
# yaml and PIL are imported inside the functions that use them so this module
# imports with the standard library alone (see tests/test_make_short_cards.py).
HERE = pathlib.Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); import render_sheets as R
import captions
import cards
import media
from short_variants import safe_slug, select_short, short_paths
FPS = 30; OUT_W, OUT_H = 1080, 1920; RW, RH = 1296, 2304      # render at 1.2x so zoompan never upsamples
TOP, BOT = 360, 312                                            # bands at render scale (300 / 260 at 1080 wide)
CAP_BAR = 118                                                  # caption bar height on the 2400x1350 scene PNGs
NAVY, BLUE = "#1F3864", "#2E75B6"
GRAD = f"radial-gradient(1100px 700px at 20% 10%, {BLUE} 0%, {NAVY} 45%, #0d1a33 100%)"

#: Ceiling on any single ffmpeg call. Generous — a 59 s Short encodes in well under a minute —
#: but finite: a filter graph that can never terminate (see media.check_motion) has to surface
#: as a failed render, not as a job that never returns.
RUN_TIMEOUT = 600

#: Every part's pixels are limited range, but libx264 only writes the VUI flag saying so when
#: a conversion actually happened — so a still-sourced media part came out tagged `tv` while
#: every card, sheet and footage part came out untagged. Parts are joined with `-c:v copy`, so
#: the finished Short inherited whichever tag the first part carried. This bitstream filter
#: writes the flag unconditionally, and it survives the copy.
RANGE_BSF = "h264_metadata=video_full_range_flag=0"

#: Frames held after the narration finishes, in every scene part.
#:
#: narrate.py trims the silence off both ends of each WAV and prepends narrate.LEAD_IN_S
#: (0.3 s), so the silence a viewer hears at a cut is this pad plus that lead-in. At the 0.6 s
#: this used to be, that is 0.9 s of dead air between the last word of one scene and the first
#: of the next — long enough that silencedetect flags it and the narration audibly "cuts out"
#: at every join. 0.25 + 0.3 = 0.55 s: a breath, not a gap.
#:
#: Applied to EVERY scene kind, not only `kind: media`. The arithmetic is identical — the only
#: other thing the pad covers is encode_scene's 0.3 s fade-out, which now begins 0.05 s before
#: the last word ends instead of 0.3 s after it — and a mixed Short that kept 0.6 s on its card
#: scenes would still have 0.9 s of dead air at every card-led join, which is the defect.
SCENE_PAD = 0.25

#: How two parts meet. `fade` is what every existing spec gets and must keep getting.
#:
#: Measured on the published day-3 Short: the 0.3 s fade-out of one part meeting the 0.3 s
#: fade-in of the next is a 0.55 s dip to luma 0.0, four times, plus a 0.3 s opening fade —
#: about 3.0 s of a 45.3 s video, spent at exactly the moments the eye would re-engage. It
#: also makes the file undetectable to a scene-change detector: `scdet=threshold=12` finds
#: ZERO cuts across the whole Short, because every join is black meeting black.
#:
#: `cut` drops both `fade=` clauses. The parts still encode identically and the concat
#: demuxer still stream-copies them, so nothing else in main() changes.
#: `xfade` is a known value and is REFUSED here: it cannot run over a concat demuxer (every
#: part has to become its own input with an explicit offset), and that rewrite is not in
#: this change. `xfade_offsets` below is the arithmetic it will need.
JOINS = ("cut", "fade", "xfade")
DEFAULT_JOIN = "fade"
DEFAULT_XFADE_S = 0.12
DEFAULT_XFADE_STYLE = "fade"

#: FORWARD DECLARATION — nothing reads this yet, and NO render is capped by it today. Same
#: footnote as `xfade` above: a name a later task will build on, not a check that runs.
#:
#: Task 10 (the `beats:` branch) is the intended consumer. What it is meant to become: a
#: renderer-side backstop on how long one picture may stay on screen, deliberately generous
#: against the author-side cards.MAX_SCENE_S (3.0 s lore / 4.0 s data), so that it catches a
#: spec built by something other than parksheet/cards.py. Until that lands, a spec may hold a
#: picture for as long as it likes and nothing here objects.
MAX_PICTURE_S = 6.0


@dataclasses.dataclass(frozen=True)
class Transitions:
    join: str = DEFAULT_JOIN
    #: FORWARD DECLARATIONS, like MAX_PICTURE_S above: transitions() parses and coerces these,
    #: but nothing reads them, because their only consumer is the `xfade` pass that refuses
    #: above. They are therefore unvalidated beyond the coercion — whoever builds that pass
    #: owns bounds-checking them at the same time.
    duration: float = DEFAULT_XFADE_S
    style: str = DEFAULT_XFADE_STYLE


def transitions(spec: dict) -> Transitions:
    """The spec's top-level `transitions:` block. Absent -> today's fades, exactly."""
    block = (spec or {}).get("transitions") or {}
    if not isinstance(block, dict):
        raise SystemExit(f"spec `transitions:` must be a mapping, got {type(block).__name__}")
    unknown = set(block) - {"join", "duration", "style"}
    if unknown:
        raise SystemExit(f"unknown transitions key(s) {', '.join(sorted(unknown))}; "
                         f"known: join, duration, style")
    join = str(block.get("join", DEFAULT_JOIN))
    if join not in JOINS:
        raise SystemExit(f"unknown transitions.join {join!r}; known: {', '.join(JOINS)}")
    if join == "xfade":
        raise SystemExit(
            "transitions.join: xfade needs every part as its own ffmpeg input with an "
            "explicit offset, which replaces the concat-demuxer stream copy in main(). That "
            "pass is not built yet (spec 2026-09-19-engagement-v4-design.md section 4.2, "
            "step 2). Use `join: cut` for now; xfade_offsets() is the arithmetic it needs.")
    return Transitions(join=join,
                       duration=float(block.get("duration", DEFAULT_XFADE_S)),
                       style=str(block.get("style", DEFAULT_XFADE_STYLE)))


def fade_steps(dur: float, join: str) -> str:
    """The `fade=` clauses for one part, ending in a comma so it prefixes `format=yuv420p`.

    Empty under `join: cut`. This is the ONLY place in the renderer that builds the string,
    so there is one thing to read when asking whether a part fades.
    """
    if join == "cut":
        return ""
    return f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(0.0, dur - 0.3):.3f}:d=0.3,"


def scene_pad(short: dict) -> float:
    """Frames held after the narration ends, from `short.scene_pad` or the constant.

    The silence a viewer hears at a cut is this plus the NEXT scene's narrate.LEAD_IN_S.
    At the defaults that is 0.25 + 0.3 = 0.55 s; the v4 pair (0.10 + 0.05) is 0.15 s.
    """
    value = (short or {}).get("scene_pad")
    if value is None:
        return SCENE_PAD
    pad = float(value)
    if not 0.0 < pad <= 1.0:
        raise SystemExit(f"short.scene_pad must be in (0, 1.0]; got {pad!r}. Some pad has "
                         f"to survive or the last word of every scene is clipped.")
    return pad


def xfade_offsets(durations, t: float) -> list:
    """Where each `xfade` join starts, given the part durations and one transition length.

    With durations d0..dn and transition T the running length is Lk = sum(d0..dk) - k*T, and
    the k-th join's offset is L(k-1) - T. Pure arithmetic, so the single-pass join that will
    use it has one tested thing to build on.
    """
    offsets, running = [], 0.0
    for index, duration in enumerate(list(durations)[:-1]):
        running += float(duration) - (t if index else 0.0)
        offsets.append(round(running - t, 4))
    return offsets


#: Input options for the concat in the CAPTIONED final pass, which is the only pass that runs
#: the parts through a filter graph.
#:
#: The parts are encoded separately and do not agree on the colour description libx264 writes
#: (a JPEG-sourced media part comes out untagged, a card part bt470bg, a PNG-sourced one
#: bt709) or on sample aspect ratio, so at the FIRST part boundary ffmpeg says "Reconfiguring
#: filter graph because video parameters changed" and rebuilds the graph. Every caption PNG is
#: a single-frame input that has long since hit EOF by then, so the rebuilt overlays have no
#: second input at all: captions stop dead at the end of scene 1 and never come back, with
#: ffmpeg exiting 0 and saying nothing. Measured on a real 5-scene Short, that lost 86 of 102
#: word windows.
#:
#: `-reinit_filter 0` pins the graph to the parameters the first part arrived with, which is
#: exactly what the uncaptioned `-c:v copy` concat does anyway. `-loop 1` on every caption
#: input fixes the symptom too — an input that never ends is still there after a rebuild — but
#: it costs a full PNG decode per input per frame: measured on the same Short, the final pass
#: went from 12 s to over 300 s (still unfinished), so this is the cheap end of the fix.
CONCAT_INPUT_ARGS = ("-reinit_filter", "0")

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"ffmpeg timed out after {RUN_TIMEOUT}s:\n{' '.join(map(str, cmd))}")
    if r.returncode != 0: raise SystemExit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-1500:]}")
def dur_of(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)

def probe_size(p):
    """(width, height) of a media file's first video stream, or None if ffprobe cannot say.

    None is a real answer, not an error: media.wants_blur_fill() reads it as "keep the
    cover-and-crop fill", so a source we cannot measure renders the way it always did rather
    than having its framing changed on a guess.
    """
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0:s=x", str(p)],
                         capture_output=True, text=True).stdout
    for line in (out or "").splitlines():
        parts = line.strip().split("x")
        if len(parts) == 2 and all(q.isdigit() and int(q) for q in parts):
            return int(parts[0]), int(parts[1])
    return None

def encode_scene(png, wav, dur, crf, join=DEFAULT_JOIN):
    """One still + one narration WAV -> an mp4 beside the PNG. Returns that path.

    Slow zoom to 1.06x over the whole scene, 0.3 s fades either end under the default
    `join: fade` and none at all under `join: cut` (fade_steps owns that string), audio padded
    so the last word is never clipped. Every scene kind - sheet, pan and card - encodes here.

    `-color_range tv` + RANGE_BSF tag the output limited range. The pixels always were; only
    some parts carried the tag, and the parts are concatenated with `-c:v copy`, so the
    finished Short's declared range depended on which scene was encoded first.
    """
    n = math.ceil(dur * FPS); zmax = 1.06; dz = (zmax - 1.0) / n
    vf = (f"scale={RW}:{RH}:flags=lanczos,zoompan=z='min(zoom+{dz:.7f},{zmax})':"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},"
          f"{fade_steps(dur, join)}format=yuv420p")
    out = pathlib.Path(png).with_suffix(".mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-i", str(wav),
         "-filter_complex",
         f"[0:v]{vf}[v];[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
         f"aformat=sample_rates=48000:channel_layouts=stereo[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
         "-preset", "medium", "-crf", str(crf), "-r", str(FPS), "-color_range", "tv",
         "-bsf:v", RANGE_BSF, "-c:a", "aac", "-b:a", "128k", str(out)])
    return out

def encode_media_scene(src, motion, layers, wav, dur, crf, out, join=DEFAULT_JOIN):
    """One media file + its layer PNGs + one narration WAV -> an mp4. Returns `out`.

    The composite is three things stacked: the footage or still, put through the motion's
    filter chain; then each layer PNG - a full-frame transparent screenshot - laid over it at
    0,0; then the whole thing scaled to the delivered Short. Laying the layers at 0,0 is what
    keeps media.overlay_box / media.credit_box the single place that decides where anything
    sits, and therefore the single place that keeps clear of the attribution watermark.

    How the source fills the frame depends on its shape, which is why it is probed here: a
    landscape source is letterboxed over a blurred copy of itself instead of being cropped to
    its middle column (media.ffmpeg_video_steps). Either way the fill ends at RWxRH, so the
    layer geometry above is unchanged.

    The output flags are encode_scene's, byte for byte, because the parts are concatenated
    with `-c:v copy`: a media scene that encoded differently would break the concat.
    """
    args = list(media.CLIP_INPUT_ARGS) if motion == "clip" else []
    args += ["-i", str(src), "-i", str(wav)]
    for layer in layers:
        args += ["-i", str(layer)]
    size = probe_size(src)
    steps = media.ffmpeg_video_steps(motion, dur, RW, RH, FPS,
                                     src_w=size[0] if size else None,
                                     src_h=size[1] if size else None)
    stage = "m0"
    for i, _layer in enumerate(layers):
        # eof_action=repeat (the default) holds the single PNG frame over the whole scene.
        steps.append(f"[{stage}][{i + 2}:v]overlay=x=0:y=0:format=auto[m{i + 1}]")
        stage = f"m{i + 1}"
    # out_range=tv because a JPEG still decodes full-range: without it that scene encodes
    # yuvj420p while every card and sheet scene encodes yuv420p, and `-c:v copy` concat
    # would put a brightness jump at the cut.
    steps.append(f"[{stage}]scale={OUT_W}:{OUT_H}:flags=lanczos:out_range=tv,"
                 f"{fade_steps(dur, join)}format=yuv420p[v]")
    steps.append("[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
                 "aformat=sample_rates=48000:channel_layouts=stereo[a]")
    run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(steps),
         "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
         "-preset", "medium", "-crf", str(crf), "-r", str(FPS), "-color_range", "tv",
         "-bsf:v", RANGE_BSF, "-c:a", "aac", "-b:a", "128k", str(out)])
    return out


def media_layers(scene, brand, work, k):
    """Screenshot the scene's overlay and credit plate as full-frame transparent PNGs.

    Credit last, so it is drawn on top: the two boxes never overlap, but the attribution is
    the one thing that must never end up behind anything.
    """
    layers = []
    for name, doc in (("overlay", media.overlay_html(scene["overlay"], brand, RW, RH)
                       if scene.get("overlay") else None),
                      ("credit", media.credit_plate_html(scene["credit"], brand, RW, RH)
                       if scene.get("credit") else None)):
        if doc is None:
            continue
        hp = work / f"{name}_{k}.html"; hp.write_text(doc, encoding="utf-8")
        png = work / f"{name}_{k}.png"; R.screenshot(hp, png, RW, RH, transparent=True)
        layers.append(png)
    return layers


def card_box_under_captions(width=RW, height=RH):
    """(left, top, w, h) for a `kind: card` scene when captions are on: the frame below the band.

    A card scene IS the frame, so by default its heading lands exactly where a caption goes.
    Rather than drop the captions — a card-only data Short is the case they help most — the
    CARD moves: cards.card_html already sizes its type to whatever box it is handed, so the
    card simply becomes a shorter card. The side margin is media.SAFE_X_FRAC, the one a media
    scene's plate already uses, so the two scene kinds inset their text alike.

    Derived from the UNCONSTRAINED band at its DEFAULT position and size, which is what keeps
    this from being circular. Two consequences, both deliberate: a card scene never pushes the
    top band anywhere (the clearance below it is exactly CLEARANCE_FRAC either way), and a
    card scene DOES override a `center`/`lower` band — the card owns the frame below the top
    band, so a band dropped onto it would overprint the card. caption_plan says so out loud.
    """
    top = captions.caption_box(width, height)[3] + round(height * captions.CLEARANCE_FRAC)
    x = round(width * media.SAFE_X_FRAC)
    return (x, top, int(width) - 2 * x, int(height) - top)


def scene_card_top(scene, width=OUT_W, height=OUT_H):
    """The top edge of whatever this scene draws where a caption wants to go, or None.

    A `media` scene is imagery: the top of the frame is free unless it carries a card overlay,
    and then the constraint is media.overlay_box, the same rectangle every media scene uses.
    A `kind: card` scene is moved below the band instead (card_box_under_captions), so it
    reports that box's top and constrains nothing. EVERYTHING else owns the top of the frame
    from y=0 — the legacy sheet/pan layout puts the Short's hook there — and a caption over
    one of those is text printed on text.
    """
    scene = scene or {}
    if media.is_media(scene):
        return media.overlay_box(width, height)[1] if scene.get("overlay") else None
    if cards.is_card(scene):
        return card_box_under_captions(width, height)[1]
    return 0


def caption_plan(spec, short, width=OUT_W, height=OUT_H, position="top", size="default"):
    """(the band, the scene indexes it cannot cover) for one Short.

    Captions run the length of the Short, so there is ONE band and it cannot move scene by
    scene without jumping. It is sized against the card that reaches highest among the scenes
    it can cover, and captions.caption_box shrinks or lifts it to clear that card. A scene
    that leaves no readable band at all — caption_box refuses it — is dropped from the caption
    pass rather than overprinted, and said out loud in caption_cues. A `kind: card` scene owns
    the frame below the top band, so it overrides a `center`/`lower` position outright; that
    is announced here rather than left as a band that quietly is not where the spec put it.
    """
    tops, skipped = {}, set()
    for idx in short["scenes"]:
        top = scene_card_top((spec.get("scenes") or [])[idx], width, height)
        try:
            captions.caption_box(width, height, top, position, size)
        except ValueError:
            skipped.add(idx)
        else:
            tops[idx] = top
    limits = [t for t in tops.values() if t is not None]
    box = captions.caption_box(width, height, min(limits) if limits else None, position, size)
    if position != "top" and box != captions.caption_box(width, height, None, position, size):
        carded = sorted(i for i in tops if cards.is_card((spec.get("scenes") or [])[i]))
        if carded:
            print(f"captions: position {position!r} overridden — scene(s) "
                  f"{', '.join(f'{i:02d}' for i in carded)} are full-frame cards, which are "
                  f"drawn BELOW the band, so the band stays at y={box[1]}-{box[3]} rather "
                  f"than dropping onto a card", flush=True)
    return box, skipped


def caption_cues(scenes, audio_dir, skipped=(), hook_seconds=0.0):
    """[(scene index, part start, part end)] -> the cues for the whole Short.

    `part end` is the limit each scene's captions are clamped to, so a held phrase never
    bleeds over the cut onto the next scene's footage. A scene whose provider gave no word
    timings is skipped out loud rather than silently dropped — `null` in its words.json means
    a non-English Kokoro voice or an ElevenLabs response with no alignment, and the fix
    (re-narrate, or change the voice) is not obvious from a Short that quietly has no words
    over one of its scenes.
    """
    cues = []
    for idx, start, end in scenes:
        if idx in skipped:
            print(f"scene {idx:02d}: captions skipped — this scene's own layout owns the top "
                  f"of the frame (a full-frame card, or the legacy hook band), and a caption "
                  f"there would print text over text", flush=True)
            continue
        words = captions.read_words(pathlib.Path(audio_dir) / f"scene_{idx:02d}.wav")
        if not words:
            print(f"scene {idx:02d}: no word timings — captions skipped for this scene "
                  f"(narrate.py writes scene_{idx:02d}.words.json beside the WAV)", flush=True)
            continue
        cues.extend(captions.build_cues(words, start, limit=end,
                                        hook_seconds=hook_seconds))
    return cues


def render_captions(cues, cfg, brand, work, box):
    """One transparent PNG per spoken word. Returns [(png, start, end)] in time order.

    The page is the band rather than the whole frame — ffmpeg holds one decoded RGBA frame per
    input, and at 1080x1920 a hundred-odd word PNGs is a gigabyte for pixels that are entirely
    transparent. The band's own y comes back to the overlay, so captions.caption_box is still
    the only thing that decides where a caption sits.
    """
    band_h = box[3] - box[1]
    out = []
    for n, win in enumerate(captions.word_windows(cues)):
        doc = captions.caption_html(cues[win.cue], win.word, cfg.accent, brand, OUT_W, box,
                                    pop=cfg.pop, size=cfg.size)
        hp = work / f"cap_{n:04d}.html"; hp.write_text(doc, encoding="utf-8")
        png = work / f"cap_{n:04d}.png"
        R.screenshot(hp, png, OUT_W, band_h, transparent=True)
        out.append((png, win.start, win.end))
    return out


def caption_plan_json(cues, overlays, box, cfg):
    """What was actually burned in, as a dict: the band, the accent, one row per word window.

    Written beside the parts so the pixel test over a finished Short reads the render's own
    plan instead of re-deriving it from the spec — a re-derivation can agree with a broken
    render, and it would need a YAML parser the bare `uv run --with pytest` environment does
    not have. It also answers "which word was on screen at 12.3 s?" without re-running
    anything. `overlays` came straight from word_windows(cues), so the two zip exactly.
    """
    rows = []
    for (png, start, end), win in zip(overlays, captions.word_windows(cues)):
        cue = cues[win.cue]
        rows.append({"start": round(start, 3), "end": round(end, 3), "text": cue.text,
                     "lit": cue.words[win.word].text, "png": pathlib.Path(png).name})
    return {"band": list(box), "accent": cfg.accent, "windows": rows}


def caption_filter(overlays, y, plate_seconds=None):
    """The filter graph that burns the word PNGs into the concatenated video.

    One `overlay` per word, each gated by `enable='between(t,a,b)'` — this ffmpeg build has
    no drawtext, so every pixel of text in this pipeline is a pre-rendered PNG. Input 0 is
    the concat. When a hook plate is present it is input 1 — a full-frame PNG overlaid at
    (0, 0) and gated to its own opening window — and the captions start at 2.
    """
    steps, stage, first = [], "0:v", 1
    if plate_seconds is not None:
        steps.append(f"[0:v][1:v]overlay=x=0:y=0:format=auto:"
                     f"enable='between(t,0,{plate_seconds:.2f})'[p0]")
        stage, first = "p0", 2
    for n, (_png, start, end) in enumerate(overlays, start=first):
        steps.append(f"[{stage}][{n}:v]overlay=x=0:y={y}:format=auto:"
                     f"enable='between(t,{start:.3f},{end:.3f})'[c{n}]")
        stage = f"c{n}"
    steps.append(f"[{stage}]format=yuv420p[vout]")
    return steps


def highlight_bbox(im):
    """Bounding box of the orange (#E67E22) highlight rings drawn by render_sheets, or None."""
    from PIL import ImageChops
    r, g, b = im.split(); tol = 28
    mask = r.point(lambda v: 255 if abs(v - 0xE6) < tol else 0)
    mask = ImageChops.multiply(mask, g.point(lambda v: 255 if abs(v - 0x7E) < tol else 0))
    mask = ImageChops.multiply(mask, b.point(lambda v: 255 if abs(v - 0x22) < tol else 0))
    return mask.getbbox()

def scene_html(hook, caption, img_path, fx, fy, mode="cover", pan=None):
    fit = "object-fit:cover" if mode == "cover" else "object-fit:contain;padding:28px;box-sizing:border-box"
    midbg = "#fff" if mode == "cover" else "#e8eef6"
    if pan:  # fixed magnification: image width pan['w'], positioned so the highlight sits mid-band
        fit = f"position:absolute;left:{pan['left']:.0f}px;top:{pan['top']:.0f}px;width:{pan['w']:.0f}px;height:auto;object-fit:unset"; midbg = "#fff"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{R.BASE_CSS}
html,body{{width:{RW}px;height:{RH}px;background:{NAVY}}}
.top{{position:absolute;left:0;top:0;width:{RW}px;height:{TOP}px;background:{GRAD};display:flex;flex-direction:column;justify-content:center;padding:0 64px}}
.brand{{color:#dbe7f7;font-size:30px;margin-bottom:18px}} .brand i{{width:24px;height:24px;background:#fff}}
.hook{{color:#fff;font-family:Carlito,Arial,sans-serif;font-weight:700;font-size:86px;line-height:1.08;letter-spacing:-.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.mid{{position:absolute;left:0;top:{TOP}px;width:{RW}px;height:{RH-TOP-BOT}px;overflow:hidden;background:{midbg}}}
.mid img{{{"width:100%;height:100%;" if not pan else ""}{fit};object-position:{fx*100:.1f}% {fy*100:.1f}%}}
.bot{{position:absolute;left:0;bottom:0;width:{RW}px;height:{BOT}px;background:{NAVY};border-top:10px solid {BLUE};display:flex;flex-direction:column;justify-content:center;padding:0 64px}}
.cap{{color:#fff;font-family:Carlito,Arial,sans-serif;font-weight:700;font-size:58px;line-height:1.15;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.url{{color:#a9bcd8;font-size:30px;margin-top:16px}}
</style></head><body>
<div class="top"><div class="brand"><i></i>KDesk Accounting</div><div class="hook">{html.escape(hook)}</div></div>
<div class="mid"><img src="file://{img_path}"></div>
<div class="bot"><div class="cap">{html.escape(caption)}</div><div class="url">kdeskaccounting.com</div></div>
</body></html>"""

def end_card_wanted(short, override=None):
    """Whether this Short closes on a CTA plate.

    A terminal CTA plate occupies the single highest-retention second of a Short and spends
    it on an ask. ParkSheet's script v2 (2026-09-16) replaces it with a <= 6-word sign-off
    spoken OVER the payoff frame, and its `short:` block therefore carries `hook`, `scenes`
    and `signoff` with NO `cta:` -- so a plate here would put back exactly the thing the
    sign-off removed. Every KDesk spec carries `cta:` and is unaffected.

    `override` is --end-card / --no-end-card, and wins either way.
    """
    if override is not None:
        return bool(override)
    return bool(str((short or {}).get("cta") or "").strip())

def end_html(cta, brand=None):
    """The closing CTA card.

    `brand` is a `cards.brand_tokens()` dict from the spec's `brand:` block. A spec that carries
    one signs off in its own name — a second venture's Short must not end on KDesk's tagline.
    Without it the card is byte-for-byte the KDesk outro every existing Short already uses.
    """
    if not str(cta or "").strip():
        raise KeyError(
            "short.cta is empty: there is no copy for an end plate. A spec that signs off "
            "over its payoff frame carries `signoff:` and no `cta:`, and must render with "
            "--no-end-card (which is also the default for such a spec).")
    head, _, link = cta.partition("→"); head = head.strip() or cta; link = link.strip()
    link_html = f'<div class="link">{html.escape(link)}</div>' if link else ""
    grad = GRAD if brand is None else (f"radial-gradient(1100px 700px at 20% 10%, "
                                       f"{brand['bg_alt']} 0%, {brand['bg']} 45%, {brand['bg']} 100%)")
    name = "KDesk Accounting" if brand is None else html.escape(brand["name"])
    sub = "Pure Excel · No macros · Windows &amp; Mac" if brand is None else html.escape(brand["url"])
    fg = "#fff" if brand is None else brand["fg"]
    muted = "#dbe7f7" if brand is None else brand["muted"]
    accent = "#ffd966" if brand is None else brand["accent"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{R.BASE_CSS}
html,body{{width:{RW}px;height:{RH}px;background:{grad}}}
.wrap{{position:absolute;left:0;top:0;width:{RW}px;height:{RH}px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 90px}}
.brand{{color:{muted};font-size:40px;margin-bottom:60px}} .brand i{{width:32px;height:32px;background:{fg}}}
.cta{{color:{fg};font-family:Carlito,Arial,sans-serif;font-weight:700;font-size:92px;line-height:1.12}}
.link{{color:{accent};font-family:Carlito,Arial,sans-serif;font-weight:700;font-size:58px;line-height:1.2;margin-top:44px;word-break:break-all}}
.sub{{color:{muted};font-size:40px;margin-top:56px}}
</style></head><body><div class="wrap"><div class="brand"><i></i>{name}</div><div class="cta">{html.escape(head)}</div>{link_html}<div class="sub">{sub}</div></div></body></html>"""

def main():
    # yaml and PIL are imported AFTER parse_args so `--help` needs the standard library
    # alone — tests/test_make_short_signoff.py asks the real CLI which flags it exposes, and
    # it runs in the bare `uv run --with pytest` environment, not the render venv.
    ap = argparse.ArgumentParser()
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--slug", help="render marketing/video/<slug>/scenes.yaml from this repo")
    where.add_argument("--spec", help="path to a scenes.yaml anywhere on disk; its `slug:` key "
                                      "names the build directory (use for a card-only spec)")
    ap.add_argument("--crf", type=int, default=26)
    ap.add_argument("--variant", default=None, help="named block under `shorts:` (default: legacy `short:`)")
    caps = ap.add_mutually_exclusive_group()
    caps.add_argument("--captions", dest="captions", action="store_true", default=None,
                      help="burn word-timed captions into the top of the frame, whatever the "
                           "spec's `captions:` block says")
    caps.add_argument("--no-captions", dest="captions", action="store_false",
                      help="render without captions even if the spec asks for them")
    ends = ap.add_mutually_exclusive_group()
    ends.add_argument("--end-card", dest="end_card", action="store_true", default=None,
                      help="append the closing CTA plate even if the spec has no `cta:`")
    ends.add_argument("--no-end-card", dest="end_card", action="store_false",
                      help="never append the closing CTA plate (script v2 signs off in-scene)")
    a = ap.parse_args()
    import yaml
    from PIL import Image, ImageChops
    # --slug also builds a path, so it is validated before it is used to open anything.
    slug = safe_slug(a.slug) if a.slug else None
    spec_path = pathlib.Path(a.spec).expanduser() if a.spec else REPO / "marketing/video" / slug / "scenes.yaml"
    spec = yaml.safe_load(open(spec_path))
    # Preflight: every media scene is checked here, before a single frame is rendered.
    media.validate_spec(spec, spec_path)
    cap = captions.settings(spec, a.captions)
    slug = slug or safe_slug(spec["slug"]); sh = select_short(spec, a.variant)
    tr = transitions(spec)
    pad = scene_pad(sh)
    # The hook plate rides the caption pass, so it is read HERE, beside the caption settings
    # and with the end-plate preflight below: a malformed `short.plate:` block must fail
    # before anything is rendered, not after six scenes have been narrated and encoded.
    plate = captions.plate_settings(sh)
    if plate is not None and not cap.enabled:
        raise SystemExit(
            "short.plate rides the caption pass, and this spec renders with captions off — "
            "the final join would be a stream copy with nowhere to put the overlay. Turn "
            "captions on for this spec, or drop the plate.")
    # Preflight the end plate alongside every other spec check: --end-card on a spec that
    # carries no `cta:` has no copy to put on the plate, and must say so HERE — before a
    # build directory exists, let alone six narrated and encoded scenes. end_html is pure
    # string building, so paying for it twice costs nothing.
    if end_card_wanted(sh, a.end_card):
        end_html(sh.get("cta"))
    cap_box, cap_skip = (caption_plan(spec, sh, position=cap.position, size=cap.size)
                         if cap.enabled else (None, set()))
    build = HERE / "build" / slug; paths = short_paths(build, slug, a.variant); work = paths.work; work.mkdir(parents=True, exist_ok=True)
    fj = build / "frames/focus.json"
    focus = json.load(open(fj)) if fj.exists() else {}
    dj = build / "audio" / "durations.json"
    if not dj.exists():
        raise SystemExit(
            f"no narration durations at {dj}\n"
            f"Synthesize them first:\n"
            f"  scripts/video/.venv-tts/bin/python scripts/video/narrate.py "
            f"--spec {spec_path} --out {build / 'audio'}")
    durs = json.load(open(dj))
    parts = []
    # Where each scene lands in the finished Short. Measured from the ENCODED part rather than
    # from the `dur` asked for: `-t 4.633` at 30 fps lands on a frame boundary, and one frame
    # of drift per scene is visible on a caption that is meant to light up on a syllable.
    # Probed only when captions are on — an uncaptioned render must not grow an ffprobe a scene.
    timeline = [0.0]
    cap_scenes = []

    def add_part(path, idx=None):
        parts.append(path)
        if not cap.enabled:
            return
        seconds = dur_of(path)
        if idx is not None:
            cap_scenes.append((idx, timeline[0], timeline[0] + seconds))
        timeline[0] += seconds

    ranges = {str(k): v for k, v in (sh.get("ranges") or {}).items()}
    btokens = cards.brand_tokens(spec.get("brand"))
    wbv = wbf = None
    for k, idx in enumerate(sh["scenes"]):
        sc = spec["scenes"][idx]; mode = "cover"; fx = fy = 0.5; pan = None
        if media.is_media(sc):
            # Footage or a still as the whole frame, with the card (if any) as an overlay.
            # Already validated by media.validate_spec() before any rendering began.
            src = media.resolve_src(spec_path, sc["src"]); kind = media.media_kind(src)
            motion = sc.get("motion") or media.default_motion(kind)
            layers = media_layers(sc, btokens, work, k)
            wav = build / "audio" / f"scene_{idx:02d}.wav"
            adur = float(durs.get(str(idx), 0) or dur_of(wav)); dur = adur + pad
            out = encode_media_scene(src, motion, layers, wav, dur, a.crf,
                                     work / f"scene_{k}.mp4", join=tr.join)
            add_part(out, idx)
            print(f"scene {idx:02d}: media {kind}/{motion} {dur:.1f}s -> {out.name}", flush=True)
            continue
        if cards.is_card(sc):
            # A card is already 9:16 — use it as the whole frame, no top/bottom banding.
            # With captions on it is boxed below the band instead: a card scene is all text,
            # so a caption over it prints text on text, and the card is the thing that moves.
            png = work / f"scene_{k}.png"
            R.render_card_scene(png, sc["template"], sc.get("data", {}), spec.get("brand"),
                                RW, RH, html_dir=work,
                                box=card_box_under_captions(RW, RH) if cap.enabled else None)
            wav = build / "audio" / f"scene_{idx:02d}.wav"
            adur = float(durs.get(str(idx), 0) or dur_of(wav)); dur = adur + pad
            out = encode_scene(png, wav, dur, a.crf, join=tr.join)
            add_part(out, idx); print(f"scene {idx:02d}: card {dur:.1f}s -> {out.name}", flush=True)
            continue
        if str(idx) in ranges:  # dedicated portrait-friendly render of a narrower range, trimmed to the table
            if wbv is None:
                from openpyxl import load_workbook
                rec = build / "recalc" / "src.xlsx"; wbv = load_workbook(rec, data_only=True); wbf = load_workbook(rec)
            raw = work / f"portrait_{idx:02d}.png"
            foc = R.render_sheet(wbv, wbf, sc["sheet"], ranges[str(idx)], raw, tuple(sc.get("highlight", [])), 1.0, "", spec.get("workbook_name", "Workbook.xlsx"), show_caption=False)
            px, py = foc["fx"] * R.W, foc["fy"] * R.H
            im = Image.open(raw).convert("RGB").crop((0, R.TOP_H, R.W, R.H - R.TAB_H)); ox, oy = 0, R.TOP_H
            bbox = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
            if bbox:
                x0, y0 = max(0, bbox[0] - 20), max(0, bbox[1] - 20); im = im.crop((x0, y0, min(im.width, bbox[2] + 48), min(im.height, bbox[3] + 20))); ox += x0; oy += y0
            cropped = work / f"crop_{idx:02d}.png"; im.save(cropped); mode = "pan"
            fx = (px - ox) / im.width; fy = (py - oy) / im.height
            band_w, band_h = RW, RH - TOP - BOT
            # magnify as far as 1.85x the band width, but never so far that the orange highlight ring(s) leave the band
            hb = highlight_bbox(im)
            scale = 1.85 * RW / im.width
            if hb:
                hw, hh = hb[2] - hb[0], hb[3] - hb[1]
                scale = min(scale, (band_w - 96) / max(hw, 1), (band_h - 96) / max(hh, 1)); scale = max(scale, min(1.0, RW / im.width))
                fx = ((hb[0] + hb[2]) / 2) / im.width; fy = ((hb[1] + hb[3]) / 2) / im.height
            w_img = im.width * scale; h_img = im.height * scale
            left = (band_w - w_img) / 2 if w_img <= band_w else min(0.0, max(band_w - w_img, band_w / 2 - fx * w_img))
            top = (band_h - h_img) / 2 if h_img <= band_h else min(0.0, max(band_h - h_img, band_h / 2 - fy * h_img))
            pan = {"w": w_img, "left": left, "top": top}
        else:
            src = Image.open(build / "frames" / f"scene_{idx:02d}.png"); crop = src.crop((0, 0, src.width, src.height - CAP_BAR))
            cropped = work / f"crop_{idx:02d}.png"; crop.save(cropped)
            f = focus.get(str(idx), {}); fx = min(0.72, max(0.30, float(f.get("fx", 0.5)))); fy = min(0.60, max(0.20, float(f.get("fy", 0.5)) * src.height / crop.height))
        hp = work / f"scene_{k}.html"; hp.write_text(scene_html(sh["hook"], sc.get("caption", ""), cropped.resolve(), fx, fy, mode, pan))
        png = work / f"scene_{k}.png"; R.screenshot(hp, png, RW, RH)
        wav = build / "audio" / f"scene_{idx:02d}.wav"; adur = float(durs.get(str(idx), 0) or dur_of(wav)); dur = adur + pad
        out = encode_scene(png, wav, dur, a.crf, join=tr.join)
        add_part(out, idx); print(f"scene {idx:02d}: {dur:.1f}s -> {out.name}", flush=True)
    brand = cards.brand_tokens(spec["brand"]) if spec.get("brand") else None
    if end_card_wanted(sh, a.end_card):
        hp = work / "end.html"; hp.write_text(end_html(sh.get("cta"), brand)); png = work / "end.png"; R.screenshot(hp, png, RW, RH)
        out = work / "end.mp4"; n = int(1.5 * FPS)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex",
             f"[0:v]scale={RW}:{RH},zoompan=z='1':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},fade=t=in:st=0:d=0.3,format=yuv420p[v]", "-map", "[v]", "-map", "1:a", "-t", "1.5",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", str(out)])
        add_part(out)
    lst = work / "concat.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    final = paths.final
    # Captions are burned in HERE, in the pass that was already joining the parts, rather than
    # in a second one: the concat is a stream copy today, so this is the only re-encode the
    # Short ever gets, loudnorm and all. With captions off it stays the stream copy it was.
    cap_cues = (caption_cues(cap_scenes, build / "audio", cap_skip, cap.hook_seconds)
                if cap.enabled else [])
    if plate is not None:
        # The plate IS the hook text. A word-by-word caption running underneath it puts two
        # texts on one frame, which is more than the opening second can be read at.
        cap_cues = captions.drop_inside(cap_cues, plate.seconds)
    overlays = render_captions(cap_cues, cap, cards.brand_tokens(spec.get("brand")), work,
                               cap_box) if cap.enabled else []
    if overlays:
        (work / "captions.json").write_text(
            json.dumps(caption_plan_json(cap_cues, overlays, cap_box, cap), indent=1),
            encoding="utf-8")
        args = [*CONCAT_INPUT_ARGS, "-f", "concat", "-safe", "0", "-i", str(lst)]
        plate_seconds = None
        if plate is not None:
            hp = work / "plate.html"
            hp.write_text(captions.plate_html(plate, cap.accent,
                                              cards.brand_tokens(spec.get("brand")),
                                              OUT_W, OUT_H), encoding="utf-8")
            png = work / "plate.png"
            R.screenshot(hp, png, OUT_W, OUT_H, transparent=True)
            args += ["-i", str(png)]
            plate_seconds = plate.seconds
        for png, _s, _e in overlays:
            args += ["-i", str(png)]
        steps = caption_filter(overlays, cap_box[1], plate_seconds)
        steps.append("[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
        run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(steps),
             "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium",
             "-crf", str(a.crf), "-r", str(FPS), "-color_range", "tv", "-bsf:v", RANGE_BSF,
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
        print(f"captions: {len(overlays)} word windows burned in "
              f"(accent {cap.accent}, band y={cap_box[1]}-{cap_box[3]})", flush=True)
    else:
        if cap.enabled:
            # A spec that asked for captions and got none is almost always a narration
            # problem, not a caption one — and an uncaptioned Short that nobody was warned
            # about is how a broken narrate.py run reaches a publish queue.
            print("captions: enabled, but no scene produced a window — every selected scene "
                  "was either skipped (its own layout owns the top of the frame) or has no "
                  "word timings. Re-run narrate.py to write the scene_NN.words.json files; "
                  "rendering without captions.", flush=True)
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    total = dur_of(final)
    if total > 59.5: raise SystemExit(f"Short too long: {total:.1f}s (>59 s) — pick shorter scenes")
    rev = paths.review; rev.mkdir(exist_ok=True)
    for name, t in (("t01", 1.0), ("mid", total / 2), ("end", max(0.0, total - 1.0))):
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(final), "-frames:v", "1", str(rev / f"{name}.png")])
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-show_entries", "format=duration,size", "-of", "default=nw=1", str(final)], capture_output=True, text=True).stdout.replace("\n", " ")
    print("FINAL:", final, "|", probe.strip())
if __name__ == "__main__": main()
