#!/usr/bin/env python3
"""YouTube Shorts via Upload-Post (NOT the Data API — see scripts/video/youtube_publish.py)."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class YouTubePublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("youtube", **kw)
