"""The venture's channel identity on each platform -- the ONE place a rename changes.

2026-11-09 (~14:00): the ParkSheet channels were renamed to "Park Detective". The product, the
sheet and the Gumroad store stay "ParkSheet"; only the channel/handle identity moved. The YouTube
channel id did not change, so `selectors_youtube.CHANNEL_ID` stays where it is.

Stdlib-free on purpose (no imports): browser/ and publishers/ modules both import it, including
scripts run directly from scripts/browser/.

The LEGACY_* values are the pre-rename identity, kept ONLY so logs, ledgers and old run output can
still be parsed. No driver may accept a LEGACY_* value as proof it is on the right channel.
"""

# --- current identity (verified by Stephen 2026-11-09 after the rename) ----------------------
YOUTUBE_CHANNEL_NAME = "Park Detective"   # Studio header #entity-name; Switch account menu title
YOUTUBE_HANDLE = "@ParkDetective"         # channel id unchanged: UC7ApR5Ntbc4DRkkZ_FrwyOw
TIKTOK_HANDLE = "parkdetective"           # https://www.tiktok.com/@parkdetective
TIKTOK_NAME = "Park Detective"
INSTAGRAM_HANDLE = "park.detective"       # https://www.instagram.com/park.detective/
INSTAGRAM_NAME = "Park Detective"

# --- pre-2026-11-09 identity: for parsing history only, never for a channel check ------------
LEGACY_YOUTUBE_CHANNEL_NAME = "ParkSheet"
LEGACY_YOUTUBE_HANDLE = "@Parksheet"
LEGACY_TIKTOK_HANDLE = "parksheet"         # tiktok.com/@parksheet (some KDesk comments wrote @park.sheet)
LEGACY_INSTAGRAM_HANDLE = "park.sheet"


def tiktok_profile_url(handle: str = TIKTOK_HANDLE) -> str:
    return f"https://www.tiktok.com/@{handle.lstrip('@')}"


def instagram_profile_url(handle: str = INSTAGRAM_HANDLE) -> str:
    return f"https://www.instagram.com/{handle.lstrip('@')}/"
