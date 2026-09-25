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

#: The renderer's backstop on how long ONE picture may stay on screen, read by scene_beats().
#: Deliberately generous against the author-side cards.MAX_SCENE_S (3.0 s lore / 4.0 s data),
#: so it catches a spec built by something other than parksheet/cards.py rather than second-
#: guessing one that was.
#:
#: It bounds a BEAT, not a scene: a scene without `beats:` is one picture for as long as its
#: narration runs and nothing here objects, because capping that would refuse every spec that
#: already renders. The defect this change set exists to remove — day 3's 32 s still — is
#: removed by splitting the scene into beats, and this is what stops a "split" that is not one.
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

    Empty under `join: cut`. Every SCENE part's pair of fades is built here and nowhere else,
    so there is one thing to read when asking whether a scene fades. The closing CTA plate is
    the one exception, and it is one because it is not a pair: the plate ramps up from black
    and has never ramped down (nothing follows it), so main() builds its lone in-fade inline
    and drops it under `join: cut` exactly as this does.
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


def scene_beats(scene: dict) -> list:
    """One media scene's `beats:`, validated and normalised. `[]` when it has none.

    A beat is a SUB-SHOT: it shares the scene's single narration WAV and its caption cues,
    and only the picture cuts. Day 3 held one still for 32 s; the same scene as beats is
    nineteen pictures, none of them on screen for more than three seconds, against the same
    audio — which is the whole point of the key.

    What is checked here is the SHAPE, and it raises SystemExit because a malformed spec is
    the operator's problem, not an exception to catch. The media half — does each beat's file
    exist, is its motion legal for that kind of source, is its crop a crop — is checked by
    media.validate_spec(), which already asks those questions of a scene's own `src:` and can
    answer them in the same preflight pass. Both run before a frame is rendered.

    One beat is not a beat — it is the scene — and is refused rather than silently flattened,
    because ParkSheet's `_scene` already declines to emit a one-entry list, so a spec that
    carries one was built by something that did not know the contract.

    `motion` is left as the spec wrote it (possibly ""): the default depends on whether the
    beat's own `src` is a still or footage, which is resolved where the path is. Defaulting
    blind would put a zoompan on footage and freeze it.
    """
    beats = (scene or {}).get("beats")
    if not beats:
        return []
    if not isinstance(beats, list):
        raise SystemExit(f"a scene's `beats:` must be a list, got {type(beats).__name__}")
    if len(beats) < 2:
        raise SystemExit("a scene's `beats:` has one entry; one picture IS the scene. Drop "
                         "the key, or give it two.")
    out = []
    for index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            raise SystemExit(f"beats[{index}] is {type(beat).__name__}, expected a mapping")
        src = str(beat.get("src") or "").strip()
        if not src:
            raise SystemExit(f"beats[{index}] has no `src`; a beat is a picture")
        try:
            seconds = float(beat.get("seconds") or 0.0)
        except (TypeError, ValueError):
            raise SystemExit(f"beats[{index}] `seconds` must be a number, got "
                             f"{beat.get('seconds')!r}") from None
        if seconds <= 0.0:
            raise SystemExit(f"beats[{index}] has `seconds: {seconds:.2f}`; a beat is a "
                             f"picture on screen, so it needs a positive length")
        if seconds > MAX_PICTURE_S:
            raise SystemExit(
                f"beats[{index}] is {seconds:.2f}s and the renderer's backstop is "
                f"{MAX_PICTURE_S}s. One picture held longer than that is the defect this "
                f"whole change set exists to remove.")
        out.append({"src": src, "seconds": seconds,
                    "motion": str(beat.get("motion") or "").strip(),
                    "crop": dict(beat.get("crop") or {}),
                    # The PICTURE's own attribution, not the scene's: a still borrowed into a
                    # footage scene is licensed on its own line. `credit` is the short line
                    # the plate burns in (media.scene_credits); `credit_line` is the fuller
                    # one — URL, licence, modifications — that belongs in the description, and
                    # nothing reads it yet (cards.spec_credits is still unwired). Both default
                    # to "" so a spec written before the keys existed falls back to the
                    # scene's `credit:`, which is what it has always meant.
                    "credit": str(beat.get("credit") or "").strip(),
                    "credit_line": str(beat.get("credit_line") or "").strip()})
    return out


def scene_steps(scene: dict) -> list:
    """One CARD scene's `steps:`, validated and normalised. `[]` when it has none.

    A step is to a card what a beat is to a photograph: it shares the scene's single
    narration WAV and its caption cues, and only the PICTURE changes. The picture of a
    card scene is the card, so a step is not a different file -- it is the SAME card drawn
    further on, `cards.card_html(..., reveal=)`. A month of crowd scores painting itself in
    date order is eight pictures out of one data block and no photograph at all.

    `reveal` is 0.0 to 1.0 and must STRICTLY INCREASE: two steps at the same reveal are the
    same PNG twice, which is a picture change in `cuts.json` that a viewer cannot see, and
    the gate would be counting a cut that is not there.

    The LAST step must be exactly 1.0. A card scene that ended half-drawn would leave the
    payoff card unfinished on the frame the video ends on -- and on a data day that frame
    is the whole point of the video.

    Like `scene_beats`, one entry is refused rather than flattened: one picture IS the
    scene, and a spec that carries one was built by something that did not know the
    contract. And like `scene_beats` this raises SystemExit, because a malformed spec is
    the operator's problem and not an exception to catch.
    """
    steps = (scene or {}).get("steps")
    if not steps:
        return []
    if not isinstance(steps, list):
        raise SystemExit(f"a scene's `steps:` must be a list, got {type(steps).__name__}")
    if len(steps) < 2:
        raise SystemExit("a scene's `steps:` has one entry; one picture IS the scene. Drop "
                         "the key, or give it two.")
    out = []
    previous = -1.0
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise SystemExit(f"steps[{index}] is {type(step).__name__}, expected a mapping")
        if step.get("reveal") is None:
            raise SystemExit(f"steps[{index}] needs a `reveal`: how much of the card is "
                             f"drawn yet, 0.0 to 1.0")
        try:
            reveal = float(step["reveal"])
        except (TypeError, ValueError):
            raise SystemExit(f"steps[{index}] `reveal` must be a number, got "
                             f"{step.get('reveal')!r}") from None
        if not 0.0 <= reveal <= 1.0:
            raise SystemExit(f"steps[{index}] has `reveal: {reveal:g}`, and a reveal is a "
                             f"fraction of the card between 0.0 and 1.0")
        if reveal <= previous:
            raise SystemExit(
                f"steps[{index}] reveals {reveal:g} after {previous:g}; a step's reveal has "
                f"to increase. Two steps at the same reveal render the same PNG twice, "
                f"which puts a picture change in cuts.json that nobody can see.")
        previous = reveal
        try:
            seconds = float(step.get("seconds") or 0.0)
        except (TypeError, ValueError):
            raise SystemExit(f"steps[{index}] `seconds` must be a number, got "
                             f"{step.get('seconds')!r}") from None
        if seconds <= 0.0:
            raise SystemExit(f"steps[{index}] has `seconds: {seconds:.2f}`; a step is a "
                             f"picture on screen, so it needs a positive length")
        if seconds > MAX_PICTURE_S:
            raise SystemExit(
                f"steps[{index}] is {seconds:.2f}s and the renderer's backstop is "
                f"{MAX_PICTURE_S}s. One picture held longer than that is the defect this "
                f"whole change set exists to remove.")
        out.append({"reveal": reveal, "seconds": seconds})
    if out[-1]["reveal"] != 1.0:
        raise SystemExit(
            f"the last step reveals {out[-1]['reveal']:g}; a card scene has to finish drawn. "
            f"The video's last frame is its payoff frame, and half a card is not a payoff.")
    return out


def beat_spans(beats, dur: float) -> list:
    """The beats' seconds rescaled to the scene's REAL duration, summing exactly to it.

    ParkSheet writes the spec before narrate.py runs, so its `seconds` are an estimate from
    the word count. The renderer knows what the scene actually encodes to, so it is what
    makes the beats add up — otherwise a 5% estimate error compounds across nineteen beats
    into a picture that outlives its WAV, or a last beat that never gets to the screen.

    The last span absorbs the rounding rather than being rounded itself, so the sum is `dur`
    to the millisecond and the concat cannot drift against `-t`.

    MAX_PICTURE_S is re-checked HERE and not only in scene_beats(), because the estimate is
    not what reaches the screen: two beats of 3.0 s each — both inside the backstop — against
    a 20 s narration are two pictures held for 10.1 s, which is the exact defect the backstop
    exists to catch. scene_beats() cannot see it; it runs in the preflight, before narrate.py's
    durations are read. A spec that trips this is one whose beats do not cover its narration.
    """
    nominal = [float(beat["seconds"]) for beat in beats]
    if not nominal:
        return []
    total = sum(nominal) or 1.0
    spans = [round(float(dur) * value / total, 3) for value in nominal]
    spans[-1] = round(float(dur) - sum(spans[:-1]), 3)
    for index, span in enumerate(spans):
        if span > MAX_PICTURE_S:
            raise SystemExit(
                f"beats[{index}] asks for {nominal[index]:.2f}s of a {sum(nominal):.2f}s "
                f"estimate, which over this scene's real {float(dur):.2f}s is {span:.2f}s on "
                f"screen — past the renderer's {MAX_PICTURE_S}s backstop. The beats do not "
                f"cover the narration: add more of them, or lengthen the ones that are short.")
    return spans


def prepare_beats(beats, spec_path) -> list:
    """scene_beats() output -> what encode_media_scene() renders. The other half of the pair.

    Three things, and all three need the beat's FILE, which is why they cannot happen in
    scene_beats(): its `src` is spec-relative like the scene's, its default motion depends on
    whether that file is a still or footage, and a crop is meaningless on footage.

    Footage is never re-framed. `hold` is the one motion legal on both kinds, so it is the one
    that can arrive carrying a crop meant for a still, and media.ffmpeg_video_steps cannot see
    the kind of its source — it is handed a label, not a path. So the crop is dropped here,
    where the path is, rather than refused: `beats` is authored per picture and a crop that
    followed a src from a still to a clip is a re-frame nobody asked for, not a spec error.

    Returns new dicts; the spec's own are not touched.
    """
    out = []
    for beat in beats:
        beat = dict(beat)
        beat["src"] = media.resolve_src(spec_path, beat["src"])
        kind = media.media_kind(beat["src"])
        beat["motion"] = beat["motion"] or media.default_motion(kind)
        if kind == "video":
            beat["crop"] = {}
        out.append(beat)
    return out


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


def step_frames(spans, fps: int = FPS) -> list:
    """Frames per card step, summing EXACTLY to the scene's own frame count.

    The scene is `math.ceil(dur * fps)` frames -- the same number `encode_scene` hands
    zoompan -- and the steps have to partition it, because the zoom expression continues
    across them: a step that claimed more frames than it renders would restart the push
    in the wrong place.

    The last step absorbs the rounding, exactly as `beat_spans` lets the last span absorb
    it. A step reduced below one frame is a spec asking for more steps than there are
    frames, which is refused rather than rendered as a step nobody sees.
    """
    spans = [float(span) for span in spans]
    total = math.ceil(sum(spans) * int(fps))
    counts = [max(1, round(span * int(fps))) for span in spans]
    counts[-1] = total - sum(counts[:-1])
    if counts[-1] < 1:
        raise SystemExit(
            f"{len(spans)} steps do not fit in {total} frames: the last one comes out at "
            f"{counts[-1]} frames. Ask for fewer steps, or a longer scene.")
    return counts


def encode_card_steps(pngs, spans, wav, dur, crf, out, join=DEFAULT_JOIN):
    """Several renders of ONE card + one narration WAV -> an mp4. Returns `out`.

    One input and one chain per step, each ending at the delivered size, then the `concat`
    FILTER -- not the demuxer, which would mean encoding every step to its own file first.
    This is `beat_steps` for a card, and it borrows BEAT_TAIL for the same reason: concat
    demands identical size, pixel format and SAR, and BEAT_TAIL is the one place those are
    spelled.

    The PUSH IS CONTINUOUS. `encode_scene` zooms one still from 1.00 to 1.06 across the
    whole scene; a stepped card does the same, by giving step k's zoompan the zoom the
    scene had reached by then (`1.0 + frames_before * dz`) instead of starting it over. A
    card that snapped back to 1.00 at every step would read as a stutter, which is the
    opposite of what steps are for.

    The output flags are `encode_scene`'s, byte for byte, because the parts are
    concatenated with `-c:v copy`: a card scene that encoded differently would break the
    concat.
    """
    pngs = list(pngs)
    counts = step_frames(spans)
    n = math.ceil(float(dur) * FPS); zmax = 1.06; dz = (zmax - 1.0) / n
    args, steps, before = [], [], 0
    for index, (png, frames) in enumerate(zip(pngs, counts)):
        args += ["-i", str(png)]
        span = frames / FPS
        steps.append(
            f"[{index}:v]scale={RW}:{RH}:flags=lanczos,"
            f"zoompan=z='min({1.0 + before * dz:.7f}+on*{dz:.7f},{zmax})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={OUT_W}x{OUT_H}:fps={FPS},"
            f"{BEAT_TAIL}trim=duration={span:.3f},setpts=PTS-STARTPTS[c{index}]")
        before += frames
    steps.append("".join(f"[c{i}]" for i in range(len(pngs)))
                 + f"concat=n={len(pngs)}:v=1:a=0[m0]")
    steps.append(f"[m0]{fade_steps(dur, join)}format=yuv420p[v]")
    args += ["-i", str(wav)]
    steps.append(f"[{len(pngs)}:a]apad=pad_dur=2,afade=t=in:d=0.05,"
                 "aformat=sample_rates=48000:channel_layouts=stereo[a]")
    run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(steps),
         "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
         "-preset", "medium", "-crf", str(crf), "-r", str(FPS), "-color_range", "tv",
         "-bsf:v", RANGE_BSF, "-c:a", "aac", "-b:a", "128k", str(out)])
    return out


#: What every beat chain agrees on before the `concat` filter will join them, on top of the
#: RWxRH size the chains already end at.
#:
#: MEASURED, not defensive: the media-demo JPEG decodes yuvj444p and the demo clip yuv420p,
#: and concatenating those two beats is `Error reinitializing filters!`, exit 234, no output
#: file — concat demands identical size, PIXEL FORMAT and SAR, and a beats scene is the first
#: thing in this renderer that puts two different sources into one graph.
#:
#: COLOUR RANGE is the fourth thing they have to agree on and the one concat does NOT refuse:
#: a still decodes full range and footage limited, so a mixed beats scene would hand `[m0]` a
#: stream that is full range for one beat and limited for the next. The `[v]` step's
#: `out_range=tv` then converts the lot under whichever range the joined stream claims, and
#: half the beats come out with crushed or lifted blacks. `in_range=auto` reads what each beat
#: actually is and `out_range=tv` puts them all in the range every other part of the Short is
#: already in, so the conversion happens once, per beat, while they can still be told apart.
#: `format=yuv420p` is the format the finished part is written in anyway (see the `[v]` step),
#: and `setsar=1` pins the last of it: a source with a non-square SAR would otherwise join one
#: that has square pixels.
BEAT_TAIL = "scale=in_range=auto:out_range=tv,format=yuv420p,setsar=1,"


def beat_steps(beats, dur: float, fill=None, focus=(0.5, 0.5)) -> list:
    """The filter-graph chains that cut several pictures together into one `dur`-long `[m0]`.

    One input and one chain per beat, each ending at RWxRH, then the `concat` FILTER — not
    the demuxer, which would mean encoding every beat to its own file first. `concat` demands
    every input agree on size, pixel format and SAR, which is why each chain finishes on the
    render size the way a scene without beats finishes on it.

    `trim=duration=` + `setpts=PTS-STARTPTS` closes each beat. Without it `concat` inherits
    zoompan's `d=` frame count — zoompan declares the frames it MIGHT emit, not the ones it
    did — and the beats overrun: the scene runs past its WAV and `-t` guillotines the last
    ones. It rides on the end of the motion chain rather than in a step of its own so that
    every `[b<i>]` is a single linear chain from input to render size.

    Returns the chains; the caller owns the inputs, in the same order (see encode_media_scene).
    """
    steps = []
    for index, (beat, span) in enumerate(zip(beats, beat_spans(beats, dur))):
        # prepare_beats() drops this; reaching here with one means a caller built the list by
        # hand, and a silently re-framed clip is exactly what would not be noticed.
        if beat.get("crop") and media.media_kind(beat["src"]) == "video":
            raise SystemExit(
                f"beats[{index}] has a video src and a `crop:`, and footage is never "
                f"re-framed. Pass the beats through make_short.prepare_beats(), which drops "
                f"it, or take the crop off the beat.")
        size = probe_size(beat["src"])
        chains = media.ffmpeg_video_steps(
            beat["motion"], span, RW, RH, FPS,
            src_w=size[0] if size else None, src_h=size[1] if size else None,
            src_label=f"{index}:v", out_label=f"b{index}",
            fill=fill, focus=focus, crop=beat.get("crop"))
        trim = f"trim=duration={span:.3f},setpts=PTS-STARTPTS"
        # `clip` ends on exactly this trim already — it is how motion_chain bounds footage
        # that is looped at the input — so the normalisation is spliced in front of that one
        # rather than trimming an already-trimmed stream a second time. Every beat therefore
        # ends the same way, whatever its motion and whatever its source.
        body = chains[-1].removesuffix(f"[b{index}]").removesuffix(trim).rstrip(",")
        chains[-1] = f"{body},{BEAT_TAIL}{trim}[b{index}]"
        steps += chains
    steps.append("".join(f"[b{i}]" for i in range(len(beats)))
                 + f"concat=n={len(beats)}:v=1:a=0[m0]")
    return steps


def focus_notice(idx: int, fill, focus, sources) -> str | None:
    """The line that says a scene's `focus:` is aiming nothing, or None when it aims.

    `focus` aims a CROP — which column (or row) of an over-wide source survives the cover.
    The blur fill crops nothing: the whole picture is fitted INSIDE the frame over a blurred
    copy of itself, so there is no overflow to choose from and media.blur_fill_steps takes no
    focus at all. That is correct, and it is also invisible — the key is accepted by
    media.scene_fill, validated to two fractions in [0, 1], and then silently dropped, which
    is the one outcome an author cannot see in the render. So it is said out loud, once, by
    scene, in the style of the `captions: position ... overridden` notice.

    `fill` is the scene's override (None = the source's ratio decides, exactly as
    media.ffmpeg_video_steps decides it) and `sources` is every file this scene actually
    renders: its own `src`, or its beats'. One blur-filled source is enough — the focus is
    the scene's, and it aims none of that picture.

    Nothing is probed unless the scene asked for an off-centre focus, so no existing spec —
    all of which are the default centre — pays an ffprobe for this.
    """
    if tuple(focus) == (0.5, 0.5):
        return None
    if fill is None:
        sizes = [probe_size(src) or (None, None) for src in sources]
        if not any(media.wants_blur_fill(w, h) for w, h in sizes):
            return None
        why = (f"its source is wider than media.BLUR_FILL_RATIO ({media.BLUR_FILL_RATIO}), "
               f"so it blur-fills")
    elif fill != "blur":
        return None
    else:
        why = "it says `fill: blur`"
    return (f"scene {idx:02d}: focus [{focus[0]:.2f}, {focus[1]:.2f}] is aiming nothing — "
            f"{why}, which letterboxes the whole picture over a blurred copy of itself and "
            f"crops nothing for a focus to choose. Say `fill: crop` on this scene to crop to "
            f"that point instead.")


def encode_media_scene(src, motion, layers, wav, dur, crf, out, join=DEFAULT_JOIN,
                       fill=None, focus=(0.5, 0.5), beats=()):
    """One media file — or several beat sources — + layer PNGs + one WAV -> an mp4.

    The composite is three things stacked: the footage or still, put through the motion's
    filter chain; then each layer PNG - a full-frame transparent screenshot - laid over it at
    0,0; then the whole thing scaled to the delivered Short. Laying the layers at 0,0 is what
    keeps media.overlay_box / media.credit_box the single place that decides where anything
    sits, and therefore the single place that keeps clear of the attribution watermark.

    How the source fills the frame depends on its shape, which is why it is probed here: a
    landscape source is letterboxed over a blurred copy of itself instead of being cropped to
    its middle column (media.ffmpeg_video_steps). The scene may override that with `fill`, and
    aim the crop with `focus` (media.scene_fill). Either way the fill ends at RWxRH, so the
    layer geometry above is unchanged.

    `beats` (media.resolve_src'd, scene_beats-validated) cuts the picture into sub-shots over
    the same WAV: the beat sources become inputs 0..n-1, the WAV input n, the layers n+1 on,
    and beat_steps() concatenates them into the `[m0]` a single source would have produced.
    Empty — which is every existing spec — and the graph is the one it has always been, from
    the input order out.

    The output flags are encode_scene's, byte for byte, because the parts are concatenated
    with `-c:v copy`: a media scene that encoded differently would break the concat.
    """
    beats = list(beats or ())
    if beats:
        args = []
        for beat in beats:
            # Only `clip` loops, exactly as below: `hold` on footage is meant to play the
            # shot through and freeze its last frame, and a looped input never reaches tpad.
            if beat["motion"] == "clip":
                args += list(media.CLIP_INPUT_ARGS)
            args += ["-i", str(beat["src"])]
        steps = beat_steps(beats, dur, fill=fill, focus=focus)
    else:
        args = list(media.CLIP_INPUT_ARGS) if motion == "clip" else []
        args += ["-i", str(src)]
        size = probe_size(src)
        steps = media.ffmpeg_video_steps(motion, dur, RW, RH, FPS,
                                         src_w=size[0] if size else None,
                                         src_h=size[1] if size else None,
                                         fill=fill, focus=focus)
    audio = len(beats) if beats else 1
    args += ["-i", str(wav)]
    for layer in layers:
        args += ["-i", str(layer)]
    stage = "m0"
    for i, _layer in enumerate(layers):
        # eof_action=repeat (the default) holds the single PNG frame over the whole scene.
        steps.append(f"[{stage}][{i + audio + 1}:v]overlay=x=0:y=0:format=auto[m{i + 1}]")
        stage = f"m{i + 1}"
    # out_range=tv because a JPEG still decodes full-range: without it that scene encodes
    # yuvj420p while every card and sheet scene encodes yuv420p, and `-c:v copy` concat
    # would put a brightness jump at the cut.
    steps.append(f"[{stage}]scale={OUT_W}:{OUT_H}:flags=lanczos:out_range=tv,"
                 f"{fade_steps(dur, join)}format=yuv420p[v]")
    steps.append(f"[{audio}:a]apad=pad_dur=2,afade=t=in:d=0.05,"
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

    ONE plate, however many pictures the scene shows: media.credit_text() is the scene's own
    credit and its beats' own credits, deduplicated. A scene without beats gets exactly the
    string it always got, so its plate does not move.
    """
    credit = media.credit_text(scene)
    layers = []
    for name, doc in (("overlay", media.overlay_html(scene["overlay"], brand, RW, RH)
                       if scene.get("overlay") else None),
                      ("credit", media.credit_plate_html(credit, brand, RW, RH)
                       if credit else None)):
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

    The settings are recorded beside the band because the band alone cannot say what drew
    it: `size` and `position` chose the geometry, `pop` and `hook_seconds` chose the type
    and the phrasing, and a sidecar that named the PNGs without naming those could not tell
    a `large` render from a `default` one. `band` is where the captions actually LANDED
    (a full-frame card overrides `position` back to the top); `position` is what was asked.
    """
    rows = []
    for (png, start, end), win in zip(overlays, captions.word_windows(cues)):
        cue = cues[win.cue]
        rows.append({"start": round(start, 3), "end": round(end, 3), "text": cue.text,
                     "lit": cue.words[win.word].text, "png": pathlib.Path(png).name})
    return {"band": list(box), "accent": cfg.accent, "position": cfg.position,
            "size": cfg.size, "pop": cfg.pop, "hook_seconds": cfg.hook_seconds,
            "windows": rows}


def cut_plan_json(rows, join: str, total: float, extra_cuts=(), sfx=()) -> dict:
    """Where the picture changes, according to the renderer rather than to a detector.

    `scdet` cannot see our joins: it returns ZERO cuts on the published day-3 Short and on
    a hand-made hard-cut concat of two of its parts, because every part fades to black at
    its own edges and a black-meeting-black join has no discontinuity to find. So the
    authoritative list is written here, beside captions.json, and the pixel detectors stay
    what they are -- smoke tests.

    Two clocks, and they are not the same one. A row's `start` and `seconds` are ABSOLUTE
    seconds on the finished Short's timeline, measured from the encoded parts; its `beats`
    are the SPANS the renderer cut that part into — durations, summing to the part — because
    that is what beat_spans() hands the filter graph. `cuts` is the absolute list the two
    produce together: every picture change after frame 0, in time order. Each part boundary
    is one (under `join: fade` the dip to black IS the join, so it still counts), and so is
    every beat boundary INSIDE a part — which is every span but the last, whose end is the
    part boundary already counted, or the end of the video.

    `extra_cuts` is for a part that changes the picture without being a scene: today that is
    the closing CTA plate, which carries no scene index to put in a row. Its boundary is a
    picture change like any other and belongs in `cuts` — a gate that measured the last
    scene's hold as running through the plate would be measuring a picture that is not on
    screen, and can hard-fail on it. So `scenes` stays scene-only and `cuts` stays complete.

    Which means: `sum(scenes[].seconds)` is NOT `duration_s` when a plate is present — it is
    short by the plate's 1.5 s. Anything that needs the finished runtime reads the whole
    Short's length, never the row sum; the rows are where the SCENES are, not what the Short
    adds up to.

    Two spellings of that length, and they differ by up to a frame. `duration_s` here is the
    PROBED file, written after the final pass. The audio mix needs the same number one pass
    EARLIER — the bed is trimmed and faded against it, and the whooshes are placed on `cuts`
    — so main() takes the timeline length (the sum of the encoded parts, plate included) and
    builds this plan in memory before the pass that writes the file this one measures. A
    frame of difference is a bed that fades out 33 ms off; anything larger means the concat
    did not join what the timeline says it did.

    `sfx` is every SOUND EFFECT START on the same timeline (`sfx_placements`), as
    `{at, role}` rows. It is written on every render -- an empty list when there are none
    -- so a gate can tell "this render placed no sound" from "this renderer never knew
    how to say", which is the difference between a pass and a fail-closed.
    """
    cuts = [round(float(at), 3) for at in extra_cuts if float(at) > 0]
    for row in rows:
        at = float(row["start"])
        for span in row["beats"][:-1]:
            at += float(span)
            cuts.append(round(at, 3))
        if float(row["start"]) > 0:
            cuts.append(round(float(row["start"]), 3))
    return {"join": join, "duration_s": round(float(total), 3),
            "cuts": sorted(cuts), "sfx": [dict(row) for row in sfx],
            "scenes": list(rows)}


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


# --- the audio mix -------------------------------------------------------------------------
#
# There was no audio path of any kind here before 2026-09-19: the only audio filters in the
# renderer were apad, afade, aformat and the final loudnorm, and the published day-3 Short
# measured a quietest-5%-window of -88.0 dBFS with 8.8% of windows below -60. A bed is the
# cheapest continuity device there is -- it bridges the cuts and gives the whoosh something
# to land against -- and it costs 0.81 s of render time for 12.8 s of output, because the
# whole mix rides the pass that already re-encodes the audio.
#
# Absent an `audio:` block the renderer emits exactly the chain it always emitted, so every
# existing spec renders the same bytes it rendered yesterday.

#: How far bed_gain_db may push a bed before the numbers are read as a typo rather than as a
#: quiet asset. Measured beds run -13 to -29 LUFS against a -22 target, so ±30 dB is loose
#: enough to be nobody's ceiling and tight enough to catch a transposed or invented figure.
BED_GAIN_LIMIT_DB = 30.0


@dataclasses.dataclass(frozen=True)
class Bed:
    src: str
    #: The asset's measured integrated loudness, from its manifest row. NOT measured here:
    #: a one-pass loudnorm is dynamic, so the mix would depend on where the loop lands.
    lufs: float
    target_lufs: float = -22.0
    fade_in: float = 0.6
    fade_out: float = 1.2


@dataclasses.dataclass(frozen=True)
class Duck:
    #: Swept against the real voice envelope: 0.03:8 gives ~10-11 dB of duck. Under 8 dB the
    #: bed fights the voice; past 14 dB it pumps audibly under near-continuous narration.
    #: attack=5 ms catches consonant onsets; release=300 ms lets the bed back up inside a
    #: sentence gap without chattering.
    threshold: float = 0.03
    ratio: int = 8
    attack: int = 5
    release: int = 300


#: What a cue may BE. Deliberately short: sound-design section 2.2 measured every other
#: candidate and they all made the loudness range worse -- a tick on 100 caption cues took
#: it 2.2 -> 1.4 LU and drove the limiter 1.1 dB harder. The riser is the only thing that
#: moved it the other way (+0.7 LU), and the hit is what the riser is for.
SFX_ROLES: tuple[str, ...] = ("riser", "hit")

#: What a cue may key off. One timeline, because one is what there is evidence for.
CUE_TIMELINES: tuple[str, ...] = ("payoff",)


@dataclasses.dataclass(frozen=True)
class SfxCue:
    """One sound keyed to one moment, rather than to the cut cadence.

    `lead` starts it this far BEFORE the moment, so a 1.5 s riser is fully under way by
    the time the payoff frame arrives. `lead: 0` is a hit ON it.
    """
    role: str
    src: str
    on: str = "payoff"
    lead: float = 0.0
    gain_db: float = -9.0


@dataclasses.dataclass(frozen=True)
class Sfx:
    src: str
    #: -9, not the -6 this shipped with. MEASURED (sound-design section 2.4): the whoosh
    #: is -13.0 LUFS and lands near -19 at -6 dB, roughly 2 LU under the voice's -17.1 --
    #: nothing like the "12 to 18 dB below narration" of creator lore, which appears in no
    #: standard. R 128 s4's Loudness-to-Dialogue Ratio "should not exceed 5 LU": audible,
    #: never dominant. With more than one thing on the SFX bus, -9 is the safer floor.
    gain_db: float = -9.0
    #: Start the whoosh this far BEFORE the cut, so it peaks on it.
    lead: float = 0.20
    #: How many structural beats the video has. A whoosh on every cut is a cartoon; one at
    #: each of the two boundaries between three ~11 s beats is an edit.
    beats: int = 3
    #: Sounds keyed to a MOMENT rather than to the cadence. Empty on every spec written
    #: before cues existed, so the mix such a spec produces is unchanged.
    cues: tuple[SfxCue, ...] = ()


@dataclasses.dataclass(frozen=True)
class Master:
    lufs: float = -16.0
    tp: float = -1.5
    lra: int = 11


@dataclasses.dataclass(frozen=True)
class AudioMix:
    bed: Bed | None
    duck: Duck
    sfx: Sfx | None
    master: Master


def bed_gain_db(target_lufs: float, measured_lufs: float) -> float:
    """How far to push the bed: the target level minus what the file actually measures."""
    return round(float(target_lufs) - float(measured_lufs), 3)


def beat_boundaries(cuts, runtime: float, beats: int = 3) -> list:
    """The cut nearest each structural beat division. `beats` beats give `beats - 1` of them.

    Spec section 2 S13: about three beats of about eleven seconds, SFX only at the
    boundaries. A whoosh on all sixteen picture changes is not sound design, it is a
    cartoon.

    Two divisions can land on the same cut (a short Short with few cuts), and the duplicate
    is dropped rather than stacking two whooshes on one frame -- which is why the caller
    must take its input count from THIS list and not from `beats - 1`.
    """
    cuts = sorted(float(cut) for cut in cuts)
    if not cuts or beats < 2:
        return []
    out = []
    for k in range(1, int(beats)):
        target = float(runtime) * k / float(beats)
        nearest = min(cuts, key=lambda cut: abs(cut - target))
        if nearest not in out:
            out.append(nearest)
    return sorted(out)


def sfx_placements(mix, boundaries, payoff_s) -> list:
    """Every SFX START on the finished timeline, in time order. `[]` when there are none.

    The START, not the event it keys off: a whoosh at `lead` before a cut is HEARD from
    `cut - lead`, and that is the number the gate's placement and density lines (S16, S17)
    have to read. Written into cuts.json beside the picture changes, because that file is
    already the renderer's own record of what it did and a second file would be a second
    thing to keep in step.
    """
    out = []
    if mix is None or mix.sfx is None:
        return out
    for at in boundaries:
        out.append({"at": round(max(0.0, float(at) - mix.sfx.lead), 3), "role": "whoosh"})
    if payoff_s is not None:
        for cue in mix.sfx.cues:
            out.append({"at": round(max(0.0, float(payoff_s) - cue.lead), 3),
                        "role": cue.role})
    return sorted(out, key=lambda row: (row["at"], row["role"]))


def loudnorm_filter(master) -> str:
    """The master loudnorm, as an `-af` value. The one place its numbers are spelled."""
    return f"loudnorm=I={master.lufs:g}:TP={master.tp:g}:LRA={master.lra:g}"


def plain_audio_steps(master: Master) -> str:
    """The chain a spec with no `audio:` block gets — byte-identical to what it always got."""
    return f"[0:a]{loudnorm_filter(master)}[aout]"


def _only(block, known, what):
    """`block` as a plain dict, refusing any key outside `known` by name."""
    block = block or {}
    if not isinstance(block, dict):
        raise SystemExit(f"spec `audio.{what}:` must be a mapping, got {type(block).__name__}")
    unknown = set(block) - set(known)
    if unknown:
        raise SystemExit(f"unknown audio.{what} key(s) {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(known)}")
    return block


def _sfx_cues(raw, resolve) -> tuple:
    """`audio.sfx.cues:` -> a tuple of SfxCue. `()` when the spec has none.

    `resolve` is `audio_settings`'s own `resolved(name, raw)`, so a cue's file is checked
    and made absolute exactly the way the bed and the whoosh are -- a missing file refuses
    the render rather than silently dropping the sound it was supposed to make.

    One cue per role. Two risers is not a design, it is a spec written twice, and the
    second one would simply be mixed on top of the first at the same instant.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise SystemExit(f"spec `audio.sfx.cues:` must be a list, got {type(raw).__name__}")
    cues, seen = [], set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise SystemExit(f"audio.sfx.cues[{index}] is {type(entry).__name__}, "
                             f"expected a mapping")
        unknown = set(entry) - {"role", "src", "on", "lead", "gain_db"}
        if unknown:
            raise SystemExit(f"unknown audio.sfx.cues[{index}] key(s) "
                             f"{', '.join(sorted(unknown))}; known: role, src, on, lead, "
                             f"gain_db")
        role = str(entry.get("role") or "").strip()
        if not role:
            raise SystemExit(f"audio.sfx.cues[{index}] needs a `role`; known: "
                             f"{', '.join(SFX_ROLES)}")
        if role not in SFX_ROLES:
            raise SystemExit(f"audio.sfx.cues[{index}] has role {role!r}; known: "
                             f"{', '.join(SFX_ROLES)}. Sound-design section 2.2 measured "
                             f"every other candidate and they all made the loudness range "
                             f"worse.")
        if role in seen:
            raise SystemExit(f"audio.sfx.cues names {role!r} twice; one cue per role, or "
                             f"the second is simply mixed over the first at the same "
                             f"instant.")
        seen.add(role)
        if not entry.get("src"):
            raise SystemExit(f"audio.sfx.cues[{index}] ({role}) has no `src`, so there is "
                             f"no file to mix.")
        on = str(entry.get("on") or "payoff").strip()
        if on not in CUE_TIMELINES:
            raise SystemExit(f"audio.sfx.cues[{index}] fires `on: {on}`; the only timeline "
                             f"a cue may key off is {', '.join(CUE_TIMELINES)}.")
        lead = float(entry.get("lead", 0.0))
        if lead < 0:
            raise SystemExit(f"audio.sfx.cues[{index}] has `lead: {lead:g}`; a lead starts "
                             f"the sound BEFORE the moment, so it cannot be negative.")
        cues.append(SfxCue(role=role, src=resolve(f"sfx.cues[{index}]", entry),
                           on=on, lead=lead,
                           gain_db=float(entry.get("gain_db", -9.0))))
    return tuple(cues)


def audio_settings(spec: dict, spec_path):
    """The spec's `audio:` block, with every file resolved and checked. None when absent.

    A missing file REFUSES the render. It never silently drops the bed: a Short that was
    meant to carry music and came out silent is indistinguishable from one that was not,
    and the whole point of round 3 is to hear the difference.
    """
    block = (spec or {}).get("audio")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise SystemExit(f"spec `audio:` must be a mapping, got {type(block).__name__}")
    unknown = set(block) - {"bed", "duck", "sfx", "master"}
    if unknown:
        raise SystemExit(f"unknown audio key(s) {', '.join(sorted(unknown))}; "
                         f"known: bed, duck, sfx, master")

    def resolved(name, raw):
        src = raw.get("src")
        if not src:
            raise SystemExit(f"audio.{name} has no `src:`, so there is no file to mix.")
        # media.resolve_src raises (FileNotFoundError, or ValueError for a src that climbs
        # out of the spec's repo) — the render has to stop either way, but with the hint
        # about where these two files come from, because nothing downloads them.
        try:
            return str(media.resolve_src(spec_path, src))
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(
                f"audio.{name}.src does not exist: {src}\n{exc}\n"
                f"Audio is fetched BY HAND -- the code never downloads it. The picks are "
                f"Mixkit 'Forest Treasure' id 138 "
                f"(https://assets.mixkit.co/music/138/138.mp3) and Mixkit 'Cinematic whoosh "
                f"fast transition' id 1492 "
                f"(https://assets.mixkit.co/active_storage/sfx/1492/1492.wav). Put them in "
                f"media/audio/ and row them in media/manifest.yaml; see ParkSheet's RUNBOOK "
                f"'Music and SFX'.") from None

    for name in ("bed", "sfx"):
        # `bed:` with nothing under it is a spec that asked for music and would have got
        # silence. Every refusal in this function is that same rule: never silently drop it.
        if name in block and not block[name]:
            raise SystemExit(f"spec `audio.{name}:` is empty. Give it a `src:` (and, for the "
                             f"bed, its measured `lufs:`), or drop the key.")
    for name in ("sfx", "duck", "master"):
        # Each of these only means something against a bed: the whooshes are mixed onto the
        # music bus, the duck IS the bed's compressor, and the master rides the same chain.
        # Accepted and ignored, they read in a spec as applied.
        # `name in block`, not `block.get(name)`: `duck: {}` is falsy and still says, to
        # anyone reading the spec, that this Short ducks its music.
        if name in block and not block.get("bed"):
            raise SystemExit(
                f"audio.{name} without audio.bed: there is no bed-less path through the mix, "
                f"so the render would emit the plain loudnorm chain and this block would "
                f"vanish without a word. Add a `bed:`, or drop `{name}:`.")
    # Shape-checked before EITHER block touches a file: an unknown `audio.sfx` key (this is
    # what makes `cues:` need no capability probe -- GC7) must refuse the spec at preflight
    # even when `audio.bed.src` also happens to be missing, rather than lose the word "cuez"
    # behind whichever block's file check runs first.
    if block.get("sfx"):
        _only(block["sfx"], ("on_cut", "src", "gain_db", "lead", "beats", "cues"), "sfx")
    bed = None
    if block.get("bed"):
        raw = _only(block["bed"], ("src", "lufs", "target_lufs", "fade_in", "fade_out"), "bed")
        if raw.get("lufs") is None:
            raise SystemExit("audio.bed.lufs is missing. The bed's gain is target minus "
                             "measured, so an unmeasured bed has no gain. Run ParkSheet's "
                             "scripts/measure_audio_asset.py.")
        # A sign-flipped measurement is one keystroke and it is SILENT: `lufs: 13.2` for a
        # -13.2 LUFS asset makes the gain -35.2 dB, ffmpeg returns 0, and the Short ships
        # with a bed nobody can hear. ebur128 reports loudness below full scale, so the
        # measurement is always negative.
        lufs = float(raw["lufs"])
        if lufs >= 0:
            raise SystemExit(
                f"audio.bed.lufs is {lufs:g}, which cannot be a measurement: ebur128 reports "
                f"negative LUFS (loudness below full scale). A sign-flipped measurement is "
                f"silent, not loud — the gain would come out {bed_gain_db(float(raw.get('target_lufs', -22.0)), lufs):g} dB. "
                f"Use the number as ebur128 printed it, e.g. -13.2.")
        target = float(raw.get("target_lufs", -22.0))
        gain = bed_gain_db(target, lufs)
        if abs(gain) > BED_GAIN_LIMIT_DB:
            raise SystemExit(
                f"audio.bed would be gained {gain:+g} dB (target {target:g} minus measured "
                f"{lufs:g}), past the {BED_GAIN_LIMIT_DB:g} dB sanity bound. That is a typo "
                f"in one of the two numbers, not a bed: re-measure the asset with "
                f"ParkSheet's scripts/measure_audio_asset.py.")
        bed = Bed(src=resolved("bed", raw), lufs=lufs, target_lufs=target,
                  fade_in=float(raw.get("fade_in", 0.6)),
                  fade_out=float(raw.get("fade_out", 1.2)))
    sfx = None
    if block.get("sfx"):
        # `on_cut:` is the spec's own name for the file (research section 5); `src:` is
        # accepted as the spelling every other block in this renderer uses.
        raw = _only(block["sfx"], ("on_cut", "src", "gain_db", "lead", "beats", "cues"),
                    "sfx")
        beats = int(raw.get("beats", 3))
        if beats < 2:
            # `beats - 1` boundaries: one beat has none, and the whole sfx block would be
            # read, resolved, and then place nothing.
            raise SystemExit(
                f"audio.sfx.beats is {beats}, and {beats} beat{'' if beats == 1 else 's'} "
                f"ha{'s' if beats == 1 else 've'} no boundary to put a whoosh on — the SFX "
                f"would be configured and never heard. Use 2 or more (3 is the default: two "
                f"whooshes), or drop `sfx:`.")
        cues = _sfx_cues(raw.get("cues"), resolved)
        sfx = Sfx(src=resolved("sfx", {"src": raw.get("on_cut") or raw.get("src")}),
                  gain_db=float(raw.get("gain_db", -9.0)),
                  lead=float(raw.get("lead", 0.20)),
                  beats=beats,
                  cues=cues)
    duck = _only(block.get("duck"), ("threshold", "ratio", "attack", "release"), "duck")
    master = _only(block.get("master"), ("lufs", "tp", "lra"), "master")
    return AudioMix(bed=bed,
                    duck=Duck(**{k: float(v) for k, v in duck.items()}),
                    sfx=sfx,
                    master=Master(**{k: float(v) for k, v in master.items()}))


def audio_steps(mix: AudioMix, *, runtime: float, cuts, bed_index: int, sfx_indexes,
                cue_indexes=(), payoff_s=None, voice: str = "0:a") -> list:
    """The audio half of the final filter graph. Verified end to end at full scale.

    `runtime` is the FINISHED Short's length, not the sum of the scene rows: a closing CTA
    plate is 1.5 s of picture that carries no scene, so a bed trimmed to the rows would fade
    out before the plate and leave the last frames in the silence this block exists to end.

    `cue_indexes` are the inputs for `mix.sfx.cues`, in the cues' own order, and
    `payoff_s` is where the payoff frame starts -- the last scene's start on the finished
    timeline. With no payoff (a spec with no scene rows) no cue is placed: a sound with
    nowhere to land is not quietly dropped onto second zero.
    """
    master = mix.master
    if mix.bed is None:
        return [plain_audio_steps(master)]
    steps = [f"[{voice}]aformat=sample_rates=48000:channel_layouts=stereo,"
             f"asplit=2[vox][key]"]
    gain = bed_gain_db(mix.bed.target_lufs, mix.bed.lufs)
    fade_out_at = max(0.0, float(runtime) - mix.bed.fade_out)
    steps.append(
        f"[{bed_index}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"atrim=0:{float(runtime):.3f},asetpts=PTS-STARTPTS,volume={gain:g}dB,"
        f"afade=t=in:d={mix.bed.fade_in:g},"
        f"afade=t=out:st={fade_out_at:.3f}:d={mix.bed.fade_out:g}[bed]")
    steps.append(f"[bed][key]sidechaincompress=threshold={mix.duck.threshold:g}:"
                 f"ratio={mix.duck.ratio:g}:attack={mix.duck.attack:g}:"
                 f"release={mix.duck.release:g}:detection=rms[bedduck]")
    labels = ["bedduck"]
    if mix.sfx is not None and sfx_indexes:
        for n, (index, at) in enumerate(
                zip(sfx_indexes,
                    beat_boundaries(cuts, runtime, mix.sfx.beats)), start=1):
            delay = max(0, round((float(at) - mix.sfx.lead) * 1000))
            # aformat FIRST: adelay takes one delay per channel, so `adelay=2747|2747` on a
            # mono whoosh delays the one channel it has and silently discards the second
            # value. atrim and apad LAST: amix ends with its longest input, so a whoosh
            # delayed near the end would otherwise run the music bus past the last frame.
            steps.append(f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                         f"volume={mix.sfx.gain_db:g}dB,adelay={delay}|{delay},"
                         f"atrim=0:{float(runtime):.3f},"
                         f"apad=whole_dur={float(runtime):.3f}[s{n}]")
            labels.append(f"s{n}")
    if mix.sfx is not None and cue_indexes and payoff_s is not None:
        for n, (index, cue) in enumerate(zip(cue_indexes, mix.sfx.cues), start=1):
            delay = max(0, round((float(payoff_s) - cue.lead) * 1000))
            steps.append(f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                         f"volume={cue.gain_db:g}dB,adelay={delay}|{delay},"
                         f"atrim=0:{float(runtime):.3f},"
                         f"apad=whole_dur={float(runtime):.3f}[q{n}]")
            labels.append(f"q{n}")
    steps.append("".join(f"[{label}]" for label in labels)
                 + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0[music]")
    steps.append(f"[vox][music]amix=inputs=2:normalize=0,alimiter=limit=0.97,"
                 f"{loudnorm_filter(master)}[aout]")
    return steps


def audio_inputs(mix: AudioMix, boundaries, bed_index: int):
    """The extra ffmpeg `-i` arguments for the mix, and the input indexes they will take.

    `bed_index` is the next free input, counted explicitly by the caller rather than derived
    from `len(args)`: the bed carries `-stream_loop -1` in front of its own `-i`, so
    arithmetic on the argument list is off by one for it and for every whoosh after it. These
    inputs are always queued LAST — the caption pass numbers its plate and its word PNGs from
    1, and a bed in front of them would burn the wrong word onto the wrong frame.

    One whoosh input per BOUNDARY, never per `beats - 1`: two divisions of a short runtime can
    pick the same cut, and beat_boundaries drops the duplicate. Then one input per CUE, in the
    cues' own order, so `audio_steps` can zip the two lists.

    Returns (args, bed_index, sfx_indexes, cue_indexes).
    """
    args = ["-stream_loop", "-1", "-i", mix.bed.src]
    count = bed_index + 1
    sfx_indexes, cue_indexes = [], []
    if mix.sfx is not None:
        for _at in boundaries:
            sfx_indexes.append(count)
            args += ["-i", mix.sfx.src]
            count += 1
        for cue in mix.sfx.cues:
            cue_indexes.append(count)
            args += ["-i", cue.src]
            count += 1
    return args, bed_index, sfx_indexes, cue_indexes


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
    # Preflight: every media scene is checked here, before a single frame is rendered. The
    # shape of a scene's `beats:` belongs to this module (it is the render that consumes it),
    # so it is checked in the same pass rather than when the loop below reaches that scene.
    media.validate_spec(spec, spec_path)
    for _scene in spec.get("scenes") or []:
        if media.is_media(_scene or {}):
            scene_beats(_scene)
            if (_scene or {}).get("steps"):
                raise SystemExit(
                    "a `media` scene carries `steps:`, which only a `card` scene renders — "
                    "a step redraws a card further on, and a photograph has no reveal. Use "
                    "`beats:` to cut a media scene's picture.")
        elif cards.is_card(_scene or {}):
            scene_steps(_scene)
            if (_scene or {}).get("beats"):
                raise SystemExit(
                    "a `card` scene carries `beats:`, which only a `media` scene renders — "
                    "a beat cuts to a picture, and a card scene's picture is the card. Use "
                    "`steps:` to draw the card a row at a time.")
        elif (_scene or {}).get("beats") or (_scene or {}).get("steps"):
            raise SystemExit(
                f"a `{(_scene or {}).get('kind')}` scene carries `beats:` or `steps:`, and "
                f"neither key is read for this scene kind. Nothing would have read it.")
    cap = captions.settings(spec, a.captions)
    slug = slug or safe_slug(spec["slug"]); sh = select_short(spec, a.variant)
    tr = transitions(spec)
    # Preflighted here, beside every other spec block: a missing bed or whoosh file must
    # refuse the render BEFORE a scene is narrated or encoded, and it must refuse rather
    # than silently render the silence this block exists to end.
    mix = audio_settings(spec, spec_path)
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
    # A `kind: card` first scene IS the frame-0 text: it is a full-frame plate of type that
    # caption_plan already moves the caption band around. The hook plate knows nothing about
    # scene 0's layout — it places itself on captions.BAND_CENTER_FRAC — so over a card it
    # would print the Short's biggest type straight through the card's own copy. Skipped
    # rather than drawn, announced rather than silent, and NO cue is dropped: with no plate
    # up, the word-by-word captions are the hook text again.
    picked = sh.get("scenes") or []
    if plate is not None and picked and cards.is_card(spec["scenes"][picked[0]]):
        print(f"short.plate: skipped — scene {picked[0]:02d} is a full-frame card and "
              f"already carries the frame-0 text; a plate over it would print the Short's "
              f"biggest type through the card's own copy.", flush=True)
        plate = None
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
    # Probed on EVERY render, captioned or not: cuts.json below is the authoritative cut list
    # (nothing else can see a join that dips to black), and a nominal one would be a re-derivation
    # of the spec rather than a record of the render. One ffprobe a part is what that costs.
    timeline = [0.0]
    cap_scenes = []
    cut_rows = []
    cut_extras = []

    def add_part(path, idx=None, spans=()):
        """Append an encoded part, and record where it landed. `spans` are its beat lengths.

        A part with no `idx` is not a scene — it is the closing CTA plate — so it gets no row.
        It still gets its boundary into the cut list: the picture changes there whatever the
        part is called.
        """
        parts.append(path)
        seconds = dur_of(path)
        if seconds <= 0:
            # ffprobe answering nothing (a missing or unreadable part) reads as 0.0 here, and
            # a 0.0 in the timeline silently stacks every later scene on top of this one.
            raise SystemExit(f"ffprobe measured {path} at {seconds:.3f}s. Every part of the "
                             f"Short has a duration, so this is a failed probe, and the "
                             f"caption offsets and cuts.json below are built on it.")
        if idx is None:
            cut_extras.append(round(timeline[0], 3))
        else:
            cut_rows.append({"scene": idx, "start": round(timeline[0], 3),
                             "seconds": round(seconds, 3), "beats": list(spans)})
            if cap.enabled:
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
            # `scene_focus`, not `focus`: the name at this scope is the sheet pipeline's
            # frames/focus.json dict, which a later legacy scene still reads.
            fill, scene_focus = media.scene_fill(sc)
            beats = prepare_beats(scene_beats(sc), spec_path)
            note = focus_notice(idx, fill, scene_focus,
                                [beat["src"] for beat in beats] or [src])
            if note:
                print(note, flush=True)
            # The SAME spans beat_steps() trims each beat to — rescaled against the `dur` this
            # part was encoded with, not against what it probed to. Those trims are the picture
            # changes that are actually on screen, so re-deriving them from the probed duration
            # would move the cut list off the cuts (and, on a stub or a mismeasure, trip the
            # backstop against a length nothing rendered).
            spans = beat_spans(beats, dur)
            out = encode_media_scene(src, motion, layers, wav, dur, a.crf,
                                     work / f"scene_{k}.mp4", join=tr.join,
                                     fill=fill, focus=scene_focus, beats=beats)
            add_part(out, idx, spans)
            shot = f"{len(beats)} beats" if beats else f"{kind}/{motion}"
            print(f"scene {idx:02d}: media {shot} {dur:.1f}s -> {out.name}", flush=True)
            continue
        if cards.is_card(sc):
            # A card is already 9:16 — use it as the whole frame, no top/bottom banding.
            # With captions on it is boxed below the band instead: a card scene is all text,
            # so a caption over it prints text on text, and the card is the thing that moves.
            box = card_box_under_captions(RW, RH) if cap.enabled else None
            wav = build / "audio" / f"scene_{idx:02d}.wav"
            adur = float(durs.get(str(idx), 0) or dur_of(wav)); dur = adur + pad
            steps = scene_steps(sc)
            if steps:
                # The SAME spans encode_card_steps trims each step to — rescaled against
                # the `dur` this part is encoded with, exactly as a media scene's beats are.
                spans = beat_spans(steps, dur)
                pngs = []
                for s, step in enumerate(steps):
                    png = work / f"scene_{k}_step{s}.png"
                    R.render_card_scene(png, sc["template"], sc.get("data", {}),
                                        spec.get("brand"), RW, RH, html_dir=work,
                                        box=box, reveal=step["reveal"])
                    pngs.append(png)
                out = encode_card_steps(pngs, spans, wav, dur, a.crf,
                                        work / f"scene_{k}.mp4", join=tr.join)
                add_part(out, idx, spans)
                print(f"scene {idx:02d}: card {len(steps)} steps {dur:.1f}s -> {out.name}",
                      flush=True)
                continue
            png = work / f"scene_{k}.png"
            R.render_card_scene(png, sc["template"], sc.get("data", {}), spec.get("brand"),
                                RW, RH, html_dir=work, box=box)
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
        # The plate's own fade, and the ONE clause fade_steps does not build: it ramps up
        # from black and never ramps down, because it is the last frame of the Short rather
        # than a part something follows. `join: cut` means no part dips to black, and this
        # plate is a part — left in, it put the dip back at the one join most likely to be
        # watched to the end of. fade_steps(1.5, join) is NOT the way to say that: it would
        # add the fade-out this plate has never had and move every default render.
        fade = "" if tr.join == "cut" else "fade=t=in:st=0:d=0.3,"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex",
             f"[0:v]scale={RW}:{RH},zoompan=z='1':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},{fade}format=yuv420p[v]", "-map", "[v]", "-map", "1:a", "-t", "1.5",
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
    overlays = render_captions(cap_cues, cap, btokens, work, cap_box) if cap.enabled else []
    # The mix's clock. The finished Short is the sum of the parts just encoded — INCLUDING
    # the closing plate, which is a part with no scene row — so the bed's length is the
    # timeline, never `sum(row["seconds"])`, which is short by the plate's 1.5 s and would
    # fade the music out before the last picture. cuts.json below is rebuilt from the probed
    # file; the whooshes need the same list one pass earlier, so it is built here in memory.
    mixed = mix is not None and mix.bed is not None
    runtime, cuts, boundaries = timeline[0], [], []
    # The payoff frame is the START of the LAST scene. Script v2 signs off in <= 6 words
    # spoken OVER it, and mediaplan.pin_payoff puts the payoff asset on that scene, so the
    # last scene IS the payoff and a cue needs no spec key of its own to find it.
    payoff_s = cut_rows[-1]["start"] if cut_rows else None
    if mixed:
        cuts = cut_plan_json(cut_rows, tr.join, runtime, cut_extras)["cuts"]
        if mix.sfx is not None:
            boundaries = beat_boundaries(cuts, runtime, mix.sfx.beats)
    placed = sfx_placements(mix if mixed else None, boundaries, payoff_s)
    if cap.enabled and not overlays:
        # A spec that asked for captions and got none is almost always a narration problem,
        # not a caption one — and an uncaptioned Short that nobody was warned about is how a
        # broken narrate.py run reaches a publish queue. Said HERE rather than in the stream
        # copy below, because a plate keeps the filter pass alive with no window in it, and
        # that render needs the warning just as much.
        print("captions: enabled, but no scene produced a window — every selected scene "
              "was either skipped (its own layout owns the top of the frame) or has no "
              "word timings. Re-run narrate.py to write the scene_NN.words.json files; "
              + ("the hook plate is still drawn, so the pass runs for it alone."
                 if plate is not None else
                 "there is no hook plate either, so nothing is burned in at all."),
              flush=True)
    # `or plate is not None`: the plate is rendered and queued inside this branch, and it is
    # NOT caption collateral — it is the frame the feed judges. With `if overlays:` alone, a
    # Short whose narration produced no word timings lost the plate as well, silently, and
    # became the stream copy behind a warning that talked only about captions.
    if overlays or plate is not None:
        (work / "captions.json").write_text(
            json.dumps(caption_plan_json(cap_cues, overlays, cap_box, cap), indent=1),
            encoding="utf-8")
        args = [*CONCAT_INPUT_ARGS, "-f", "concat", "-safe", "0", "-i", str(lst)]
        # Every `-i` is an input index the filter graph names, so they are counted as they
        # are appended rather than derived from len(args) — the bed's `-stream_loop -1` sits
        # in front of its own `-i` and throws any arithmetic on the argument list off by one.
        inputs = 1
        plate_seconds = None
        if plate is not None:
            hp = work / "plate.html"
            hp.write_text(captions.plate_html(plate, cap.accent, btokens, OUT_W, OUT_H),
                          encoding="utf-8")
            png = work / "plate.png"
            R.screenshot(hp, png, OUT_W, OUT_H, transparent=True)
            args += ["-i", str(png)]
            inputs += 1
            plate_seconds = plate.seconds
        for png, _s, _e in overlays:
            args += ["-i", str(png)]
            inputs += 1
        steps = caption_filter(overlays, cap_box[1], plate_seconds)
        if mixed:
            extra, bed_index, sfx_indexes, cue_indexes = audio_inputs(mix, boundaries, inputs)
            args += extra
            steps.extend(audio_steps(mix, runtime=runtime, cuts=cuts, bed_index=bed_index,
                                     sfx_indexes=sfx_indexes, cue_indexes=cue_indexes,
                                     payoff_s=payoff_s))
        else:
            steps.append(plain_audio_steps(mix.master if mix is not None else Master()))
        run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(steps),
             "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium",
             "-crf", str(a.crf), "-r", str(FPS), "-color_range", "tv", "-bsf:v", RANGE_BSF,
             "-c:a", "aac", "-b:a", "160k" if mixed else "128k",
             "-movflags", "+faststart", str(final)])
        print(f"captions: {len(overlays)} word windows burned in "
              f"(accent {cap.accent}, band y={cap_box[1]}-{cap_box[3]})", flush=True)
    else:
        if mixed:
            # -c:v copy: the video is untouched, so the whole mix costs 0.81 s for 12.8 s of
            # output. This is exactly the command the filtergraph was verified with.
            extra, bed_index, sfx_indexes, cue_indexes = audio_inputs(mix, boundaries, 1)
            run(["ffmpeg", "-y", "-loglevel", "error", *CONCAT_INPUT_ARGS,
                 "-f", "concat", "-safe", "0", "-i", str(lst), *extra,
                 "-filter_complex", ";".join(
                     audio_steps(mix, runtime=runtime, cuts=cuts, bed_index=bed_index,
                                 sfx_indexes=sfx_indexes, cue_indexes=cue_indexes,
                                 payoff_s=payoff_s)),
                 "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac",
                 "-b:a", "160k", "-movflags", "+faststart", str(final)])
        else:
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy", "-af", loudnorm_filter(mix.master if mix is not None else Master()), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    total = dur_of(final)
    # Beside captions.json, and written on every render: a `scdet` pass over a Short whose
    # joins dip to black finds nothing, so this file — not a pixel detector — is what a
    # cadence check reads. Written before the length check below, because a Short that came
    # out too long is exactly the one whose cut list someone wants to look at.
    cut_plan = cut_plan_json(cut_rows, tr.join, total, cut_extras, sfx=placed)
    (work / "cuts.json").write_text(json.dumps(cut_plan, indent=1), encoding="utf-8")
    changes = len(cut_plan["cuts"])
    print(f"cuts: {changes} picture change{'' if changes == 1 else 's'} in {total:.1f}s",
          flush=True)
    if mixed:
        gain = bed_gain_db(mix.bed.target_lufs, mix.bed.lufs)
        print(f"audio: bed {pathlib.Path(mix.bed.src).name} at {gain:+g} dB "
              f"(measured {mix.bed.lufs:g} -> {mix.bed.target_lufs:g} LUFS), ducked "
              f"{mix.duck.threshold:g}:{mix.duck.ratio:g}, "
              f"{len(boundaries)} whoosh{'' if len(boundaries) == 1 else 'es'} at "
              f"{', '.join(f'{at:.2f}s' for at in boundaries) or 'no boundary'}",
              flush=True)
        if placed:
            print("audio: sfx at "
                  + ", ".join(f"{row['at']:.2f}s {row['role']}" for row in placed),
                  flush=True)
    if total > 59.5: raise SystemExit(f"Short too long: {total:.1f}s (>59 s) — pick shorter scenes")
    rev = paths.review; rev.mkdir(exist_ok=True)
    for name, t in (("t01", 1.0), ("mid", total / 2), ("end", max(0.0, total - 1.0))):
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(final), "-frames:v", "1", str(rev / f"{name}.png")])
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-show_entries", "format=duration,size", "-of", "default=nw=1", str(final)], capture_output=True, text=True).stdout.replace("\n", " ")
    print("FINAL:", final, "|", probe.strip())
if __name__ == "__main__": main()
