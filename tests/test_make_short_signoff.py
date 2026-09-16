"""make_short.py's optional end plate. No encode, no Chrome, no venv.

`tests/conftest.py` already puts `scripts/video` on sys.path, and make_short imports yaml and
PIL inside the functions that use them, so importing the module here needs nothing but the
standard library — the same arrangement tests/test_make_short_cards.py relies on.
"""
import pathlib
import sys

import pytest

import make_short


def test_a_spec_with_a_cta_still_gets_its_end_plate():
    assert make_short.end_card_wanted({"hook": "h", "scenes": [0], "cta": "Free sheet → x"})


def test_a_spec_with_a_sign_off_and_no_cta_gets_no_end_plate():
    """Script v2 signs off over the payoff frame; a plate would put the ask back."""
    assert not make_short.end_card_wanted(
        {"hook": "h", "scenes": [0], "signoff": "Planning a trip? Guide's in bio."}
    )


def test_an_empty_or_whitespace_cta_is_no_cta():
    assert not make_short.end_card_wanted({"hook": "h", "scenes": [0], "cta": "   "})
    assert not make_short.end_card_wanted({"hook": "h", "scenes": [0], "cta": None})


def test_the_flag_overrides_the_spec_in_both_directions():
    with_cta = {"hook": "h", "scenes": [0], "cta": "Free sheet → x"}
    without = {"hook": "h", "scenes": [0], "signoff": "Planning a trip? Guide's in bio."}

    assert not make_short.end_card_wanted(with_cta, False)
    assert make_short.end_card_wanted(without, True)


def test_forcing_an_end_card_on_a_spec_with_no_cta_is_refused_at_render_time():
    """`--end-card` cannot invent copy: end_html needs a string to put on the plate."""
    with pytest.raises(KeyError):
        make_short.end_html(None, None)


def test_the_cli_exposes_both_flags():
    import subprocess

    out = subprocess.run(
        [sys.executable, str(pathlib.Path(make_short.__file__)), "--help"],
        capture_output=True, text=True,
    ).stdout

    assert "--end-card" in out
    assert "--no-end-card" in out
    assert "--spec" in out


# --- the guard has to be reachable from main(), and has to fire before anything renders ----

def _stub_module(name, **attrs):
    import types
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


CTA_LESS_SPEC = {
    "slug": "signoff-demo",
    "short": {"hook": "h", "scenes": [0], "signoff": "Planning a trip? Guide's in bio."},
    "scenes": [{"kind": "card", "template": "ranked_list", "narration": "x",
                "data": {"heading": "h", "subheading": "s", "items": [], "footer": "f"}}],
}


def _run_main(monkeypatch, tmp_path, spec, *argv):
    """main() with yaml and PIL stubbed out — neither is in the bare pytest environment."""
    spec_path = tmp_path / "scenes.yaml"
    spec_path.write_text("# parsed by the stubbed yaml below, not by PyYAML\n")
    monkeypatch.setitem(sys.modules, "yaml", _stub_module("yaml", safe_load=lambda _f: spec))
    monkeypatch.setitem(sys.modules, "PIL", _stub_module(
        "PIL", Image=_stub_module("PIL.Image"), ImageChops=_stub_module("PIL.ImageChops")))
    monkeypatch.setattr(sys, "argv", ["make_short.py", "--spec", str(spec_path), *argv])
    return make_short.main()


def test_forcing_an_end_card_on_a_cta_less_spec_reaches_the_guards_message(monkeypatch, tmp_path):
    """`sh["cta"]` would raise a bare KeyError('cta') and the guard's advice would never print."""
    with pytest.raises(KeyError) as excinfo:
        _run_main(monkeypatch, tmp_path, CTA_LESS_SPEC, "--end-card")

    message = str(excinfo.value)
    assert "short.cta is empty" in message
    assert "--no-end-card" in message
    assert "signoff" in message


def test_the_end_card_guard_fires_before_a_single_scene_is_rendered(monkeypatch, tmp_path):
    """Failing after six scenes have narrated and encoded costs minutes; failing here costs none."""
    def boom(*a, **k):
        raise AssertionError("the render started before the end-plate guard ran")

    monkeypatch.setattr(make_short.R, "screenshot", boom)
    monkeypatch.setattr(make_short, "run", boom)

    with pytest.raises(KeyError):
        _run_main(monkeypatch, tmp_path, CTA_LESS_SPEC, "--end-card")
