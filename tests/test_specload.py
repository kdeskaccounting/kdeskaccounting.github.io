"""specload: `extends:` spec inheritance (ParkSheet audit #5, 2026-11-03).

The bare suite has no yaml, so `yaml.safe_load` is stubbed with `json.load` -- JSON is
YAML, and every rule here is about the merge, not the parser.
"""
import json
import sys
import types

import pytest

import specload


@pytest.fixture(autouse=True)
def json_yaml(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(safe_load=json.load))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


BASE = {"brand": {"name": "ParkSheet", "accent": "#1F6F3D", "font_bundle": "carlito"},
        "captions": {"enabled": True, "position": "top", "size": "large", "pop": 1.14},
        "short": {"scene_pad": 0.1, "plate": {"style": "search", "position": "top"}},
        "scenes": [{"narration": "template scene, never rendered"}],
        "disclaimer": "Not affiliated."}


def test_a_spec_without_extends_is_returned_untouched(tmp_path):
    spec = _write(tmp_path / "scenes.yaml", BASE)
    assert specload.load(spec) == BASE


def test_mappings_merge_and_everything_else_replaces(tmp_path):
    _write(tmp_path / "_template" / "scenes.yaml", BASE)
    child = _write(tmp_path / "slug" / "scenes.yaml", {
        "extends": "../_template/scenes.yaml", "slug": "parksheet-hand-x",
        "short": {"hook": "Why?", "plate": {"text": "why?", "seconds": 2.3}},
        "captions": {"position": "center"},
        "scenes": [{"narration": "one"}, {"narration": "two"}],
        "disclaimer": None})
    spec = specload.load(child)
    assert "extends" not in spec
    assert spec["slug"] == "parksheet-hand-x"
    assert spec["brand"] == BASE["brand"]
    assert spec["captions"] == {"enabled": True, "position": "center", "size": "large",
                                "pop": 1.14}
    assert spec["short"] == {"scene_pad": 0.1, "hook": "Why?",
                             "plate": {"style": "search", "position": "top",
                                       "text": "why?", "seconds": 2.3}}
    assert [s["narration"] for s in spec["scenes"]] == ["one", "two"]
    assert spec["disclaimer"] is None


def test_extends_chains_relative_to_each_file(tmp_path):
    _write(tmp_path / "a" / "base.yaml", {"brand": {"name": "A", "url": "a"}})
    _write(tmp_path / "b" / "mid.yaml", {"extends": "../a/base.yaml", "brand": {"url": "b"}})
    leaf = _write(tmp_path / "c" / "leaf.yaml", {"extends": "../b/mid.yaml", "slug": "s"})
    assert specload.load(leaf) == {"brand": {"name": "A", "url": "b"}, "slug": "s"}


def test_a_cycle_is_refused_by_name(tmp_path):
    _write(tmp_path / "a.yaml", {"extends": "b.yaml"})
    _write(tmp_path / "b.yaml", {"extends": "a.yaml"})
    with pytest.raises(ValueError) as excinfo:
        specload.load(tmp_path / "a.yaml")
    assert "cycle" in str(excinfo.value)


def test_a_missing_base_is_refused_naming_the_path(tmp_path):
    leaf = _write(tmp_path / "leaf.yaml", {"extends": "nope/scenes.yaml"})
    with pytest.raises(FileNotFoundError) as excinfo:
        specload.load(leaf)
    assert "nope" in str(excinfo.value)


def test_the_merge_never_mutates_the_base(tmp_path):
    base = {"short": {"plate": {"style": "search"}}}
    merged = specload.merge(base, {"short": {"plate": {"text": "x"}}})
    assert base == {"short": {"plate": {"style": "search"}}}
    assert merged == {"short": {"plate": {"style": "search", "text": "x"}}}
