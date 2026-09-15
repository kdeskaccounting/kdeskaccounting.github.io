#!/usr/bin/env python3
"""Instagram Reels via Upload-Post (media_type=REELS, shared to feed)."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class InstagramPublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("instagram", **kw)
