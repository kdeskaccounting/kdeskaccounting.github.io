#!/usr/bin/env python3
"""Publisher contract: dry-run everywhere, queue cards instead of silent failures.

A publisher either returns a url (it published) or a queued_path (it wrote a paste-ready
card plus the asset under marketing/publish-queue/<platform>/ for Stephen). It never
raises past publish() for an upstream problem, and never swallows one either.
Stdlib only at import time.

Redaction: `detail` carries exception text and URLs straight into a git-tracked queue
card, the ledger and stdout, so every PublishResult masks it once at construction via
browser.session.redact_secrets - one choke point rather than a call each caller can
forget. Publisher.mask() adds the credentials only the instance knows (a key passed to
the constructor is in neither os.environ nor a token file). `detail` is the ONLY field
masked: the title and description are Stephen's own copy and reach the card verbatim.

The card *file* is written by session.write_queue_card so the dated `<date>-<slug>.md`
naming and its collision suffix live in exactly one place. The card *body* is local:
session.queue_card_markdown is a "why + numbered steps" login card, while a publish card
has to be paste-ready (title, caption, tags, privacy).
"""
from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from browser import session  # noqa: E402  (scripts/browser/session.py)

REPO = pathlib.Path(__file__).resolve().parents[2]


@dataclasses.dataclass(frozen=True)
class PublishResult:
    platform: str
    ok: bool
    url: str | None
    queued_path: str | None
    detail: str

    def __post_init__(self) -> None:
        # Frozen, so the mask has to go in through object.__setattr__. Doing it here means
        # no code path can hand an unredacted detail to a card, the ledger or stdout.
        object.__setattr__(self, "detail", session.redact_secrets(self.detail))
        if self.url is not None:
            object.__setattr__(self, "url", session.redact_secrets(self.url))


def queue_card_body(platform: str, meta: dict, detail: str, asset_name: str,
                    now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now().astimezone()
    tags = " ".join(f"#{t.replace(' ', '')}" for t in meta.get("tags", []))
    # Only `detail` is machine text (an exception, a response body, a URL). The title and
    # description are Stephen's own copy and must reach the card verbatim — masking the whole
    # body turned "The secret: a faster close" into "The secret: *** faster close", which is
    # both wrong to paste and alarming to read.
    detail = session.redact_secrets(detail)
    return (f"# {platform} — {meta.get('title', meta.get('slug', 'untitled'))}\n\n"
            f"Queued {now.strftime('%Y-%m-%d %H:%M %z')} by scripts/publishers/{platform}.py\n\n"
            f"## Why it is here\n\n{detail}\n\n"
            f"## Asset\n\n`{asset_name}` — sitting next to this card in the same folder.\n\n"
            f"## Title (copy this)\n\n{meta.get('title', '')}\n\n"
            f"## Caption (copy this)\n\n{meta.get('description', '')}\n\n"
            f"## Tags\n\n{tags or '(none)'}\n\n"
            f"## Privacy\n\n{meta.get('privacy', 'public')}\n")


def link_or_copy(asset: pathlib.Path, dest: pathlib.Path) -> str:
    """Symlink the mp4 next to its card; fall back to a real copy across filesystems."""
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    try:
        dest.symlink_to(asset.resolve())
        return "symlink"
    except OSError:
        shutil.copy2(asset, dest)
        return "copy"


def card_slug(meta: dict, asset: pathlib.Path) -> str:
    """Filename stem for the queue card — a name, never a path.

    `slug` comes from an author-written meta.json, so a stray separator (or a `..`) must
    not steer the write out of marketing/publish-queue/<platform>/.
    """
    raw = session.redact_secrets(meta.get("slug") or asset.stem)
    cleaned = raw.replace("/", "-").replace("\\", "-").strip(". ")
    return cleaned or asset.stem


class Publisher(abc.ABC):
    platform: str = "base"

    def __init__(self, *, repo: pathlib.Path = REPO) -> None:
        self.repo = pathlib.Path(repo)

    @abc.abstractmethod
    def capabilities(self) -> dict:
        """What this publisher can do right now (credentials present, limits, form variant)."""

    def preflight(self) -> PublishResult | None:
        """Return a not-ok PublishResult to abort before touching the asset, or None to proceed."""
        return None

    def extra_secrets(self) -> tuple[str, ...]:
        """Literal credential values this publisher holds that known_secrets() cannot see.

        A key passed to the constructor never reaches os.environ or a token file, so the
        global sweep is blind to it. Overriding this is how a publisher stays maskable.
        """
        return ()

    def mask(self, text) -> str:
        """Redact with this publisher's own credentials on top of the global sweep."""
        extra = tuple(str(s) for s in self.extra_secrets() if s)
        out = session.redact_secrets(text, secrets=extra) if extra else str(text or "")
        return session.redact_secrets(out)

    def _remask(self, result: PublishResult) -> PublishResult:
        """Re-mask a result built elsewhere (parse_response) with this publisher's key.

        PublishResult masks itself with the global sweep at construction; only the instance
        knows an explicitly-passed key. dataclasses.replace re-runs __post_init__, so both
        layers end up applied.
        """
        if not tuple(s for s in self.extra_secrets() if s):
            return result
        return dataclasses.replace(
            result,
            detail=self.mask(result.detail),
            url=None if result.url is None else self.mask(result.url))

    @abc.abstractmethod
    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        """Platform-specific publish. Raise or return a not-ok result to trigger queue()."""

    def queue(self, asset: pathlib.Path, meta: dict, detail: str) -> PublishResult:
        detail = self.mask(detail)
        now = dt.datetime.now().astimezone()
        body = queue_card_body(self.platform, meta, detail, asset.name, now)
        card = session.write_queue_card(self.repo, self.platform,
                                        card_slug(meta, asset), body, now)
        link_or_copy(asset, card.parent / asset.name)
        return PublishResult(platform=self.platform, ok=False, url=None,
                             queued_path=str(card.relative_to(self.repo)), detail=detail)

    def publish(self, asset: pathlib.Path, meta: dict, dry_run: bool) -> PublishResult:
        asset = pathlib.Path(asset)
        if not asset.exists():
            raise FileNotFoundError(f"asset not found: {asset}")
        if dry_run:
            return PublishResult(platform=self.platform, ok=True, url=None, queued_path=None,
                                 detail=(f"dry-run: would publish {asset.name} to {self.platform} "
                                         f"as {meta.get('title', '')!r} "
                                         f"[{meta.get('privacy', 'public')}]"))
        blocked = self.preflight()
        if blocked is not None:
            return self.queue(asset, meta, blocked.detail)
        try:
            result = self._remask(self._do_publish(asset, meta))
        except Exception as exc:  # noqa: BLE001 — queues, not silent failures
            return self.queue(asset, meta, f"{type(exc).__name__}: {exc}")
        if not result.ok:
            return self.queue(asset, meta, result.detail)
        return result
