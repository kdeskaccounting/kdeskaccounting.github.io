"""scripts/publishers/upload_post.py — the REST client, its form, and its failure modes."""
import pathlib

from publishers import upload_post as up

META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel #Shorts",
        "description": "PV of the remaining payments.", "privacy": "public",
        "tags": ["ASC 842", "Excel"]}


def _fields(platform, meta=META):
    return dict(up.build_form(platform, meta))


def test_endpoint_and_auth_header_match_the_documented_api():
    assert up.API_URL == "https://api.upload-post.com/api/upload"
    assert up.auth_header("abc123") == {"Authorization": "Apikey abc123"}
    assert up.FILE_FIELD == "video"
    assert up.PLATFORM_FIELD == "platform[]"


def test_build_form_always_sends_user_platform_title_and_description():
    pairs = up.build_form("youtube", META)
    assert ("platform[]", "youtube") in pairs
    f = dict(pairs)
    assert f["user"] == up.DEFAULT_PROFILE
    assert f["title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert f["description"] == "PV of the remaining payments."


def test_build_form_maps_youtube_privacy_tags_and_category():
    f = _fields("youtube")
    assert f["privacyStatus"] == "public"
    assert f["categoryId"] == "27"                  # Education, same as youtube_publish.py
    assert f["selfDeclaredMadeForKids"] == "false"
    assert dict(up.build_form("youtube", {**META, "privacy": "unlisted"}))["privacyStatus"] == "unlisted"


def test_build_form_maps_tiktok_privacy_level_and_direct_post():
    f = _fields("tiktok")
    assert f["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert f["post_mode"] == "DIRECT_POST"
    assert dict(up.build_form("tiktok", {**META, "privacy": "private"}))["privacy_level"] == "SELF_ONLY"


def test_build_form_maps_instagram_to_reels_shared_to_feed():
    f = _fields("instagram")
    assert f["media_type"] == "REELS"
    assert f["share_to_feed"] == "true"


def test_build_form_truncates_the_title_to_the_youtube_limit():
    f = dict(up.build_form("youtube", {**META, "title": "A" * 150}))
    assert len(f["title"]) == 100


def test_parse_response_reads_the_per_platform_url():
    res = up.parse_response("youtube", 200, {
        "success": True,
        "results": {"youtube": {"success": True, "url": "https://youtube.com/watch?v=VID",
                                "video_id": "VID"}},
        "usage": {"count": 12, "limit": 100}})
    assert res.ok is True
    assert res.url == "https://youtube.com/watch?v=VID"
    assert "12/100" in res.detail


def test_parse_response_reports_a_per_platform_failure_inside_a_200():
    res = up.parse_response("tiktok", 200, {
        "success": True,
        "results": {"tiktok": {"success": False, "error": "account not connected"}}})
    assert res.ok is False
    assert "account not connected" in res.detail


def test_parse_response_surfaces_the_http_error_message():
    res = up.parse_response("tiktok", 403, {
        "success": False, "message": "TikTok uploads not available on Free plan."})
    assert res.ok is False
    assert "403" in res.detail
    assert "Free plan" in res.detail


def test_parse_response_handles_an_async_accepted_upload():
    res = up.parse_response("youtube", 200, {
        "success": True, "message": "Upload initiated successfully in background.",
        "request_id": "1a2b3c", "total_platforms": 1})
    assert res.ok is False                       # no url yet -> queue it rather than claim success
    assert "1a2b3c" in res.detail


def test_publisher_without_an_api_key_queues_instead_of_calling_the_network(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")

    def explode(*a, **k):
        raise AssertionError("no HTTP call may happen without a key")

    monkeypatch.setattr(up, "_http_post", explode)
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert res.queued_path is not None
    assert "UPLOAD_POST_KEY" in res.detail
    assert (tmp_path / res.queued_path).exists()


def test_publisher_with_a_key_posts_the_multipart_form_and_returns_the_url(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    seen = {}

    def fake_post(url, headers, fields, file_field, file_path):
        seen.update(url=url, headers=headers, fields=fields,
                    file_field=file_field, file_path=str(file_path))
        return 200, {"success": True,
                     "results": {"youtube": {"success": True, "url": "https://youtu.be/VID",
                                             "video_id": "VID"}}}

    monkeypatch.setattr(up, "_http_post", fake_post)
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is True
    assert res.url == "https://youtu.be/VID"
    assert seen["url"] == up.API_URL
    assert seen["headers"]["Authorization"] == "Apikey k-123"
    assert seen["file_field"] == "video"
    assert ("platform[]", "youtube") in seen["fields"]


def test_publisher_queues_on_an_http_error(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (
        429, {"success": False, "message": "This upload would exceed your monthly limit."}))
    res = up.UploadPostPublisher("tiktok", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert "monthly limit" in res.detail
    card = tmp_path / res.queued_path
    assert card.exists()
    assert (card.parent / "x.mp4").exists()


def test_dry_run_makes_no_call_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no")))
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=True)
    assert res.ok is True and res.url is None
    assert not (tmp_path / "marketing").exists()


def test_capabilities_reports_the_key_state_and_the_form_variant(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    caps = up.UploadPostPublisher("tiktok", repo=tmp_path).capabilities()
    assert caps["platform"] == "tiktok"
    assert caps["has_key"] is False
    assert caps["form_variant"] == "platform[]"
    assert caps["needs_paid_plan"] is True          # TikTok is not on the free tier
    assert pathlib.Path(caps["queue_dir"]).name == "tiktok"


# ============================ fix round 1 ============================

# --- The key the publisher was CONSTRUCTED with is not in os.environ, so the global
# known_secrets() sweep cannot see it. Each case below echoes the key BARE - no `key=`,
# no `token:`, no `Apikey ` prefix - so no pattern can catch it and only the publisher
# supplying its own credential keeps it out of the card, the ledger line and stdout.

KEY = "up_live_SECRETVALUE1"


def test_a_key_echoed_bare_in_an_error_body_is_masked_in_the_card(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (
        401, {"success": False, "message": f"Invalid or expired credential {KEY} for profile kdesk"}))
    res = up.UploadPostPublisher("youtube", repo=tmp_path, api_key=KEY).publish(
        asset, META, dry_run=False)
    assert res.ok is False
    assert KEY not in res.detail
    assert "***" in res.detail
    assert KEY not in (tmp_path / res.queued_path).read_text(encoding="utf-8")


def test_a_key_echoed_bare_in_an_exception_is_masked_in_the_card(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")

    def boom(*a, **k):
        raise RuntimeError(f"ConnectionError while authenticating as {KEY}")

    monkeypatch.setattr(up, "_http_post", boom)
    res = up.UploadPostPublisher("tiktok", repo=tmp_path, api_key=KEY).publish(
        asset, META, dry_run=False)
    assert KEY not in res.detail
    assert KEY not in (tmp_path / res.queued_path).read_text(encoding="utf-8")


def test_an_apikey_scheme_in_an_exception_is_masked_even_without_the_literal(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")

    def boom(*a, **k):
        raise RuntimeError("ConnectionError; sent Authorization: Apikey up_live_someother")

    monkeypatch.setattr(up, "_http_post", boom)
    res = up.UploadPostPublisher("tiktok", repo=tmp_path, api_key="up_live_different1").publish(
        asset, META, dry_run=False)
    assert "up_live_someother" not in res.detail
    assert "Apikey ***" in res.detail


def test_a_successful_result_masks_the_publishers_own_key_in_the_url(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (200, {
        "success": True,
        "results": {"youtube": {"success": True, "url": f"https://youtu.be/VID?ref={KEY}"}}}))
    res = up.UploadPostPublisher("youtube", repo=tmp_path, api_key=KEY).publish(
        asset, META, dry_run=False)
    assert res.ok is True
    assert KEY not in res.url


# --- Upload-Post documents per-platform overrides (youtube_title, tiktok_title, …)
# alongside the bare title/description. Sending both is harmless if the bare pair already
# wins and necessary if it does not. Unverified against the live API - hence the explicit
# capabilities() listing, so the first real upload can be checked against it.

def test_build_form_sends_both_the_bare_and_the_per_platform_text_fields():
    f = _fields("youtube")
    assert f["title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert f["youtube_title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert f["description"] == "PV of the remaining payments."
    assert f["youtube_description"] == "PV of the remaining payments."


def test_per_platform_text_fields_follow_the_platform():
    assert _fields("tiktok")["tiktok_title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert _fields("instagram")["instagram_title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert "youtube_title" not in _fields("tiktok")


def test_per_platform_title_is_truncated_like_the_bare_one():
    f = dict(up.build_form("youtube", {**META, "title": "A" * 150}))
    assert len(f["youtube_title"]) == 100


def test_capabilities_lists_the_fields_that_are_not_verified_against_the_live_api(tmp_path):
    caps = up.UploadPostPublisher("youtube", repo=tmp_path).capabilities()
    assert "youtube_title" in caps["unverified_fields"]
    assert "youtube_description" in caps["unverified_fields"]
    assert up.PLATFORM_FIELD in caps["unverified_fields"]


# --- An async acceptance (request_id, no url) was treated as a flat failure, so a video
# that Upload-Post had actually accepted produced a queue card telling Stephen to post it
# again — a duplicate upload against a 10/month quota. Poll the documented status endpoint
# a bounded number of times first; only give up with an explicit "do not re-upload".

def _accepted(*a, **k):
    return 200, {"success": True, "message": "Upload initiated successfully in background.",
                 "request_id": "req-1a2b3c", "total_platforms": 1}


def test_status_endpoint_and_poll_budget_are_explicit():
    assert up.STATUS_URL == "https://api.upload-post.com/api/uploadposts/status"
    assert up.STATUS_ATTEMPTS >= 2
    assert up.STATUS_DELAY_S > 0


def test_an_async_accepted_upload_is_polled_until_the_status_endpoint_returns_a_url(
        tmp_path, monkeypatch):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    pending = {"success": True, "request_id": "req-1a2b3c", "status": "processing"}
    done = {"success": True,
            "results": {"youtube": {"success": True, "url": "https://youtu.be/VID"}}}
    calls, slept, seen = [], [], {}

    def fake_get(url, headers, params):
        seen.update(url=url, params=params)
        calls.append(1)
        return 200, (done if len(calls) >= 3 else pending)

    monkeypatch.setattr(up, "_http_post", _accepted)
    monkeypatch.setattr(up, "_http_get", fake_get)
    monkeypatch.setattr(up, "_sleep", lambda s: slept.append(s))
    res = up.UploadPostPublisher("youtube", repo=tmp_path, api_key="k-123").publish(
        asset, META, dry_run=False)
    assert res.ok is True
    assert res.url == "https://youtu.be/VID"
    assert "req-1a2b3c" in res.detail
    assert len(calls) == 3
    assert slept == [up.STATUS_DELAY_S, up.STATUS_DELAY_S]
    assert seen["url"] == up.STATUS_URL
    assert seen["params"] == {"request_id": "req-1a2b3c"}
    assert not (tmp_path / "marketing").exists()


def test_an_async_upload_that_never_completes_queues_with_the_request_id(tmp_path, monkeypatch):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    calls = []
    monkeypatch.setattr(up, "_http_post", _accepted)
    monkeypatch.setattr(up, "_http_get", lambda *a, **k: (
        calls.append(1), (200, {"success": True, "request_id": "req-1a2b3c"}))[1])
    monkeypatch.setattr(up, "_sleep", lambda s: None)
    res = up.UploadPostPublisher("youtube", repo=tmp_path, api_key="k-123").publish(
        asset, META, dry_run=False)
    assert res.ok is False
    assert len(calls) == up.STATUS_ATTEMPTS           # bounded, never an open loop
    card = (tmp_path / res.queued_path).read_text(encoding="utf-8")
    assert "req-1a2b3c" in res.detail and "req-1a2b3c" in card
    assert "do not re-upload" in card.lower()


def test_an_ordinary_http_failure_is_never_polled(tmp_path, monkeypatch):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")

    def no_get(*a, **k):
        raise AssertionError("a 403 is not an async acceptance; it must not be polled")

    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (
        403, {"success": False, "message": "TikTok uploads not available on Free plan."}))
    monkeypatch.setattr(up, "_http_get", no_get)
    res = up.UploadPostPublisher("tiktok", repo=tmp_path, api_key="k-123").publish(
        asset, META, dry_run=False)
    assert res.ok is False
    assert "Free plan" in res.detail


def test_a_status_poll_that_raises_still_queues_rather_than_escaping(tmp_path, monkeypatch):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", _accepted)
    monkeypatch.setattr(up, "_http_get", lambda *a, **k: (_ for _ in ()).throw(
        OSError("status endpoint unreachable")))
    monkeypatch.setattr(up, "_sleep", lambda s: None)
    res = up.UploadPostPublisher("youtube", repo=tmp_path, api_key="k-123").publish(
        asset, META, dry_run=False)
    assert res.ok is False
    assert res.queued_path is not None
    assert "req-1a2b3c" in res.detail
