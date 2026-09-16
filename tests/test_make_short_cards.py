"""make_short.py's card branch, with the ffmpeg seam stubbed - no encode, no Chrome, no venv.

make_short imports yaml/PIL inside the functions that need them, so the module itself imports
with the standard library alone and these tests run in the plain `uv run --with pytest`
environment. `run()` is the single seam every ffmpeg invocation goes through; stubbing it lets
us assert the exact command the card branch builds instead of waiting on an encode.
"""
import json
import math
import pathlib
import sys
import types

import pytest

import make_short as M

SPEC = {
    "slug": "card-demo",
    "brand": {"name": "Park Sheet", "url": "parksheet.com", "accent": "#FFD966"},
    "short": {"hook": "Three layouts", "scenes": [0, 1], "cta": "More → parksheet.com"},
    "scenes": [
        {"kind": "card", "template": "ranked_list",
         "data": {"heading": "Shortest waits", "subheading": "Magic Kingdom",
                  "items": [{"rank": 1, "label": "Speedway", "value": 5}],
                  "footer": "Powered by Queue-Times.com"},
         "narration": "one"},
        {"kind": "card", "template": "changed",
         "data": {"heading": "What changed", "subheading": "This week",
                  "items": [{"label": "Test Track", "value": "Reopened on Tuesday after a "
                                                             "long refurbishment this week."}],
                  "footer": "Powered by Queue-Times.com"},
         "narration": "two"},
    ],
}
DURATIONS = {"0": 4.0, "1": 6.0}


def _expected_encode_cmd(png, wav, out, dur, crf=26):
    """The ffmpeg command as make_short built it before encode_scene was extracted.

    Plus `-color_range tv`, added later so the TAG matches the limited-range pixels every
    scene kind already produced — see the colour-range tests below.
    """
    n = math.ceil(dur * 30)
    dz = (1.06 - 1.0) / n
    vf = (f"scale=1296:2304:flags=lanczos,zoompan=z='min(zoom+{dz:.7f},1.06)':"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps=30,"
          f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(0.0, dur - 0.3):.3f}:d=0.3,format=yuv420p")
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-i", str(wav),
            "-filter_complex",
            f"[0:v]{vf}[v];[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
            f"aformat=sample_rates=48000:channel_layouts=stereo[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
            "-preset", "medium", "-crf", str(crf), "-r", "30", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "128k", str(out)]


# --- encode_scene ---------------------------------------------------------------------

def test_encode_scene_writes_its_mp4_beside_the_png_it_was_given(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "run", lambda cmd: None)
    out = M.encode_scene(tmp_path / "scene_0.png", tmp_path / "scene_00.wav", 5.0, 26)
    assert out == tmp_path / "scene_0.mp4"


@pytest.mark.parametrize("dur,crf", [(5.0, 26), (12.9, 20), (0.7, 30)])
def test_encode_scene_builds_the_command_the_inline_block_used_to_build(tmp_path, monkeypatch,
                                                                        dur, crf):
    """Locks the encode byte-for-byte: existing Shorts must come out of the extraction unchanged."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    png, wav = tmp_path / "scene_1.png", tmp_path / "scene_03.wav"
    out = M.encode_scene(png, wav, dur, crf)
    assert seen == [_expected_encode_cmd(png, wav, out, dur, crf)]


# --- the card branch of main() ---------------------------------------------------------

@pytest.fixture
def stub_main(tmp_path, monkeypatch):
    """Run main() against a card-only spec with every external tool stubbed out."""
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(safe_load=lambda fh: SPEC))
    monkeypatch.setitem(sys.modules, "PIL",
                        types.SimpleNamespace(Image=object(), ImageChops=object()))
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml\n")
    build = tmp_path / "build" / "card-demo"
    (build / "audio").mkdir(parents=True)
    (build / "audio" / "durations.json").write_text(json.dumps(DURATIONS))
    monkeypatch.setattr(M, "HERE", tmp_path)
    monkeypatch.setattr(M, "dur_of", lambda p: 30.0)
    monkeypatch.setattr(M, "subprocess",
                        types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout="")))
    cards_seen, shots, cmds = [], [], []
    monkeypatch.setattr(M.R, "render_card_scene",
                        lambda *a, **k: cards_seen.append((a, k)))
    monkeypatch.setattr(M.R, "screenshot", lambda *a, **k: shots.append(a))
    monkeypatch.setattr(M, "run", cmds.append)
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path)])
    return types.SimpleNamespace(build=build, cards=cards_seen, shots=shots, cmds=cmds,
                                 spec_path=spec_path)


def test_card_branch_renders_each_card_at_the_short_canvas(stub_main):
    M.main()
    assert len(stub_main.cards) == 2
    (png0, template0, data0, brand0, w0, h0), kw0 = stub_main.cards[0]
    assert template0 == "ranked_list" and data0 == SPEC["scenes"][0]["data"]
    assert brand0 == SPEC["brand"]
    assert (w0, h0) == (M.RW, M.RH) == (1296, 2304)
    assert kw0["html_dir"] == stub_main.build / "short"
    assert png0 == stub_main.build / "short" / "scene_0.png"
    assert stub_main.cards[1][0][1] == "changed"


def test_card_branch_encodes_its_own_png_against_the_narrated_wav(stub_main):
    M.main()
    work = stub_main.build / "short"
    for k, idx in enumerate(SPEC["short"]["scenes"]):
        dur = DURATIONS[str(idx)] + 0.6
        assert stub_main.cmds[k] == _expected_encode_cmd(
            work / f"scene_{k}.png", stub_main.build / "audio" / f"scene_{idx:02d}.wav",
            work / f"scene_{k}.mp4", dur)


def test_card_branch_concatenates_into_the_slugs_final_short(stub_main):
    M.main()
    final = stub_main.build / "card-demo-short.mp4"
    concat = [c for c in stub_main.cmds if "concat" in c]
    assert len(concat) == 1 and str(final) in concat[0]
    listed = (stub_main.build / "short" / "concat.txt").read_text().splitlines()
    assert listed == [f"file '{stub_main.build / 'short' / n}'"
                      for n in ("scene_0.mp4", "scene_1.mp4", "end.mp4")]


def test_a_card_only_short_needs_no_frames_or_focus_json(stub_main):
    M.main()  # build/frames never existed; the card branch must not read it
    assert not (stub_main.build / "frames").exists()


def test_missing_narration_durations_names_narrate_py(stub_main):
    (stub_main.build / "audio" / "durations.json").unlink()
    with pytest.raises(SystemExit) as e:
        M.main()
    assert "narrate.py" in str(e.value)
    assert "durations.json" in str(e.value)


@pytest.mark.parametrize("slug", ["../../etc", "a/b", ".."])
def test_a_traversing_slug_is_rejected_before_it_is_used_to_open_a_spec(stub_main, slug):
    """--slug also builds a path (marketing/video/<slug>/scenes.yaml), so validate it first."""
    sys.argv = ["make_short.py", "--slug", slug]   # restored by the fixture's monkeypatch
    with pytest.raises(SystemExit) as e:
        M.main()
    assert "slug" in str(e.value)


# --- colour range ------------------------------------------------------------------------

def test_every_scene_kind_tags_its_output_limited_range(tmp_path, monkeypatch):
    """The pixels were always limited range; only the TAG was missing, and only on some
    parts. Parts are concatenated with `-c:v copy`, so mixed tagging leaves the finished
    Short's range depending on which scene happened to be encoded first."""
    seen = []
    monkeypatch.setattr(M, "run", seen.append)
    M.encode_scene(tmp_path / "scene_0.png", tmp_path / "scene_00.wav", 5.0, 26)
    cmd = seen[0]
    assert cmd[cmd.index("-color_range") + 1] == "tv"
