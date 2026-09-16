"""Spec-shape helpers shared by build_video.py and make_short.py. Stdlib only.

Legacy specs carry one `short:` block. Newer specs add `shorts: {name: block}` so one
workbook yields several Shorts (different hook, scenes, cell ranges). Variant None means
the legacy block, and its output filenames are unchanged.
"""
import re
from collections import namedtuple

ShortPaths = namedtuple("ShortPaths", "final work review")

#: Scene kinds that carry their own content. A spec made only of these renders with no Excel
#: file and no LibreOffice recalculation, which is what makes a data Short cheap: `card` is
#: text from the scene's own `data:`, `media` is a video or a still from the scene's `src:`.
WORKBOOK_FREE_KINDS = ("title", "outro", "card", "media")

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


def needs_workbook(spec: dict) -> bool:
    """Does this spec need its `source:` workbook staged and recalculated?

    Only if some scene actually shows a spreadsheet. `kind:` has always been optional and
    its absence has always meant `sheet`, so the default here is the expensive one.
    """
    return any(sc.get("kind", "sheet") not in WORKBOOK_FREE_KINDS
               for sc in (spec.get("scenes") or []))
