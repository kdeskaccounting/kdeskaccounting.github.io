"""Load a scenes.yaml spec, resolving `extends:` (2026-11-03, ParkSheet audit #5).

A spec may name a base spec it inherits from:

    extends: ../_template/scenes.yaml     # relative to THIS file (or absolute, or ~)
    slug: parksheet-hand-<slug>
    short: {hook: ..., plate: {text: ...}}
    scenes: [...]

The contract, all of it (ParkSheet's `parksheet/handspec.py` implements the same three
rules for its lint and gate, and a test there compares the two on the real template):

  1. mappings merge key by key, recursively, the child winning;
  2. anything else -- a list (so `scenes:` whole), a string, a number, `null` -- replaces;
  3. `extends:` chains (a base may extend another), is resolved relative to the file that
     names it, and a cycle or a chain deeper than MAX_DEPTH is refused by name.

A spec with no `extends:` comes back exactly as `yaml.safe_load` returned it -- the same
object, nothing copied -- so every existing spec renders unchanged. `yaml` is imported
inside `load`, so this module imports with the standard library alone (the bare test
environment), like captions.py.
"""
from __future__ import annotations

import pathlib

MAX_DEPTH = 8
KEY = "extends"


def merge(base, child):
    """`child` over `base`: mappings merge recursively, everything else replaces."""
    if isinstance(base, dict) and isinstance(child, dict):
        out = dict(base)
        for key, value in child.items():
            out[key] = merge(base[key], value) if key in base else value
        return out
    return child


def load(path, _chain=()):
    """The spec at `path`, with every `extends:` above it merged in."""
    import yaml  # lazy: absent from the bare test environment

    path = pathlib.Path(path).expanduser()
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or KEY not in data:
        return data
    here = path.resolve()
    chain = (*_chain, here)
    parent_raw = data[KEY]
    if not isinstance(parent_raw, str) or not parent_raw.strip():
        raise ValueError(f"{path}: `extends:` must be a path to a base spec, "
                         f"got {parent_raw!r}")
    parent = pathlib.Path(parent_raw).expanduser()
    if not parent.is_absolute():
        parent = path.parent / parent
    parent = parent.resolve()
    if parent in chain:
        raise ValueError(f"{path}: `extends:` cycle: "
                         + " -> ".join(str(p) for p in (*chain, parent)))
    if len(chain) >= MAX_DEPTH:
        raise ValueError(f"{path}: `extends:` chain deeper than {MAX_DEPTH}")
    if not parent.is_file():
        raise FileNotFoundError(f"{path}: `extends: {parent_raw}` -> {parent} does not exist")
    base = load(parent, chain)
    if not isinstance(base, dict):
        raise ValueError(f"{parent}: a base spec must be a mapping, got {type(base).__name__}")
    child = {key: value for key, value in data.items() if key != KEY}
    return merge(base, child)


if __name__ == "__main__":
    # `specload.py <spec>` prints the resolved spec as JSON: what the renderer will see.
    import json
    import sys

    print(json.dumps(load(sys.argv[1]), indent=1, sort_keys=True, ensure_ascii=False))
