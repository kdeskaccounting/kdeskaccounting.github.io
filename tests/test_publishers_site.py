"""scripts/publishers/site.py — cross-post a Short to the Hugo site."""
import datetime as dt

from publishers import site

DATE = dt.date(2026, 9, 14)
META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel",
        "description": "PV of the remaining payments, every month.",
        "video_url": "https://youtube.com/shorts/n1BlUeme0k4",
        "tags": ["ASC 842", "Excel"], "product": "asc842"}


def test_post_path_is_dated_under_content_shorts(tmp_path):
    assert site.post_path(tmp_path, DATE, "asc842-liability") == (
        tmp_path / "content" / "shorts" / "2026-09-14-asc842-liability.md")


def test_post_markdown_has_hugo_frontmatter_and_embeds_the_video_url():
    md = site.post_markdown(DATE, "asc842-liability", META)
    assert md.startswith("---\n")
    assert 'title: "ASC 842 Lease Liability in Excel"' in md
    assert "date: 2026-09-14" in md
    assert 'type: "shorts"' in md
    assert 'tags: ["ASC 842", "Excel"]' in md
    assert "https://youtube.com/shorts/n1BlUeme0k4" in md
    assert md.count("---\n") >= 2
    assert "PV of the remaining payments, every month." in md


def test_post_markdown_uses_the_youtube_embed_form_for_a_shorts_url():
    md = site.post_markdown(DATE, "s", {**META, "video_url": "https://youtube.com/shorts/ABC123"})
    assert 'src="https://www.youtube.com/embed/ABC123"' in md


def test_post_markdown_uses_the_embed_form_for_a_youtu_be_url():
    md = site.post_markdown(DATE, "s", {**META, "video_url": "https://youtu.be/ABC123"})
    assert 'src="https://www.youtube.com/embed/ABC123"' in md


def test_post_markdown_uses_the_embed_form_for_the_watch_url_upload_post_returns():
    # Upload-Post's documented success body carries the watch?v= form, so this is the
    # shape publish.py actually feeds the site publisher after a YouTube upload.
    md = site.post_markdown(DATE, "s", {**META, "video_url": "https://youtube.com/watch?v=ABC123"})
    assert 'src="https://www.youtube.com/embed/ABC123"' in md


def test_site_publisher_writes_the_post_and_returns_the_permalink(tmp_path):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    res = site.SitePublisher(repo=tmp_path, today=DATE).publish(asset, META, dry_run=False)
    assert res.ok is True
    assert res.url == "https://kdeskaccounting.com/shorts/2026-09-14-asc842-liability/"
    assert site.post_path(tmp_path, DATE, "asc842-liability").exists()


def test_site_publisher_dry_run_writes_nothing(tmp_path):
    (tmp_path / "x.mp4").write_bytes(b"v")
    res = site.SitePublisher(repo=tmp_path, today=DATE).publish(tmp_path / "x.mp4", META, dry_run=True)
    assert res.ok is True
    assert not (tmp_path / "content").exists()


def test_site_publisher_queues_when_there_is_no_video_url(tmp_path):
    (tmp_path / "x.mp4").write_bytes(b"v")
    meta = {k: v for k, v in META.items() if k != "video_url"}
    res = site.SitePublisher(repo=tmp_path, today=DATE).publish(tmp_path / "x.mp4", meta, dry_run=False)
    assert res.ok is False
    assert "video_url" in res.detail
    assert (tmp_path / res.queued_path).exists()
