#!/usr/bin/env python3
"""TikTok via Upload-Post. Needs the paid plan; on the free tier this queues a card."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class TikTokPublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("tiktok", **kw)
