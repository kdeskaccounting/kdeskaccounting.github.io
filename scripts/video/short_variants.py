"""Named Short variants for a scenes.yaml spec.

Legacy specs carry one `short:` block. Newer specs add `shorts: {name: block}` so one
workbook yields several Shorts (different hook, scenes, cell ranges). Variant None means
the legacy block, and its output filenames are unchanged.
"""
from collections import namedtuple

ShortPaths = namedtuple("ShortPaths", "final work review")


def select_short(spec: dict, variant: str | None) -> dict:
    named = spec.get("shorts") or {}
    if variant is None:
        if "short" in spec:
            return spec["short"]
        raise KeyError("spec has no `short:` block" + (f"; named variants: {', '.join(named)}" if named else ""))
    if variant in named:
        return named[variant]
    raise KeyError(f"no short variant {variant!r}; available: {', '.join(named) or '(none)'}")


def all_variants(spec: dict) -> list[tuple[str | None, dict]]:
    out = [(None, spec["short"])] if "short" in spec else []
    out += list((spec.get("shorts") or {}).items())
    return out


def short_paths(build, slug: str, variant: str | None) -> ShortPaths:
    sfx = "" if variant is None else f"-{variant}"
    return ShortPaths(build / f"{slug}-short{sfx}.mp4", build / f"short{sfx}", build / f"short-review{sfx}")
