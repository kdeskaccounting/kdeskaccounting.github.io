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
