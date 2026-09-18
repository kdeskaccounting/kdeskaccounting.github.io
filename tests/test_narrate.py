"""narrate.py's provider selection, cache key, credit estimate and CLI — no network, no venv.

narrate.py is run by the TTS venv (`scripts/video/.venv-tts/bin/python`), which has yaml,
numpy, soundfile, kokoro and requests. This test environment has none of them, so every one
of those imports lives inside the function that needs it and the module imports with the
standard library alone — the same rule make_short.py follows.

The seams stubbed here:
  _post_tts / _get_voices  the two HTTP calls (nothing else does network I/O)
  run                      the single subprocess seam (ffmpeg), as in make_short.py
  synth_scene              one scene's audio, so main() can be driven without either

RFC 2606 domains and obviously-fake keys only. A real key never appears in a test.
"""
import json
import pathlib
import sys
import types

import pytest

import narrate as N

FAKE_KEY = "sk_fake_elevenlabs_key_0123456789"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"          # the ElevenLabs id used in the docs example


def spec_with(tts=None, voice=None, scenes=None):
    spec = {"slug": "demo", "scenes": scenes if scenes is not None else [
        {"narration": "First scene."}, {"narration": "Second scene."}]}
    if tts is not None:
        spec["tts"] = tts
    if voice is not None:
        spec["voice"] = voice
    return spec


# --- provider selection from the spec --------------------------------------------------

def test_a_spec_with_no_tts_block_is_kokoro_on_the_historical_default_voice():
    cfg = N.tts_config(spec_with())
    assert cfg.provider == N.KOKORO
    assert cfg.voice == N.DEFAULT_KOKORO_VOICE == "am_michael"
    assert cfg.model == ""


def test_a_legacy_top_level_voice_still_selects_kokoro():
    """Every scenes.yaml in marketing/video/ is `voice: am_michael` with no tts: block."""
    cfg = N.tts_config(spec_with(voice="af_heart"))
    assert (cfg.provider, cfg.voice) == (N.KOKORO, "af_heart")


def test_the_tts_block_selects_elevenlabs_with_the_documented_defaults():
    cfg = N.tts_config(spec_with(tts={"provider": "elevenlabs", "voice": VOICE_ID}))
    assert cfg.provider == N.ELEVENLABS
    assert cfg.voice == VOICE_ID
    assert cfg.model == N.DEFAULT_EL_MODEL == "eleven_multilingual_v2"
    assert cfg.voice_settings() == {"stability": 0.5, "similarity_boost": 0.75}


def test_the_tts_block_carries_model_and_voice_settings_through():
    cfg = N.tts_config(spec_with(tts={"provider": "elevenlabs", "voice": VOICE_ID,
                                      "model": "eleven_flash_v2_5", "stability": 0.2,
                                      "similarity_boost": 0.9, "style": 0.1,
                                      "use_speaker_boost": True}))
    assert cfg.model == "eleven_flash_v2_5"
    assert cfg.voice_settings() == {"stability": 0.2, "similarity_boost": 0.9,
                                    "style": 0.1, "use_speaker_boost": True}


def test_provider_kokoro_in_the_tts_block_uses_that_blocks_voice():
    cfg = N.tts_config(spec_with(tts={"provider": "kokoro", "voice": "bf_emma"}))
    assert (cfg.provider, cfg.voice) == (N.KOKORO, "bf_emma")
    assert cfg.voice_settings() == {}, "kokoro has no ElevenLabs voice_settings"


@pytest.mark.parametrize("given", ["ElevenLabs", "  elevenlabs  ", "ELEVENLABS"])
def test_the_provider_name_is_read_case_and_whitespace_insensitively(given):
    cfg = N.tts_config(spec_with(tts={"provider": given, "voice": VOICE_ID}))
    assert cfg.provider == N.ELEVENLABS


def test_an_unknown_provider_is_refused_by_name():
    with pytest.raises(SystemExit) as e:
        N.tts_config(spec_with(tts={"provider": "openai", "voice": "x"}))
    assert "openai" in str(e.value) and "elevenlabs" in str(e.value)


def test_elevenlabs_without_a_voice_id_is_refused_rather_than_guessed():
    """A wrong voice_id is a billed request in someone else's voice."""
    with pytest.raises(SystemExit) as e:
        N.tts_config(spec_with(tts={"provider": "elevenlabs"}))
    assert "voice" in str(e.value).lower()


def test_the_cli_voice_flag_overrides_the_spec_for_the_selected_provider():
    cfg = N.tts_config(spec_with(tts={"provider": "elevenlabs", "voice": VOICE_ID}),
                       voice="OTHERVOICEID12345678")
    assert cfg.voice == "OTHERVOICEID12345678"


def test_an_elevenlabs_spec_remembers_which_kokoro_voice_to_fall_back_to():
    """tts.voice is an ElevenLabs id — Kokoro cannot speak it, so the fallback needs its own."""
    cfg = N.tts_config(spec_with(tts={"provider": "elevenlabs", "voice": VOICE_ID},
                                 voice="af_heart"))
    assert cfg.kokoro_voice == "af_heart"
    back = cfg.fallback()
    assert (back.provider, back.voice) == (N.KOKORO, "af_heart")
    assert back.model == "" and back.voice_settings() == {}
    assert back.speed == cfg.speed


def test_the_fallback_voice_defaults_when_the_spec_names_no_kokoro_voice():
    cfg = N.tts_config(spec_with(tts={"provider": "elevenlabs", "voice": VOICE_ID}))
    assert cfg.fallback().voice == N.DEFAULT_KOKORO_VOICE


# --- the cache key ---------------------------------------------------------------------

EL = {"provider": "elevenlabs", "voice": VOICE_ID}


@pytest.mark.parametrize("a,b", [
    # provider
    (N.tts_config(spec_with(tts=EL)), N.tts_config(spec_with(voice="am_michael"))),
    # model
    (N.tts_config(spec_with(tts=EL)),
     N.tts_config(spec_with(tts=dict(EL, model="eleven_flash_v2_5")))),
    # voice id
    (N.tts_config(spec_with(tts=EL)), N.tts_config(spec_with(tts=dict(EL, voice="OTHER")))),
    # voice_settings
    (N.tts_config(spec_with(tts=EL)), N.tts_config(spec_with(tts=dict(EL, stability=0.9)))),
])
def test_the_cache_key_changes_when_any_of_the_billed_parameters_changes(a, b):
    assert N.cache_hash(a, "Same words.") != N.cache_hash(b, "Same words.")


def test_the_provider_alone_changes_the_cache_key():
    """The parametrized pair above also differs by model (kokoro has none), so a hash that
    dropped `provider` would still pass it. Construct two configs identical but for provider."""
    a = N.TTSConfig(provider=N.KOKORO, voice="same", speed=1.0)
    b = N.TTSConfig(provider=N.ELEVENLABS, voice="same", speed=1.0)
    assert N.cache_hash(a, "Words.") != N.cache_hash(b, "Words.")


def test_the_cache_key_changes_with_text():
    cfg = N.tts_config(spec_with(tts=EL))
    assert N.cache_hash(cfg, "Words.") != N.cache_hash(cfg, "Other words.")


def test_speed_is_part_of_the_kokoro_cache_key():
    """Kokoro really does resample on --speed, so the audio differs and the key must too."""
    cfg = N.tts_config(spec_with(voice="am_michael"))
    fast = N.tts_config(spec_with(voice="am_michael"), speed=1.2)
    assert N.cache_hash(cfg, "Words.") != N.cache_hash(fast, "Words.")


def test_the_cache_key_is_stable_across_runs_so_unchanged_text_is_never_re_billed():
    cfg = N.tts_config(spec_with(tts=dict(EL, similarity_boost=0.75, stability=0.5)))
    other = N.tts_config(spec_with(tts=dict(EL, stability=0.5, similarity_boost=0.75)))
    assert N.cache_hash(cfg, "Words.") == N.cache_hash(other, "Words.")


def test_a_kokoro_wav_cached_under_the_old_voice_speed_text_hash_is_still_a_hit():
    """The pre-provider cache format. Re-synthesis is free but not instant; keep the hits."""
    cfg = N.tts_config(spec_with(voice="am_michael"))
    legacy = N.legacy_kokoro_hash("am_michael", 1.0, "Words.")
    assert N.hash_matches(legacy, cfg, "Words.")
    assert N.hash_matches(N.cache_hash(cfg, "Words."), cfg, "Words.")


def test_the_legacy_hash_is_not_accepted_for_an_elevenlabs_config():
    cfg = N.tts_config(spec_with(tts=EL))
    assert not N.hash_matches(N.legacy_kokoro_hash(VOICE_ID, 1.0, "Words."), cfg, "Words.")


# --- the key -------------------------------------------------------------------------

def test_the_environment_variable_wins_over_the_key_file(tmp_path, monkeypatch):
    kf = tmp_path / "elevenlabs-api-key.txt"
    kf.write_text("from_the_file_9999\n")
    monkeypatch.setattr(N, "KEY_FILE", kf)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "from_the_env_9999")
    assert N.api_key() == "from_the_env_9999"


def test_the_key_file_is_read_and_stripped_when_the_environment_is_empty(tmp_path, monkeypatch):
    kf = tmp_path / "elevenlabs-api-key.txt"
    kf.write_text("  from_the_file_9999\n")
    monkeypatch.setattr(N, "KEY_FILE", kf)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert N.api_key() == "from_the_file_9999"


def test_no_key_anywhere_reads_as_absent_rather_than_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "KEY_FILE", tmp_path / "nothing-here.txt")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert N.api_key() is None


# --- credit arithmetic -----------------------------------------------------------------

@pytest.mark.parametrize("model,rate", [
    ("eleven_multilingual_v2", 1.0),
    ("eleven_v3", 1.0),
    ("eleven_flash_v2_5", 0.5),
    ("eleven_turbo_v2_5", 0.5),
])
def test_flash_and_turbo_bill_half_a_credit_per_character(model, rate):
    assert N.credits_per_char(model) == rate


def test_estimated_credits_round_up_because_the_meter_is_whole_credits():
    assert N.estimate_credits("eleven_multilingual_v2", 412) == 412
    assert N.estimate_credits("eleven_flash_v2_5", 412) == 206
    assert N.estimate_credits("eleven_flash_v2_5", 101) == 51


def test_scene_text_collapses_whitespace_the_way_the_synthesiser_sees_it():
    assert N.narration_text({"narration": "  two   lines\nof  text "}) == "two lines of text"
    assert N.narration_text({}) == ""
    assert N.narration_text({"narration": None}) == ""


# --- the two HTTP seams ----------------------------------------------------------------

class _Resp:
    def __init__(self, status=200, content=b"", payload=None, text=""):
        self.status_code, self.content, self._payload, self.text = status, content, payload, text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_post_tts_sends_the_documented_request(monkeypatch):
    """The synthesis call is the /with-timestamps one: same body, JSON back instead of MP3.

    The word timings burned-in captions need come from the same request that makes the audio,
    so there is never a second billed call and never a transcript that disagrees with it.
    """
    seen = {}

    def post(url, headers=None, params=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, params=params, body=json, timeout=timeout)
        return _Resp(200, b'{"audio_base64":""}')

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=post))
    status, content = N._post_tts(VOICE_ID, FAKE_KEY, {"text": "hi", "model_id": "m"})
    assert (status, content) == (200, b'{"audio_base64":""}')
    assert seen["url"] == \
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps"
    assert seen["headers"]["xi-api-key"] == FAKE_KEY
    assert seen["headers"]["accept"] == "application/json"
    assert seen["params"] == {"output_format": "mp3_44100_128"}
    assert seen["body"] == {"text": "hi", "model_id": "m"}
    assert seen["timeout"] == N.TTS_TIMEOUT_S


def test_get_voices_hits_the_voices_endpoint_with_the_key_header(monkeypatch):
    seen = {}

    def get(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers, timeout=timeout)
        return _Resp(200, payload={"voices": []})

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(get=get))
    assert N._get_voices(FAKE_KEY) == (200, {"voices": []})
    assert seen["url"] == "https://api.elevenlabs.io/v1/voices"
    assert seen["headers"] == {"xi-api-key": FAKE_KEY}


def test_get_voices_survives_a_non_json_body(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(
        get=lambda *a, **k: _Resp(502, text="<html>bad gateway</html>")))
    status, payload = N._get_voices(FAKE_KEY)
    assert status == 502 and "bad gateway" in payload["detail"]


def test_the_request_body_is_text_model_id_and_voice_settings():
    cfg = N.tts_config(spec_with(tts=EL))
    assert N.request_body(cfg, "Hello.") == {
        "text": "Hello.", "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}


# --- error text ------------------------------------------------------------------------

@pytest.mark.parametrize("status,needle", [
    (401, "key was rejected"), (402, "out of credits"), (429, "rate limited"),
    (500, "server error"), (503, "server error"), (422, "refused"),
])
def test_each_documented_failure_gets_its_own_sentence(status, needle):
    assert needle in N.http_error_message(status, b"{}")


def test_an_error_body_that_echoes_the_key_never_reaches_the_caller():
    """ElevenLabs 401 bodies quote the request. The key must not survive into stdout."""
    body = json.dumps({"detail": {"message": f"Invalid API key: {FAKE_KEY}"}}).encode()
    out = N.http_error_message(401, body, FAKE_KEY)
    assert FAKE_KEY not in out
    assert "***" in out


def test_a_long_error_body_is_redacted_before_it_is_truncated():
    body = ("x" * 400 + FAKE_KEY).encode()
    out = N.http_error_message(401, body, FAKE_KEY, limit=500)
    assert FAKE_KEY not in out


def test_the_env_key_is_masked_even_when_it_is_not_handed_in(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_env_fake_key_01234567")
    N.session.known_secrets.cache_clear()
    try:
        out = N.http_error_message(401, b"bad key sk_env_fake_key_01234567")
        assert "sk_env_fake_key_01234567" not in out
    finally:
        N.session.known_secrets.cache_clear()


# --- ffmpeg --------------------------------------------------------------------------

def test_the_ffmpeg_command_produces_the_pipelines_own_wav_format(tmp_path):
    cmd = N.ffmpeg_cmd(tmp_path / "a.mp3", tmp_path / "a.wav")
    assert cmd[0] == N.FFMPEG
    assert cmd[-1] == str(tmp_path / "a.wav")
    for flag, value in (("-ac", "1"), ("-ar", "24000"), ("-c:a", "pcm_s16le")):
        assert cmd[cmd.index(flag) + 1] == value
    assert str(tmp_path / "a.mp3") in cmd


def test_a_failed_ffmpeg_raises_a_redacted_tts_error(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_env_fake_key_01234567")
    N.session.known_secrets.cache_clear()
    monkeypatch.setattr(N.subprocess, "run", lambda *a, **k: types.SimpleNamespace(
        returncode=1, stderr="boom sk_env_fake_key_01234567"))
    try:
        with pytest.raises(N.TTSError) as e:
            N.run([N.FFMPEG, "-i", "x"])
        assert "sk_env_fake_key_01234567" not in str(e.value)
        assert "ffmpeg failed" in str(e.value)
    finally:
        N.session.known_secrets.cache_clear()


# --- synth_elevenlabs error handling ---------------------------------------------------

def test_a_non_2xx_becomes_a_tts_error_and_decodes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (402, b'{"detail":"no credits"}'))
    monkeypatch.setattr(N, "decode_to_wav", lambda *a, **k: pytest.fail("must not decode"))
    cfg = N.tts_config(spec_with(tts=EL))
    with pytest.raises(N.TTSError) as e:
        N.synth_elevenlabs(cfg, "Hello.", tmp_path / "scene_00.wav", FAKE_KEY)
    assert "out of credits" in str(e.value)


def test_an_empty_200_body_is_a_failure_not_a_silent_scene(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (200, b""))
    cfg = N.tts_config(spec_with(tts=EL))
    with pytest.raises(N.TTSError) as e:
        N.synth_elevenlabs(cfg, "Hello.", tmp_path / "scene_00.wav", FAKE_KEY)
    assert "empty body" in str(e.value)


def test_a_2xx_decodes_the_mp3_it_was_handed(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(N, "_post_tts", lambda v, k, b, **kw: (200, _timestamped()))
    monkeypatch.setattr(N, "decode_to_wav",
                        lambda content, path, alignment=None, lead_in_s=N.LEAD_IN_S:
                        seen.update(content=content, path=path) or (3.25, None))
    cfg = N.tts_config(spec_with(tts=EL))
    assert N.synth_elevenlabs(cfg, "Hello.", tmp_path / "scene_00.wav", FAKE_KEY) == (3.25, None)
    assert seen["content"] == b"ID3audio"


# --- main(): the synthesis loop --------------------------------------------------------

MAIN_SPEC_SCENES = [{"narration": "First scene."}, {"narration": ""},
                    {"narration": "Third scene."}]


@pytest.fixture
def drive(tmp_path, monkeypatch):
    """Run main() with yaml stubbed, no key on the machine, and synth_scene recorded."""
    holder = types.SimpleNamespace(spec=spec_with(scenes=[dict(s) for s in MAIN_SPEC_SCENES]),
                                   calls=[], out=tmp_path / "audio", seconds=2.5, fail_on=None,
                                   words=[{"text": "First", "start": 0.3, "end": 0.7}])
    monkeypatch.setitem(sys.modules, "yaml",
                        types.SimpleNamespace(safe_load=lambda fh: holder.spec))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")

    def fake_synth(cfg, text, wav_path, key=None):
        holder.calls.append(types.SimpleNamespace(cfg=cfg, text=text, key=key))
        if holder.fail_on is not None and text == holder.fail_on and cfg.provider == N.ELEVENLABS:
            raise N.TTSError("ElevenLabs: rate limited (429) — re-run")
        pathlib.Path(wav_path).write_bytes(b"RIFFfake")
        return holder.seconds, holder.words

    real_synth_scene = N.synth_scene
    monkeypatch.setattr(N, "synth_scene", fake_synth)
    monkeypatch.setattr(N, "api_key", lambda: holder.key)
    holder.key = None

    def use_real_synth():
        """Restore the real dispatch, so a test can reach synth_elevenlabs' own handling.

        Kokoro is stubbed at synth_kokoro instead — the model is not installed here — which
        leaves the ElevenLabs half genuine all the way down to the _post_tts seam.
        """
        monkeypatch.setattr(N, "synth_scene", real_synth_scene)
        monkeypatch.setattr(N, "synth_kokoro", lambda cfg, text, wav: (
            pathlib.Path(wav).write_bytes(b"RIFFkokoro"), (holder.seconds, holder.words))[1])

    holder.use_real_synth = use_real_synth
    holder.run = lambda *extra: N.main(["--spec", str(spec_path), "--out", str(holder.out),
                                        *extra])
    holder.meta = lambda i: json.loads((holder.out / f"scene_{i:02d}.json").read_text())
    holder.durations = lambda: json.loads((holder.out / "durations.json").read_text())
    return holder


def test_a_kokoro_spec_narrates_every_scene_that_has_words(drive):
    assert drive.run() == 0
    assert [c.text for c in drive.calls] == ["First scene.", "Third scene."]
    assert drive.durations() == {"0": 2.5, "1": 0.0, "2": 2.5}
    assert drive.meta(0)["provider_used"] == "kokoro"


def test_an_elevenlabs_spec_with_no_key_prints_one_loud_line_and_uses_kokoro(drive, capsys):
    drive.spec["tts"] = dict(EL)
    assert drive.run() == 0
    err = capsys.readouterr().err
    loud = [ln for ln in err.splitlines() if "ELEVENLABS FALLBACK" in ln]
    assert len(loud) == 1, f"expected exactly one loud line, got {err!r}"
    assert all(c.cfg.provider == N.KOKORO for c in drive.calls)
    assert all(c.cfg.voice == N.DEFAULT_KOKORO_VOICE for c in drive.calls)
    assert drive.meta(0)["provider_used"] == "kokoro"
    assert drive.meta(2)["provider_used"] == "kokoro"


def test_an_elevenlabs_spec_with_a_key_synthesises_through_elevenlabs(drive, capsys):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    assert drive.run() == 0
    assert "ELEVENLABS FALLBACK" not in capsys.readouterr().err
    assert [c.cfg.provider for c in drive.calls] == [N.ELEVENLABS, N.ELEVENLABS]
    assert all(c.key == FAKE_KEY for c in drive.calls)
    assert drive.meta(0)["provider_used"] == "elevenlabs"
    assert drive.meta(0)["model"] == "eleven_multilingual_v2"


def test_a_second_run_over_unchanged_text_bills_nothing(drive):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.run()
    drive.calls.clear()
    assert drive.run() == 0
    assert drive.calls == [], "cached scenes must not be re-synthesized"
    assert drive.durations() == {"0": 2.5, "1": 0.0, "2": 2.5}


def test_switching_provider_invalidates_the_cache(drive):
    drive.key = FAKE_KEY
    drive.run()                       # kokoro
    drive.calls.clear()
    drive.spec["tts"] = dict(EL)      # now elevenlabs, same words
    assert drive.run() == 0
    assert [c.cfg.provider for c in drive.calls] == [N.ELEVENLABS, N.ELEVENLABS]


def test_changing_only_the_model_invalidates_the_cache(drive):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.run()
    drive.calls.clear()
    drive.spec["tts"] = dict(EL, model="eleven_flash_v2_5")
    assert drive.run() == 0
    assert len(drive.calls) == 2


def test_a_failed_scene_exits_2_and_never_starts_the_next_one(drive, capsys):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.fail_on = "First scene."
    assert drive.run() == 2
    assert [c.text for c in drive.calls] == ["First scene."]
    err = capsys.readouterr().err
    assert "429" in err and "--allow-fallback" in err


def test_a_failed_scene_leaves_no_meta_so_the_cache_stays_consistent(drive):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.run()                                   # everything cached and good
    drive.spec["scenes"][0]["narration"] = "First scene, reworded."
    drive.fail_on = "First scene, reworded."
    assert drive.run() == 2
    assert not (drive.out / "scene_00.json").exists(), "a stale meta would cache a wrong duration"
    assert (drive.out / "scene_02.json").exists(), "untouched scenes stay cached"


def test_allow_fallback_narrates_only_the_failed_scene_with_kokoro(drive, capsys):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.fail_on = "First scene."
    assert drive.run("--allow-fallback") == 0
    providers = [(c.text, c.cfg.provider) for c in drive.calls]
    assert providers == [("First scene.", N.ELEVENLABS), ("First scene.", N.KOKORO),
                         ("Third scene.", N.ELEVENLABS)]
    assert drive.meta(0)["provider_used"] == "kokoro"
    assert drive.meta(2)["provider_used"] == "elevenlabs"


def test_a_fallback_scene_is_cached_under_the_kokoro_key_not_the_elevenlabs_one(drive):
    """Otherwise the next run, with the API healthy, would keep the Kokoro audio forever."""
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.fail_on = "First scene."
    drive.run("--allow-fallback")
    kokoro_cfg = N.tts_config(drive.spec).fallback()
    assert drive.meta(0)["hash"] == N.cache_hash(kokoro_cfg, "First scene.")
    drive.calls.clear()
    drive.fail_on = None
    assert drive.run() == 0
    assert [c.text for c in drive.calls] == ["First scene."], "scene 0 re-synthesizes on ElevenLabs"


# --- main(): --dry-run -----------------------------------------------------------------

def test_dry_run_prints_per_scene_counts_the_total_and_the_credit_estimate(drive, capsys,
                                                                           monkeypatch):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    monkeypatch.setattr(N, "_post_tts",
                        lambda *a, **k: pytest.fail("a dry run must not touch the network"))
    assert drive.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert "scene 00:    12 characters" in out
    assert "scene 01:     0 characters   (no narration)" in out
    assert "total: 24 characters across 3 scenes" in out
    assert "1 credit/char -> ~24 credits" in out
    assert drive.calls == []
    assert not drive.out.exists(), "a dry run writes nothing"


def test_dry_run_halves_the_estimate_on_a_flash_model(drive, capsys):
    drive.spec["tts"] = dict(EL, model="eleven_flash_v2_5")
    assert drive.run("--dry-run") == 0
    out = capsys.readouterr().out
    assert "0.5 credit/char -> ~12 credits" in out


def test_dry_run_on_a_kokoro_spec_says_zero_credits(drive, capsys):
    assert drive.run("--dry-run") == 0
    assert "local synthesis -> 0 credits" in capsys.readouterr().out


# --- main(): --tts-check ---------------------------------------------------------------

VOICES = {"voices": [{"voice_id": VOICE_ID, "name": "Adam", "category": "premade"},
                     {"voice_id": "OTHER1234567890ABCDE", "name": "Rachel",
                      "category": "premade"}]}


def test_tts_check_names_the_voice_and_exits_zero(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(tts=EL))
    monkeypatch.setattr(N, "api_key", lambda: FAKE_KEY)
    monkeypatch.setattr(N, "_get_voices", lambda key: (200, VOICES))
    assert N.tts_check(cfg) == 0
    out = capsys.readouterr().out
    assert "Adam" in out and "premade" in out and VOICE_ID in out
    assert FAKE_KEY not in out


def test_tts_check_exits_2_when_the_configured_voice_is_not_on_the_account(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(tts=dict(EL, voice="NOSUCHVOICEID1234567")))
    monkeypatch.setattr(N, "api_key", lambda: FAKE_KEY)
    monkeypatch.setattr(N, "_get_voices", lambda key: (200, VOICES))
    assert N.tts_check(cfg) == 2
    err = capsys.readouterr().err
    assert "NOSUCHVOICEID1234567" in err and "Adam" in err


def test_tts_check_exits_2_with_no_key(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(tts=EL))
    monkeypatch.setattr(N, "api_key", lambda: None)
    monkeypatch.setattr(N, "_get_voices", lambda key: pytest.fail("no key means no request"))
    assert N.tts_check(cfg) == 2
    assert "ELEVENLABS_API_KEY" in capsys.readouterr().err


def test_tts_check_exits_2_on_an_http_error(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(tts=EL))
    monkeypatch.setattr(N, "api_key", lambda: FAKE_KEY)
    monkeypatch.setattr(N, "_get_voices", lambda key: (401, {"detail": f"bad {FAKE_KEY}"}))
    assert N.tts_check(cfg) == 2
    err = capsys.readouterr().err
    assert "key was rejected" in err and FAKE_KEY not in err


def test_tts_check_exits_2_on_a_transport_error(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(tts=EL))
    monkeypatch.setattr(N, "api_key", lambda: FAKE_KEY)

    def boom(key):
        raise OSError(f"connection refused while sending {FAKE_KEY}")

    monkeypatch.setattr(N, "_get_voices", boom)
    assert N.tts_check(cfg) == 2
    err = capsys.readouterr().err
    assert FAKE_KEY not in err and "connection refused" in err


def test_tts_check_on_a_kokoro_spec_says_so_rather_than_calling_the_api(monkeypatch, capsys):
    cfg = N.tts_config(spec_with(voice="am_michael"))
    monkeypatch.setattr(N, "_get_voices", lambda key: pytest.fail("kokoro has no API"))
    assert N.tts_check(cfg) == 2
    assert "kokoro" in capsys.readouterr().err


def test_tts_check_runs_from_main_without_an_out_directory(drive, monkeypatch):
    drive.spec["tts"] = dict(EL)
    monkeypatch.setattr(N, "_get_voices", lambda key: (200, VOICES))
    drive.key = FAKE_KEY
    spec_path = drive.out.parent / "scenes.yaml"
    assert N.main(["--spec", str(spec_path), "--tts-check"]) == 0


def test_synthesis_without_an_out_directory_is_an_argparse_error(drive):
    spec_path = drive.out.parent / "scenes.yaml"
    with pytest.raises(SystemExit) as e:
        N.main(["--spec", str(spec_path)])
    assert e.value.code == 2


# ============================ fix round: review "Needs fixes" ============================

# --- 1. A transport error on the PAID path escaped as a traceback. tts_check already wrapped
# _get_voices; the synthesis call site did not, so a dropped connection mid-batch produced a
# raw requests exception — whose str() carries the full request URL — instead of exit 2.

def test_a_transport_error_on_the_paid_path_becomes_a_redacted_one_line_error(tmp_path,
                                                                              monkeypatch):
    def boom(*a, **k):
        raise ConnectionError(f"HTTPSConnectionPool: refused\nwhile sending key={FAKE_KEY}")

    monkeypatch.setattr(N, "_post_tts", boom)
    monkeypatch.setattr(N, "decode_to_wav", lambda *a, **k: pytest.fail("must not decode"))
    cfg = N.tts_config(spec_with(tts=EL))
    with pytest.raises(N.TTSError) as e:
        N.synth_elevenlabs(cfg, "Hello.", tmp_path / "scene_00.wav", FAKE_KEY)
    message = str(e.value)
    assert FAKE_KEY not in message
    assert "\n" not in message, "a queue card and a build log both want one line"
    assert "ConnectionError" in message and "could not reach" in message


def test_a_transport_error_does_not_chain_the_raw_exception(tmp_path, monkeypatch):
    """__cause__/__context__ are printed by an uncaught traceback — and they are not redacted."""
    monkeypatch.setattr(N, "_post_tts",
                        lambda *a, **k: (_ for _ in ()).throw(ConnectionError(FAKE_KEY)))
    cfg = N.tts_config(spec_with(tts=EL))
    with pytest.raises(N.TTSError) as e:
        N.synth_elevenlabs(cfg, "Hello.", tmp_path / "scene_00.wav", FAKE_KEY)
    assert e.value.__cause__ is None and e.value.__suppress_context__


def test_a_transport_error_exits_2_and_leaves_the_cache_consistent(drive, monkeypatch, capsys):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.use_real_synth()
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (_ for _ in ()).throw(
        ConnectionError("connection reset by peer")))
    assert drive.run() == 2
    assert not (drive.out / "scene_00.json").exists()
    assert not (drive.out / "durations.json").exists()
    err = capsys.readouterr().err
    assert "could not reach" in err and "--allow-fallback" in err


def test_a_transport_error_falls_back_per_scene_when_allowed(drive, monkeypatch):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.use_real_synth()
    calls = []

    def flaky(voice, key, body, **kw):
        calls.append(body["text"])
        if body["text"] == "First scene.":
            raise ConnectionError("connection reset by peer")
        return 200, _timestamped()

    monkeypatch.setattr(N, "_post_tts", flaky)
    monkeypatch.setattr(N, "decode_to_wav",
                        lambda content, path, alignment=None, lead_in_s=N.LEAD_IN_S:
                        (pathlib.Path(path).write_bytes(b"RIFF"), (3.0, None))[1])
    assert drive.run("--allow-fallback") == 0
    assert calls == ["First scene.", "Third scene."]
    assert drive.meta(0)["provider_used"] == "kokoro"
    assert drive.meta(2)["provider_used"] == "elevenlabs"


def test_a_failure_of_the_fallback_retry_itself_exits_2_rather_than_crashing(drive,
                                                                            monkeypatch):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.use_real_synth()
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (_ for _ in ()).throw(
        ConnectionError("down")))
    monkeypatch.setattr(N, "synth_kokoro", lambda *a, **k: (_ for _ in ()).throw(
        N.TTSError("kokoro model is not installed")))
    assert drive.run("--allow-fallback") == 2
    assert not (drive.out / "scene_00.json").exists()


# --- 2. --speed is a Kokoro control. It sat in the ElevenLabs cache key while never reaching
# the API, so `--speed 1.2` re-billed a whole spec for byte-identical audio.

def test_a_stray_speed_flag_on_an_elevenlabs_spec_is_refused(capsys):
    with pytest.raises(SystemExit) as e:
        N.tts_config(spec_with(tts=EL), speed=1.2)
    message = str(e.value)
    assert "--speed" in message and "tts.speed" in message


def test_speed_one_needs_no_spec_entry_because_it_changes_nothing():
    assert N.tts_config(spec_with(tts=EL), speed=1.0).provider == N.ELEVENLABS


def test_a_matching_tts_speed_makes_the_flag_legal_and_lands_in_voice_settings():
    cfg = N.tts_config(spec_with(tts=dict(EL, speed=1.2)), speed=1.2)
    assert cfg.voice_settings()["speed"] == 1.2
    assert cfg.speed == 1.2


def test_a_speed_flag_that_disagrees_with_the_spec_is_refused():
    with pytest.raises(SystemExit) as e:
        N.tts_config(spec_with(tts=dict(EL, speed=1.1)), speed=1.2)
    assert "1.1" in str(e.value)


def test_speed_is_not_part_of_the_elevenlabs_cache_key():
    """It is not sent, so it cannot change the audio — and must not re-bill for it."""
    slow = N.TTSConfig(provider=N.ELEVENLABS, voice=VOICE_ID, speed=1.0,
                       model=N.DEFAULT_EL_MODEL)
    fast = N.TTSConfig(provider=N.ELEVENLABS, voice=VOICE_ID, speed=1.9,
                       model=N.DEFAULT_EL_MODEL)
    assert N.cache_hash(slow, "Words.") == N.cache_hash(fast, "Words.")


def test_a_spec_speed_still_changes_the_key_because_it_rides_in_voice_settings():
    plain = N.tts_config(spec_with(tts=EL))
    spoken_faster = N.tts_config(spec_with(tts=dict(EL, speed=1.2)), speed=1.2)
    assert N.cache_hash(plain, "Words.") != N.cache_hash(spoken_faster, "Words.")


def test_the_kokoro_fallback_speaks_at_the_rate_the_spec_asked_for():
    cfg = N.tts_config(spec_with(tts=dict(EL, speed=1.2), voice="af_heart"), speed=1.2)
    assert cfg.fallback().speed == 1.2


# --- 3. The no-key fallback is automatic, which is right for a local render but wrong for a
# paid batch: a deleted key file would render the whole Saturday run in Kokoro and succeed.

def test_require_provider_exits_2_when_the_no_key_fallback_took_over(drive, capsys):
    drive.spec["tts"] = dict(EL)
    drive.key = None
    assert drive.run("--require-provider", "elevenlabs") == 2
    assert drive.calls == [], "nothing may be synthesized"
    assert not drive.out.exists(), "not even the output directory"
    err = capsys.readouterr().err
    assert "--require-provider elevenlabs" in err and "kokoro" in err


def test_require_provider_is_satisfied_by_the_resolved_provider(drive):
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    assert drive.run("--require-provider", "elevenlabs") == 0
    assert [c.cfg.provider for c in drive.calls] == [N.ELEVENLABS, N.ELEVENLABS]


def test_require_provider_kokoro_is_satisfied_by_a_kokoro_spec(drive):
    assert drive.run("--require-provider", "kokoro") == 0
    assert len(drive.calls) == 2


def test_require_provider_rejects_a_name_that_is_not_a_provider(drive):
    with pytest.raises(SystemExit) as e:
        drive.run("--require-provider", "openai")
    assert e.value.code == 2


def test_require_provider_does_not_stop_a_per_scene_allow_fallback(drive):
    """--require-provider guards the batch-wide decision, not a single scene's retry.

    The two flags are contradictory by nature; --allow-fallback is the explicit per-scene
    opt-in and stays the more specific instruction.
    """
    drive.spec["tts"] = dict(EL)
    drive.key = FAKE_KEY
    drive.fail_on = "First scene."
    assert drive.run("--require-provider", "elevenlabs", "--allow-fallback") == 0
    assert drive.meta(0)["provider_used"] == "kokoro"


# ======================= word timings for burned-in captions (2026-09-15) =======================
#
# Every synthesized scene writes `<scene>.words.json` beside its WAV, in seconds against the
# audio that is actually concatenated — i.e. AFTER finish()'s silence trim and 0.3 s lead-in.
# Getting that offset wrong is the one failure mode that cannot be seen in a unit test of the
# renderer: the captions would simply drift against the voice.

def _alignment(text, step=0.05):
    """An ElevenLabs character alignment for `text`, one step per character."""
    chars = list(text)
    return {"characters": chars,
            "character_start_times_seconds": [round(i * step, 3) for i in range(len(chars))],
            "character_end_times_seconds": [round((i + 1) * step, 3) for i in range(len(chars))]}


def _tok(text, whitespace="", start_ts=None, end_ts=None):
    return types.SimpleNamespace(text=text, whitespace=whitespace,
                                 start_ts=start_ts, end_ts=end_ts)


# --- folding characters into words --------------------------------------------------------

def test_the_character_alignment_folds_into_words_on_whitespace():
    words = N.fold_alignment(_alignment("Magic Kingdom, now."))
    assert [w["text"] for w in words] == ["Magic", "Kingdom,", "now."]
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[0]["end"] == pytest.approx(0.25)
    assert words[1]["start"] == pytest.approx(0.30)
    assert words[2]["end"] == pytest.approx(0.95)


def test_punctuation_stays_attached_to_the_word_it_follows():
    words = N.fold_alignment(_alignment('He said "stop!" — twice.'))
    assert [w["text"] for w in words] == ["He", "said", '"stop!"', "—", "twice."]


def test_runs_of_whitespace_never_produce_an_empty_word():
    words = N.fold_alignment(_alignment("two  \n spaced"))
    assert [w["text"] for w in words] == ["two", "spaced"]


def test_an_alignment_that_is_missing_or_ragged_yields_no_words_rather_than_nonsense():
    assert N.fold_alignment(None) is None
    assert N.fold_alignment({}) is None
    ragged = _alignment("abc")
    ragged["character_end_times_seconds"] = ragged["character_end_times_seconds"][:-1]
    assert N.fold_alignment(ragged) is None


def test_an_alignment_of_pure_whitespace_yields_an_empty_list_not_none():
    assert N.fold_alignment(_alignment("   ")) == []


# --- folding Kokoro's tokens into words ----------------------------------------------------

def test_kokoro_tokens_fold_into_words_with_punctuation_attached():
    """misaki emits punctuation as its own token, with no phonemes and so no timestamps."""
    tokens = [_tok("Magic", "", 0.10, 0.45), _tok("Kingdom", "", 0.50, 1.10),
              _tok(".", " "), _tok("Now", "", 1.30, 1.60), _tok("!", "")]
    words = N.fold_kokoro_tokens([(tokens, 0.0)])
    assert [w["text"] for w in words] == ["MagicKingdom.", "Now!"]
    assert words[0]["start"] == pytest.approx(0.10)
    assert words[0]["end"] == pytest.approx(1.10)


def test_a_word_boundary_is_the_token_that_carries_whitespace():
    tokens = [_tok("one", " ", 0.0, 0.4), _tok("two", " ", 0.5, 0.9), _tok("three", "", 1.0, 1.4)]
    assert [w["text"] for w in N.fold_kokoro_tokens([(tokens, 0.0)])] == ["one", "two", "three"]


def test_each_kokoro_chunk_is_offset_by_the_audio_before_it():
    """The pipeline yields one Result per chunk, each timed from its own zero."""
    first = [_tok("one", "", 0.0, 0.4)]
    second = [_tok("two", "", 0.0, 0.4)]
    words = N.fold_kokoro_tokens([(first, 0.0), (second, 2.5)])
    assert [w["start"] for w in words] == [pytest.approx(0.0), pytest.approx(2.5)]


def test_kokoro_tokens_with_no_timestamps_at_all_yield_none():
    """Non-English G2P produces no start_ts; captions are skipped rather than faked."""
    assert N.fold_kokoro_tokens([([_tok("bonjour", " "), _tok("monde", "")], 0.0)]) is None
    assert N.fold_kokoro_tokens([(None, 0.0)]) is None
    assert N.fold_kokoro_tokens([]) is None


# --- the offset against the audio that is actually concatenated ----------------------------

def test_the_word_offset_is_the_lead_in_minus_whatever_the_trim_removed():
    assert N.words_offset(0) == pytest.approx(N.LEAD_IN_S)
    assert N.words_offset(N.SR // 2) == pytest.approx(N.LEAD_IN_S - 0.5)
    assert N.LEAD_IN_S == 0.3          # the default; tts.lead_in_s overrides it per spec


def test_shifting_words_moves_them_onto_the_finished_wav():
    words = [{"text": "a", "start": 1.0, "end": 1.4}]
    assert N.shift_words(words, 0.3) == [{"text": "a", "start": 1.3, "end": 1.7}]


def test_a_word_the_trim_ate_into_is_clamped_to_zero_not_left_negative():
    words = [{"text": "a", "start": 0.05, "end": 0.40}]
    shifted = N.shift_words(words, -0.2)
    assert shifted[0]["start"] == 0.0
    assert shifted[0]["end"] == pytest.approx(0.2)


def test_shifting_nothing_stays_nothing():
    assert N.shift_words(None, 0.3) is None


# --- the with-timestamps request and response ----------------------------------------------

def test_post_tts_asks_for_timestamps_and_json(monkeypatch):
    seen = {}

    def post(url, headers=None, params=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, params=params, body=json)
        return _Resp(200, b"{}")

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=post))
    assert N._post_tts(VOICE_ID, FAKE_KEY, {"text": "hi", "model_id": "m"}) == (200, b"{}")
    assert seen["url"] == \
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps"
    assert seen["headers"]["accept"] == "application/json"
    assert seen["headers"]["xi-api-key"] == FAKE_KEY
    assert seen["params"] == {"output_format": "mp3_44100_128"}
    assert seen["body"] == {"text": "hi", "model_id": "m"}


def _timestamped(audio=b"ID3audio", text="Magic now."):
    import base64
    return json.dumps({"audio_base64": base64.b64encode(audio).decode(),
                       "alignment": _alignment(text)}).encode()


def test_the_timestamped_response_yields_the_mp3_and_its_alignment():
    audio, alignment = N.parse_timestamped_response(_timestamped())
    assert audio == b"ID3audio"
    assert alignment["characters"][:5] == list("Magic")


def test_a_response_with_no_alignment_still_yields_audio():
    import base64
    body = json.dumps({"audio_base64": base64.b64encode(b"ID3x").decode()}).encode()
    assert N.parse_timestamped_response(body) == (b"ID3x", None)


@pytest.mark.parametrize("body,needle", [
    (b"<html>not json</html>", "not JSON"),
    (b'{"alignment": {}}', "no audio"),
    (b'{"audio_base64": ""}', "no audio"),
    (b'{"audio_base64": "!!!not base64!!!"}', "could not be decoded"),
])
def test_an_unusable_timestamped_response_is_a_named_failure(body, needle):
    with pytest.raises(N.TTSError) as exc:
        N.parse_timestamped_response(body)
    assert needle in str(exc.value)


def test_an_unusable_response_body_is_redacted_before_it_is_reported():
    body = f'{{"detail": "bad key {FAKE_KEY}"'.encode()
    with pytest.raises(N.TTSError) as exc:
        N.parse_timestamped_response(body, FAKE_KEY)
    assert FAKE_KEY not in str(exc.value)


def test_synth_elevenlabs_returns_the_seconds_and_the_words(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (200, _timestamped()))
    monkeypatch.setattr(N, "decode_to_wav",
                        lambda content, path, alignment=None, lead_in_s=N.LEAD_IN_S: (
                            seen.update(content=content, alignment=alignment)
                            or (3.25, [{"text": "Magic"}])))
    cfg = N.tts_config(spec_with(tts=EL))
    assert N.synth_elevenlabs(cfg, "Magic now.", tmp_path / "scene_00.wav", FAKE_KEY) == \
        (3.25, [{"text": "Magic"}])
    assert seen["content"] == b"ID3audio"
    assert seen["alignment"]["characters"][0] == "M"


# --- main(): the words file is part of the cache -------------------------------------------

def test_every_synthesized_scene_writes_its_word_timings_beside_the_wav(drive):
    import captions as C
    assert drive.run() == 0
    assert C.read_words(drive.out / "scene_00.wav") == drive.words
    assert C.read_words(drive.out / "scene_02.wav") == drive.words
    assert not C.words_path(drive.out / "scene_01.wav").exists(), \
        "a scene with no narration has no audio and no words"


def test_a_provider_that_gave_no_timings_writes_null_and_says_captions_are_skipped(drive,
                                                                                   capsys):
    drive.words = None
    assert drive.run() == 0
    import captions as C
    assert C.words_path(drive.out / "scene_00.wav").read_text() == "null"
    assert C.read_words(drive.out / "scene_00.wav") is None
    err = capsys.readouterr().err
    assert "scene 00" in err and "captions" in err


def test_a_cached_scene_with_no_words_file_is_re_synthesized(drive):
    """A cache hit has to yield words too, or the first captioned render finds none."""
    import captions as C
    assert drive.run() == 0
    C.words_path(drive.out / "scene_00.wav").unlink()
    drive.calls.clear()
    assert drive.run() == 0
    assert [c.text for c in drive.calls] == ["First scene."]
    assert C.read_words(drive.out / "scene_00.wav") == drive.words


def test_a_cache_hit_leaves_the_words_file_untouched(drive):
    import captions as C
    drive.run()
    stamp = C.words_path(drive.out / "scene_00.wav").read_text()
    drive.calls.clear()
    assert drive.run() == 0
    assert drive.calls == []
    assert C.words_path(drive.out / "scene_00.wav").read_text() == stamp


def test_an_empty_fold_is_stored_as_no_timings_rather_than_an_empty_list(drive, capsys):
    """A fold that came back empty is a scene with no captions, not a scene with zero words.

    Caching `[]` would be a cache hit that promises words and delivers none; make_short would
    read it as falsy and skip the scene anyway, but silently. Normalise it to `null`, warn, and
    let the next run re-synthesize if the text changes.
    """
    import captions as C
    drive.words = []
    assert drive.run() == 0
    assert C.words_path(drive.out / "scene_00.wav").read_text() == "null"
    assert C.read_words(drive.out / "scene_00.wav") is None
    err = capsys.readouterr().err
    assert "scene 00" in err and "captions" in err


# --- the lead-in is a spec key ---------------------------------------------------------

def test_the_lead_in_defaults_to_the_constant_and_is_not_a_voice_setting():
    cfg = N.tts_config({"tts": {"provider": "elevenlabs", "voice": "v1"}})
    assert cfg.lead_in_s == N.LEAD_IN_S
    assert "lead_in_s" not in cfg.voice_settings()


def test_a_spec_lead_in_reaches_the_config_and_stays_out_of_the_request_body():
    cfg = N.tts_config({"tts": {"provider": "elevenlabs", "voice": "v1", "lead_in_s": 0.05}})
    assert cfg.lead_in_s == pytest.approx(0.05)
    assert "lead_in_s" not in cfg.voice_settings()
    assert "lead_in_s" not in N.request_body(cfg, "hello")["voice_settings"]


def test_an_impossible_lead_in_is_refused_by_name():
    with pytest.raises(SystemExit) as excinfo:
        N.tts_config({"tts": {"provider": "elevenlabs", "voice": "v1", "lead_in_s": -0.5}})
    assert "lead_in_s" in str(excinfo.value)


def test_the_words_offset_follows_the_lead_in_it_was_given():
    assert N.words_offset(0, 0.05) == pytest.approx(0.05)
    assert N.words_offset(N.SR // 2, 0.05) == pytest.approx(0.05 - 0.5)
    assert N.words_offset(0) == pytest.approx(N.LEAD_IN_S)


def test_the_lead_in_is_not_in_the_cache_key_so_the_bill_does_not_move():
    """The audio ElevenLabs bills for is identical; only the local silence changes."""
    plain = N.tts_config({"tts": {"provider": "elevenlabs", "voice": "v1"}})
    short = N.tts_config({"tts": {"provider": "elevenlabs", "voice": "v1", "lead_in_s": 0.05}})
    assert N.cache_hash(plain, "hello") == N.cache_hash(short, "hello")


def test_the_elevenlabs_path_hands_its_lead_in_down_to_the_decode(tmp_path, monkeypatch):
    """The config carries the lead-in; decode_to_wav is what actually prepends the silence."""
    seen = {}
    monkeypatch.setattr(N, "_post_tts", lambda *a, **k: (200, _timestamped()))
    monkeypatch.setattr(N, "decode_to_wav",
                        lambda content, path, alignment=None, lead_in_s=N.LEAD_IN_S: (
                            seen.update(lead_in_s=lead_in_s) or (3.25, None)))
    cfg = N.tts_config(spec_with(tts=dict(EL, lead_in_s=0.05)))
    N.synth_elevenlabs(cfg, "Magic now.", tmp_path / "scene_00.wav", FAKE_KEY)
    assert seen["lead_in_s"] == pytest.approx(0.05)


def test_a_changed_lead_in_re_renders_the_wav_even_though_the_cache_key_did_not_move(drive):
    """The bill does not move, so the hash cannot — the meta carries the lead-in instead."""
    assert drive.run() == 0
    narrated = len(drive.calls)
    assert narrated
    assert drive.meta(0)["lead_in_s"] == pytest.approx(N.LEAD_IN_S)
    assert drive.run() == 0 and len(drive.calls) == narrated, "an unchanged spec is a hit"
    drive.spec["tts"] = {"lead_in_s": 0.05}
    assert drive.run() == 0
    assert len(drive.calls) == 2 * narrated, "a shortened lead-in must re-render every scene"
    assert drive.meta(0)["lead_in_s"] == pytest.approx(0.05)
