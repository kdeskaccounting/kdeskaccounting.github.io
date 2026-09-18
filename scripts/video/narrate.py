#!/usr/bin/env python3
"""
Synthesize per-scene narration WAVs. Two providers, selected by the spec's `tts:` block:

  tts:
    provider: elevenlabs        # or kokoro (the default when the block is absent)
    voice: pNInz6obpgDQGcFmaJgB # ElevenLabs voice_id; for kokoro, the Kokoro voice name
    model: eleven_multilingual_v2
    stability: 0.5              # optional voice_settings; sensible defaults applied
    similarity_boost: 0.75

A legacy top-level `voice: am_michael` (what every marketing/video/*/scenes.yaml carries)
still means Kokoro, unchanged.

  scripts/video/.venv-tts/bin/python scripts/video/narrate.py --spec … --out …
  …/narrate.py --spec … --tts-check          # GET /v1/voices, prove the voice_id, exit 0/2
  …/narrate.py --spec … --dry-run            # character counts + credit estimate, no network
  …/narrate.py --spec … --out … --require-provider elevenlabs   # fail instead of falling back

--speed is a Kokoro control. ElevenLabs takes a rate only inside voice_settings, so on an
elevenlabs spec `--speed` other than 1.0 is refused unless the spec carries a matching
`tts.speed` — a stray flag would otherwise change the cache key and re-bill for identical
audio. For the same reason the top-level speed is not part of the ElevenLabs cache key.

Output is identical for both providers: 24 kHz mono WAVs plus durations.json, so assemble.py
and make_short.py never learn which provider spoke. ElevenLabs returns MP3, which ffmpeg
converts; both paths then get the same silence trim and 0.3 s lead-in.

Every synthesized scene also writes `scene_NN.words.json` beside its WAV — the word timings
burned-in captions need (scripts/video/captions.py), in seconds against the FINISHED WAV, i.e.
after that trim and lead-in, because that is the audio make_short concatenates. ElevenLabs
supplies them from the /with-timestamps endpoint, which returns the alignment alongside the
audio it describes, so there is no second billed request and no transcript that can disagree
with the voice. Kokoro supplies them from its own MTokens, which carry start_ts/end_ts only
when the English G2P ran — a non-English voice writes `null` and that scene renders
uncaptioned, with one line saying so. The words file is part of the cache: a scene cached
before captions existed re-synthesizes once (free on Kokoro, one request on ElevenLabs) so a
cache hit always yields words.

Caches by a hash of (provider, voice, model, voice_settings, text) for ElevenLabs — speed rides
inside voice_settings there, so the key only moves when the request body would — and of
(voice, speed, text) for Kokoro. Switching provider re-synthesizes; unchanged text is never
re-billed. Pre-existing Kokoro caches keyed by the old (voice, speed, text) shape are still hits.

Key: ELEVENLABS_API_KEY, else ~/kdesk-analytics/elevenlabs-api-key.txt (0600). It is never
printed: every error string goes through scripts/browser/session.redact_secrets first.

Run with the pipeline venv (yaml, numpy, soundfile, kokoro, requests live there). Every one of
those imports is inside the function that needs it, so this module imports with the standard
library alone and tests/test_narrate.py can drive it.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
# spaCy (inside Kokoro's G2P) auto-installs its English model via `uv pip`; it needs the venv.
os.environ.setdefault("VIRTUAL_ENV", str(HERE / ".venv-tts"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(HERE))
from browser import session  # noqa: E402  (scripts/browser/session.py — the one scrubber)
import captions  # noqa: E402  (scripts/video/captions.py — stdlib only, words.json lives there)

SR = 24000
#: Silence prepended to every scene by finish(), both providers. Word timings are written
#: against the finished WAV, so they carry it.
LEAD_IN_S = 0.3
KOKORO = "kokoro"
ELEVENLABS = "elevenlabs"
PROVIDERS = (KOKORO, ELEVENLABS)

DEFAULT_KOKORO_VOICE = "am_michael"
DEFAULT_EL_MODEL = "eleven_multilingual_v2"
#: Applied unless the spec overrides them. ElevenLabs' own console defaults.
DEFAULT_VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75}
#: Other voice_settings keys a spec may set. An unknown key is a 422, so the set is closed.
OPTIONAL_VOICE_SETTINGS = ("style", "use_speaker_boost", "speed")

API_BASE = "https://api.elevenlabs.io/v1"
#: Synthesis goes through /with-timestamps, so the character alignment burned-in captions need
#: arrives with the audio it describes — one billed request, and a transcript that cannot
#: disagree with the voice. The response is JSON carrying base64 MP3, not raw audio.
TIMESTAMPS_PATH = "with-timestamps"
OUTPUT_FORMAT = "mp3_44100_128"
KEY_ENV = "ELEVENLABS_API_KEY"
KEY_FILE = pathlib.Path.home() / "kdesk-analytics" / "elevenlabs-api-key.txt"
TTS_TIMEOUT_S = 180          # a paragraph of speech, not an API ping
VOICES_TIMEOUT_S = 30
FFMPEG = next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg")
               if os.path.exists(p)), "ffmpeg")


class TTSError(RuntimeError):
    """A provider failure. The message is already redacted — print it as it arrives."""


def redact(text, key: str | None = None) -> str:
    """Mask credentials before `text` reaches stdout, a log or a queue card.

    session.redact_secrets(secrets=…) REPLACES the known set rather than adding to it, so the
    union is passed explicitly: the key in hand may have come from somewhere the file/env
    sweep does not look (a --key flag one day, a key file moved for a test).
    """
    secrets = session.known_secrets()
    if key:
        secrets = secrets | {str(key)}
    return session.redact_secrets(text, secrets=secrets)


# ---------------------------------------------------------------- configuration from the spec

@dataclasses.dataclass(frozen=True)
class TTSConfig:
    """Everything that decides what the audio sounds like — and what it costs.

    `settings` is a sorted tuple of pairs rather than a dict so the config stays hashable and
    the cache key cannot change with dict ordering.

    `kokoro_voice` is not part of the cache key: it is the local voice to use if ElevenLabs
    is unavailable. It has to be carried separately because tts.voice is an ElevenLabs id,
    which Kokoro cannot speak.
    """
    provider: str
    voice: str
    speed: float = 1.0
    model: str = ""
    settings: tuple = ()
    kokoro_voice: str = DEFAULT_KOKORO_VOICE
    #: Silence prepended by finish(). NOT a voice setting and NOT in the cache key: the
    #: provider bills for identical audio either way, and only the local silence changes.
    #: An unknown key inside voice_settings is a 422, so it is carried here instead.
    lead_in_s: float = LEAD_IN_S

    def voice_settings(self) -> dict:
        return dict(self.settings)

    def fallback(self) -> "TTSConfig":
        """The same spec narrated locally by Kokoro."""
        return dataclasses.replace(self, provider=KOKORO, voice=self.kokoro_voice,
                                   model="", settings=())


def _lead_in(block: dict) -> float:
    """The `tts.lead_in_s` a spec asks for, or the constant. Refuses an impossible one."""
    value = block.get("lead_in_s")
    if value is None:
        return LEAD_IN_S
    lead = float(value)
    if not 0.0 <= lead <= 1.0:
        raise SystemExit(f"tts.lead_in_s must be in [0, 1.0]; got {lead!r}. It is the "
                         f"silence prepended to every scene, and the word timings carry it.")
    return lead


def tts_config(spec: dict, voice: str | None = None, speed: float = 1.0) -> TTSConfig:
    block = spec.get("tts") or {}
    if not isinstance(block, dict):
        raise SystemExit(f"spec `tts:` must be a mapping, got {type(block).__name__}")
    provider = str(block.get("provider", KOKORO)).strip().lower()
    if provider not in PROVIDERS:
        raise SystemExit(f"unknown tts provider {provider!r}: choose one of "
                         f"{', '.join(PROVIDERS)}")
    legacy_voice = spec.get("voice")
    if provider == KOKORO:
        chosen = str(voice or block.get("voice") or legacy_voice or DEFAULT_KOKORO_VOICE)
        return TTSConfig(provider=KOKORO, voice=chosen, speed=float(speed),
                         kokoro_voice=chosen, lead_in_s=_lead_in(block))
    chosen = voice or block.get("voice")
    if not chosen:
        raise SystemExit("tts.provider is elevenlabs but no tts.voice was given. Set the "
                         "ElevenLabs voice_id in the spec (or pass --voice); a guessed id "
                         "is a billed request in somebody else's voice.")
    # --speed is a Kokoro control: this API takes a rate only inside voice_settings. A stray
    # --speed therefore used to change the cache key while changing nothing about the audio,
    # which re-bills a whole spec for bytes it already has. Make the spec say it or say no.
    spec_speed = block.get("speed")
    if float(speed) != 1.0 and (spec_speed is None or float(spec_speed) != float(speed)):
        raise SystemExit(
            f"--speed {float(speed):g} is a Kokoro control. ElevenLabs is sent a rate only "
            f"inside voice_settings, so this flag would change the cache key and re-bill for "
            f"byte-identical audio. The spec says tts.speed: {spec_speed!r}. Either set "
            f"`tts.speed: {float(speed):g}` in the spec to mean it, or drop --speed.")
    speed = float(spec_speed) if spec_speed is not None else float(speed)
    settings = dict(DEFAULT_VOICE_SETTINGS)
    for name in tuple(DEFAULT_VOICE_SETTINGS) + OPTIONAL_VOICE_SETTINGS:
        if name in block:
            settings[name] = block[name]
    return TTSConfig(provider=ELEVENLABS, voice=str(chosen), speed=float(speed),
                     model=str(block.get("model") or DEFAULT_EL_MODEL),
                     settings=tuple(sorted(settings.items())),
                     kokoro_voice=str(legacy_voice or DEFAULT_KOKORO_VOICE),
                     lead_in_s=_lead_in(block))


def narration_text(scene: dict) -> str:
    """One scene's narration, whitespace-collapsed exactly as the synthesiser receives it."""
    return " ".join(str(scene.get("narration") or "").split())


# ------------------------------------------------------------------------------- the cache key

def cache_hash(cfg: TTSConfig, text: str) -> str:
    """Every parameter that changes the audio (or the bill), in one stable digest."""
    payload = {"provider": cfg.provider, "voice": cfg.voice, "model": cfg.model,
               "voice_settings": cfg.voice_settings(), "text": text}
    if cfg.provider == KOKORO:
        # Kokoro resamples on speed, so the audio really does differ. ElevenLabs is never sent
        # the top-level speed — only voice_settings["speed"], which is already in the payload —
        # so including it here would invalidate the cache and re-bill for identical bytes.
        payload["speed"] = float(cfg.speed)
    return hashlib.sha1(json.dumps(payload, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")).hexdigest()


def legacy_kokoro_hash(voice: str, speed: float, text: str) -> str:
    """The pre-provider cache key: sha1("voice|speed|text")."""
    return hashlib.sha1(f"{voice}|{speed}|{text}".encode()).hexdigest()


def hash_matches(stored: str | None, cfg: TTSConfig, text: str) -> bool:
    """Is a cached WAV still valid for this config and text?

    The legacy shape is accepted for Kokoro only, so the six existing walkthroughs do not all
    re-narrate the first time this lands. An ElevenLabs config never matches it — a WAV whose
    provenance is unknown must not be assumed to be ElevenLabs audio.
    """
    if not stored:
        return False
    if stored == cache_hash(cfg, text):
        return True
    return cfg.provider == KOKORO and stored == legacy_kokoro_hash(cfg.voice, cfg.speed, text)


# ----------------------------------------------------------------------------------- the key

def api_key() -> str | None:
    """The ElevenLabs key: environment first, then the 0600 file. Never logged."""
    from_env = (os.environ.get(KEY_ENV) or "").strip()
    if from_env:
        return from_env
    try:
        value = pathlib.Path(KEY_FILE).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value or None


def no_key_message() -> str:
    return (f"no ElevenLabs key — set {KEY_ENV} in the environment or put the key in "
            f"{KEY_FILE} (chmod 600)")


# ---------------------------------------------------------------------------- credit estimate

def credits_per_char(model: str) -> float:
    """ElevenLabs bills 1 credit/character, halved on the flash and turbo models."""
    name = (model or "").lower()
    return 0.5 if ("flash" in name or "turbo" in name) else 1.0


def estimate_credits(model: str, chars: int) -> int:
    """Rounded up: the meter counts whole credits."""
    return int(math.ceil(chars * credits_per_char(model)))


def dry_run_lines(spec: dict, cfg: TTSConfig) -> list[str]:
    scenes = spec.get("scenes") or []
    lines, total = [], 0
    for i, scene in enumerate(scenes):
        n = len(narration_text(scene))
        total += n
        lines.append(f"scene {i:02d}: {n:>5} characters" + ("" if n else "   (no narration)"))
    lines.append(f"total: {total} characters across {len(scenes)} scenes")
    if cfg.provider == ELEVENLABS:
        rate = credits_per_char(cfg.model)
        lines.append(f"provider elevenlabs · voice {cfg.voice} · model {cfg.model} · "
                     f"{rate:g} credit/char -> ~{estimate_credits(cfg.model, total)} credits")
    else:
        lines.append(f"provider kokoro · voice {cfg.voice} · local synthesis -> 0 credits")
    lines.append("(dry run: nothing was sent and nothing was written)")
    return lines


# -------------------------------------------------------------------------- the network seams

def request_body(cfg: TTSConfig, text: str) -> dict:
    return {"text": text, "model_id": cfg.model, "voice_settings": cfg.voice_settings()}


def _post_tts(voice_id: str, key: str, body: dict,
              *, output_format: str = OUTPUT_FORMAT) -> tuple[int, bytes]:
    """The one synthesis network seam. Returns (status, body bytes). Tests monkeypatch this.

    The body bytes are the /with-timestamps JSON envelope — `audio_base64` plus `alignment` —
    not raw MP3. parse_timestamped_response() takes it apart.
    """
    import requests  # lazy: absent outside the TTS venv
    resp = requests.post(f"{API_BASE}/text-to-speech/{voice_id}/{TIMESTAMPS_PATH}",
                         headers={"xi-api-key": key, "accept": "application/json",
                                  "content-type": "application/json"},
                         params={"output_format": output_format},
                         json=body, timeout=TTS_TIMEOUT_S)
    return resp.status_code, resp.content


def _get_voices(key: str) -> tuple[int, dict]:
    """The read-only network seam (--tts-check). Tests monkeypatch this."""
    import requests  # lazy: absent outside the TTS venv
    resp = requests.get(f"{API_BASE}/voices", headers={"xi-api-key": key},
                        timeout=VOICES_TIMEOUT_S)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"detail": resp.text[:500]}


HTTP_HINTS = {
    401: "the key was rejected (401) — check the key in the environment or the key file",
    402: "the account is out of credits (402) — top up, or set tts.provider: kokoro",
    403: "this key may not use that voice or model (403)",
    422: "the request body was refused (422) — usually an unknown model_id or a "
         "voice_settings key this model does not take",
    429: "rate limited (429) — re-run; the cache keeps every scene that already synthesized",
}


def http_error_message(status: int, body, key: str | None = None, limit: int = 300) -> str:
    """One clear sentence per failure mode, with the provider's own text appended.

    Redacted BEFORE it is truncated: trimming first can cut a token in half and leave a
    usable prefix behind (the lesson session.fail_card learned the hard way).
    """
    hint = HTTP_HINTS.get(status)
    if hint is None:
        hint = (f"server error ({status}) — ElevenLabs' side, not ours; retry later"
                if status >= 500 else f"HTTP {status}")
    raw = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body or "")
    safe = redact(raw, key).strip()
    if len(safe) > limit:
        safe = safe[:limit] + " […truncated]"
    return f"ElevenLabs: {hint}. {safe}".strip()


# --------------------------------------------------------------------------------- word timings
#
# Both providers hand back timings against the RAW synthesised audio. finish() then trims the
# silence either side and prepends LEAD_IN_S, and it is that WAV make_short concatenates — so
# every timing is moved by `words_offset(trim_start)` before it is written. Getting this wrong
# does not fail anything; it just makes the captions drift against the voice.

def parse_timestamped_response(content, key: str | None = None) -> tuple[bytes, dict | None]:
    """The /with-timestamps envelope -> (mp3 bytes, alignment). Raises TTSError if unusable.

    A missing `alignment` is not an error: the audio is still good, and the scene simply
    renders without captions. A missing or undecodable `audio_base64` is, because there is
    then no scene at all.
    """
    raw = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) \
        else str(content or "")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise TTSError(f"ElevenLabs: /{TIMESTAMPS_PATH} returned a body that is not JSON. "
                       f"{redact(raw, key)[:300]}") from None
    if not isinstance(payload, dict) or not payload.get("audio_base64"):
        raise TTSError(f"ElevenLabs: /{TIMESTAMPS_PATH} returned no audio "
                       f"(no `audio_base64` in the response). "
                       f"{redact(raw, key)[:300]}")
    try:
        audio = base64.b64decode(payload["audio_base64"], validate=True)
    except Exception:  # noqa: BLE001 — binascii.Error and anything else it may raise
        raise TTSError(f"ElevenLabs: the `audio_base64` in the /{TIMESTAMPS_PATH} response "
                       f"could not be decoded as base64") from None
    alignment = payload.get("alignment") or None
    return audio, (alignment if isinstance(alignment, dict) else None)


def fold_alignment(alignment) -> list | None:
    """ElevenLabs' per-CHARACTER alignment -> per-word timings.

    Split on whitespace only, so punctuation stays attached to the word it follows — a cue
    reading "stop" where the voice said "stop!" loses the line's whole shape.
    """
    if not isinstance(alignment, dict):
        return None
    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not isinstance(chars, list) or not isinstance(starts, list) or not isinstance(ends, list):
        return None
    if not chars or not (len(chars) == len(starts) == len(ends)):
        return None
    words, text, start, end = [], "", None, None
    for char, char_start, char_end in zip(chars, starts, ends):
        char = str(char)
        if not char.strip():
            if text:
                words.append({"text": text, "start": start, "end": end})
            text, start, end = "", None, None
            continue
        try:
            char_start, char_end = float(char_start), float(char_end)
        except (TypeError, ValueError):
            continue
        if start is None:
            start = char_start
        end = char_end
        text += char
    if text:
        words.append({"text": text, "start": start, "end": end})
    return words


def fold_kokoro_tokens(groups) -> list | None:
    """Kokoro's MTokens -> per-word timings. `groups` is [(tokens, chunk offset in seconds)].

    KPipeline yields one Result per chunk, each timed from its own zero, so the chunk offset
    is the audio already emitted before it. A token carries `whitespace` when it ENDS a word,
    which is what keeps misaki's separate punctuation tokens ("Magic" + ".") on the word they
    belong to. Timestamps exist only when the English G2P ran — `None` means this scene gets
    no captions rather than invented ones.
    """
    words, saw_timing = [], False
    for tokens, offset in (groups or []):
        text, start, end = "", None, None
        for token in (tokens or []):
            token_start = getattr(token, "start_ts", None)
            token_end = getattr(token, "end_ts", None)
            if token_start is not None:
                saw_timing = True
                if start is None:
                    start = float(offset) + float(token_start)
            if token_end is not None:
                end = float(offset) + float(token_end)
            text += str(getattr(token, "text", "") or "")
            if str(getattr(token, "whitespace", "") or ""):
                if text.strip() and start is not None and end is not None:
                    words.append({"text": text.strip(), "start": start, "end": end})
                text, start, end = "", None, None
        if text.strip() and start is not None and end is not None:
            words.append({"text": text.strip(), "start": start, "end": end})
    return words if saw_timing else None


def words_offset(trim_start_samples: int, lead_in_s: float = LEAD_IN_S) -> float:
    """Seconds to add to a raw timing so it lines up with the finished WAV.

    finish() drops `trim_start_samples` from the front and prepends `lead_in_s` of silence.
    """
    return lead_in_s - (int(trim_start_samples) / SR)


def shift_words(words, offset: float):
    """Move every timing by `offset`, clamped at zero. `None` in, `None` out."""
    if words is None:
        return None
    out = []
    for word in words:
        start = max(0.0, float(word["start"]) + offset)
        end = max(start, float(word["end"]) + offset)
        out.append({"text": word["text"], "start": round(start, 3), "end": round(end, 3)})
    return out


# ------------------------------------------------------------------------------- audio plumbing

def run(cmd: list) -> None:
    """The single subprocess seam (ffmpeg), as in make_short.py. Tests monkeypatch this."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise TTSError(redact(f"ffmpeg failed ({r.returncode}): {' '.join(str(c) for c in cmd)}"
                              f"\n{(r.stderr or '')[-800:]}"))


def ffmpeg_cmd(mp3: pathlib.Path, wav: pathlib.Path) -> list:
    """ElevenLabs MP3 -> the pipeline's format: 24 kHz, mono, 16-bit PCM WAV."""
    return [FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3),
            "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", "-f", "wav", str(wav)]


def trim_bounds(audio) -> tuple[int, int]:
    """The [start, stop) samples finish() keeps. Pulled out so word timings can follow it."""
    import numpy as np  # lazy: absent outside the TTS venv
    idx = np.where(np.abs(audio) > 0.01)[0]
    if not len(idx):
        return 0, len(audio)
    return max(0, int(idx[0]) - int(0.1 * SR)), int(idx[-1]) + int(0.25 * SR)


def finish(audio, lead_in_s: float = LEAD_IN_S):
    """Trim the silence either side and prepend `lead_in_s` — the Kokoro path, always.

    Both providers go through here, so an ElevenLabs scene lines up against the frames exactly
    as a Kokoro one does and assemble.py needs no change.
    """
    import numpy as np  # lazy: absent outside the TTS venv
    audio = np.asarray(audio, dtype=np.float32)
    start, stop = trim_bounds(audio)
    audio = audio[start:stop]
    return np.concatenate([np.zeros(int(lead_in_s * SR), dtype=np.float32), audio])


def finish_with_words(audio, words, lead_in_s: float = LEAD_IN_S):
    """finish(), plus the same scene's word timings moved onto the WAV it produced."""
    import numpy as np  # lazy: absent outside the TTS venv
    audio = np.asarray(audio, dtype=np.float32)
    start, _stop = trim_bounds(audio)
    return finish(audio, lead_in_s), shift_words(words, words_offset(start, lead_in_s))


def write_wav(path: pathlib.Path, audio) -> None:
    """Write through a temp file so a crash never leaves a half-written scene in the cache."""
    import soundfile as sf  # lazy: absent outside the TTS venv
    path = pathlib.Path(path)
    tmp = path.with_suffix(".part.wav")
    sf.write(str(tmp), audio, SR)
    os.replace(tmp, path)


def decode_to_wav(mp3_bytes: bytes, wav_path: pathlib.Path,
                  alignment: dict | None = None,
                  lead_in_s: float = LEAD_IN_S) -> tuple[float, list | None]:
    """MP3 bytes -> a finished scene WAV. Returns (seconds, word timings or None)."""
    import soundfile as sf  # lazy: absent outside the TTS venv
    wav_path = pathlib.Path(wav_path)
    mp3 = wav_path.with_suffix(".mp3")
    raw = wav_path.with_suffix(".raw.wav")
    mp3.write_bytes(mp3_bytes)
    try:
        run(ffmpeg_cmd(mp3, raw))
        audio, sr = sf.read(str(raw), dtype="float32")
        if sr != SR:
            raise TTSError(f"ffmpeg produced {sr} Hz audio, expected {SR} Hz")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        audio, words = finish_with_words(audio, fold_alignment(alignment), lead_in_s)
        write_wav(wav_path, audio)
        return len(audio) / SR, words
    finally:
        for scratch in (mp3, raw):
            try:
                scratch.unlink()
            except OSError:
                pass


# ------------------------------------------------------------------------------- synthesis

_KOKORO_PIPE = None


def _kokoro_pipeline():
    global _KOKORO_PIPE
    if _KOKORO_PIPE is None:
        from kokoro import KPipeline  # lazy: absent outside the TTS venv
        _KOKORO_PIPE = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    return _KOKORO_PIPE


def synth_kokoro(cfg: TTSConfig, text: str, wav_path: pathlib.Path) -> tuple[float, list | None]:
    """One scene through the local model. Returns (seconds, word timings or None).

    KPipeline yields one Result per chunk; each carries its own audio and, when the English
    G2P ran, MTokens with start_ts/end_ts timed from that chunk's zero. The running sample
    count is therefore the offset each chunk's timings need.
    """
    import numpy as np  # lazy: absent outside the TTS venv
    pipe = _kokoro_pipeline()
    chunks, groups, emitted = [], [], 0
    for result in pipe(text, voice=cfg.voice, speed=cfg.speed):
        chunk = getattr(result, "audio", None)
        if chunk is None:
            chunk = result[2]
        groups.append((getattr(result, "tokens", None), emitted / SR))
        chunks.append(chunk)
        emitted += len(chunk)
    audio, words = finish_with_words(np.concatenate(chunks).astype(np.float32),
                                     fold_kokoro_tokens(groups), cfg.lead_in_s)
    write_wav(wav_path, audio)
    return len(audio) / SR, words


def transport_message(exc: BaseException, key: str | None = None, limit: int = 300) -> str:
    """A dropped connection as one redacted line, not a traceback.

    requests raises ConnectionError/Timeout/SSLError whose str() embeds the full request URL,
    and urllib3's chained context can carry headers. Collapsed to a single line because this
    ends up in a build log and, one day, a queue card. Redacted before it is truncated.
    """
    detail = " ".join(f"{type(exc).__name__}: {exc}".split())
    safe = redact(detail, key)
    if len(safe) > limit:
        safe = safe[:limit] + " […truncated]"
    return f"ElevenLabs: could not reach {API_BASE} — {safe}"


def synth_elevenlabs(cfg: TTSConfig, text: str, wav_path: pathlib.Path,
                     key: str) -> tuple[float, list | None]:
    try:
        status, content = _post_tts(cfg.voice, key, request_body(cfg, text))
    except TTSError:
        raise
    except Exception as exc:  # noqa: BLE001 — a dead network is a failed scene, not a crash
        # `from None`: an uncaught traceback prints __cause__/__context__, and those carry the
        # raw exception text this function exists to redact.
        raise TTSError(transport_message(exc, key)) from None
    if status >= 300:
        raise TTSError(http_error_message(status, content, key))
    if not content:
        raise TTSError("ElevenLabs: HTTP 200 with an empty body — no audio to decode")
    audio, alignment = parse_timestamped_response(content, key)
    return decode_to_wav(audio, wav_path, alignment, cfg.lead_in_s)


def synth_scene(cfg: TTSConfig, text: str, wav_path: pathlib.Path,
                key: str | None = None) -> tuple[float, list | None]:
    """One scene, whichever provider the config names. Returns (seconds, word timings)."""
    if cfg.provider == ELEVENLABS:
        return synth_elevenlabs(cfg, text, wav_path, key)
    return synth_kokoro(cfg, text, wav_path)


# ------------------------------------------------------------------------------- --tts-check

def tts_check(cfg: TTSConfig) -> int:
    """Prove the configured voice_id exists on this account. 0 = yes, 2 = anything else."""
    if cfg.provider != ELEVENLABS:
        print(f"--tts-check checks the ElevenLabs API, but this spec's provider is "
              f"{cfg.provider!r}. Add a `tts: {{provider: elevenlabs, voice: …}}` block.",
              file=sys.stderr)
        return 2
    key = api_key()
    if not key:
        print(f"--tts-check: {no_key_message()}", file=sys.stderr)
        return 2
    try:
        status, payload = _get_voices(key)
    except Exception as exc:  # noqa: BLE001 — a transport error is a failed check, not a crash
        print(redact(f"--tts-check: GET {API_BASE}/voices failed: "
                     f"{type(exc).__name__}: {exc}", key), file=sys.stderr)
        return 2
    if status >= 300:
        print(f"--tts-check: {http_error_message(status, json.dumps(payload), key)}",
              file=sys.stderr)
        return 2
    voices = payload.get("voices") or []
    match = next((v for v in voices if str(v.get("voice_id")) == cfg.voice), None)
    if match is None:
        listed = ", ".join(f"{v.get('name')} ({v.get('voice_id')})" for v in voices[:8]) or "(none)"
        print(f"--tts-check: voice_id {cfg.voice!r} is not on this account "
              f"({len(voices)} voices available: {listed}). Fix tts.voice in the spec.",
              file=sys.stderr)
        return 2
    print(f"OK  elevenlabs voice {cfg.voice} = {match.get('name')} · "
          f"category {match.get('category')} · model {cfg.model} · "
          f"{len(voices)} voices on the account")
    return 0


# ------------------------------------------------------------------------------------- main

def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", help="directory for scene WAVs + durations.json "
                                  "(required unless --dry-run or --tts-check)")
    ap.add_argument("--voice", help="override the spec's voice for the selected provider")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="print character counts and the credit estimate; send nothing")
    ap.add_argument("--tts-check", action="store_true",
                    help="confirm the configured ElevenLabs voice_id exists, then exit")
    ap.add_argument("--allow-fallback", action="store_true",
                    help="on an ElevenLabs failure, narrate that scene with Kokoro instead "
                         "of failing the build (mixes voices — off by default)")
    ap.add_argument("--require-provider", choices=PROVIDERS, default=None,
                    help="refuse to synthesize anything unless narration resolves to this "
                         "provider. Turns the silent no-key fallback into a failed build, "
                         "which is what a paid batch wants")
    a = ap.parse_args(argv)

    import yaml  # lazy: absent outside the TTS venv
    with open(a.spec) as fh:
        spec = yaml.safe_load(fh)
    cfg = tts_config(spec, a.voice, a.speed)

    if a.tts_check:
        return tts_check(cfg)
    if a.dry_run:
        for line in dry_run_lines(spec, cfg):
            print(line)
        return 0
    if not a.out:
        ap.error("--out is required unless --dry-run or --tts-check")

    key = api_key() if cfg.provider == ELEVENLABS else None
    if cfg.provider == ELEVENLABS and not key:
        # One loud line, then carry on locally: every dry run, test and CI path in this repo
        # must keep working on a machine that has no ElevenLabs key.
        print(f"!!! ELEVENLABS FALLBACK: {no_key_message()}. Narrating with Kokoro "
              f"({cfg.fallback().voice}) instead — this build will NOT sound like an "
              f"ElevenLabs one. Run with --tts-check to diagnose.",
              file=sys.stderr, flush=True)
        cfg = cfg.fallback()

    # After the fallback decision, before anything is written: a Saturday batch that silently
    # rendered in Kokoro because a key file went missing is exactly what this flag prevents.
    if a.require_provider and cfg.provider != a.require_provider:
        print(f"--require-provider {a.require_provider}, but narration resolved to "
              f"{cfg.provider}. Nothing was synthesized and nothing was written.",
              file=sys.stderr, flush=True)
        return 2

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    durations = {}
    for i, scene in enumerate(spec["scenes"]):
        text = narration_text(scene)
        wav, meta = out / f"scene_{i:02d}.wav", out / f"scene_{i:02d}.json"
        if not text:
            durations[i] = 0.0
            continue
        # The words file is part of the cache: a hit that yielded no timings would make the
        # first captioned render of an old build come out silently uncaptioned. A scene
        # cached before captions existed therefore re-synthesizes once — free on Kokoro,
        # one billed request on ElevenLabs — and is a hit forever after.
        if wav.exists() and meta.exists() and captions.words_path(wav).exists():
            try:
                stored = json.loads(meta.read_text())
            except (OSError, ValueError):
                stored = {}
            # The lead-in is deliberately NOT in the cache key — it changes no billed byte —
            # so it is compared here instead: a spec that shortens it re-renders the WAV
            # locally (and its word timings with it) without re-billing anything it need not.
            if (hash_matches(stored.get("hash"), cfg, text)
                    and float(stored.get("lead_in_s", LEAD_IN_S)) == cfg.lead_in_s):
                durations[i] = stored["seconds"]
                print(f"scene {i:02d}: cached {durations[i]:.1f}s "
                      f"[{stored.get('provider_used', KOKORO)}]")
                continue
        # Drop the meta BEFORE synthesizing: a crash then leaves a scene with no meta, which
        # re-synthesizes next run. Leaving a stale meta beside a new WAV would instead cache a
        # wrong duration, and assemble.py would cut the audio against the wrong frame length.
        scene_cfg = cfg
        try:
            meta.unlink()
        except OSError:
            pass
        try:
            seconds, words = synth_scene(scene_cfg, text, wav, key)
        except TTSError as exc:
            print(f"scene {i:02d}: {exc}", file=sys.stderr, flush=True)
            if not (scene_cfg.provider == ELEVENLABS and a.allow_fallback):
                print("Refusing to build half an ElevenLabs video and half a Kokoro one. "
                      "Fix the error, or pass --allow-fallback to narrate the failed scenes "
                      "locally. Scenes already synthesized stay cached.",
                      file=sys.stderr, flush=True)
                return 2
            scene_cfg = scene_cfg.fallback()
            print(f"scene {i:02d}: --allow-fallback — narrating with kokoro "
                  f"({scene_cfg.voice})", file=sys.stderr, flush=True)
            try:
                seconds, words = synth_scene(scene_cfg, text, wav, None)
            except TTSError as retry_exc:
                print(f"scene {i:02d}: the Kokoro fallback failed too: {retry_exc}",
                      file=sys.stderr, flush=True)
                return 2
        durations[i] = seconds
        # Written BEFORE the meta, for the same reason the meta is dropped before synthesis:
        # the meta is what says this scene is cached, so nothing may claim a hit until every
        # file a hit promises is on disk.
        # `not words`, not `words is None`: a fold that came back EMPTY is a scene with no
        # captions, not a scene with zero words, and caching `[]` would be a cache hit that
        # promises timings and delivers none. Normalised to `null` so it reads back as absent.
        if not words:
            words = None
            print(f"scene {i:02d}: {scene_cfg.provider} returned no word timings — captions "
                  f"will be skipped for this scene", file=sys.stderr, flush=True)
        captions.write_words(wav, words)
        meta.write_text(json.dumps({"hash": cache_hash(scene_cfg, text), "seconds": seconds,
                                    "voice": scene_cfg.voice,
                                    "provider_used": scene_cfg.provider,
                                    "model": scene_cfg.model, "speed": scene_cfg.speed,
                                    "lead_in_s": scene_cfg.lead_in_s,
                                    "text": text}))
        print(f"scene {i:02d}: {seconds:.1f}s  [{scene_cfg.provider}]", flush=True)
    with open(out / "durations.json", "w") as fh:
        json.dump(durations, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
