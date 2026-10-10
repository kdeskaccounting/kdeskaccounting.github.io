#!/usr/bin/env python3
"""
Human narration: a person's raw recording replaces TTS for one Short.

  voice: human                          # top level of scenes.yaml: the switch
  human_voice: voice/inbox/w42-08-lions-rock.wav    # absolute, or relative to the spec's repo
  # human_voice: [main.wav, main.fix1.wav]          # a list: later files are patches (see below)

  scripts/video/.venv-tts/bin/python scripts/video/human_voice.py --spec …/scenes.yaml
  scripts/video/.venv-tts/bin/python scripts/video/make_short.py  --spec …/scenes.yaml --no-end-card

human_voice.py takes the place of narrate.py for that spec and writes exactly what narrate.py
writes — `build/<slug>/audio/scene_NN.wav`, `scene_NN.words.json`, `durations.json` — so
make_short.py renders it with no other change: scene durations follow the read, the
`when: {word: …}` cues and the captions resolve against the human word timings, and the
pictures, plate, loop and mix are untouched. narrate.py refuses a `voice: human` spec (it
would overwrite the read with TTS), and make_short.py refuses to render one whose audio
directory is not a human build of THIS recording and THIS script (`audio/human.json`).

The recording (one WAV per Short, mono 48 kHz 24-bit, unprocessed, ~5 s of room tone first;
a flub is fixed by pausing and re-reading the whole sentence) goes through:

  1. denoise      DeepFilterNet 3 (an ephemeral `uv` env, pinned below); ffmpeg afftdn,
                  noise-sampled on the leading room tone, if that env cannot be built
  2. polish       high-pass 80 Hz, -2 dB at 250 Hz, +2.5 dB presence at 4 kHz, de-ess,
                  3:1 compression (ffmpeg, the chain in POLISH)
  2b. tempo       optional, `human_voice_tempo: 1.1` in the spec: a pitch-preserving speed-up
                  (ffmpeg atempo, WSOLA) of the cleaned read, BEFORE anything is transcribed
                  or cut, so the takes, word timings, gaps and scene lengths all follow the
                  faster read. 1.0 (the default) leaves the audio untouched.
  2c. breaths     quiet, unvoiced stretches (an inhale before a sentence, a gasp) are
                  replaced with the file's own room tone AFTER transcription, so the gap
                  trimmer sees them as the silences they are (BREATH_* below); `--keep-breaths`
                  turns this off
  3. transcribe   faster-whisper with word timestamps (another ephemeral `uv` env), one
                  pause-separated phrase at a time so a re-read cannot be merged into its
                  flub; words Whisper itself scores under MIN_WORD_P are dropped
  4. align        the transcript against the script's sentences, in order; where a sentence
                  was read more than once the LAST complete take is kept and every earlier
                  take, false start and stray word is cut. Missing / extra words are reported.
  5. edit         silences between sentences longer than 0.35 s become 0.30 s, pauses inside
                  a sentence longer than 0.45 s become 0.30 s (the TTS pacing); scene joins
                  land at sentence ends, sized so tail + short.scene_pad + lead-in = 0.30 s
  6. loudness     one gain for the whole read to the house narration level (HOUSE_LUFS,
                  measured on the ElevenLabs stems the gate passes), then a peak limiter
  7. verify       the finished narration is transcribed again and compared with the script

Captions keep the SCRIPT's words and spelling; only their timings come from the recording.

Patching one sentence: record just that sentence (room tone first, as always) into a second
file and list it after the main one. Each patch is aligned on its own against the whole
script, and a complete take in a later file replaces that sentence's take from an earlier one.

The pure logic (sentence splitting, normalisation, the take-keeping alignment, the gap
trimmer, the word-time mapping, the report) imports with the standard library alone, so
tests/test_human_voice.py drives it under `uv run --with pytest`. numpy/soundfile/yaml are
imported inside the functions that need them, as in narrate.py.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import difflib
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

HUMAN = "human"
MARKER = "human.json"
SR = 48000
FFMPEG = next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg")
               if os.path.exists(p)), "ffmpeg")
UV = shutil.which("uv") or "/opt/homebrew/bin/uv"

#: faster-whisper runs in an ephemeral uv env: .venv-tts does not carry it, and its CTranslate2
#: wheels have nothing to do with the render. Audio is handed over as a numpy array because
#: this version's own decoder trips over newer PyAV (`metadata_errors`).
WHISPER_ENV = ["--no-project", "--with", "faster-whisper==1.2.1"]
DEFAULT_MODEL = "medium.en"
#: Words Whisper itself gives under this probability are hallucinations in a pause or a
#: breath (measured on the stand-in: every invented word was p <= 0.03, every real one
#: p >= 0.28). They are dropped before alignment and listed in the report.
MIN_WORD_P = 0.05
#: The verification pass uses the model every ParkSheet build is already checked with.
VERIFY_MODEL = "small.en"
#: DeepFilterNet 0.5.6 needs torch/torchaudio 2.1 (it imports torchaudio.backend.common) and
#: numpy < 2, hence its own pinned env on Python 3.11.
DEEPFILTER_ENV = ["--no-project", "--python", "3.11", "--with", "deepfilternet==0.5.6",
                  "--with", "torch==2.1.2", "--with", "torchaudio==2.1.2", "--with", "numpy<2",
                  "--with", "soundfile"]
#: How far DeepFilterNet may pull the noise down. Unlimited suppression on a quiet closet
#: recording buys nothing and costs artefacts on breaths and soft consonants.
DEFAULT_ATTEN_LIM_DB = 30.0

#: The house narration level: the ElevenLabs stems of three hand builds that pass S9
#: (lions-rock -16.5, red-pavement -16.5, two-finger-point -17.1 LUFS integrated, measured
#: 2026-10-08 over the concatenated scene WAVs). The render's bed gain, duck and master
#: loudnorm were tuned against stems at this level, so the human read lands here too.
HOUSE_LUFS = -16.5
#: Sample-peak ceiling of the limiter after the gain (linear 0.79 = -2 dBFS). The master
#: loudnorm in make_short owns the true-peak figure S9 measures; this only stops the gain
#: from clipping a plosive on the way there.
PEAK_LIMIT = 0.79

#: `human_voice_tempo:` bounds. atempo itself takes 0.5-100, but a read sped up past ~1.3x stops
#: sounding like a person, and one slowed down below ~0.8x smears; outside these it is a typo.
TEMPO_MIN, TEMPO_MAX = 0.75, 1.5


def spec_tempo(spec) -> float:
    """`human_voice_tempo:` -> a float in [TEMPO_MIN, TEMPO_MAX]; 1.0 when it is not set."""
    raw = (spec or {}).get("human_voice_tempo")
    if raw in (None, ""):
        return 1.0
    try:
        tempo = float(raw)
    except (TypeError, ValueError):
        raise SystemExit(f"human_voice_tempo must be a number, got {raw!r}")
    if not (TEMPO_MIN <= tempo <= TEMPO_MAX):
        raise SystemExit(f"human_voice_tempo {tempo:g} is outside {TEMPO_MIN:g}-{TEMPO_MAX:g} "
                         f"(1.1 = 10% faster, pitch unchanged)")
    return tempo


def tempo_filter(tempo: float) -> str | None:
    """The ffmpeg filter for a pitch-preserving tempo change, or None for 1.0 (no-op)."""
    if abs(tempo - 1.0) < 1e-6:
        return None
    return f"atempo={tempo:.6g}"


#: Breaths. An inhale sits 25-35 dB under the voice, above the VAD threshold (loud - 35 dB), so
#: without this it is "speech" and no gap around it is ever trimmed (measured on Stephen's
#: W42 lions-rock read: one 7.3 s island across four sentences, 2.4 s of inhales in it).
#: A breath is a run of frames more than BREATH_DB under the loud speech level AND unvoiced
#: (no pitch), at least BREATH_MIN_S long; BREATH_GUARD_S at each end is left alone so a
#: soft onset or a decaying word tail is never clipped. Weak fricatives (f, th) are shorter
#: than the minimum; sibilants are louder than the ceiling.
BREATH_DB = 22.0
#: Outside every transcript word the bar is lower: an inhale between sentences measured
#: loud - 17 dB on the W42 reads (louder than the in-word bar, voiced or not), and no word
#: is there to protect. Sibilant onsets ("So") sit at loud - 3..6 dB, far above it.
BREATH_DB_OUTSIDE = 15.0
BREATH_MIN_S = 0.15
BREATH_GUARD_S = 0.04
BREATH_VOICED = 0.45      # normalised autocorrelation peak (70-350 Hz) that counts as voiced


def breath_spans(db, voiced, loud: float, floor: float, hop: float = 0.01,
                 below: float = BREATH_DB, min_len: float = BREATH_MIN_S,
                 guard: float = BREATH_GUARD_S, in_word=None,
                 below_outside: float = BREATH_DB_OUTSIDE) -> list[tuple[float, float]]:
    """Per-frame dB and voicing -> the (start, end) seconds to replace with room tone.

    A frame is breath-like if it is unvoiced and under `loud - below`, or (when `in_word`
    says no transcript word covers it) under `loud - below_outside`, voiced or not. A run
    of breath-like frames (silence frames included, so a breath with a gap in it is one
    run) counts if it is at least `min_len` long and some of it is above `floor` (else it
    is plain silence already). `guard` at each end is left alone.
    """
    ceiling, outside = loud - below, loud - below_outside

    def breathy(k):
        if in_word is not None and not in_word[k] and db[k] < outside:
            return True
        return db[k] < ceiling and not voiced[k]

    out, k, n = [], 0, len(db)
    while k < n:
        if breathy(k):
            j = k
            while j < n and breathy(j):
                j += 1
            a, b = k * hop, j * hop
            if b - a >= min_len and any(db[x] > floor for x in range(k, j)):
                a2, b2 = a + guard, b - guard
                if b2 - a2 > 0.02:
                    out.append((round(a2, 3), round(b2, 3)))
            k = j
        else:
            k += 1
    return out


#: ffmpeg polish chain, applied to the denoised file before anything is cut. Gentle on
#: purpose: a Yeti in a closet is already close and dry; this is clean-up, not a sound.
POLISH = ",".join([
    "highpass=f=80:poles=2",
    "equalizer=f=250:t=q:w=1.0:g=-2",       # closet boxiness
    "equalizer=f=4000:t=q:w=0.9:g=2.5",     # presence
    "deesser=i=0.4:m=0.5:f=0.5:s=o",
    "acompressor=threshold=-24dB:ratio=3:attack=5:release=120:knee=4:makeup=2",
])


@dataclasses.dataclass(frozen=True)
class Pacing:
    """The edit's timing rules, in seconds. Defaults match the ElevenLabs hand builds."""
    sentence_limit: float = 0.35    # a gap between sentences longer than this ...
    sentence_target: float = 0.30   # ... becomes this
    pause_limit: float = 0.45       # a pause inside a sentence longer than this ...
    pause_target: float = 0.30      # ... becomes this
    scene_gap: float = 0.30         # silence heard at a scene join: tail + pad + lead-in
    last_tail: float = 0.30         # after the final word of the Short
    edge_fade: float = 0.004        # fade at every piece edge, against clicks


def spec_pacing(spec, base: Pacing = Pacing()) -> Pacing:
    """`human_voice_pacing: {sentence_gap: s, pause: s}` -> a Pacing.

    sentence_gap is the silence between sentences AND at a scene join (tail + pad + lead-in);
    any longer gap in the read becomes it. pause is the same for a pause inside a sentence
    (a pause up to pause + 0.15 s is kept as read). Unset keys keep the defaults.
    """
    cfg = (spec or {}).get("human_voice_pacing") or {}
    unknown = set(cfg) - {"sentence_gap", "pause"}
    if unknown:
        raise SystemExit(f"human_voice_pacing: unknown key(s) {sorted(unknown)} "
                         f"(sentence_gap, pause)")
    out = base
    if cfg.get("sentence_gap") is not None:
        gap = float(cfg["sentence_gap"])
        if not 0.1 <= gap <= 0.6:
            raise SystemExit(f"human_voice_pacing.sentence_gap {gap:g} is outside 0.1-0.6 s")
        out = dataclasses.replace(out, sentence_target=gap, scene_gap=gap,
                                  sentence_limit=min(out.sentence_limit, gap + 0.05))
    if cfg.get("pause") is not None:
        pause = float(cfg["pause"])
        if not 0.05 <= pause <= 0.6:
            raise SystemExit(f"human_voice_pacing.pause {pause:g} is outside 0.05-0.6 s")
        out = dataclasses.replace(out, pause_target=pause,
                                  pause_limit=min(out.pause_limit, pause + 0.15))
    return out


# =============================================================================== the switch

def is_human(spec) -> bool:
    """Does this spec ask for a human read (`voice: human`)?"""
    return str((spec or {}).get("voice") or "").strip().lower() == HUMAN


def human_sources(spec: dict, spec_path) -> list[pathlib.Path]:
    """`human_voice:` -> existing absolute paths, main recording first, patches after."""
    raw = spec.get("human_voice")
    if not raw:
        raise SystemExit("this spec says `voice: human` but has no `human_voice:` — name the "
                         "recording (absolute, or relative to the spec's repository root)")
    items = raw if isinstance(raw, list) else [raw]
    import media  # stdlib-only module; repo_root is the rule media `src:` paths follow
    root = media.repo_root(spec_path)
    out = []
    for item in items:
        path = pathlib.Path(str(item)).expanduser()
        path = path if path.is_absolute() else root / path
        if not path.is_file():
            raise SystemExit(f"human_voice {item!r} does not exist (looked for {path})")
        out.append(path.resolve())
    return out


def selected_scenes(spec: dict) -> list[int]:
    """The scene indices the Short plays, in order (`short.scenes`), else every scene."""
    short = spec.get("short") or {}
    picked = short.get("scenes")
    return list(picked) if picked else list(range(len(spec.get("scenes") or [])))


def narration_tokens(scene: dict) -> list[str]:
    """One scene's narration as display tokens, split exactly as narrate.py splits it."""
    return " ".join(str((scene or {}).get("narration") or "").split()).split()


def script_digest(spec: dict) -> str:
    """What the captions will say: the selected scenes' narration, in order."""
    text = "\n".join(" ".join(narration_tokens(spec["scenes"][i])) for i in selected_scenes(spec))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def file_digest(path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_audio(spec: dict, spec_path, audio_dir) -> None:
    """make_short.py's guard. Raises SystemExit when the audio does not match the spec.

    A `voice: human` spec renders only from a human build of the same recording(s) and the
    same script; a TTS spec refuses a directory a human build last wrote (narrate.py removes
    the marker when it re-synthesises, so this only fires if nobody re-narrated).
    """
    audio_dir = pathlib.Path(audio_dir)
    marker = audio_dir / MARKER
    command = (f"scripts/video/.venv-tts/bin/python scripts/video/human_voice.py "
               f"--spec {spec_path}")
    if not is_human(spec):
        if marker.exists():
            raise SystemExit(f"{audio_dir} holds a HUMAN read ({MARKER}), but this spec is "
                             f"TTS. Re-run narrate.py for it, or set `voice: human`.")
        return
    try:
        stored = json.loads(marker.read_text())
    except (OSError, ValueError):
        raise SystemExit(f"this spec is `voice: human`, but {audio_dir} is not a human build "
                         f"(no readable {MARKER}). Build the narration first:\n  {command}")
    sources = human_sources(spec, spec_path)
    want = [file_digest(p) for p in sources]
    if stored.get("source_sha1") != want:
        raise SystemExit(f"the human narration in {audio_dir} was built from a different "
                         f"recording than `human_voice:` names now. Rebuild it:\n  {command}")
    if abs(float(stored.get("tempo", 1.0)) - spec_tempo(spec)) > 1e-6:
        raise SystemExit(f"the human narration in {audio_dir} was built at tempo "
                         f"{float(stored.get('tempo', 1.0)):g}, but the spec now says "
                         f"human_voice_tempo {spec_tempo(spec):g}. Rebuild it:\n  {command}")
    if stored.get("script_sha1") != script_digest(spec):
        raise SystemExit(f"the narration text changed after the human narration was built; "
                         f"the captions would not match the voice. Rebuild it (and re-record "
                         f"the changed sentence if the words differ):\n  {command}")


# ============================================================================== text: pure

_SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*$")


def sentence_spans(tokens: list[str]) -> list[tuple[int, int]]:
    """Display tokens -> [start, end) token spans, one per sentence (ends on . ! or ?)."""
    spans, start = [], 0
    for i, token in enumerate(tokens):
        if _SENTENCE_END.search(token):
            spans.append((start, i + 1))
            start = i + 1
    if start < len(tokens):
        spans.append((start, len(tokens)))
    return spans


_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


def _pieces(token: str) -> list[str]:
    """One display token -> its normalised word(s): lower case, hyphens split, punctuation
    and apostrophes dropped ("I'd" -> "id", "'55" -> "55", "27,000" -> "27000")."""
    token = token.lower().replace("’", "'").replace("‘", "'")
    out = []
    for part in re.split(r"[-–—/]+", token):
        word = re.sub(r"[^a-z0-9]", "", part)
        if word:
            out.append(word)
    return out


def _parse_number(words: list[str], i: int) -> tuple[int, int | None]:
    """Longest run of spelled-out number words at `i` -> (end index, value) or (i, None).

    "a hundred and sixty" -> 160, "twenty seven thousand" -> 27000, "fifty five" -> 55.
    """
    total, current, k, end, last = 0, 0, i, i, None
    n = len(words)
    while k < n:
        w = words[k]
        if w == "a" and k == i and k + 1 < n and words[k + 1] in ("hundred", "thousand", "million"):
            current, last, k = 1, "unit", k + 1
            continue
        if w == "and" and end > i and k + 1 < n and (words[k + 1] in _UNITS or words[k + 1] in _TENS):
            k += 1
            continue
        if w in _UNITS and last not in ("unit", "teen"):
            value = _UNITS[w]
            if last == "ten" and value >= 10:
                break
            current += value
            last = "teen" if value >= 10 else "unit"
        elif w in _TENS and last not in ("unit", "teen", "ten"):
            current += _TENS[w]
            last = "ten"
        elif w == "hundred" and last in ("unit", "teen", "ten") and current % 100:
            current *= 100
            last = "hundred"
        elif w in ("thousand", "million") and last is not None:
            total += max(current, 1) * _SCALES[w]
            current, last = 0, "scale"
        else:
            break
        k += 1
        end = k
    if end == i:
        return i, None
    return end, total + current


def normalise(tokens: list[str]) -> list[tuple[str, tuple[int, ...]]]:
    """Display tokens -> [(normalised word, (display token indices it came from))].

    Spelled-out numbers fold into digits so "a hundred and sixty" in the script meets the
    "160" Whisper writes. Applied identically to the script and the transcript.
    """
    flat = [(w, i) for i, token in enumerate(tokens) for w in _pieces(token)]
    words = [w for w, _ in flat]
    out, k = [], 0
    while k < len(flat):
        end, value = _parse_number(words, k)
        if value is not None:
            out.append((str(value), tuple(sorted({flat[j][1] for j in range(k, end)}))))
            k = end
        else:
            out.append((flat[k][0], (flat[k][1],)))
            k += 1
    return out


_DIGIT_GROUP = re.compile(r"^,\d{3}\b")


def merge_digit_groups(words: list[dict]) -> list[dict]:
    """Whisper writes "27,000" as two timed words, "27" and ",000"; put them back together
    so the number meets the script's "twenty-seven thousand" as one word, and both of its
    caption tokens are timed across the whole of it."""
    out: list[dict] = []
    for w in words:
        text = str(w.get("text", "")).strip()
        if (out and _DIGIT_GROUP.match(text)
                and re.search(r"\d$", str(out[-1].get("text", "")).strip())):
            prev = dict(out[-1])
            prev["text"] = str(prev["text"]).strip() + text
            prev["end"] = w.get("end", prev.get("end"))
            out[-1] = prev
        else:
            out.append(w)
    return out


def sub_cost(a: str, b: str) -> float:
    """Cost of hearing `b` where the script says `a`: 0 if equal, near 0 if spelled alike."""
    if a == b:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return min(1.0, round((1.0 - ratio) * 1.5, 4))


def edit_table(heard: list[str], script: list[str]) -> list[list[float]]:
    """Word-level Levenshtein table D[r][p]: heard[:r] against script[:p]."""
    rows, cols = len(heard) + 1, len(script) + 1
    table = [[0.0] * cols for _ in range(rows)]
    for p in range(1, cols):
        table[0][p] = float(p)
    for r in range(1, rows):
        table[r][0] = float(r)
        for p in range(1, cols):
            table[r][p] = min(table[r - 1][p] + 1.0, table[r][p - 1] + 1.0,
                              table[r - 1][p - 1] + sub_cost(script[p - 1], heard[r - 1]))
    return table


def align_ops(heard: list[str], script: list[str]) -> list[tuple[str, int | None, int | None]]:
    """The edit script heard -> script: ("ok"|"sub", si, hi), ("del", si, None) for a script
    word not heard, ("ins", None, hi) for a heard word not in the script."""
    table = edit_table(heard, script)
    r, p, ops = len(heard), len(script), []
    while r > 0 or p > 0:
        if r > 0 and p > 0 and math.isclose(
                table[r][p], table[r - 1][p - 1] + sub_cost(script[p - 1], heard[r - 1])):
            ops.append(("ok" if script[p - 1] == heard[r - 1] else "sub", p - 1, r - 1))
            r, p = r - 1, p - 1
        elif p > 0 and math.isclose(table[r][p], table[r][p - 1] + 1.0):
            ops.append(("del", p - 1, None))
            p -= 1
        else:
            ops.append(("ins", None, r - 1))
            r -= 1
    return ops[::-1]


# ======================================================================= alignment: pure

@dataclasses.dataclass(frozen=True)
class Costs:
    junk: float = 0.9       # a word in no take (cut); under an insertion, so edge strays go
    abandon: float = 0.5    # a false start: a take that stops partway through
    retake: float = 0.3     # reading an already-read sentence again in full
    skip: float = 1.0       # per word of a sentence that was never read
    lookback: int = 2       # how many sentences back a full re-read may reach


@dataclasses.dataclass
class Take:
    sentence: int
    start: int              # transcript word index, inclusive
    end: int                # exclusive
    complete: bool
    cost: float


def align_script(heard: list[str], script: list[list[str]], costs: Costs = Costs(),
                 skip_cost: float | None = None) -> list[Take]:
    """Segment the transcript into takes of the script's sentences, in reading order.

    `heard` is the normalised transcript, `script` the normalised sentences. Every heard
    word is either inside a take or junk. A take is COMPLETE (the whole sentence, give or
    take misreadings) or ABANDONED (a false start: it matches a prefix and stops). Moving on
    to sentence i happens only through a complete take of it (or by skipping it, at
    `skip_cost` a word); after that, a complete re-read of any of the `lookback` previous
    sentences is a retake. The minimum-cost segmentation wins. Which take is KEPT is
    `kept_takes`' job: the last complete one per sentence.

    `skip_cost=0` aligns a patch file, which may hold any subset of the sentences.
    """
    skip = costs.skip if skip_cost is None else skip_cost
    m, n = len(heard), len(script)
    inf = float("inf")
    best = [[inf] * (n + 1) for _ in range(m + 1)]
    back: list[list[tuple | None]] = [[None] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    tables: dict[tuple[int, int], list[list[float]]] = {}

    def table(j: int, s: int) -> list[list[float]]:
        key = (j, s)
        if key not in tables:
            length = len(script[s])
            tables[key] = edit_table(heard[j:j + length + 3 + length // 3], script[s])
        return tables[key]

    def relax(j2, i2, value, link):
        if value < best[j2][i2] - 1e-9:
            best[j2][i2] = value
            back[j2][i2] = link

    for j in range(m + 1):
        for i in range(n + 1):
            here = best[j][i]
            if here == inf:
                continue
            if i < n:   # never read: skip it
                relax(j, i + 1, here + skip * len(script[i]), (j, i, "skip", i, None))
            if j == m:
                continue
            relax(j + 1, i, here + costs.junk, (j, i, "junk", None, None))
            candidates = [(s, s == i) for s in range(max(0, i - costs.lookback), min(i + 1, n))]
            for s, forward in candidates:
                tab = table(j, s)
                length = len(script[s])
                for r in range(1, len(tab)):
                    full = tab[r][length]
                    if forward:
                        relax(j + r, i + 1, here + full, (j, i, "take", s, True))
                    else:
                        relax(j + r, i, here + full + costs.retake, (j, i, "take", s, True))
                    if length > 1 and r <= length:
                        partial = min(tab[r][1:length])
                        relax(j + r, i, here + partial + costs.abandon, (j, i, "take", s, False))
    takes: list[Take] = []
    j, i = m, n
    while (j, i) != (0, 0):
        link = back[j][i]
        if link is None:
            raise RuntimeError("alignment found no path")  # cannot happen: junk + skip always do
        pj, pi, kind, s, complete = link
        if kind == "take":
            tab = table(pj, s)
            r = j - pj
            cost = tab[r][len(script[s])] if complete else min(tab[r][1:len(script[s])])
            takes.append(Take(sentence=s, start=pj, end=j, complete=complete, cost=cost))
        j, i = pj, pi
    return takes[::-1]


def kept_takes(takes: list[Take], sentences: int) -> list[Take | None]:
    """The take each sentence keeps: its LAST complete take, else None (never read whole)."""
    kept: list[Take | None] = [None] * sentences
    for take in takes:
        if take.complete:
            kept[take.sentence] = take
    return kept


# ===================================================================== the report: pure

def take_report(script_tokens: list[str], script_norm: list[tuple[str, tuple]],
                heard_words: list[str]) -> dict:
    """Missing / extra / misheard words for one kept take, in the SCRIPT's own spelling."""
    ops = align_ops(heard_words, [w for w, _ in script_norm])
    missing, extra, heard_as = [], [], []
    for kind, si, hi in ops:
        if kind == "del":
            missing.append(" ".join(script_tokens[k] for k in script_norm[si][1]))
        elif kind == "ins":
            extra.append(heard_words[hi])
        elif kind == "sub":
            shown = " ".join(script_tokens[k] for k in script_norm[si][1])
            if sub_cost(script_norm[si][0], heard_words[hi]) >= 0.6:
                missing.append(shown)
                extra.append(heard_words[hi])
            else:
                heard_as.append(f"{shown} -> {heard_words[hi]}")
    return {"missing": missing, "extra": extra, "heard_as": heard_as, "ops": ops}


def word_error_rate(script: list[str], heard: list[str]) -> float:
    """Plain WER (substitutions count whole), for the verification pass."""
    if not script:
        return 0.0 if not heard else 1.0
    ops = align_ops(heard, script)
    errors = sum(1 for kind, _, _ in ops if kind != "ok")
    return round(errors / len(script), 4)


# ============================================================ timing and the edit: pure

def token_times(n_tokens: int, script_norm: list[tuple[str, tuple]], ops,
                heard_times: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Source-time (start, end) for every display token of one sentence.

    A normalised word that was heard takes its transcript word's times; several display
    tokens sharing one (a spelled-out number) split its span by length; a token never heard
    is interpolated between its neighbours, so a caption still lights up in order.
    """
    spans: list[tuple[float, float] | None] = [None] * len(script_norm)
    for kind, si, hi in ops:
        if kind in ("ok", "sub") and si is not None:
            spans[si] = heard_times[hi]
    times: list[list[float] | None] = [None] * n_tokens
    for si, (_, owners) in enumerate(script_norm):
        span = spans[si]
        if span is None:
            continue
        start, end = span
        owners = list(owners)
        width = (end - start) / len(owners)
        for k, token in enumerate(owners):
            a, b = start + k * width, start + (k + 1) * width
            if times[token] is None:
                times[token] = [a, b]
            else:
                times[token] = [min(times[token][0], a), max(times[token][1], b)]
    known = [k for k, t in enumerate(times) if t is not None]
    if not known:
        raise ValueError("no word of this sentence was heard")
    out: list[tuple[float, float]] = []
    for k in range(n_tokens):
        if times[k] is not None:
            out.append((times[k][0], times[k][1]))
            continue
        before = max((x for x in known if x < k), default=None)
        after = min((x for x in known if x > k), default=None)
        lo = times[before][1] if before is not None else times[after][0]
        hi = times[after][0] if after is not None else times[before][1]
        gap_tokens = ((after if after is not None else n_tokens) -
                      (before if before is not None else -1) - 1)
        slot = (k - (before if before is not None else -1) - 1)
        width = max(hi - lo, 0.0) / max(gap_tokens, 1)
        out.append((lo + slot * width, lo + (slot + 1) * width))
    return out


def gap_length(source_gap: float, between_sentences: bool, pacing: Pacing = Pacing()) -> float:
    """The silence the edit keeps for a gap of `source_gap` seconds in the read.

    Only LONG silences are trimmed; a gap already inside the natural range is kept as read.
    """
    limit, target = ((pacing.sentence_limit, pacing.sentence_target) if between_sentences
                     else (pacing.pause_limit, pacing.pause_target))
    return source_gap if source_gap <= limit else target


@dataclasses.dataclass(frozen=True)
class Piece:
    """One stretch of output audio: source[a, b) of file `src`, or `fill` seconds of room tone."""
    src: int | None
    a: float = 0.0
    b: float = 0.0
    fill: float = 0.0

    @property
    def seconds(self) -> float:
        return self.fill if self.src is None else self.b - self.a


def speech_runs(islands: list[tuple[float, float]], start: float, end: float,
                merge: float = 0.0) -> list[tuple[float, float]]:
    """VAD islands clipped to [start, end]; neighbours closer than `merge` are joined."""
    runs: list[list[float]] = []
    for a, b in islands:
        a, b = max(a, start), min(b, end)
        if b <= a:
            continue
        if runs and a - runs[-1][1] <= merge:
            runs[-1][1] = max(runs[-1][1], b)
        else:
            runs.append([a, b])
    return [(a, b) for a, b in runs]


def join(prev_src: int | None, prev_end: float, next_src: int | None, next_start: float,
         gap: float, room_after: float, room_before: float) -> list[Piece]:
    """The silence between two speech runs, as pieces.

    Up to gap/2 comes from the clean source silence after the earlier run (`room_after` is
    how much there is) and up to gap/2 from before the later one (`room_before`); whatever
    the source cannot supply is room-tone fill in the middle. When both runs are neighbours
    in one file and the gap is long, that is exactly "cut the middle out of the silence".
    """
    half = gap / 2.0
    after = min(half, max(room_after, 0.0)) if prev_src is not None else 0.0
    before = min(half, max(room_before, 0.0)) if next_src is not None else 0.0
    pieces = []
    if after > 0:
        pieces.append(Piece(prev_src, prev_end, prev_end + after))
    if gap - after - before > 1e-6:
        pieces.append(Piece(None, fill=gap - after - before))
    if before > 0:
        pieces.append(Piece(next_src, next_start - before, next_start))
    return pieces


def coalesce(pieces: list[Piece]) -> list[Piece]:
    """Merge source pieces that touch, so a natural stretch is one piece (no edge fades)."""
    out: list[Piece] = []
    for piece in pieces:
        if piece.seconds <= 1e-9:
            continue
        last = out[-1] if out else None
        if (last is not None and piece.src is not None and last.src == piece.src
                and abs(last.b - piece.a) < 1e-6):
            out[-1] = Piece(piece.src, last.a, piece.b)
        elif last is not None and piece.src is None and last.src is None:
            out[-1] = Piece(None, fill=last.fill + piece.fill)
        else:
            out.append(piece)
    return out


def take_runs(islands: list[tuple[float, float]], lo: float, hi: float, w0: float, w1: float,
              cut_before: bool, cut_after: bool, slack: float = 0.03) -> list[tuple[float, float]]:
    """The speech runs (VAD islands, source time) that make up one kept take.

    [lo, hi] is the take's window: from the end of the transcript word before it to the
    start of the one after it. Whisper is loose at those edges (a first word after a pause
    is stretched back into the silence), so islands decide what is speech. An island that
    STRADDLES an edge is shared with the neighbouring material: if that material is kept
    and follows on (`cut_before`/`cut_after` False) it is split at the edge; if it is being
    cut (a false start, an earlier take) the island goes with whichever side holds most of
    it — so the tail of a flub never rides into the take that replaced it.
    """
    runs = []
    for a, b in islands:
        if b <= lo or a >= hi:
            continue
        if a < lo - slack:
            if cut_before and (b - lo) <= (lo - a):
                continue
            a = lo
        if b > hi + slack:
            if cut_after and (b - hi) >= (hi - a):
                continue
            b = hi
        if b - a > 0.02:
            runs.append((a, b))
    runs = [r for r in runs if r[1] > w0 - 0.25 and r[0] < w1 + 0.25] or runs
    return runs


def shared_boundary(db, prev_end: float, next_start: float, hop: float = 0.01) -> float:
    """Where two kept, back-to-back takes split: the quietest frame between the end of the
    one's last word and the start of the other's first word (per-hop dB in `db`).

    Both takes use this ONE point, the earlier as its window's end and the later as its
    start, so audio between the words lands in exactly one of them. (With the earlier
    take ending at the next word's start and the later starting at the previous word's
    end, an island across both was split twice and its middle played twice.)
    """
    a, b = sorted((prev_end, next_start))
    lo_k, hi_k = int(math.floor(a / hop)), int(math.ceil(b / hop))
    lo_k, hi_k = max(lo_k, 0), min(hi_k, len(db) - 1)
    if hi_k <= lo_k:
        return round((a + b) / 2, 3)
    k = min(range(lo_k, hi_k + 1), key=lambda x: (db[x], abs(x * hop - (a + b) / 2)))
    return round(k * hop, 3)


def audible(span: tuple[float, float], islands: list[tuple[float, float]],
            need: float = 0.03) -> bool:
    """Does a transcript word's span overlap detected speech by at least `need` seconds?"""
    a, b = span
    return any(min(b, y) - max(a, x) >= min(need, max(b - a, 0.0) * 0.5) and min(b, y) > max(a, x)
               for x, y in islands)


def snap_to_speech(spans: list[tuple[float, float]], runs: list[tuple[float, float]]
                   ) -> list[tuple[float, float]]:
    """Pull word times that Whisper put in silence onto the speech around them.

    A start in a silence moves forward to the next run; an end in a silence moves back to
    the run before it. Captions then light up with the voice, not in the pause before it.
    """
    def inside(t):
        return any(a - 1e-6 <= t <= b + 1e-6 for a, b in runs)
    out = []
    for a, b in spans:
        if runs and not inside(a):
            nxt = [r[0] for r in runs if r[0] > a]
            if nxt and nxt[0] < b + 0.6:
                a = nxt[0]
        if runs and not inside(b):
            prv = [r[1] for r in runs if r[1] < b]
            if prv and prv[-1] > a:
                b = prv[-1]
        out.append((a, max(b, a + 0.06)))
    return out


def map_time(t: float, src: int, pieces: list[Piece]) -> float:
    """A source time -> output time through `pieces`. A time that was cut out snaps to the
    nearest kept edge of the same file, so a word never lands in someone else's audio."""
    out, best, best_d = 0.0, None, float("inf")
    for piece in pieces:
        if piece.src == src:
            if piece.a - 1e-9 <= t <= piece.b + 1e-9:
                return out + (t - piece.a)
            for edge, value in ((piece.a, out), (piece.b, out + piece.seconds)):
                if abs(t - edge) < best_d:
                    best, best_d = value, abs(t - edge)
        out += piece.seconds
    if best is None:
        raise ValueError(f"no piece of source {src} to map {t:.3f}s onto")
    return best


@dataclasses.dataclass
class SentenceCut:
    """One kept sentence, ready to edit: its file and its speech runs in source time."""
    src: int
    runs: list[tuple[float, float]]      # VAD runs of the kept take, in order
    room_before: float                    # clean source silence before the first run
    room_after: float                     # ... and after the last one
    follows: bool = False                 # nothing was cut between this and the previous one


def scene_pieces(sentences: list[SentenceCut], lead: float, tail: float,
                 pacing: Pacing = Pacing()) -> list[Piece]:
    """One scene clip: lead-in, the sentences with their gaps trimmed, the tail.

    Within a sentence each pause between runs is kept up to `pause_limit` and cut to
    `pause_target` beyond it. Between two sentences that follow each other in the read
    (`follows`: nothing was cut between them) the real gap is kept, or trimmed by the
    sentence rule; where a retake or false start was cut out between them, the gap is
    rebuilt at the sentence target from the silence either side, topped up with room tone.
    """
    pieces: list[Piece] = []
    first = sentences[0]
    before = min(lead, max(first.room_before, 0.0))
    if lead - before > 1e-6:
        pieces.append(Piece(None, fill=lead - before))
    if before > 0:
        pieces.append(Piece(first.src, first.runs[0][0] - before, first.runs[0][0]))
    for k, cut in enumerate(sentences):
        if k:
            prev = sentences[k - 1]
            src_gap = cut.runs[0][0] - prev.runs[-1][1]
            if cut.follows and prev.src == cut.src and src_gap >= 0:
                gap = gap_length(src_gap, True, pacing)
                pieces += join(cut.src, prev.runs[-1][1], cut.src, cut.runs[0][0], gap,
                               src_gap, src_gap)
            else:
                pieces += join(prev.src, prev.runs[-1][1], cut.src, cut.runs[0][0],
                               pacing.sentence_target, prev.room_after, cut.room_before)
        for r, (a, b) in enumerate(cut.runs):
            if r:
                src_gap = a - cut.runs[r - 1][1]
                pieces += join(cut.src, cut.runs[r - 1][1], cut.src, a,
                               gap_length(src_gap, False, pacing), src_gap, src_gap)
            pieces.append(Piece(cut.src, a, b))
    last = sentences[-1]
    after = min(tail, max(last.room_after, 0.0))
    if after > 0:
        pieces.append(Piece(last.src, last.runs[-1][1], last.runs[-1][1] + after))
    if tail - after > 1e-6:
        pieces.append(Piece(None, fill=tail - after))
    return coalesce(pieces)


def scene_tail(pad: float, lead: float, pacing: Pacing = Pacing(), last: bool = False) -> float:
    """Silence after a scene's last word so that tail + scene_pad + next lead-in = scene_gap."""
    if last:
        return pacing.last_tail
    return max(0.05, round(pacing.scene_gap - pad - lead, 4))


# ======================================================================== audio (numpy)

def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({result.returncode}): "
                           f"{' '.join(str(c) for c in cmd[:12])}…\n{(result.stderr or '')[-1500:]}")
    return result


def load_audio(path, sr: int = SR):
    """Any audio file -> float32 mono numpy array at `sr` (through ffmpeg)."""
    import numpy as np
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def save_audio(path, audio, sr: int = SR, subtype: str = "PCM_24") -> None:
    import soundfile as sf
    path = pathlib.Path(path)
    tmp = path.with_name(path.stem + ".part.wav")
    sf.write(str(tmp), audio, sr, subtype=subtype)
    os.replace(tmp, path)


def frame_db(audio, sr: int = SR, win: float = 0.02, hop: float = 0.01):
    """RMS level per 10 ms hop, in dBFS."""
    import numpy as np
    w, h = int(win * sr), int(hop * sr)
    if len(audio) < w:
        return np.array([-120.0])
    n = 1 + (len(audio) - w) // h
    idx = np.arange(w)[None, :] + h * np.arange(n)[:, None]
    rms = np.sqrt(np.mean(audio[idx] ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-12)


def vad_islands(audio, sr: int = SR, hop: float = 0.01, floor_db: float | None = None,
                min_len: float = 0.06, bridge: float = 0.08) -> tuple[list, float]:
    """Speech islands [(start, end)] by energy, and the threshold used.

    The threshold sits 35 dB under the loud speech level (95th percentile of frames) or 10 dB
    above the noise floor, whichever is higher: sensitive enough to keep soft consonants and
    word tails, deaf to the denoised room. Gaps under `bridge` are bridged.
    """
    import numpy as np
    db = frame_db(audio, sr, hop=hop)
    loud = float(np.percentile(db, 95))
    floor = float(np.percentile(db, 10)) if floor_db is None else floor_db
    thresh = max(loud - 35.0, floor + 10.0)
    on = db > thresh
    islands, start = [], None
    for k, flag in enumerate(on):
        if flag and start is None:
            start = k
        elif not flag and start is not None:
            islands.append([start * hop, k * hop + 0.02])
            start = None
    if start is not None:
        islands.append([start * hop, len(on) * hop + 0.02])
    merged: list[list[float]] = []
    for a, b in islands:
        if merged and a - merged[-1][1] <= bridge:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged if b - a >= min_len], thresh


def voicing(audio, sr: int = SR, win: float = 0.03, hop: float = 0.01):
    """Per hop: is the frame voiced (a pitch between 70 and 350 Hz)? FFT autocorrelation."""
    import numpy as np
    w, h = int(win * sr), int(hop * sr)
    if len(audio) < w:
        return np.zeros(1, bool)
    n = 1 + (len(audio) - w) // h
    idx = np.arange(w)[None, :] + h * np.arange(n)[:, None]
    frames = audio[idx] * np.hanning(w)[None, :]
    spec = np.fft.rfft(frames, n=2 * w, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :w]
    lo, hi = int(sr / 350), int(sr / 70)
    peak = ac[:, lo:hi].max(axis=1) / np.maximum(ac[:, 0], 1e-12)
    return (peak > BREATH_VOICED) & (ac[:, 0] > 0)


def word_mask(words: list[dict], n: int, hop: float = 0.01, shrink: float = 0.04):
    """Per hop: does a transcript word cover this frame (its span shrunk by `shrink`)?"""
    mask = [False] * n
    for w in words:
        a = int(math.ceil(round((float(w["start"]) + shrink) / hop, 6)))
        b = int(math.floor(round((float(w["end"]) - shrink) / hop, 6)))
        for k in range(max(a, 0), min(b + 1, n)):
            mask[k] = True
    return mask


def remove_breaths(audio, room, floor_db: float | None, words: list[dict] | None = None,
                   sr: int = SR):
    """Replace every breath (`breath_spans`) with room tone. Returns (audio, spans).

    With `words` (the transcript), a stretch no word covers is held to the lower bar
    (BREATH_DB_OUTSIDE), voiced or not: an inhale through a half-closed throat has a pitch,
    and it is still a gasp.
    """
    import numpy as np
    hop = 0.01
    db = frame_db(audio, sr, win=0.03, hop=hop)
    voiced = voicing(audio, sr, win=0.03, hop=hop)
    n = min(len(db), len(voiced))
    in_word = word_mask(words, n, hop) if words is not None else None
    loud = float(np.percentile(db, 95))
    floor = float(np.percentile(db, 10)) if floor_db is None else floor_db
    # a 50 ms median on both: one noisy frame must not split a breath into two short runs
    db_s = np.array([np.median(db[max(0, k - 2):k + 3]) for k in range(n)])
    voiced_s = np.array([voiced[max(0, k - 2):k + 3].sum() >= 3 for k in range(n)])
    spans = breath_spans(db_s, voiced_s, loud, floor + 6.0, hop, in_word=in_word)
    out = audio.copy()
    tone = room if len(room) else np.zeros(1, np.float32)
    fade = int(0.01 * sr)
    for a, b in spans:
        i, j = int(a * sr), int(b * sr)
        fill = np.resize(tone, j - i).astype(np.float32)
        if j - i > 2 * fade:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            fill[:fade] = out[i:i + fade] * ramp[::-1] + fill[:fade] * ramp
            fill[-fade:] = out[j - fade:j] * ramp + fill[-fade:] * ramp[::-1]
        out[i:j] = fill
    return out, spans


def render_pieces(pieces: list[Piece], sources: list, room: list, fade: float,
                  sr: int = SR):
    """Pieces -> one float32 array. Fill is the file's own room tone (looped), so the
    ambience under a rebuilt gap is the ambience under every other gap."""
    import numpy as np
    out = []
    # a fill takes the room tone of the file it sits next to (the one before it, else after)
    owners, last = [], None
    for piece in pieces:
        last = piece.src if piece.src is not None else last
        owners.append(last)
    following = None
    for k in range(len(pieces) - 1, -1, -1):
        following = pieces[k].src if pieces[k].src is not None else following
        if owners[k] is None:
            owners[k] = following if following is not None else 0
    for piece, room_src in zip(pieces, owners):
        if piece.src is None:
            n = int(round(piece.fill * sr))
            tone = room[room_src] if len(room[room_src]) else np.zeros(1, np.float32)
            chunk = np.resize(tone, n).astype(np.float32)
        else:
            a, b = int(round(piece.a * sr)), int(round(piece.b * sr))
            chunk = sources[piece.src][max(a, 0):max(b, 0)].copy()
            if a < 0:
                chunk = np.concatenate([np.zeros(-a, np.float32), chunk])
        f = min(int(fade * sr), len(chunk) // 2)
        if f > 0:
            ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
            chunk[:f] *= ramp
            chunk[-f:] *= ramp[::-1]
        out.append(chunk)
    return np.concatenate(out) if out else np.zeros(0, np.float32)


def ebur128(path) -> dict:
    """Integrated loudness, LRA, max short-term and true peak of a file (ffmpeg ebur128)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    text = r.stderr
    summary = text[text.rfind("Summary:"):]

    def grab(label):
        m = re.search(label + r":\s+(-?[\d.]+|-inf)", summary)
        return None if m is None or m.group(1) == "-inf" else float(m.group(1))
    shorts = [float(x) for x in re.findall(r"S:\s*(-?[\d.]+)", text[:text.rfind("Summary:")])]
    return {"integrated_lufs": grab("I"), "lra_lu": grab("LRA"), "true_peak_dbfs": grab("Peak"),
            "max_short_term_lufs": max(shorts) if shorts else None}


# ===================================================== helpers run in ephemeral uv envs

def utterances(islands: list[tuple[float, float]], pause: float = 0.45,
               pad: float = 0.15, end: float | None = None) -> list[tuple[float, float]]:
    """Speech islands -> utterances: islands closer than `pause` joined, `pad` either side.

    Each utterance is transcribed on its own. Whisper run over a whole read collapses a
    false start into its re-read ("The lions came ... The lions came from Oregon" comes back
    as one "The lions came from Oregon", timed across both) — there is no take left to cut.
    Stephen pauses before every re-read, so a pause-separated utterance never holds two.
    """
    groups: list[list[float]] = []
    for a, b in islands:
        if groups and a - groups[-1][1] < pause:
            groups[-1][1] = b
        else:
            groups.append([a, b])
    out = []
    for a, b in groups:
        a, b = max(0.0, a - pad), b + pad
        if end is not None:
            b = min(b, end)
        out.append((round(a, 3), round(b, 3)))
    return out


def _transcribe_main(argv: list[str]) -> int:
    """`_transcribe IN OUT MODEL HOTWORDS [SPANS.json]` — runs inside the faster-whisper env.

    With SPANS, each [start, end] is transcribed separately and its words offset back onto
    the file's clock; without, the whole file is one pass (the verification read).
    """
    import numpy as np
    from faster_whisper import WhisperModel
    src, out, model_name = argv[0], argv[1], argv[2]
    hotwords = argv[3] if len(argv) > 3 and argv[3] else None
    spans = json.loads(pathlib.Path(argv[4]).read_text()) if len(argv) > 4 else None
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", src, "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    jobs = [(0.0, audio, True)] if spans is None else [
        (float(a), audio[int(a * 16000):int(b * 16000)], False) for a, b in spans]
    words = []
    for offset, chunk, whole in jobs:
        if len(chunk) < 1600:
            continue
        segments, _info = model.transcribe(
            chunk, language="en", word_timestamps=True, beam_size=5,
            condition_on_previous_text=False, vad_filter=whole,
            vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 150} if whole else None,
            hotwords=hotwords)
        limit = offset + len(chunk) / 16000
        for seg in segments:
            for w in seg.words or []:
                text = w.word.strip()
                if text:
                    start = min(offset + float(w.start), limit)
                    words.append({"text": text, "start": round(start, 3),
                                  "end": round(max(start, min(offset + float(w.end), limit)), 3),
                                  "p": round(float(w.probability), 3)})
    pathlib.Path(out).write_text(json.dumps(words, indent=0))
    return 0


def _deepfilter_main(argv: list[str]) -> int:
    """`_deepfilter IN OUT ATTEN_DB` — runs inside the DeepFilterNet env (48 kHz in/out).

    File IO goes through soundfile: torchaudio 2.1 on macOS has no audio backend installed.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from df.enhance import enhance, init_df
    src, out, atten = argv[0], argv[1], float(argv[2])
    model, state, _ = init_df(log_level="ERROR")
    audio, sr = sf.read(src, dtype="float32", always_2d=True)
    if sr != state.sr():
        raise SystemExit(f"deepfilter wants {state.sr()} Hz, got {sr}")
    tensor = torch.from_numpy(np.ascontiguousarray(audio.mean(axis=1)))[None, :]
    with torch.no_grad():
        clean = enhance(model, state, tensor, atten_lim_db=atten if atten > 0 else None)
    sf.write(out, clean.squeeze(0).numpy().astype(np.float32), sr, subtype="FLOAT")
    return 0


def transcribe(wav, out_json, model: str, hotwords: str = "", spans=None) -> list[dict]:
    cmd = [UV, "run", *WHISPER_ENV, "python", str(pathlib.Path(__file__).resolve()),
           "_transcribe", str(wav), str(out_json), model, hotwords]
    if spans is not None:
        spans_file = pathlib.Path(out_json).with_suffix(".spans.json")
        spans_file.write_text(json.dumps(spans))
        cmd.append(str(spans_file))
    run(cmd)
    return json.loads(pathlib.Path(out_json).read_text())


def denoise(raw_wav, out_wav, room: tuple[float, float], mode: str,
            atten_db: float = DEFAULT_ATTEN_LIM_DB) -> str:
    """Denoise one file. Returns the method that ran. `mode` auto tries DeepFilterNet."""
    if mode in ("auto", "deepfilter"):
        try:
            run([UV, "run", *DEEPFILTER_ENV, "python", str(pathlib.Path(__file__).resolve()),
                 "_deepfilter", str(raw_wav), str(out_wav), str(atten_db)])
            return f"deepfilternet3 (atten limit {atten_db:g} dB)"
        except (RuntimeError, OSError) as exc:
            if mode == "deepfilter":
                raise
            print(f"!!! DeepFilterNet unavailable, falling back to ffmpeg afftdn: "
                  f"{str(exc).splitlines()[0]}", file=sys.stderr, flush=True)
    if mode == "none":
        shutil.copyfile(raw_wav, out_wav)
        return "none"
    a, b = room
    chain = (f"asendcmd=c='{a:.2f} afftdn sn start',asendcmd=c='{b:.2f} afftdn sn stop',"
             f"afftdn=nr=18:nf=-60:tn=1")
    run([FFMPEG, "-y", "-v", "error", "-i", str(raw_wav), "-af", chain, "-c:a", "pcm_f32le",
         str(out_wav)])
    return f"ffmpeg afftdn (noise profile {a:.1f}-{b:.1f}s)"


# ================================================================================ the build

@dataclasses.dataclass
class Source:
    path: pathlib.Path
    audio: object = None          # processed float32 at SR
    room: object = None           # processed room tone
    room_span: tuple = (0.0, 0.0)
    words: list = dataclasses.field(default_factory=list)   # transcript
    islands: list = dataclasses.field(default_factory=list)
    floor_raw_db: float | None = None
    floor_clean_db: float | None = None
    denoiser: str = ""
    breaths: list = dataclasses.field(default_factory=list)
    frames_db: object = None      # per-10 ms level of `audio`, after the breath stage


def room_tone_span(audio, sr: int = SR) -> tuple[float, float]:
    """Where the leading room tone is: 0.3 s in, to 0.3 s before the first sustained sound.

    "Sound" is 100 ms in a row above the midpoint (in dB) between the room (10th percentile
    of frames) and the voice (95th) — a hum or a hiss never gets there, a word always does.
    """
    import numpy as np
    db = frame_db(audio, sr)
    floor, loud = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    hot = (db > floor + 0.5 * (loud - floor)).astype(int)
    run = np.convolve(hot, np.ones(10, int), mode="valid")
    first = np.nonzero(run >= 10)[0]
    onset = first[0] * 0.01 if len(first) else 0.0
    return (min(0.3, onset), max(min(0.3, onset), onset - 0.3))


def room_floor(audio, span: tuple[float, float]) -> float | None:
    """RMS level of the room-tone span, dBFS (None when there is no room tone)."""
    import numpy as np
    seg = audio[int(span[0] * SR):int(span[1] * SR)]
    if not len(seg):
        return None
    return round(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)), 1)


def prepare_source(path, work: pathlib.Path, k: int, mode: str, atten_db: float,
                   model: str, hotwords: str, tempo: float = 1.0,
                   breaths: bool = True) -> Source:
    import numpy as np
    src = Source(path=pathlib.Path(path))
    raw = load_audio(path)
    a, b = room_tone_span(raw)
    if b - a < 1.0:
        print(f"warning: {path.name}: only {b - a:.1f}s of room tone before the first word "
              f"(asked for ~5 s); the denoiser has less to learn from", file=sys.stderr)
    seg = raw[int(a * SR):int(b * SR)]
    src.floor_raw_db = round(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)), 1) \
        if len(seg) else None
    raw48 = work / f"src{k}.raw.wav"
    clean = work / f"src{k}.denoised.wav"
    polished = work / f"src{k}.polished.wav"
    transcript = work / f"src{k}.transcript.json"
    # The slow steps (denoise, transcribe) are cached on everything that changes their
    # output, so re-running after a spec or pacing tweak takes seconds, not minutes.
    key = {"raw_sha1": file_digest(path), "denoise": mode, "atten_db": atten_db,
           "polish": POLISH, "model": model, "hotwords": hotwords, "chunked": 1}
    speed = tempo_filter(tempo)
    if speed:
        # the tempo change runs before transcription, so it is part of what the cache keys on
        key["tempo"] = speed
    raw_room = (a, b)
    # the leading room tone, on the (possibly sped-up) clock everything below runs on
    a, b = a / tempo, b / tempo
    key_file = work / f"src{k}.cache.json"
    try:
        cached = json.loads(key_file.read_text())
    except (OSError, ValueError):
        cached = {}
    if cached.get("key") == key and polished.exists() and transcript.exists():
        src.denoiser = cached.get("denoiser", "") + " (cached)"
        src.words = json.loads(transcript.read_text())
    else:
        key_file.unlink(missing_ok=True)
        save_audio(raw48, raw, subtype="FLOAT")
        src.denoiser = denoise(raw48, clean, raw_room, mode, atten_db)
        run([FFMPEG, "-y", "-v", "error", "-i", str(clean), "-af",
             POLISH + (f",{speed}" if speed else ""), "-ar", str(SR),
             "-ac", "1", "-c:a", "pcm_f32le", str(polished)])
        audio = load_audio(polished)
        floor = room_floor(audio, (a, b))
        islands, _ = vad_islands(audio, floor_db=floor)
        src.words = transcribe(polished, transcript, model, hotwords,
                               spans=utterances(islands, end=len(audio) / SR))
        key_file.write_text(json.dumps({"key": key, "denoiser": src.denoiser}))
    src.audio = load_audio(polished)
    src.room_span = (a, b)
    src.room = src.audio[int(a * SR):int(b * SR)].copy()
    src.floor_clean_db = room_floor(src.audio, (a, b))
    if breaths:
        # after transcription (the cached transcript stays valid), before anything is cut
        src.audio, src.breaths = remove_breaths(src.audio, src.room, src.floor_clean_db,
                                                [w for w in src.words
                                                 if w.get("p", 1.0) >= MIN_WORD_P])
    src.islands, _ = vad_islands(src.audio, floor_db=src.floor_clean_db)
    src.frames_db = frame_db(src.audio, SR, win=0.03, hop=0.01)
    return src


@dataclasses.dataclass
class Sentence:
    scene: int
    tokens: list[str]           # display tokens
    first: int                  # index of the first token within the scene
    norm: list                  # normalise(tokens)


def script_sentences(spec: dict) -> list[Sentence]:
    out = []
    for idx in selected_scenes(spec):
        tokens = narration_tokens(spec["scenes"][idx])
        for a, b in sentence_spans(tokens):
            out.append(Sentence(scene=idx, tokens=tokens[a:b], first=a,
                                norm=normalise(tokens[a:b])))
    return out


def build(spec: dict, spec_path, out_dir: pathlib.Path, *, sources: list[pathlib.Path],
          model: str = DEFAULT_MODEL, denoise_mode: str = "auto",
          atten_db: float = DEFAULT_ATTEN_LIM_DB, pacing: Pacing = Pacing(),
          target_lufs: float = HOUSE_LUFS, allow_missing: bool = False,
          verify: bool = True, verify_model: str = VERIFY_MODEL,
          tempo: float = 1.0, breaths: bool = True) -> dict:
    """The whole pipeline. Returns the report (also written as audio/human_report.json)."""
    import numpy as np
    out_dir = pathlib.Path(out_dir)
    work = out_dir.parent / "human_work"
    work.mkdir(parents=True, exist_ok=True)
    sentences = script_sentences(spec)
    if not sentences:
        raise SystemExit("the spec's selected scenes have no narration to read")
    all_tokens = [t for s in sentences for t in s.tokens]
    # No hotwords/prompt: on a short breath-only phrase they make Whisper say them anyway.
    hot = ""
    script_norm = [[w for w, _ in s.norm] for s in sentences]

    # 1-3: every file is denoised, polished and transcribed on its own
    srcs = [prepare_source(p, work, k, denoise_mode, atten_db, model, hot, tempo, breaths)
            for k, p in enumerate(sources)]

    # 4: align. The main file reads the whole script; a patch may hold any of it.
    report_sentences = [dict(scene=s.scene, text=" ".join(s.tokens), takes=[]) for s in sentences]
    chosen: list[tuple[int, Take] | None] = [None] * len(sentences)
    heard_by_src, junk_cut = [], []
    dropped = []
    for k, src in enumerate(srcs):
        dropped += [f"{w['text']} @{w['start']:.1f}s" + (f" (file {k})" if k else "")
                    for w in src.words if w.get("p", 1.0) < MIN_WORD_P]
        src.words = merge_digit_groups([w for w in src.words if w.get("p", 1.0) >= MIN_WORD_P])
        flat = [(w, i) for i, word in enumerate(src.words) for w, _ in normalise([word["text"]])]
        heard = [w for w, _ in flat]
        # a transcript word may normalise to 0 or 2+ words; keep each one's source times
        times = [(src.words[i]["start"], src.words[i]["end"]) for _, i in flat]
        heard_by_src.append((heard, times))
        takes = align_script(heard, script_norm, skip_cost=None if k == 0 else 0.0)
        covered = set()
        for take in takes:
            covered.update(range(take.start, take.end))
            report_sentences[take.sentence]["takes"].append({
                "file": k, "start": round(times[take.start][0], 2),
                "end": round(times[take.end - 1][1], 2), "complete": take.complete,
                "heard": " ".join(heard[take.start:take.end])})
        for s, take in enumerate(kept_takes(takes, len(sentences))):
            if take is not None:
                chosen[s] = (k, take)
        junk_cut += [f"{heard[j]} @{times[j][0]:.1f}s" + (f" (file {k})" if k else "")
                     for j in range(len(heard)) if j not in covered]

    missing_sentences = [i for i, c in enumerate(chosen) if c is None]
    word_report = []
    for i, c in enumerate(chosen):
        if c is None:
            report_sentences[i].update(kept=None, missing=report_sentences[i]["text"].split(),
                                       extra=[], heard_as=[])
            continue
        k, take = c
        heard, times = heard_by_src[k]
        rep = take_report(sentences[i].tokens, sentences[i].norm, heard[take.start:take.end])
        report_sentences[i].update(kept={"file": k, "start": round(times[take.start][0], 2),
                                         "end": round(times[take.end - 1][1], 2)},
                                   missing=rep["missing"], extra=rep["extra"],
                                   heard_as=rep["heard_as"])
        word_report.append(rep)
    problems = []
    if missing_sentences:
        problems.append("never read in full: " + "; ".join(
            f"scene {sentences[i].scene:02d} \"{report_sentences[i]['text']}\""
            for i in missing_sentences))
    last = report_sentences[-1]
    if last.get("missing") and len(sentences) - 1 not in missing_sentences:
        problems.append(f"the LAST sentence is missing words ({', '.join(last['missing'])}): "
                        f"the Short would end on a fragment")
    if problems and not allow_missing:
        _print_alignment(report_sentences, junk_cut)
        raise SystemExit("refusing to build: " + " | ".join(problems) +
                         "\nRe-record (or patch) those sentences, or pass --allow-missing.")

    # 5: the edit, scene by scene
    by_scene: dict[int, list[int]] = {}
    for i, s in enumerate(sentences):
        if chosen[i] is not None:
            by_scene.setdefault(s.scene, []).append(i)
    pad = float((spec.get("short") or {}).get("scene_pad", 0.25))
    lead = float(((spec.get("tts") or {}).get("lead_in_s")) or 0.05)
    scene_ids = [idx for idx in selected_scenes(spec) if idx in by_scene]
    clips, clip_words = {}, {}
    for n_scene, idx in enumerate(scene_ids):
        cuts, word_spans = [], []
        for i in by_scene[idx]:
            k, take = chosen[i]
            src = srcs[k]
            heard, times = heard_by_src[k]
            w0, w1 = times[take.start][0], times[take.end - 1][1]
            # the window this take may draw audio from: up to the neighbouring transcript words
            # (a neighbouring word Whisper put in pure silence is no boundary: skip it)
            before = [j for j in range(take.start) if audible(times[j], src.islands)]
            after = [j for j in range(take.end, len(times)) if audible(times[j], src.islands)]
            lo = times[before[-1]][1] if before else 0.0
            hi = times[after[0]][0] if after else len(src.audio) / SR
            lo, hi = max(lo, w0 - 0.6), min(hi, w1 + 0.8)
            # is the neighbouring read KEPT and continuous with this one, or being cut?
            prev_adjacent = bool(i and chosen[i - 1] and chosen[i - 1][0] == k
                                 and chosen[i - 1][1].end == take.start)
            next_adjacent = bool(i + 1 < len(chosen) and chosen[i + 1]
                                 and chosen[i + 1][0] == k and chosen[i + 1][1].start == take.end)
            # a kept neighbour read straight on: both takes split at the same point
            if prev_adjacent:
                lo = shared_boundary(src.frames_db, times[take.start - 1][1], times[take.start][0])
            if next_adjacent:
                hi = shared_boundary(src.frames_db, times[take.end - 1][1], times[take.end][0])
            follows = prev_adjacent and (i - 1) in by_scene[idx]
            runs = take_runs(src.islands, lo, hi, w0, w1, cut_before=not prev_adjacent,
                             cut_after=not next_adjacent) or [(w0, w1)]
            cuts.append(SentenceCut(src=k, runs=runs,
                                    room_before=max(0.0, runs[0][0] - lo),
                                    room_after=max(0.0, hi - runs[-1][1]), follows=follows))
            ops = align_ops(heard[take.start:take.end], [w for w, _ in sentences[i].norm])
            tt = snap_to_speech(token_times(len(sentences[i].tokens), sentences[i].norm, ops,
                                            times[take.start:take.end]), runs)
            word_spans.append((k, sentences[i], tt))
        tail = scene_tail(pad, lead, pacing, last=(n_scene == len(scene_ids) - 1))
        pieces = scene_pieces(cuts, lead, tail, pacing)
        clips[idx] = pieces
        words = []
        for k, sent, tt in word_spans:
            for token, (a, b) in zip(sent.tokens, tt):
                start, end = map_time(a, k, pieces), map_time(b, k, pieces)
                words.append({"text": token, "start": round(start, 3),
                              "end": round(max(end, start + 0.01), 3)})
        for w_prev, w_next in zip(words, words[1:]):   # captions must run in order
            if w_next["start"] < w_prev["start"]:
                w_next["start"] = w_prev["start"]
            w_next["end"] = max(w_next["end"], w_next["start"] + 0.01)
        clip_words[idx] = words

    # per-file level match: a patch recorded at another gain is brought to the main file's
    file_gain = [0.0] * len(srcs)
    if len(srcs) > 1:
        levels = []
        for k in range(len(srcs)):
            parts = [Piece(k, a, b) for c in clips.values() for p in c if p.src == k
                     for a, b in [(p.a, p.b)]]
            if not parts:
                levels.append(None)
                continue
            probe = work / f"src{k}.kept.wav"
            save_audio(probe, render_pieces(parts, [s.audio for s in srcs],
                                            [s.room for s in srcs], 0.0))
            levels.append(ebur128(probe)["integrated_lufs"])
        if levels[0] is not None:
            file_gain = [0.0 if lv is None else levels[0] - lv for lv in levels]
    audios = [s.audio * (10 ** (g / 20.0)) for s, g in zip(srcs, file_gain)]
    rooms = [s.room * (10 ** (g / 20.0)) for s, g in zip(srcs, file_gain)]

    # 6: one gain for the whole read to the house level, then the peak limiter
    rendered = {idx: render_pieces(p, audios, rooms, pacing.edge_fade) for idx, p in clips.items()}
    gap = np.zeros(int(pad * SR), np.float32)
    whole = np.concatenate([x for idx in scene_ids for x in (rendered[idx], gap)])
    probe = work / "narration.pregain.wav"
    save_audio(probe, whole)
    before = ebur128(probe)["integrated_lufs"]
    gain_db = target_lufs - (before if before is not None else target_lufs)

    # 7: write what make_short reads, and nothing it does not
    if out_dir.exists() and not (out_dir / MARKER).exists() and any(out_dir.iterdir()):
        keep = out_dir.with_name(f"audio.tts-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        out_dir.rename(keep)
        print(f"kept the previous (TTS) narration at {keep}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("scene_*"):
        stale.unlink()
    import captions
    durations = {}
    for idx in scene_ids:
        tmp = work / f"clip_{idx:02d}.pre.wav"
        save_audio(tmp, rendered[idx], subtype="FLOAT")
        wav = out_dir / f"scene_{idx:02d}.wav"
        run([FFMPEG, "-y", "-v", "error", "-i", str(tmp), "-af",
             f"volume={gain_db:.3f}dB,alimiter=limit={PEAK_LIMIT}:attack=2:release=60:"
             f"level=0:latency=1", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s24le", str(wav)])
        seconds = len(load_audio(wav)) / SR
        durations[idx] = seconds
        captions.write_words(wav, clip_words[idx])
        (out_dir / f"scene_{idx:02d}.json").write_text(json.dumps({
            "hash": f"human:{file_digest(wav)}", "seconds": seconds, "provider_used": HUMAN,
            "voice": HUMAN, "text": " ".join(narration_tokens(spec["scenes"][idx]))}))
    with open(out_dir / "durations.json", "w") as fh:
        json.dump(durations, fh, indent=1)
    whole_out = work / "narration.wav"
    final = np.concatenate([x for idx in scene_ids
                            for x in (load_audio(out_dir / f"scene_{idx:02d}.wav"), gap)])
    save_audio(whole_out, final)
    loud = ebur128(whole_out)

    # the numbers, and the verification transcript
    script_words = sum(len(s.tokens) for s in sentences)
    runtime = sum(durations.values()) + pad * len(durations)
    gaps = []
    for idx in scene_ids:
        for prev, nxt in zip(clip_words[idx], clip_words[idx][1:]):
            gaps.append(round(nxt["start"] - prev["end"], 3))
    report = {
        "spec": str(spec_path), "built": datetime.datetime.now().isoformat(timespec="seconds"),
        "sources": [{"path": str(s.path), "denoiser": s.denoiser,
                     "room_tone_s": round(s.room_span[1] - s.room_span[0], 2),
                     "noise_floor_raw_dbfs": s.floor_raw_db,
                     "noise_floor_clean_dbfs": s.floor_clean_db,
                     "level_match_db": round(file_gain[k], 2),
                     "breaths_removed": len(s.breaths),
                     "breath_s": round(sum(b - a for a, b in s.breaths), 2)}
                    for k, s in enumerate(srcs)],
        "sentences": report_sentences, "cut_words": junk_cut, "ignored_words": dropped,
        "durations": {str(k): round(v, 3) for k, v in durations.items()},
        "narration_s": round(runtime, 2), "script_words": script_words,
        "words_per_s": round(script_words / runtime, 2) if runtime else None,
        "tempo": tempo, "pacing": dataclasses.asdict(pacing),
        "gain_db": round(gain_db, 2), "loudness": loud,
        "target_lufs": target_lufs,
        "word_gaps_max_s": max(gaps) if gaps else None,
        "problems": problems,
    }
    if verify:
        # padded with a second of silence: Whisper invents words at an abrupt end
        padded = work / "verify.input.wav"
        save_audio(padded, np.concatenate([np.zeros(int(0.5 * SR), np.float32), final,
                                           np.zeros(int(1.0 * SR), np.float32)]))
        heard = merge_digit_groups(transcribe(padded, work / "verify.transcript.json",
                                              verify_model, ""))
        heard_norm = [w for word in heard for w, _ in normalise([word["text"]])]
        script_flat = [w for s in sentences for w in [x for x, _ in s.norm]]
        rep = take_report(all_tokens, normalise(all_tokens), heard_norm)
        report["verify"] = {"wer": word_error_rate(script_flat, heard_norm),
                            "missing": rep["missing"], "extra": rep["extra"],
                            "heard_as": rep["heard_as"],
                            "transcript": " ".join(w["text"] for w in heard)}
    sources_sha = [file_digest(p) for p in sources]
    (out_dir / MARKER).write_text(json.dumps({
        "sources": [str(p) for p in sources], "source_sha1": sources_sha,
        "script_sha1": script_digest(spec), "tempo": tempo, "built": report["built"]}, indent=1))
    (out_dir / "human_report.json").write_text(json.dumps(report, indent=1, default=str))
    return report


def _print_alignment(sentences: list[dict], junk: list[str]) -> None:
    for s in sentences:
        takes = s.get("takes") or []
        kept = s.get("kept")
        cut = [t for t in takes if not (kept and t["file"] == kept["file"]
                                        and t["start"] == kept["start"])]
        head = (f"scene {s['scene']:02d}  kept {kept['start']:.2f}-{kept['end']:.2f}s"
                + (f" (file {kept['file']})" if kept and kept["file"] else "")
                if kept else f"scene {s['scene']:02d}  NOT READ IN FULL")
        print(f"{head}  {s['text']}")
        for t in cut:
            print(f"      cut {'take' if t['complete'] else 'false start'} "
                  f"{t['start']:.2f}-{t['end']:.2f}s: \"{t['heard']}\"")
        for label in ("missing", "extra", "heard_as"):
            if s.get(label):
                print(f"      {label}: {', '.join(s[label])}")
    if junk:
        print(f"cut (not in the script): {', '.join(junk)}")


def print_report(report: dict) -> None:
    for s in report["sources"]:
        print(f"source {s['path']}\n  denoise: {s['denoiser']}; room tone {s['room_tone_s']}s; "
              f"noise floor {s['noise_floor_raw_dbfs']} -> {s['noise_floor_clean_dbfs']} dBFS"
              + (f"; level matched {s['level_match_db']:+.1f} dB" if s["level_match_db"] else "")
              + (f"; {s['breaths_removed']} breaths ({s['breath_s']}s) to room tone"
                 if s.get("breaths_removed") else ""))
    _print_alignment(report["sentences"], report["cut_words"])
    loud = report["loudness"]
    print(f"narration {report['narration_s']}s"
          + (f" (tempo {report['tempo']:g}x)" if report.get("tempo", 1.0) != 1.0 else "")
          + f", {report['script_words']} words, "
          f"{report['words_per_s']} w/s (gate S10 wants >= 3.0 on the finished Short); "
          f"gain {report['gain_db']:+.1f} dB -> {loud['integrated_lufs']} LUFS "
          f"(house {report['target_lufs']}), TP {loud['true_peak_dbfs']}, "
          f"LRA {loud['lra_lu']}, max short-term {loud['max_short_term_lufs']}; "
          f"longest gap between words {report['word_gaps_max_s']}s")
    print("scene seconds: " + ", ".join(f"{k}: {v:.2f}" for k, v in report["durations"].items()))
    v = report.get("verify")
    if v:
        print(f"verify (re-transcribed): WER {v['wer']:.1%}"
              + (f"; missing {', '.join(v['missing'])}" if v["missing"] else "")
              + (f"; extra {', '.join(v['extra'])}" if v["extra"] else "")
              + (f"; heard as {', '.join(v['heard_as'])}" if v["heard_as"] else ""))
    if report["problems"]:
        print("!!! " + " | ".join(report["problems"]))


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_transcribe":
        return _transcribe_main(argv[1:])
    if argv and argv[0] == "_deepfilter":
        return _deepfilter_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--spec", required=True, help="the Short's scenes.yaml (voice: human)")
    ap.add_argument("--wav", action="append", default=None,
                    help="override `human_voice:` (repeat: main recording, then patches)")
    ap.add_argument("--out", default=None,
                    help="audio directory (default scripts/video/build/<slug>/audio)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model for alignment")
    ap.add_argument("--verify-model", default=VERIFY_MODEL,
                    help="faster-whisper model for the check of the finished narration")
    ap.add_argument("--denoise", choices=("auto", "deepfilter", "afftdn", "none"),
                    default="auto")
    ap.add_argument("--atten-db", type=float, default=DEFAULT_ATTEN_LIM_DB,
                    help="DeepFilterNet attenuation limit, dB (0 = unlimited)")
    ap.add_argument("--target-lufs", type=float, default=HOUSE_LUFS)
    ap.add_argument("--sentence-gap", type=float, default=None,
                    help="override human_voice_pacing.sentence_gap")
    ap.add_argument("--tempo", type=float, default=None,
                    help="override `human_voice_tempo:` (pitch-preserving speed, e.g. 1.1); "
                         "make_short.py refuses the build unless the spec says the same")
    ap.add_argument("--keep-breaths", action="store_true",
                    help="leave inhales in (default: replace them with room tone)")
    ap.add_argument("--allow-missing", action="store_true",
                    help="build even if a sentence was never read in full")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip re-transcribing the finished narration")
    a = ap.parse_args(argv)
    import yaml
    spec_path = pathlib.Path(a.spec).expanduser().resolve()
    spec = yaml.safe_load(spec_path.read_text())
    if not is_human(spec) and not a.wav:
        raise SystemExit("this spec is not `voice: human`; set it (and `human_voice:`), or "
                         "pass --wav to build a human read anyway")
    sources = ([pathlib.Path(w).expanduser().resolve() for w in a.wav] if a.wav
               else human_sources(spec, spec_path))
    for path in sources:
        if not path.is_file():
            raise SystemExit(f"no such recording: {path}")
    out = (pathlib.Path(a.out) if a.out else HERE / "build" / spec["slug"] / "audio")
    tempo = spec_tempo(spec if a.tempo is None else {"human_voice_tempo": a.tempo})
    pacing = spec_pacing(spec)
    if a.sentence_gap is not None:
        pacing = spec_pacing({"human_voice_pacing": {"sentence_gap": a.sentence_gap}}, pacing)
    report = build(spec, spec_path, out, sources=sources, model=a.model,
                   denoise_mode=a.denoise, atten_db=a.atten_db, pacing=pacing,
                   target_lufs=a.target_lufs, allow_missing=a.allow_missing,
                   verify=not a.no_verify, verify_model=a.verify_model, tempo=tempo,
                   breaths=not a.keep_breaths)
    print_report(report)
    print(f"wrote {out} (report: {out / 'human_report.json'}; listen: "
          f"{out.parent / 'human_work' / 'narration.wav'})")
    if a.wav and not is_human(spec):
        print("note: the spec is not `voice: human`, so make_short.py will refuse this "
              "audio until it is (or until narrate.py re-synthesises it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
