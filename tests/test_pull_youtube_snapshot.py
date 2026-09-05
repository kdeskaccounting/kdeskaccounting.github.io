"""Pure parts of scripts/pull_youtube_snapshot.py (weekly row for marketing/seo-tracking/youtube-snapshots.jsonl)."""
import pull_youtube_snapshot as py


def test_iso_duration_seconds():
    assert py.iso_duration_seconds("PT49S") == 49
    assert py.iso_duration_seconds("PT4M36S") == 276
    assert py.iso_duration_seconds("PT1H2M3S") == 3723
    assert py.iso_duration_seconds("PT3M") == 180


ITEMS = [
    {"id": "a", "snippet": {"title": "T" * 90, "publishedAt": "2026-09-02T15:01:00Z"},
     "status": {"privacyStatus": "public"}, "contentDetails": {"duration": "PT49S"},
     "statistics": {"viewCount": "75", "likeCount": "1", "commentCount": "0"}},
    {"id": "b", "snippet": {"title": "Long", "publishedAt": "2026-09-02T15:02:00Z"},
     "status": {"privacyStatus": "public"}, "contentDetails": {"duration": "PT4M36S"},
     "statistics": {"viewCount": "3"}},   # no likeCount/commentCount -> 0
]


def test_summarize_videos_normalises_and_sorts_by_views_desc():
    rows = py.summarize_videos(ITEMS)
    assert [r["id"] for r in rows] == ["a", "b"]
    assert rows[0]["title"] == "T" * 70 and rows[0]["published"] == "2026-09-02"
    assert rows[0]["views"] == 75 and rows[0]["likes"] == 1
    assert rows[1]["likes"] == 0 and rows[1]["comments"] == 0
    assert rows[0]["seconds"] == 49 and rows[1]["seconds"] == 276


def test_build_snapshot_splits_shorts_from_long_form_and_tolerates_missing_analytics():
    channel = {"id": "UC1", "snippet": {"title": "KDeskAccounting"},
               "statistics": {"subscriberCount": "0", "viewCount": "0", "videoCount": "2"}}
    snap = py.build_snapshot(channel, py.summarize_videos(ITEMS), analytics=None, window=("2026-08-01", "2026-09-03"))
    assert snap["source"] == "youtube_data_api_v3"
    assert snap["channel_id"] == "UC1" and snap["video_count"] == 2
    assert snap["shorts_views"] == 75 and snap["longform_views"] == 3   # <= 60 s counts as a Short
    assert snap["analytics"] is None and snap["analytics_window"] == ["2026-08-01", "2026-09-03"]
    assert "pulled_at" in snap and len(snap["videos"]) == 2


def test_build_snapshot_keeps_analytics_row_when_present():
    channel = {"id": "UC1", "snippet": {"title": "K"}, "statistics": {}}
    snap = py.build_snapshot(channel, [], analytics={"views": 75, "estimatedMinutesWatched": 19}, window=("a", "b"))
    assert snap["analytics"]["views"] == 75 and snap["subscribers"] == 0
