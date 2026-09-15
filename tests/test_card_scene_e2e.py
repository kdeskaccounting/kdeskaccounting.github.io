"""End-to-end: a card-only spec renders through build_video.py --frames-only.

Needs the render venv (playwright/yaml/openpyxl) and a headless Chrome, so it skips in a bare
pytest environment and on CI runners. It is the test that proves the card kind is actually
wired into the pipeline, not just into cards.py — and that a spec whose scenes are all cards
renders with no workbook and no LibreOffice, from a path outside this repo.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = REPO / "scripts" / "video" / ".venv-tts" / "bin" / "python"
BUILD_VIDEO = REPO / "scripts" / "video" / "build_video.py"
MAKE_SHORT = REPO / "scripts" / "video" / "make_short.py"
SPEC = REPO / "marketing" / "video" / "card-demo" / "scenes.yaml"

needs_venv = pytest.mark.skipif(not VENV_PY.exists(),
                                reason="render venv scripts/video/.venv-tts is absent")


def _run(args, timeout=600):
    return subprocess.run([str(VENV_PY), *args], capture_output=True, text=True,
                          timeout=timeout, cwd=REPO)


@needs_venv
def test_build_video_frames_only_renders_every_card_scene():
    build = REPO / "scripts" / "video" / "build" / "card-demo"
    # clear everything this run should produce, but keep build/audio: narration is cached by
    # text hash and re-synthesizing it costs a minute of Kokoro for no extra coverage.
    shutil.rmtree(build / "frames", ignore_errors=True)
    shutil.rmtree(build / "recalc", ignore_errors=True)
    (build / "src.xlsx").unlink(missing_ok=True)
    proc = _run([str(BUILD_VIDEO), "--spec", str(SPEC), "--frames-only"])
    assert proc.returncode == 0, proc.stderr[-2000:]
    frames = build / "frames"
    for i in range(3):
        png = frames / f"scene_{i:02d}.png"
        assert png.exists(), f"{png} missing\n{proc.stdout}"
        assert png.stat().st_size > 10_000, f"{png} is suspiciously small"
    focus = json.loads((frames / "focus.json").read_text())
    assert all(focus[str(i)]["static"] is True for i in range(3))
    assert "card" in proc.stdout
    # no workbook was staged or recalculated: the spec has no `source:` key
    assert not (build / "src.xlsx").exists()
    assert not (build / "recalc").exists()
    assert "recalc" not in proc.stdout


@needs_venv
def test_build_video_renders_a_card_spec_that_lives_outside_the_repo(tmp_path):
    """The second venture keeps its spec in its own repo and calls this pipeline by path."""
    spec = tmp_path / "scenes.yaml"
    spec.write_text(SPEC.read_text(encoding="utf-8").replace("slug: card-demo",
                                                             "slug: card-demo-external"),
                    encoding="utf-8")
    build = REPO / "scripts" / "video" / "build" / "card-demo-external"
    if build.exists():
        shutil.rmtree(build)
    try:
        proc = _run([str(BUILD_VIDEO), "--spec", str(spec), "--frames-only"])
        assert proc.returncode == 0, proc.stderr[-2000:]
        assert (build / "frames" / "scene_02.png").stat().st_size > 10_000
    finally:
        shutil.rmtree(build, ignore_errors=True)


@needs_venv
@pytest.mark.parametrize("script", [BUILD_VIDEO, MAKE_SHORT], ids=["build_video", "make_short"])
def test_help_advertises_the_spec_flag(script):
    """An external preflight greps --help before it calls either script."""
    proc = _run([str(script), "--help"], timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "--spec" in proc.stdout


@needs_venv
def test_end_card_follows_the_spec_brand_instead_of_hardcoding_kdesk():
    """A second venture's Short must not sign off as KDesk Accounting.

    Runs inside the render venv because make_short imports yaml/PIL/openpyxl at module level.
    """
    code = "\n".join([
        "import sys; sys.path.insert(0, 'scripts/video')",
        "import make_short as M, cards",
        "legacy = M.end_html('Free 3-lease version \\u2192 kdeskaccounting.com/templates/asc842')",
        "assert 'KDesk Accounting' in legacy, 'legacy outro must be unchanged'",
        "assert 'Pure Excel' in legacy, 'legacy outro must be unchanged'",
        "brand = cards.brand_tokens({'name': 'Park Sheet', 'url': 'parksheet.com', "
        "'accent': '#FFD966'})",
        "branded = M.end_html('Every park, every week \\u2192 parksheet.com', brand)",
        "assert 'Park Sheet' in branded and 'parksheet.com' in branded",
        "assert 'KDesk' not in branded and 'Pure Excel' not in branded",
        "print('ok')",
    ])
    proc = _run(["-c", code], timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]


@needs_venv
def test_make_short_refuses_both_slug_and_spec():
    proc = _run([str(MAKE_SHORT), "--slug", "card-demo", "--spec", str(SPEC)], timeout=120)
    assert proc.returncode != 0
    assert "not allowed with" in proc.stderr
