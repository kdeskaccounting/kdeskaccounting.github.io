"""Spec-shape helpers shared by build_video.py and make_short.py. Stdlib only.

Legacy specs carry one `short:` block. Newer specs add `shorts: {name: block}` so one
workbook yields several Shorts (different hook, scenes, cell ranges). Variant None means
the legacy block, and its output filenames are unchanged.
"""
import re
from collections import namedtuple

ShortPaths = namedtuple("ShortPaths", "final work review")

#: A slug is one path segment: it becomes scripts/video/build/<slug>.
SLUG_RE = re.compile(r"[A-Za-z0-9._-]+")


def safe_slug(slug) -> str:
    """Validate the `slug:` of a spec that may have come from outside this repo.

    The slug names a build directory, so a spec another repo hands us must not be able to
    steer writes out of scripts/video/build/ - `.` and `..` pass the character class and are
    rejected separately.
    """
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug) or slug in (".", ".."):
        raise SystemExit(f"bad spec slug {slug!r}: a slug is one path segment of letters, "
                         f"digits, dot, underscore or hyphen (and not '.' or '..')")
    return slug


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
