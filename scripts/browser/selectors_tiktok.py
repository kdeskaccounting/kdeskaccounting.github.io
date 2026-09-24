"""Every TikTok Studio UI anchor, in one place (spec Chrome rule 6).

When TikTok moves the uploader, this is the only file that changes.

**Status, 2026-09-15.** The debug Chrome is now signed in to TikTok Studio as @park.sheet, and
every anchor reachable *without committing anything* has been resolved live against it. What
that does and does not cover is the thing to read before trusting a line below:

* **Verified** anchors were counted on the live page by `tiktok_web.py --check` /
  `scripts/browser/runs/2026-09-15/selectors-*`. They carry `# verified 2026-09-15` plus how.
* **Post-file only** anchors — the caption editor, the scheduler, the submit button — do not
  exist in the DOM until a video has been handed to TikTok, and `--check` may not select a
  file to see them, because that starts a real upload. They stay in `POST_FILE_ONLY` forever
  for that reason, but that is no longer the same thing as being a guess: on 2026-09-23 a real
  video was carried through the scheduler by hand, so most of this section now carries
  `# verified 2026-09-23` instead of `# UNVERIFIED` — see the anchor-by-anchor notes below.
  What is still genuinely unverified (never confirmed even by that pass) stays `# UNVERIFIED`
  and in `UNVERIFIED`.

**Status, 2026-09-23.** The "When to post" control turned out not to be a switch — it is two
`<input type='radio' name='postSchedule'>`, so `SCHEDULE_RADIO_NAME` replaces the old
`SCHEDULE_TOGGLE`/`SCHEDULE_TOGGLE_TEXT` guess (and the `NOT_INSIDE_A_BUTTON` guard that
guess needed no longer exists — a role-scoped radio lookup cannot land on a button). The date
and time fields are read-only text inputs told apart by the shape of their value, not by
position. See the scheduler section below for the rest.

Three things the 2026-09-15 pass established that the previous guesses had wrong:

1. **There is no "Scheduled" tab.** The content page is a single Posts table whose own copy
   says "Your posted and scheduled videos will appear here." `[role=tab]` matches 0 on it.
   The driver therefore reads one list and never clicks a tab.
2. **The studio shell has no ARIA table.** `[role=row]`, `li` and `<table>` all match 0; the
   list is built from TikTok's own `data-tt` component ids (`components_PostTable_*`,
   `components_RowLayout_*`, `components_NoVideos_*`), which is what the row anchors use now.
3. **`get_by_role("button", name="Post")` matched the sidebar.** Playwright's accessible-name
   match is a case-insensitive *substring* by default, and the left nav has a "Posts" button
   that sorts before the form. That is why the old `--check` reported `post button OK` on a
   page with no Post button at all, and why every role lookup here is resolved with
   `exact=True`.

The anchors stay written as role / label / text where TikTok's own copy is the stable part,
and the structural ones are as shallow as the markup allows. A long CSS chain guessed from
memory would be worse than useless: it fails *silently* by matching nothing.
"""

# --- URLs. These are the addresses Stephen types himself, and all three were opened live.
STUDIO_URL = "https://www.tiktok.com/tiktokstudio"      # verified 2026-09-15: logged-in dashboard
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"   # verified 2026-09-15: uploader stage
CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"  # verified 2026-09-15: Posts table

# Hosts the studio may legitimately redirect to and still be the logged-in dashboard. An
# explicit allow-list, never a suffix match: `tiktok.com.evil.example` must stay unexpected.
ALT_HOSTS = ("tiktok.com",)

# The path fragment that means "this profile is signed out". session.classify tests it with
# `in url.path`, so it must be a path fragment and not a whole URL.
LOGIN_MARKER = "/login"
# What Stephen does when the marker shows up. TikTok's desktop login offers a QR code that is
# scanned with the phone app — the only login step that never types a password into a driver.
# Unverifiable while the profile is signed IN, which is the state we want it to stay in.
LOGIN_QR_TEXT = "Use QR code"                     # UNVERIFIED (only visible signed out)

# --- Upload page, BEFORE a file is chosen. Everything `--check` can honestly see.
# A plain <input type=file>, which is what makes Playwright's set_input_files work without
# touching the OS file dialog. It is `display:none` and fed by the "Select video" button, so
# it must never be waited on with state="visible" — set_input_files does not need visibility.
FILE_INPUT = "input[type=file]"                   # verified 2026-09-15: matched 1, accept="video/*"
# TikTok's own test ids for the pre-file uploader stage. These are the only two `data-e2e`
# attributes on the page, which makes them the honest "has the uploader rendered" signal.
SELECT_VIDEO_CONTAINER = "[data-e2e='select_video_container']"  # verified 2026-09-15: matched 1
SELECT_VIDEO_BUTTON = "[data-e2e='select_video_button']"        # verified 2026-09-15: matched 1
# What to wait for before counting anything on the upload page. Without it the read races the
# render: a probe run that waited only on body text found FILE_INPUT missing, and the same
# run found it present once this anchor had appeared.
UPLOAD_PAGE_READY = SELECT_VIDEO_CONTAINER        # verified 2026-09-15

# --- Upload page, ONLY AFTER TikTok has taken the file.
# None of the below is in the DOM on the bare upload page (all counted 0 live on 2026-09-15),
# and making them appear means starting a real upload — so they are guesses, flagged as such,
# and the driver waits for them *after* set_input_files rather than before.
#
# The caption box is a rich-text editor (DraftJS/Lexical), not a <textarea>: it takes clicks
# and typed keys, not fill(). Kept as the broad attribute selector on purpose — it matches a
# DraftJS `.public-DraftEditor-content` and a Lexical `[data-lexical-editor]` alike, where a
# guess at either class name would match neither if TikTok picked the other.
CAPTION_EDITOR = "div[contenteditable='true']"    # UNVERIFIED (post-file only)
CAPTION_MAX = 2200                                # UNVERIFIED (post-file only)
# Text beside the caption box once the form is live. Used in the manual queue-card steps, so
# Stephen knows what he is waiting for; the driver's own wait is on CAPTION_EDITOR, which is
# the element it actually needs rather than a label that may be reworded.
UPLOAD_READY_TEXT = "Caption"                     # UNVERIFIED (post-file only)

# The scheduler, verified live 2026-09-23 in the post-file form (uploading a real video is
# the only way to see any of this, so "post-file only" still applies to every line below even
# where the value itself is no longer a guess).
#
# "When to post" is NOT a switch — the 2026-09-15 guess was wrong. It is two
# `<input type='radio' name='postSchedule'>` with `<label for=…>` text "Now" / "Schedule".
# The first `[role='switch']` on the page is the disabled, aria-hidden "High-quality uploads"
# toggle: clicking it hangs the driver. get_by_role("radio", name=SCHEDULE_RADIO_NAME,
# exact=True) is unambiguous because it is role-scoped — a radio lookup can never resolve to
# the <button> that submits, so (unlike the old switch/text guess) no NOT_INSIDE_A_BUTTON-style
# guard is needed here.
SCHEDULE_RADIO_NAME = "Schedule"                  # verified 2026-09-23: <input type=radio>, labelled
POST_NOW_RADIO_NAME = "Now"                       # verified 2026-09-23: the other radio, checked by default

# Selecting Schedule reveals two READ-ONLY text inputs, both `input.TUXTextInputCore-input`
# with no placeholder, no aria-label and no stable DOM-order guarantee (seen time-then-date
# live, but that is TikTok's layout choice, not a contract) — so SCHEDULE_DATE_INPUT and
# SCHEDULE_TIME_INPUT are deliberately the SAME selector. The driver tells them apart by
# reading each one's current value against DATE_VALUE_RE / TIME_VALUE_RE, never by position.
# Being read-only text inputs, `fill()` cannot set them — see tiktok_web.set_schedule.
SCHEDULE_DATE_INPUT = "input.TUXTextInputCore-input"   # verified 2026-09-23: 2 matched, read-only
SCHEDULE_TIME_INPUT = "input.TUXTextInputCore-input"   # verified 2026-09-23: 2 matched, read-only
DATE_VALUE_RE = r"^\d{4}-\d{2}-\d{2}$"            # verified 2026-09-23: e.g. "2026-09-19"
TIME_VALUE_RE = r"^\d{2}:\d{2}$"                  # verified 2026-09-23: e.g. "19:10", 24-hour
# How the two fields want their values once found — tiktok_web.format_date/_time, unit-tested,
# so a wrong format here is a one-constant fix rather than a code change.
DATE_FORMAT = "%Y-%m-%d"                          # verified 2026-09-23
TIME_FORMAT = "%H:%M"                             # verified 2026-09-23

# Clicking the time input opens two columns of `.tiktok-timepicker-option-text`: hours 00-23
# on the left, minutes on the right in 5-minute steps (00, 05, … 55). The active option adds
# `tiktok-timepicker-is-active`, but the driver does not need that class — it clicks the
# option whose own text equals the target hour/minute. A programmatic `.click()` scrolled an
# option into view but did not select it; a real pointer click did (Playwright's default).
TIME_HOUR_OPTION = ".tiktok-timepicker-option-text.tiktok-timepicker-left"    # verified 2026-09-23
TIME_MINUTE_OPTION = ".tiktok-timepicker-option-text.tiktok-timepicker-right"  # verified 2026-09-23

# Clicking the date input opens a calendar: `.month-title` header (e.g. "September / 2026"),
# `‹`/`›` arrows either side of it, and day cells `.day.valid` (out-of-range / other-month days
# are plain `.day`, with no `valid`, and must never be clicked). CALENDAR_NEXT/CALENDAR_PREV
# are selected by POSITION relative to the title — the arrows carry no stable class or
# accessible name that was found live — so this is a guess about structure, not about copy,
# and stays UNVERIFIED until a real month change has been driven end to end.
CALENDAR_MONTH_TITLE = ".month-title"             # verified 2026-09-23
CALENDAR_DAY = ".day.valid"                       # verified 2026-09-23
CALENDAR_NEXT = "xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' month-title ')]/following-sibling::*[1]"  # UNVERIFIED (position guess)
CALENDAR_PREV = "xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' month-title ')]/preceding-sibling::*[1]"  # UNVERIFIED (position guess)

# Shown under the pickers when the chosen datetime is too soon. The driver asserts this text
# is ABSENT after setting the date and time, before it ever clicks submit.
TOO_SOON_TEXT = "Schedule at least 15 minutes in advance"   # verified 2026-09-23

# The submit button is labelled "Schedule" when the scheduler is on and "Post" when it is off.
# Both are resolved with exact=True: "Post" as a substring also matches the sidebar's "Posts"
# entry, which sorts FIRST in the DOM — `.first` would have clicked the nav, not the form.
# SCHEDULE_RADIO_NAME and SCHEDULE_BUTTON_TEXT are the SAME WORD, "Schedule" — that used to be
# the danger (see the old NOT_INSIDE_A_BUTTON guard, now gone): a text-only click could land on
# either. get_by_role scopes by role first (radio vs button), so the two can never collide.
POST_BUTTON_TEXT = "Post"                         # verified 2026-09-23: exact <button>Post</button>
SCHEDULE_BUTTON_TEXT = "Schedule"                 # verified 2026-09-23: exact <button>Schedule</button>

# First-run account modals ("Turn on automatic content checks?", "New editing features added",
# "Allow your video to be saved for scheduled posting?") were seen once, each with exactly one
# primary button, and dismissed by hand. They should not recur, but dismiss_first_run_dialogs
# tolerates them by clicking a button with one of these exact names — never "Post", never
# "Discard" — before the scheduler is touched.
FIRST_RUN_DIALOG_BUTTONS = ("Allow", "Got it", "Turn on")   # verified 2026-09-23: literal copy

# The XHR whose completion means "TikTok accepted it" (rule 6: wait_for_response, not a sleep).
# The URL change to the content page is the second, independent confirmation, so a drifted
# fragment here costs a retry rather than a wrong answer. Only a real post would show it.
POST_RESPONSE = "/project/post/"                  # UNVERIFIED (only visible on a real submit)

# How far ahead TikTok Studio lets a post be scheduled. Reported through capabilities() and
# enforced before anything is typed, so an over-long schedule fails on our side with a clear
# message instead of inside TikTok's form. The limit lives in the post-file scheduler.
MAX_SCHEDULE_DAYS = 10                            # UNVERIFIED (post-file only)

# --- Content page (the idempotency read).
# The whole list, header block and body block alike. Also the "has the page rendered" anchor:
# it exists whether or not the account has posts, which the rows and the empty state do not.
POSTS_TABLE = "[data-tt='components_PostTable_Container']"   # verified 2026-09-15: matched 3
CONTENT_PAGE_READY = POSTS_TABLE                  # verified 2026-09-15

# One row per post. `components_RowLayout_FlexRow` is the row layout TikTok uses inside the
# posts table; the `:not(:has(...))` is not decoration but the header exclusion — the column
# header ("Posts (Created on) / Privacy / Views / Likes / Comments / Actions") is built from
# exactly the same component and carries text, so without it the header reads as a post row
# and `scheduled_ready_js` would call the list settled before a single real row had arrived.
#
# Half of this is verified and half is not, and the halves matter separately:
#   * the exclusion IS verified — bare `[data-tt='components_RowLayout_FlexRow']` matched 1
#     (the header) and this selector matched 0, live, in both Playwright and a raw
#     document.querySelectorAll (`:has()` is supported by the Chrome the driver drives);
#   * the row shape is NOT — @park.sheet has zero posts, so no real row has ever been seen.
POST_ROW = "[data-tt='components_RowLayout_FlexRow']:not(:has([data-tt^='components_PostTableHeader']))"  # UNVERIFIED (no post exists to render a row)
# Tried only when POST_ROW matches nothing, and deliberately different *in kind* rather than a
# near-copy: if TikTok drops its `data-tt` ids or moves the list back to a real table, the
# semantic row role is what it would land on. It matched 0 live (nothing on the studio uses
# role=row today), and it cannot reach the sidebar — the nav is buttons, never rows.
POST_ROW_FALLBACK = "[role='row']"                # UNVERIFIED (no post exists to render a row)
# At most this many lines of a row are offered to the caption match. A row is a thumbnail, a
# caption, a date, a status and four counters; the caption is not reliably the first line, so
# every line is a candidate (see tiktok_web.row_matches) instead of betting on one index.
POST_ROW_MAX_LINES = 12                           # verified 2026-09-15 (our cap, not TikTok's)
# Substring of the empty-state copy, lowercased. This is what lets "no scheduled posts" be
# told apart from "the list has not rendered yet" — the distinction that decides whether a
# skip is safe. When neither this nor a row appears, the driver times out and queues a card.
SCHEDULED_EMPTY_TEXT = "no posts yet"             # verified 2026-09-15: live empty state reads
#   "No posts yet / Your posted and scheduled videos will appear here. / Upload first video"

# There is no Scheduled tab and no Scheduled filter: one table holds posted and scheduled
# videos together (TikTok's own empty-state copy says so, and `[role=tab]` matched 0 on the
# content page). Kept as a named fact rather than a comment because the driver asserts on it:
# read_scheduled must NOT click anything, and the day a tab reappears this flips to False and
# the tab anchor comes back beside it.
CONTENT_HAS_SCHEDULED_TAB = False                 # verified 2026-09-15: no [role=tab] on the page

# Anchors that only exist once a video has been handed to TikTok, so `--check` reports them as
# "post-file only" instead of MISSING. Selecting a file to see them would start a real upload,
# which is exactly what a read-only canary may not do.
POST_FILE_ONLY = (
    "CAPTION_EDITOR",
    "UPLOAD_READY_TEXT",
    "SCHEDULE_RADIO_NAME",
    "SCHEDULE_DATE_INPUT",
    "SCHEDULE_TIME_INPUT",
    "TIME_HOUR_OPTION",
    "TIME_MINUTE_OPTION",
    "CALENDAR_MONTH_TITLE",
    "CALENDAR_DAY",
    "CALENDAR_NEXT",
    "CALENDAR_PREV",
    "TOO_SOON_TEXT",
    "POST_BUTTON_TEXT",
    "SCHEDULE_BUTTON_TEXT",
)

# Every anchor above that has never been seen live. capabilities() publishes this list and
# `--check` is what shortens it: delete a name here in the same commit that confirms it.
# FILE_INPUT, POSTS_TABLE, SELECT_VIDEO_*, SCHEDULED_EMPTY_TEXT and the URLs left this list on
# 2026-09-15; the whole post-file scheduler (radio, date/time inputs, time picker, calendar day
# cells, the too-soon text, both submit labels) left it 2026-09-23 — a real upload was driven
# end to end. Only the calendar month arrows (guessed by position, never actually clicked to
# change a month) and the anchors that still need a post on the account remain.
UNVERIFIED = (
    "LOGIN_QR_TEXT",
    "CAPTION_EDITOR",
    "CAPTION_MAX",
    "UPLOAD_READY_TEXT",
    "CALENDAR_NEXT",
    "CALENDAR_PREV",
    "POST_RESPONSE",
    "POST_ROW",
    "POST_ROW_FALLBACK",
    "max_schedule_days",
)
