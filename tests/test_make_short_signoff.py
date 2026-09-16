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
