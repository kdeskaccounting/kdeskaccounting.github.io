"""Music-bed rotation: `audio.bed: rotate` picks one bed from the spec's `bed_pool` (2026-11-09).

ParkSheet's stall deep-dive (research_notes/.../stall_deep_dive/content_pass.md, section 6)
found one Mixkit bed under 39 of 40 uploads, then another under every v6 post: the
"identical background music across numerous videos" YouTube's mass-produced-content policy
names. The v6 template now says

    audio:
      bed: rotate
    bed_pool:
    - {id: mixkit-little-bells-506, src: media/audio/..., lufs: -24.0, target_lufs: -24, fade_in: 0.3, fade_out: 1.2}
    - ...

and this module turns `rotate` into one pool entry, deterministically from the spec's `slug`
(sha256, so the same slug always gets the same bed on any machine and Python), and
`pool:<id>` into the named entry (the override when the pick would repeat yesterday's bed).

`bed_pool` is TOP-LEVEL on purpose: the renderer refuses an unknown `audio:` key but ignores
an unknown top-level one, so a spec that pins a concrete bed still renders on a renderer
that predates this module. A spec whose `audio.bed` is a mapping (every spec written before
2026-11-09) never reaches `pick`: `resolve_audio` returns its `audio:` block untouched, the
same object, so those renders stay byte-identical.

ParkSheet's `parksheet/beds.py` implements the same rule for its lint (which bed did the last
three posts carry?); a test there runs this file against it when the KDesk checkout is on
disk. Standard library only.
"""
from __future__ import annotations

import hashlib

ROTATE = "rotate"
POOL_PREFIX = "pool:"
POOL_KEY = "bed_pool"
#: What a pool entry may carry: an `id` plus exactly the keys `audio.bed` accepts.
BED_KEYS = ("src", "lufs", "target_lufs", "fade_in", "fade_out")


def slot(slug: str, size: int) -> int:
    """The pool index for `slug`: sha256 of the slug, big-endian, modulo the pool size."""
    if size <= 0:
        raise ValueError("bed_pool is empty")
    return int(hashlib.sha256(str(slug).encode("utf-8")).hexdigest(), 16) % size


def pool(spec: dict) -> list:
    """The spec's `bed_pool`, shape-checked. Raises ValueError naming the problem."""
    raw = (spec or {}).get(POOL_KEY)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"audio.bed asks for the pool but `{POOL_KEY}:` is "
                         f"{'missing' if raw is None else 'empty or not a list'}")
    seen = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("src"):
            raise ValueError(f"{POOL_KEY}[{index}] needs an `id` and a `src`")
        extra = set(entry) - {"id", *BED_KEYS}
        if extra:
            raise ValueError(f"{POOL_KEY}[{index}] ({entry['id']}): unknown key(s) "
                             f"{', '.join(sorted(extra))}; known: id, {', '.join(BED_KEYS)}")
        if entry["id"] in seen:
            raise ValueError(f"{POOL_KEY}: id {entry['id']!r} appears twice")
        seen.add(entry["id"])
    return raw


def pick(spec: dict) -> dict:
    """The pool entry `audio.bed` names (`rotate` or `pool:<id>`), with its `id`."""
    bed = ((spec or {}).get("audio") or {}).get("bed")
    entries = pool(spec)
    if bed == ROTATE:
        slug = (spec or {}).get("slug")
        if not slug:
            raise ValueError("audio.bed: rotate needs the spec's `slug` (the pick is by slug)")
        return entries[slot(slug, len(entries))]
    if isinstance(bed, str) and bed.startswith(POOL_PREFIX):
        want = bed[len(POOL_PREFIX):].strip()
        for entry in entries:
            if entry["id"] == want:
                return entry
        raise ValueError(f"audio.bed {bed!r}: no {POOL_KEY} entry with id {want!r}; "
                         f"ids: {', '.join(e['id'] for e in entries)}")
    raise ValueError(f"audio.bed {bed!r}: a string bed must be {ROTATE!r} or "
                     f"'{POOL_PREFIX}<id>' (or give a mapping with src/lufs)")


def resolve_audio(spec: dict):
    """The spec's `audio:` block with a `rotate` / `pool:<id>` bed replaced by its entry.

    Any other block -- absent, not a mapping, or a bed that is already a mapping -- comes
    back as the very same object, so an old spec renders exactly as it always did."""
    block = (spec or {}).get("audio")
    if not isinstance(block, dict) or not isinstance(block.get("bed"), str):
        return block
    entry = pick(spec)
    return {**block, "bed": {key: entry[key] for key in BED_KEYS if key in entry}}
