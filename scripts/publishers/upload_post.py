#!/usr/bin/env python3
"""Upload-Post REST client (https://docs.upload-post.com/api/upload-video/, read 2026-09-14).

Upload-Post holds audited YouTube / TikTok / Meta credentials, which is why it exists here:
KDesk's own Google Cloud project is un-audited, so its Data-API uploads land locked-private
and cannot be appealed (see marketing plan, "Critical finding").

  POST https://api.upload-post.com/api/upload   multipart/form-data
  Authorization: Apikey <UPLOAD_POST_KEY>
  video=@file.mp4   platform[]=youtube   user=<profile>   title=...   description=...

Doc conflict, resolved: the docs landing page shows `file=@video.mp4` plus
`platforms=tiktok,instagram,youtube`; the API reference page shows `video=@video.mp4` plus
repeated `platform[]=tiktok`. This encodes the reference page, because that is the page
documenting every platform-specific field. capabilities() reports form_variant so a future
correction is one constant.

Free tier: 10 uploads/month, YouTube + Instagram. TikTok needs the paid plan.
Key from env UPLOAD_POST_KEY; profile from env UPLOAD_POST_PROFILE (default "kdesk").
No key, or any non-2xx, or a per-platform failure -> queue() (never a silent failure).
requests is imported lazily so this module stays stdlib-importable for tests.
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import time

from publishers.base import REPO, Publisher, PublishResult

API_URL = "https://api.upload-post.com/api/upload"
USERS_URL = "https://api.upload-post.com/api/uploadposts/users"
FILE_FIELD = "video"
PLATFORM_FIELD = "platform[]"
DEFAULT_PROFILE = "kdesk"
TITLE_MAX = 100          # YouTube's limit; the shortest of the three, so it is the safe cap
FREE_TIER_PLATFORMS = ("youtube", "instagram")
UPLOAD_TIMEOUT_S = 600   # an mp4 upload, not an API ping
STATUS_URL = "https://api.upload-post.com/api/uploadposts/status"
STATUS_TIMEOUT_S = 30
STATUS_ATTEMPTS = 5      # ~30s of waiting; this runs inside a scheduled job
STATUS_DELAY_S = 6
_sleep = time.sleep      # injectable so the poll test does not actually wait

# privacy (our vocabulary) -> per-platform value
TIKTOK_PRIVACY = {"public": "PUBLIC_TO_EVERYONE", "unlisted": "SELF_ONLY", "private": "SELF_ONLY"}


def unverified_fields(platform: str) -> tuple[str, ...]:
    """Form fields encoded from the docs but never exercised against the live API.

    Surfaced through capabilities() so the first real upload can be diffed against this
    list instead of guessing which half of the contradicting doc pages was right.
    """
    return (PLATFORM_FIELD, f"{platform}_title", f"{platform}_description")


def auth_header(api_key: str) -> dict:
    return {"Authorization": f"Apikey {api_key}"}


def profile() -> str:
    return os.environ.get("UPLOAD_POST_PROFILE", DEFAULT_PROFILE)


def build_form(platform: str, meta: dict, *,
               profile_name: str | None = None) -> list[tuple[str, str]]:
    """Every non-file multipart field, in a stable order, for one platform."""
    privacy = meta.get("privacy", "public")
    title = str(meta.get("title", ""))[:TITLE_MAX]
    description = str(meta.get("description", ""))
    fields: list[tuple[str, str]] = [
        (PLATFORM_FIELD, platform),
        ("user", profile_name or profile()),
        ("title", title),
        ("description", description),
        # Upload-Post documents per-platform overrides next to the bare pair. Sending both
        # is harmless if the bare pair already wins, and necessary if it does not.
        (f"{platform}_title", title),
        (f"{platform}_description", description),
    ]
    if platform == "youtube":
        fields += [("privacyStatus", privacy),
                   ("categoryId", str(meta.get("category_id", "27"))),
                   ("selfDeclaredMadeForKids", "false")]
        for tag in meta.get("tags", []):
            fields.append(("tags", str(tag)))
    elif platform == "tiktok":
        fields += [("privacy_level", TIKTOK_PRIVACY.get(privacy, "SELF_ONLY")),
                   ("post_mode", "DIRECT_POST")]
    elif platform == "instagram":
        fields += [("media_type", meta.get("media_type", "REELS")),
                   ("share_to_feed", "true")]
    return fields


def parse_response(platform: str, status: int, payload: dict) -> PublishResult:
    def fail(detail: str) -> PublishResult:
        return PublishResult(platform=platform, ok=False, url=None, queued_path=None, detail=detail)

    if status >= 300 or not payload.get("success"):
        return fail(f"Upload-Post HTTP {status}: "
                    f"{payload.get('message') or payload.get('error') or json.dumps(payload)[:200]}")
    results = payload.get("results") or {}
    if platform not in results:
        if payload.get("request_id"):
            return fail(f"Upload-Post accepted the upload asynchronously "
                        f"(request_id {payload['request_id']}); no url yet — "
                        f"check GET /api/uploadposts/status?request_id={payload['request_id']}")
        if payload.get("job_id"):
            return fail(f"Upload-Post scheduled the upload (job_id {payload['job_id']}); no url yet")
        return fail(f"Upload-Post returned no result for {platform}: {json.dumps(payload)[:200]}")
    entry = results[platform]
    if not entry.get("success"):
        return fail(f"Upload-Post {platform} failed: "
                    f"{entry.get('error') or entry.get('message') or json.dumps(entry)[:200]}")
    url = entry.get("url")
    if not url:
        pid = entry.get("post_id") or entry.get("video_id")
        return fail(f"Upload-Post {platform} succeeded but returned no url (post_id {pid})")
    usage = payload.get("usage") or {}
    used = f" · usage {usage.get('count')}/{usage.get('limit')}" if usage else ""
    return PublishResult(platform=platform, ok=True, url=url, queued_path=None,
                         detail=f"published via Upload-Post{used}")


def list_profiles(api_key: str) -> tuple[int, dict]:
    """The documented profile listing, so `user=` can be checked before an upload.

    A wrong profile costs a 400 "Username required in form data" — and on the free tier
    there are only ten attempts a month to get it right.
    """
    return _http_get(USERS_URL, auth_header(api_key), {})


def async_request_id(platform: str, status: int, payload: dict) -> str | None:
    """The request_id of an accepted-but-not-yet-finished upload, or None.

    Only an accepted 2xx with no per-platform result qualifies. A 403 or a per-platform
    failure is a real failure and must never be polled.
    """
    if status >= 300 or not payload.get("success"):
        return None
    if platform in (payload.get("results") or {}):
        return None
    rid = payload.get("request_id")
    return str(rid) if rid else None


def poll_status(platform: str, request_id: str, headers: dict, *,
                attempts: int = STATUS_ATTEMPTS,
                delay_s: float = STATUS_DELAY_S) -> PublishResult:
    """Ask the status endpoint for a url, a bounded number of times.

    Bounded on purpose: this runs inside a scheduled job. Giving up returns a not-ok result
    whose detail carries the request_id and an explicit do-not-re-upload, because the video
    may well be live already and every retry burns one of ten monthly slots.
    A transport error on one check is recorded and retried, never raised: escaping here
    would produce a card blaming the status endpoint and omitting the request_id.
    """
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            status, payload = _http_get(STATUS_URL, headers, {"request_id": request_id})
            result = parse_response(platform, status, payload)
            if result.ok:
                return dataclasses.replace(
                    result,
                    detail=(f"{result.detail} (async request_id {request_id}, "
                            f"ready on check {attempt}/{attempts})"))
            last = result.detail
        except Exception as exc:  # noqa: BLE001 — one failed check is not a failed upload
            last = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            _sleep(delay_s)
    return PublishResult(
        platform=platform, ok=False, url=None, queued_path=None,
        detail=(f"Upload-Post accepted the upload (request_id {request_id}) but it was still "
                f"not ready after {attempts} checks: {last}. DO NOT RE-UPLOAD — it may already "
                f"be live, and each attempt burns one of the monthly upload slots. Check "
                f"{STATUS_URL}?request_id={request_id} first, and post by hand only if it "
                f"really failed."))


def _http_get(url: str, headers: dict, params: dict) -> tuple[int, dict]:
    """The read-only network seam (status, profiles). Tests monkeypatch this."""
    import requests  # lazy: absent in the test environment
    resp = requests.get(url, headers=headers, params=params, timeout=STATUS_TIMEOUT_S)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"success": False, "message": resp.text[:500]}


def _http_post(url: str, headers: dict, fields: list[tuple[str, str]],
               file_field: str, file_path: pathlib.Path) -> tuple[int, dict]:
    """The one network seam. Tests monkeypatch this; nothing else does I/O."""
    import requests  # lazy: absent in the test environment
    with open(file_path, "rb") as fh:
        resp = requests.post(url, headers=headers, data=fields,
                             files={file_field: (file_path.name, fh, "video/mp4")},
                             timeout=UPLOAD_TIMEOUT_S)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"success": False, "message": resp.text[:500]}


class UploadPostPublisher(Publisher):
    def __init__(self, platform: str, *, repo: pathlib.Path | None = None,
                 api_key: str | None = None, profile: str | None = None) -> None:
        super().__init__(repo=repo if repo is not None else REPO)
        self.platform = platform
        self._api_key = api_key
        self._profile = profile

    def api_key(self) -> str | None:
        return self._api_key or os.environ.get("UPLOAD_POST_KEY")

    def profile_name(self) -> str:
        """The Upload-Post profile whose connected accounts receive the upload."""
        return self._profile or profile()

    def extra_secrets(self) -> tuple[str, ...]:
        """The API key, so it is masked even when it came from the constructor.

        An explicitly-passed key is in neither os.environ nor a token file, so
        session.known_secrets() cannot see it. Upload-Post echoes the credential back in
        some error bodies, and an exception from requests embeds the Authorization header.
        """
        key = self.api_key()
        return (key,) if key else ()

    def capabilities(self) -> dict:
        return {"platform": self.platform,
                "transport": "upload-post",
                "endpoint": API_URL,
                "form_variant": PLATFORM_FIELD,
                "unverified_fields": list(unverified_fields(self.platform)),
                "has_key": bool(self.api_key()),          # never the key itself
                "profile": self.profile_name(),
                "needs_paid_plan": self.platform not in FREE_TIER_PLATFORMS,
                "queue_dir": str(self.repo / "marketing" / "publish-queue" / self.platform)}

    def preflight(self) -> PublishResult | None:
        if not self.api_key():
            return PublishResult(
                platform=self.platform, ok=False, url=None, queued_path=None,
                detail=("No UPLOAD_POST_KEY in the environment. Set it "
                        "(export UPLOAD_POST_KEY=...) after connecting the account at "
                        "https://www.upload-post.com/, or post this card by hand."))
        return None

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        headers = auth_header(self.api_key())
        status, payload = _http_post(API_URL, headers,
                                     build_form(self.platform, meta,
                                                profile_name=self.profile_name()),
                                     FILE_FIELD, asset)
        rid = async_request_id(self.platform, status, payload)
        if rid:
            return poll_status(self.platform, rid, headers)
        return parse_response(self.platform, status, payload)
