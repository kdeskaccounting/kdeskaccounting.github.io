"""scripts/video/illustrate.py -- the `kind: illustration` prototype renderer.

Everything tested here (spec validation, the frame-time <-> animation-delay math, pure HTML
generation per element type, the per-scene event list, and the calendar fill schedule) is pure
string/number crunching over already-parsed dicts: no YAML parsing, no Playwright, no headless
Chrome. That is the point -- see illustrate.py's own module docstring -- so this file runs in
the bare `uv run --with pytest python -m pytest tests/test_illustrate.py -q` environment, with
no render venv required. The actual rendering path (scene -> PNG sequence -> mp4) is proven by
hand against marketing/video/illustration-demo/scenes.yaml, not by a test here, because it
needs the render venv and a real headless Chrome.
"""
import pathlib

import pytest

import illustrate as I


def _scene(**overrides):
    scene = {
        "kind": "illustration",
        "seconds": 2.0,
        "bg": "#F7F3EA",
        "elements": [{"type": "emoji", "glyph": "\U0001F3F0", "at": [0.5, 0.5]}],
    }
    scene.update(overrides)
    return scene


def _spec(*elements, **scene_overrides):
    scene = _scene(**scene_overrides)
    if elements:
        scene["elements"] = list(elements)
    return {"scenes": [scene]}


# --------------------------------------------------------------------------------------------
# Module hygiene: stays importable with the standard library alone.
# --------------------------------------------------------------------------------------------

def test_module_never_imports_yaml_at_top_level():
    src = pathlib.Path(I.__file__).read_text(encoding="utf-8")
    for line in src.splitlines():
        if line.startswith("import yaml") or line.startswith("from yaml"):
            raise AssertionError("yaml must stay a lazy, in-function import: " + line)


# --------------------------------------------------------------------------------------------
# Spec validation
# --------------------------------------------------------------------------------------------

class TestValidateSpec:
    def test_accepts_a_minimal_valid_spec(self):
        I.validate_spec(_spec())  # must not raise

    def test_accepts_the_demo_shape(self):
        I.validate_spec(_spec(
            {"type": "label", "text": "MAIN STREET", "at": [0.5, 0.1],
             "enter": {"t": 0.0, "how": "slide-left"}},
            {"type": "emoji", "glyph": "\U0001F3F0", "at": [0.5, 0.3], "size": 0.22,
             "enter": {"t": 0.2, "how": "pop"}, "sfx": "pop"},
            {"type": "figure", "pose": "walk", "from": [0.08, 0.78], "to": [0.55, 0.78],
             "t0": 0.4, "t1": 2.0},
            {"type": "arrow", "from": [0.55, 0.7], "to": [0.5, 0.4],
             "enter": {"t": 2.1, "how": "draw"}, "sfx": "hit"},
        ))

    def test_rejects_non_mapping_spec(self):
        with pytest.raises(ValueError, match="mapping"):
            I.validate_spec([])

    def test_rejects_missing_scenes_key(self):
        with pytest.raises(ValueError, match="scenes"):
            I.validate_spec({})

    def test_rejects_empty_scenes(self):
        with pytest.raises(ValueError, match="scenes"):
            I.validate_spec({"scenes": []})

    def test_rejects_wrong_kind(self):
        with pytest.raises(ValueError, match="kind"):
            I.validate_spec(_spec(kind="video"))

    def test_rejects_non_positive_seconds(self):
        with pytest.raises(ValueError, match="seconds"):
            I.validate_spec(_spec(seconds=0))

    def test_rejects_negative_seconds(self):
        with pytest.raises(ValueError, match="seconds"):
            I.validate_spec(_spec(seconds=-1.0))

    @pytest.mark.parametrize("bg", ["red", "#GGG", "#12345", "", 12])
    def test_rejects_bad_bg(self, bg):
        with pytest.raises(ValueError, match="bg"):
            I.validate_spec(_spec(bg=bg))

    def test_accepts_three_digit_hex_bg(self):
        I.validate_spec(_spec(bg="#fff"))

    def test_rejects_empty_elements(self):
        with pytest.raises(ValueError, match="elements"):
            I.validate_spec(_spec(elements=[]))

    def test_rejects_unknown_element_type(self):
        with pytest.raises(ValueError, match="type"):
            I.validate_spec(_spec({"type": "sparkle", "at": [0.5, 0.5]}))

    def test_rejects_bad_sfx(self):
        with pytest.raises(ValueError, match="sfx"):
            I.validate_spec(_spec(
                {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "sfx": "boom"}))

    def test_rejects_point_out_of_range(self):
        with pytest.raises(ValueError, match="at"):
            I.validate_spec(_spec({"type": "emoji", "glyph": "x", "at": [5.0, 0.5]}))

    def test_rejects_point_with_wrong_shape(self):
        with pytest.raises(ValueError, match="at"):
            I.validate_spec(_spec({"type": "emoji", "glyph": "x", "at": [0.5]}))

    def test_rejects_bad_enter_how_for_type(self):
        with pytest.raises(ValueError, match="how"):
            I.validate_spec(_spec(
                {"type": "emoji", "glyph": "x", "at": [0.5, 0.5],
                 "enter": {"t": 0, "how": "draw"}}))

    def test_rejects_negative_enter_t(self):
        with pytest.raises(ValueError, match="enter.t"):
            I.validate_spec(_spec(
                {"type": "emoji", "glyph": "x", "at": [0.5, 0.5],
                 "enter": {"t": -1, "how": "pop"}}))

    def test_emoji_requires_glyph(self):
        with pytest.raises(ValueError, match="glyph"):
            I.validate_spec(_spec({"type": "emoji", "at": [0.5, 0.5]}))

    def test_emoji_size_must_be_in_unit_range(self):
        with pytest.raises(ValueError, match="size"):
            I.validate_spec(_spec(
                {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "size": 1.5}))

    def test_label_requires_text(self):
        with pytest.raises(ValueError, match="text"):
            I.validate_spec(_spec({"type": "label", "at": [0.5, 0.5]}))

    def test_label_accepts_slide_right(self):
        I.validate_spec(_spec(
            {"type": "label", "text": "HI", "at": [0.5, 0.5],
             "enter": {"t": 0, "how": "slide-right"}}))

    def test_tag_requires_text(self):
        with pytest.raises(ValueError, match="text"):
            I.validate_spec(_spec({"type": "tag", "at": [0.5, 0.5]}))

    def test_tag_rejects_draw_how(self):
        with pytest.raises(ValueError, match="how"):
            I.validate_spec(_spec(
                {"type": "tag", "text": "$1", "at": [0.5, 0.5],
                 "enter": {"t": 0, "how": "draw"}}))

    def test_arrow_requires_from_and_to(self):
        with pytest.raises(ValueError, match="to"):
            I.validate_spec(_spec({"type": "arrow", "from": [0.1, 0.1]}))

    def test_arrow_accepts_draw(self):
        I.validate_spec(_spec(
            {"type": "arrow", "from": [0, 0], "to": [1, 1],
             "enter": {"t": 0, "how": "draw"}}))

    def test_box_requires_w_and_h_in_range(self):
        with pytest.raises(ValueError, match="w"):
            I.validate_spec(_spec(
                {"type": "box", "at": [0.5, 0.5], "w": 2.0, "h": 0.2}))

    def test_box_label_must_be_a_string(self):
        with pytest.raises(ValueError, match="label"):
            I.validate_spec(_spec(
                {"type": "box", "at": [0.5, 0.5], "w": 0.2, "h": 0.2, "label": 5}))

    def test_figure_requires_known_pose(self):
        with pytest.raises(ValueError, match="pose"):
            I.validate_spec(_spec({"type": "figure", "pose": "dance", "at": [0.5, 0.5]}))

    def test_figure_stand_requires_at(self):
        with pytest.raises(ValueError, match="at"):
            I.validate_spec(_spec({"type": "figure", "pose": "stand"}))

    def test_figure_walk_requires_t0_and_t1(self):
        with pytest.raises(ValueError, match="t0"):
            I.validate_spec(_spec(
                {"type": "figure", "pose": "walk", "from": [0, 0], "to": [1, 1], "t1": 1.0}))

    def test_figure_walk_requires_t1_greater_than_t0(self):
        with pytest.raises(ValueError, match="t1"):
            I.validate_spec(_spec(
                {"type": "figure", "pose": "walk", "from": [0, 0], "to": [1, 1],
                 "t0": 1.0, "t1": 0.5}))

    def test_calendar_requires_positive_integer_cols(self):
        with pytest.raises(ValueError, match="cols"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 0, "step": 0.2,
                 "cells": [{"label": "Mon", "value": "$1", "tone": "low"}]}))

    def test_calendar_requires_nonempty_cells(self):
        with pytest.raises(ValueError, match="cells"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0.2, "cells": []}))

    def test_calendar_cell_requires_label(self):
        with pytest.raises(ValueError, match="label"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0.2,
                 "cells": [{"value": "$1", "tone": "low"}]}))

    def test_calendar_cell_requires_valid_tone(self):
        with pytest.raises(ValueError, match="tone"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0.2,
                 "cells": [{"label": "Mon", "value": "$1", "tone": "spicy"}]}))

    def test_calendar_cell_rejects_bad_sfx(self):
        with pytest.raises(ValueError, match="sfx"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0.2,
                 "cells": [{"label": "Mon", "value": "$1", "tone": "low", "sfx": "boom"}]}))

    def test_calendar_requires_positive_step(self):
        with pytest.raises(ValueError, match="step"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0,
                 "cells": [{"label": "Mon", "value": "$1", "tone": "low"}]}))

    def test_calendar_rejects_negative_t0(self):
        with pytest.raises(ValueError, match="t0"):
            I.validate_spec(_spec(
                {"type": "calendar", "at": [0.5, 0.5], "cols": 7, "step": 0.2, "t0": -0.1,
                 "cells": [{"label": "Mon", "value": "$1", "tone": "low"}]}))


# --------------------------------------------------------------------------------------------
# Frame-time <-> animation-delay math
# --------------------------------------------------------------------------------------------

class TestFrameTimes:
    def test_exact_multiple_of_fps(self):
        ts = I.frame_times(4.0, fps=30)
        assert len(ts) == 120
        assert ts[0] == 0.0
        assert ts[-1] == pytest.approx(119 / 30)

    def test_survives_floating_point_wobble(self):
        # 4.0 * 30 is not guaranteed to land on an exact integer in binary float arithmetic;
        # round() -- not ceil/int -- is what keeps this at 120 frames, not 119 or 121.
        assert len(I.frame_times(4.0, fps=30)) == round(4.0 * 30)

    def test_frames_are_evenly_spaced_at_one_over_fps(self):
        ts = I.frame_times(1.0, fps=30)
        for i, t in enumerate(ts):
            assert t == pytest.approx(i / 30)

    def test_too_short_for_one_frame_raises(self):
        with pytest.raises(ValueError):
            I.frame_times(0.0, fps=30)


class TestSeekDelay:
    def test_before_start_is_positive_remaining_time(self):
        assert I.seek_delay(t_event=1.0, frame_t=0.5) == 0.5

    def test_at_start_is_zero(self):
        assert I.seek_delay(t_event=1.0, frame_t=1.0) == 0.0

    def test_after_start_is_negative_elapsed(self):
        assert I.seek_delay(t_event=1.0, frame_t=1.6) == pytest.approx(-0.6)

    def test_matches_general_subtraction(self):
        for t_event in (0.0, 0.2, 2.5):
            for frame_t in (0.0, 0.1, 3.0):
                assert I.seek_delay(t_event, frame_t) == round(t_event - frame_t, 6)


# --------------------------------------------------------------------------------------------
# Calendar fill schedule
# --------------------------------------------------------------------------------------------

class TestCalendarCellTimes:
    def test_even_spacing_from_t0(self):
        assert I.calendar_cell_times(0.3, 0.3, 4) == [0.3, 0.6, 0.9, 1.2]

    def test_zero_t0(self):
        assert I.calendar_cell_times(0.0, 0.25, 3) == [0.0, 0.25, 0.5]

    def test_zero_cells_is_empty(self):
        assert I.calendar_cell_times(0.0, 0.25, 0) == []

    def test_single_cell_starts_at_t0(self):
        assert I.calendar_cell_times(1.5, 0.3, 1) == [1.5]


# --------------------------------------------------------------------------------------------
# Per-scene event list ([{t, sfx}], absolute scene time, sorted)
# --------------------------------------------------------------------------------------------

class TestSceneEvents:
    def test_elements_without_sfx_produce_no_event(self):
        scene = _scene(elements=[{"type": "emoji", "glyph": "a", "at": [0.5, 0.5]}])
        assert I.scene_events(scene) == []

    def test_pop_fade_slide_fire_at_enter_t(self):
        scene = _scene(elements=[
            {"type": "emoji", "glyph": "a", "at": [0.5, 0.5],
             "enter": {"t": 0.2, "how": "pop"}, "sfx": "pop"},
        ])
        assert I.scene_events(scene) == [{"t": 0.2, "sfx": "pop"}]

    def test_sfx_with_no_enter_fires_at_zero(self):
        scene = _scene(elements=[{"type": "emoji", "glyph": "a", "at": [0.5, 0.5], "sfx": "chime"}])
        assert I.scene_events(scene) == [{"t": 0.0, "sfx": "chime"}]

    def test_drop_offsets_to_its_own_completion(self):
        scene = _scene(elements=[
            {"type": "tag", "text": "$1", "at": [0.5, 0.5],
             "enter": {"t": 1.0, "how": "drop"}, "sfx": "hit"},
        ])
        assert I.scene_events(scene) == [{"t": round(1.0 + I.DROP_DUR, 4), "sfx": "hit"}]

    def test_draw_offsets_to_its_own_completion(self):
        scene = _scene(elements=[
            {"type": "arrow", "from": [0, 0], "to": [1, 1],
             "enter": {"t": 2.0, "how": "draw"}, "sfx": "hit"},
        ])
        assert I.scene_events(scene) == [{"t": round(2.0 + I.DRAW_DUR, 4), "sfx": "hit"}]

    def test_figure_walk_sfx_fires_at_t0(self):
        scene = _scene(elements=[
            {"type": "figure", "pose": "walk", "from": [0, 0.5], "to": [1, 0.5],
             "t0": 0.5, "t1": 2.5, "sfx": "whoosh"},
        ])
        assert I.scene_events(scene) == [{"t": 0.5, "sfx": "whoosh"}]

    def test_figure_walk_without_sfx_produces_no_event(self):
        scene = _scene(elements=[
            {"type": "figure", "pose": "walk", "from": [0, 0.5], "to": [1, 0.5],
             "t0": 0.5, "t1": 2.5},
        ])
        assert I.scene_events(scene) == []

    def test_calendar_cells_each_schedule_their_own_event(self):
        scene = _scene(elements=[
            {"type": "calendar", "at": [0.5, 0.5], "cols": 2, "step": 0.3, "t0": 0.2,
             "sfx": "pop",
             "cells": [{"label": "Mon", "value": "$1", "tone": "low"},
                       {"label": "Tue", "value": "$2", "tone": "mid"}]},
        ])
        assert I.scene_events(scene) == [{"t": 0.2, "sfx": "pop"}, {"t": 0.5, "sfx": "pop"}]

    def test_calendar_cell_sfx_overrides_the_element_default(self):
        scene = _scene(elements=[
            {"type": "calendar", "at": [0.5, 0.5], "cols": 2, "step": 0.3, "t0": 0.0,
             "sfx": "pop",
             "cells": [{"label": "Mon", "value": "$1", "tone": "low", "sfx": "chime"},
                       {"label": "Tue", "value": "$2", "tone": "mid"}]},
        ])
        events = I.scene_events(scene)
        assert events[0] == {"t": 0.0, "sfx": "chime"}
        assert events[1] == {"t": 0.3, "sfx": "pop"}

    def test_calendar_cell_with_no_default_and_no_own_sfx_produces_no_event(self):
        scene = _scene(elements=[
            {"type": "calendar", "at": [0.5, 0.5], "cols": 2, "step": 0.3, "t0": 0.0,
             "cells": [{"label": "Mon", "value": "$1", "tone": "low"}]},
        ])
        assert I.scene_events(scene) == []

    def test_events_are_sorted_by_time(self):
        scene = _scene(elements=[
            {"type": "emoji", "glyph": "a", "at": [0.1, 0.1],
             "enter": {"t": 2.0, "how": "pop"}, "sfx": "pop"},
            {"type": "emoji", "glyph": "b", "at": [0.2, 0.2],
             "enter": {"t": 0.5, "how": "pop"}, "sfx": "chime"},
        ])
        assert [e["t"] for e in I.scene_events(scene)] == [0.5, 2.0]

    def test_ties_keep_authored_order_stable_sort(self):
        scene = _scene(elements=[
            {"type": "emoji", "glyph": "a", "at": [0.1, 0.1],
             "enter": {"t": 1.0, "how": "pop"}, "sfx": "pop"},
            {"type": "emoji", "glyph": "b", "at": [0.2, 0.2],
             "enter": {"t": 1.0, "how": "pop"}, "sfx": "chime"},
        ])
        assert [e["sfx"] for e in I.scene_events(scene)] == ["pop", "chime"]


# --------------------------------------------------------------------------------------------
# Pure HTML/CSS generation, one element type at a time
# --------------------------------------------------------------------------------------------

class TestRenderElement:
    def test_emoji_contains_glyph_and_id(self):
        html, css = I.render_element(
            {"type": "emoji", "glyph": "\U0001F3F0", "at": [0.5, 0.3], "size": 0.2}, 0)
        assert "\U0001F3F0" in html
        assert 'id="el0"' in html
        assert css == ""

    def test_emoji_with_enter_carries_data_t0_and_its_keyframe(self):
        html, _ = I.render_element(
            {"type": "emoji", "glyph": "x", "at": [0.5, 0.5], "enter": {"t": 0.4, "how": "pop"}}, 1)
        assert 'data-t0="0.4000"' in html
        assert "kf-pop" in html

    def test_emoji_without_enter_has_no_data_t0(self):
        html, _ = I.render_element({"type": "emoji", "glyph": "x", "at": [0.5, 0.5]}, 0)
        assert "data-t0" not in html

    def test_label_escapes_text(self):
        html, _ = I.render_element({"type": "label", "text": "A & B", "at": [0.5, 0.5]}, 0)
        assert "A &amp; B" in html

    def test_label_slide_left_uses_its_keyframe(self):
        html, _ = I.render_element(
            {"type": "label", "text": "HI", "at": [0.5, 0.1],
             "enter": {"t": 0.0, "how": "slide-left"}}, 0)
        assert "kf-slide-left" in html

    def test_tag_contains_text_and_tag_class(self):
        html, _ = I.render_element(
            {"type": "tag", "text": "$39", "at": [0.7, 0.5],
             "enter": {"t": 1.0, "how": "drop"}}, 2)
        assert "$39" in html
        assert 'class="tag anim"' in html
        assert "kf-drop" in html

    def test_box_includes_label_when_given(self):
        html, _ = I.render_element(
            {"type": "box", "at": [0.5, 0.5], "w": 0.4, "h": 0.2, "label": "Zone"}, 0)
        assert "Zone" in html
        assert "box-rect" in html

    def test_box_without_label_has_no_label_span(self):
        html, _ = I.render_element({"type": "box", "at": [0.5, 0.5], "w": 0.4, "h": 0.2}, 0)
        assert "label-text" not in html

    def test_arrow_has_pathlength_and_marker(self):
        html, _ = I.render_element({"type": "arrow", "from": [0.1, 0.1], "to": [0.9, 0.9]}, 3)
        assert 'pathLength="1"' in html
        assert "marker-end" in html
        assert "<marker" in html

    def test_arrow_with_no_enter_leaves_arrowhead_always_on(self):
        html, _ = I.render_element({"type": "arrow", "from": [0, 0], "to": [1, 1]}, 0)
        assert "data-t0" not in html

    def test_arrow_draw_times_the_arrowhead_pop_to_land_on_completion(self):
        html, _ = I.render_element(
            {"type": "arrow", "from": [0, 0], "to": [1, 1],
             "enter": {"t": 1.0, "how": "draw"}}, 0)
        expected_head_t0 = 1.0 + I.DRAW_DUR - I.ARROWHEAD_POP_DUR
        assert f'data-t0="{expected_head_t0:.4f}"' in html
        assert "kf-draw" in html   # the line itself
        assert "kf-pop" in html    # the arrowhead's own short pop

    def test_figure_stand_is_static_without_enter(self):
        html, css = I.render_element({"type": "figure", "pose": "stand", "at": [0.5, 0.8]}, 0)
        assert "data-t0" not in html
        assert css == ""

    def test_figure_point_differs_from_stand(self):
        stand_html, _ = I.render_element({"type": "figure", "pose": "stand", "at": [0.5, 0.8]}, 0)
        point_html, _ = I.render_element({"type": "figure", "pose": "point", "at": [0.5, 0.8]}, 0)
        assert stand_html != point_html

    def test_figure_walk_emits_transform_keyframes_never_left_top(self):
        html, css = I.render_element(
            {"type": "figure", "pose": "walk", "from": [0.1, 0.8], "to": [0.6, 0.8],
             "t0": 0.4, "t1": 2.0}, 2)
        assert "@keyframes walkpos2" in css
        assert "transform:translate(" in css
        # the hard rule from the module docstring: a position animation must never be a
        # left/top keyframe (it can recompute correctly under getComputedStyle while the
        # painted frame a headless screenshot captures still shows the pre-seek position).
        assert "{left:" not in css
        assert "{top:" not in css
        assert "legsA2" in css and "legsB2" in css
        assert 'data-t0="0.4000"' in html

    def test_figure_walk_legs_keyframes_use_discrete_steps(self):
        _, css = I.render_element(
            {"type": "figure", "pose": "walk", "from": [0, 0.5], "to": [1, 0.5],
             "t0": 0.0, "t1": 1.0}, 0)
        assert "steps(1)" in css

    def test_calendar_contains_every_cell_label_value_and_tone_colour(self):
        html, _ = I.render_element({
            "type": "calendar", "at": [0.5, 0.5], "cols": 2, "step": 0.3, "t0": 0.1,
            "cells": [{"label": "Mon", "value": "$19", "tone": "low"},
                      {"label": "Tue", "value": "$39", "tone": "high"}],
        }, 0)
        assert "Mon" in html and "$19" in html
        assert "Tue" in html and "$39" in html
        assert I.TONE_COLORS["low"] in html
        assert I.TONE_COLORS["high"] in html

    def test_calendar_cell_data_t0_matches_the_fill_schedule(self):
        html, _ = I.render_element({
            "type": "calendar", "at": [0.5, 0.5], "cols": 3, "step": 0.25, "t0": 0.0,
            "cells": [{"label": "A", "value": "1", "tone": "low"},
                      {"label": "B", "value": "2", "tone": "mid"}],
        }, 5)
        assert 'data-t0="0.0000"' in html
        assert 'data-t0="0.2500"' in html


# --------------------------------------------------------------------------------------------
# Whole-scene HTML assembly
# --------------------------------------------------------------------------------------------

class TestSceneHtml:
    def test_contains_seek_function_and_background(self):
        doc = I.scene_html(_scene(bg="#ABCDEF"))
        assert "window.seek" in doc
        assert "#ABCDEF" in doc
        assert doc.lower().startswith("<!doctype html>")

    def test_includes_every_element(self):
        doc = I.scene_html(_scene(elements=[
            {"type": "emoji", "glyph": "\U0001F3F0", "at": [0.5, 0.5]},
            {"type": "label", "text": "HELLO", "at": [0.5, 0.1]},
        ]))
        assert "\U0001F3F0" in doc
        assert "HELLO" in doc

    def test_calls_seek_zero_so_a_freshly_loaded_page_matches_frame_zero(self):
        doc = I.scene_html(_scene())
        assert "window.seek(0)" in doc


# --- the first demo render clipped a label and crowded the calendar ---------------------


class TestSafeWidth:
    def test_a_short_label_keeps_the_size_the_spec_asked_for(self):
        assert I.fit_label_px("MAIN STREET", 100.0) == 100.0

    def test_a_long_label_is_shrunk_to_the_safe_width(self):
        # 22 glyphs at 0.042 H = 80.6 px would be ~1,206 px wide on a 1,080 px frame.
        px = I.fit_label_px("ONE WEEK, SEVEN PRICES", 0.042 * I.H)
        assert px < 0.042 * I.H
        assert len("ONE WEEK, SEVEN PRICES") * I.LABEL_EM_PER_CHAR * px <= I.W * I.SAFE_W + 1e-6

    def test_the_label_html_carries_the_fitted_size_and_a_max_width(self):
        frag, _ = I._label_html({"type": "label", "text": "ONE WEEK, SEVEN PRICES",
                                 "at": [0.5, 0.14], "size": 0.042}, 0)
        assert "max-width:86.0%" in frag
        fitted = I.fit_label_px("ONE WEEK, SEVEN PRICES", 0.042 * I.H)
        assert f"font-size:{fitted:.1f}px" in frag

    def test_a_three_column_calendar_keeps_the_nominal_cell(self):
        cell, gap = I.calendar_geometry(3)
        assert cell == I.CAL_CELL_W * I.W

    def test_a_seven_column_calendar_fits_the_safe_width(self):
        cell, gap = I.calendar_geometry(7)
        assert cell < I.CAL_CELL_W * I.W
        assert 7 * cell + 6 * gap <= I.W * I.SAFE_W + 1e-6
