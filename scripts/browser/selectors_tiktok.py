"""Every TikTok Studio UI anchor, in one place (spec Chrome rule 6).

When TikTok moves the uploader, this is the only file that changes.

**Read this before trusting anything below.** The debug Chrome profile
(`~/.kdesk/chrome-debug`) held no TikTok session when this file was written (2026-09-15:
cookies for `.tiktok.com` were the anonymous `ttwid` / `odin_tt` pair only, no `sessionid`),
so *no selector here has been confirmed against a logged-in TikTok Studio*. Every such
anchor carries an `# UNVERIFIED` comment and is listed in `UNVERIFIED`; `tiktok_web.py
--check` is the tool that turns the list into knowledge — it resolves each anchor read-only
and prints what did and did not appear.

Because of that, the anchors are deliberately written as role / label / text where TikTok's
own copy is the stable part, and the two structural ones (`FILE_INPUT`, `POST_ROW`) are as
shallow as a selector can be. A long CSS descendant chain guessed from memory would be worse
than useless: it would fail *silently* by matching nothing.
"""

# --- URLs. These are the addresses Stephen types himself, so they are the one part of this
# file that is known good.
STUDIO_URL = "https://www.tiktok.com/tiktokstudio"
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"

# Hosts the studio may legitimately redirect to and still be the logged-in dashboard. An
# explicit allow-list, never a suffix match: `tiktok.com.evil.example` must stay unexpected.
ALT_HOSTS = ("tiktok.com",)

# The path fragment that means "this profile is signed out". session.classify tests it with
# `in url.path`, so it must be a path fragment and not a whole URL.
LOGIN_MARKER = "/login"
# What Stephen does when the marker shows up. TikTok's desktop login offers a QR code that is
# scanned with the phone app — the only login step that never types a password into a driver.
LOGIN_QR_TEXT = "Use QR code"                     # UNVERIFIED

# --- Upload page.
# TikTok's uploader has always been a plain <input type=file>, which is what makes
# Playwright's set_input_files work without touching the OS file dialog. Shallow on purpose.
FILE_INPUT = "input[type=file]"                   # UNVERIFIED
# The caption box is a rich-text editor (DraftJS-style), not a <textarea>: it takes clicks and
# typed keys, not fill(). Kept as an attribute selector rather than a descendant chain.
CAPTION_EDITOR = "div[contenteditable='true']"    # UNVERIFIED
CAPTION_MAX = 2200                                # UNVERIFIED
# Text that only appears once the video itself has finished uploading and the form is live.
UPLOAD_READY_TEXT = "Caption"                     # UNVERIFIED

# The scheduler: a "Now" / "Schedule" pair plus a date and a time field.
SCHEDULE_TOGGLE_TEXT = "Schedule"                 # UNVERIFIED
POST_NOW_TOGGLE_TEXT = "Now"                      # UNVERIFIED
SCHEDULE_DATE_INPUT = "input[placeholder*='-']"   # UNVERIFIED
SCHEDULE_TIME_INPUT = "input[placeholder*=':']"   # UNVERIFIED
# How the two fields want their values. Both are formatted by tiktok_web.format_date/_time,
# which is unit-tested, so a wrong format here is a one-constant fix rather than a code change.
DATE_FORMAT = "%Y-%m-%d"                          # UNVERIFIED
TIME_FORMAT = "%H:%M"                             # UNVERIFIED

# The submit button is labelled "Schedule" when the scheduler is on and "Post" when it is off.
POST_BUTTON_TEXT = "Post"                         # UNVERIFIED
SCHEDULE_BUTTON_TEXT = "Schedule"                 # UNVERIFIED
# The XHR whose completion means "TikTok accepted it" (rule 6: wait_for_response, not a sleep).
# The URL change to the content page is the second, independent confirmation, so a drifted
# fragment here costs a retry rather than a wrong answer.
POST_RESPONSE = "/project/post/"                  # UNVERIFIED

# How far ahead TikTok Studio lets a post be scheduled. Reported through capabilities() and
# enforced before anything is typed, so an over-long schedule fails on our side with a clear
# message instead of inside TikTok's form.
MAX_SCHEDULE_DAYS = 10                            # UNVERIFIED

# --- Posts list (the idempotency read).
SCHEDULED_TAB_TEXT = "Scheduled"                  # UNVERIFIED
# One row per post. `[role=row]` is the semantic anchor; the fallback exists because a card
# grid has no row role, and the reader tries them in order rather than joining them with a
# comma (a comma list silently mixes two shapes and the shallower one wins).
POST_ROW = "[role='row']"                         # UNVERIFIED
POST_ROW_FALLBACK = "main li"                     # UNVERIFIED
# Substring of the empty-state copy, lowercased. This is what lets "no scheduled posts" be
# told apart from "the list has not rendered yet" — the distinction that decides whether a
# skip is safe. When neither this nor a row appears, the driver times out and queues a card.
SCHEDULED_EMPTY_TEXT = "no content"               # UNVERIFIED

# Every anchor above that has never been seen live. capabilities() publishes this list and
# `--check` is what shortens it: delete a name here in the same commit that confirms it.
UNVERIFIED = (
    "LOGIN_QR_TEXT",
    "FILE_INPUT",
    "CAPTION_EDITOR",
    "CAPTION_MAX",
    "UPLOAD_READY_TEXT",
    "SCHEDULE_TOGGLE_TEXT",
    "POST_NOW_TOGGLE_TEXT",
    "SCHEDULE_DATE_INPUT",
    "SCHEDULE_TIME_INPUT",
    "DATE_FORMAT",
    "TIME_FORMAT",
    "POST_BUTTON_TEXT",
    "SCHEDULE_BUTTON_TEXT",
    "POST_RESPONSE",
    "SCHEDULED_TAB_TEXT",
    "POST_ROW",
    "POST_ROW_FALLBACK",
    "SCHEDULED_EMPTY_TEXT",
    "max_schedule_days",
)
