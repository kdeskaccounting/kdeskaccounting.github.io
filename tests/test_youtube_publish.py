"""Pure parts of scripts/video/youtube_publish.py — the Data API replacement for the CDP Studio driver."""
import youtube_publish as yp


def test_chapters_accumulate_scene_durations_with_floor_and_gap():
    spec = {"scenes": [
        {"kind": "title", "heading": "X"},
        {"sheet": "Setup", "caption": "One period selector"},
        {"sheet": "JE Generator"},              # no caption -> falls back to sheet name
        {"kind": "outro"},
    ]}
    durations = {"0": 2.0, "1": 5.3, "2": 1.0}  # outro has no audio entry
    # each scene advances by max(3.0, dur + 0.7): 3.0, 6.0, 3.0
    assert yp.chapters(spec, durations) == "0:00 Intro\n0:03 One period selector\n0:09 JE Generator\n0:12 Get the workbook"


def test_video_body_sets_public_safe_defaults_and_truncates_to_youtube_limits():
    body = yp.video_body(title="A" * 120, description="x" * 6000, tags=["asc 842", "excel"])
    assert len(body["snippet"]["title"]) == 100
    assert len(body["snippet"]["description"]) == 5000
    assert body["snippet"]["tags"] == ["asc 842", "excel"]
    assert body["snippet"]["categoryId"] == "27"          # Education
    assert body["status"]["privacyStatus"] == "private"   # un-audited API projects are forced private anyway
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_video_body_accepts_public_when_asked():
    assert yp.video_body("t", "d", [], privacy="public")["status"]["privacyStatus"] == "public"


def test_walkthrough_description_assembles_blurb_links_chapters_and_disclaimer():
    d = yp.walkthrough_description("Tab-by-tab walkthrough.", "https://kdeskaccounting.com/templates/asc842/",
                                   "https://kdeskaccounting.gumroad.com/l/gljxc", "0:00 Intro\n0:03 Setup")
    assert d.startswith("Tab-by-tab walkthrough.")
    assert "https://kdeskaccounting.com/templates/asc842/" in d
    assert "https://kdeskaccounting.gumroad.com/l/gljxc" in d
    assert "Chapters:\n0:00 Intro\n0:03 Setup" in d
    assert "Not tax or legal advice" in d


def test_short_description_appends_disclaimer_tail():
    d = yp.short_description("The month-one entry.\nFree: https://x")
    assert d.startswith("The month-one entry.\nFree: https://x")
    assert d.rstrip().endswith("https://kdeskaccounting.com")
    assert "Not tax or legal advice" in d


def test_needs_upload_is_false_once_a_url_is_recorded():
    assert yp.needs_upload({}) is True
    assert yp.needs_upload({"url": None}) is True
    assert yp.needs_upload({"url": "https://youtu.be/abc"}) is False


def test_is_quota_error_recognises_youtube_quota_and_upload_limit_reasons():
    assert yp.is_quota_error(Exception('<HttpError 403 "quotaExceeded">')) is True
    assert yp.is_quota_error(Exception('reason: uploadLimitExceeded')) is True
    assert yp.is_quota_error(Exception("boom")) is False
