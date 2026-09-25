"""Every YouTube Studio UI anchor, in one place (spec Chrome rule 6).

When YouTube moves the uploader, this is the only file that changes.

**Why a Chrome driver at all.** The YouTube Data API is barred for uploads on this account —
an API upload is locked to `private` and stays there — and the Upload-Post free tier is
10 uploads a month, which cannot carry a daily Short plus Instagram. Stephen's 2026-09-25
ruling moved YouTube posting into the daily Chrome session, the same way
`scripts/publishers/tiktok_web.py` drives TikTok Studio.

**Status, 2026-09-25.** Unlike the TikTok file, almost nothing here is a guess. The debug
Chrome is signed in as the **ParkSheet** brand channel, and a real mp4
(`~/parksheet/build/release/2026-W38/day-6.mp4`) was carried through the whole uploader by
hand and then by the driver's own `--dry-run` — upload, title, description, "made for kids",
all three Next steps and the Visibility screen — and every draft that left behind was deleted
again, leaving the channel at its two published Shorts each time. Every anchor below carries
the date it was counted and how.

The one thing deliberately NOT exercised is the final Publish click, because that would put a
video on the channel. The three anchors that only a real publish can confirm are named in
`POST_PUBLISH_ONLY`, so `--check` reports them as "post-publish only" rather than MISSING, and
they are in `UNVERIFIED` until a live run shortens that list.

Four things the 2026-09-25 pass established that a guess would have got wrong:

1. **A ParkSheet Short lands on the *Shorts* tab, not the Videos tab.** `/videos/upload`
   (the tab labelled "Videos") matched **0** rows while `/videos/short` matched the two
   published Shorts and, mid-run, the draft. Reading only one tab is how the idempotency
   check misses a post that is already up — so the driver reads both and unions them.
2. **A draft row carries no link.** The published rows expose `a#video-title` with
   `href="/video/<id>/edit"`; the draft row's href was `null`. So a row is identified by its
   title text, never by a link that may not be there.
3. **`#close-button` is not the dialog's close button.** It resolves first to the content
   list's `ytcp-bulk-actions` close icon, which is invisible — a click on it times out. The
   uploader's own is `#ytcp-uploads-dialog-close-button`.
4. **Closing the uploader saves a draft silently.** There is no "discard?" prompt: the page
   just says "Your video <title> has been saved as draft". A draft is therefore removed from
   the *content list* (row menu → Delete forever → confirm), never from inside the dialog.

Anchors are written as YouTube's own element ids where it has them (`#title-textarea`,
`#next-button`, `#done-button`, `#privacy-radios`) because those are the stable part of a
Polymer app, and as role + accessible name where the copy is what a person reads. A long CSS
chain guessed from memory would be worse than useless: it fails *silently* by matching
nothing.
"""

# --- Identity. The debug Chrome profile also holds Stephen's PERSONAL channel, so "signed in
# to Studio" is not the same question as "signed in as ParkSheet". The driver refuses to
# upload anywhere else, and these two are how it tells.
# Seen live 2026-09-25: https://studio.youtube.com redirected to /channel/<CHANNEL_ID> and
# the header's #entity-name read "ParkSheet".
CHANNEL_ID = "UC7ApR5Ntbc4DRkkZ_FrwyOw"   # verified 2026-09-25: the URL Studio redirects to
CHANNEL_NAME = "ParkSheet"                # verified 2026-09-25: #entity-name text

# --- URLs.
STUDIO_URL = "https://studio.youtube.com"      # verified 2026-09-25: -> /channel/<CHANNEL_ID>


def channel_url(path: str = "", channel_id: str = CHANNEL_ID) -> str:
    """`https://studio.youtube.com/channel/<id>/<path>` — built, never retyped."""
    tail = f"/{path.lstrip('/')}" if path else ""
    return f"{STUDIO_URL}/channel/{channel_id}{tail}"


# The content list, one URL per tab. `videos/short` is where ParkSheet's Shorts live and
# `videos/upload` is the tab labelled "Videos" — a draft has been seen on `short`, but which
# tab YouTube files an upload under is its classification decision, not ours, so the driver
# reads BOTH (see CONTENT_TABS) and unions the rows.
CONTENT_SHORTS_URL = channel_url("videos/short")   # verified 2026-09-25: 2 published + 1 draft
CONTENT_VIDEOS_URL = channel_url("videos/upload")  # verified 2026-09-25: 0 rows, empty state
CONTENT_TABS = (CONTENT_SHORTS_URL, CONTENT_VIDEOS_URL)
#: The tab a human is sent to in a queue card, and the URL a result falls back to.
CONTENT_URL = CONTENT_SHORTS_URL

# The uploader. `?d=ud` is the deep link to the dialog that "Create → Upload videos" opens —
# same destination, no menu to chase. Opening it selects no file, so it creates NOTHING: the
# content list was unchanged after `--check`-style visits on 2026-09-25.
UPLOAD_DIALOG_URL = channel_url("videos/upload?d=ud")  # verified 2026-09-25: dialog, file input
#: The Create → Upload videos path, kept as the fallback for the day the deep link stops
#: opening the dialog on its own.
CREATE_BUTTON_NAME = "Create"            # verified 2026-09-25: aria-label="Create" in the header
UPLOAD_MENU_ITEM_TEXT = "Upload videos"  # verified 2026-09-25: #upload-button on the content page

# Hosts Studio may legitimately be on and still be the logged-in studio. An explicit
# allow-list, never a suffix match: `studio.youtube.com.evil.example` must stay unexpected.
# Empty on purpose — every signed-in Studio URL seen on 2026-09-25 stayed on studio.youtube.com.
ALT_HOSTS: tuple[str, ...] = ()
# The path fragment that means "this profile is signed out". session.classify tests it with
# `in url.path`. Signed out, Studio bounces to accounts.google.com, which the HOST check
# catches first — this is the belt to that pair of braces.
LOGIN_MARKER = "/signin"

# --- Identity anchors on the Studio shell.
CHANNEL_NAME_TEXT = "#entity-name"       # verified 2026-09-25: matched 1, text "ParkSheet"
AVATAR_BUTTON = "#avatar-btn"            # verified 2026-09-25: matched 1, aria-label "Account"
#: What to wait for before reading the channel name, so the probe does not race the render.
STUDIO_PAGE_READY = CHANNEL_NAME_TEXT    # verified 2026-09-25

# --- Content list (the idempotency read).
# verified 2026-09-25: matched 2 (the published Shorts), then 3 once a draft existed.
VIDEO_ROW = "ytcp-video-row"
# The row's title. Read live at its FULL length — an 86-character title came back whole, not
# truncated — which is what makes an equality test on the title a safe idempotency key.
ROW_TITLE = "#video-title"               # verified 2026-09-25: matched 1 per row, full text
# Only a PUBLISHED row has this; a draft row's was null (see the module docstring).
ROW_LINK = "a#video-title, a[href*='/video/']"   # verified 2026-09-25: "/video/<id>/edit"
# The visibility cell. `div.cell-body.tablecell-visibility`, read as "Public" / "Draft".
ROW_VISIBILITY = ".tablecell-visibility"  # verified 2026-09-25: "Public" x2, "Draft" on the draft
# The column header of the content table. This is the "has the page arrived" anchor, and it is
# deliberately NOT the row selector: the row selector matches nothing on an empty tab, so
# waiting on it would report an empty tab as a page that never loaded. Counted 1 on BOTH tabs,
# the empty one and the one with rows.
CONTENT_PAGE_READY = "#date-header-name"  # verified 2026-09-25: matched 1 on both tabs
#: Substring of the empty-tab copy, lowercased — this is what tells "this tab has no videos"
#: apart from "the list has not rendered yet", the distinction that decides whether it is safe
#: to upload. The Videos tab showed exactly this while the Shorts tab held three rows.
CONTENT_EMPTY_TEXT = "no content available"   # verified 2026-09-25: Videos tab empty state
#: What the visibility cell reads once a video is live, and while it is only a draft.
PUBLIC_VISIBILITY_TEXT = "Public"        # verified 2026-09-25
DRAFT_VISIBILITY_TEXT = "Draft"          # verified 2026-09-25
# A freshly closed upload reads "Pending" for a while BEFORE it settles to "Draft" — caught
# live at 11:52 on 2026-09-25, when the driver's own dry run read "Pending" and (correctly,
# under the old rule) refused to delete the row; a re-read two minutes later said "Draft".
# Both words mean the same thing to this driver: not published, safe to remove. What actually
# authorises the delete is DELETE_DRAFT_CONFIRM_TEXT, which is YouTube's own statement.
DRAFT_PENDING_TEXT = "Pending"           # verified 2026-09-25: transitional, seen live
DRAFT_VISIBILITY_TEXTS = (DRAFT_VISIBILITY_TEXT, DRAFT_PENDING_TEXT)
#: At most this many lines of a row are offered to the title match.
ROW_MAX_LINES = 12                       # our cap, not YouTube's

# --- The uploader, BEFORE a file is chosen. Everything `--check` can honestly see.
UPLOAD_DIALOG = "ytcp-uploads-dialog"    # verified 2026-09-25: matched 1 on ?d=ud
# A plain <input type=file>, which is what makes Playwright's set_input_files work without
# touching the OS file dialog. It is hidden and fed by the "Select files" button, so it must
# never be waited on with state="visible" — set_input_files does not need visibility.
FILE_INPUT = "input[type=file]"          # verified 2026-09-25: matched 1 inside the dialog
SELECT_FILES_BUTTON = "#select-files-button"   # verified 2026-09-25: matched 1
#: What to wait for before counting anything in the dialog.
UPLOAD_PAGE_READY = UPLOAD_DIALOG        # verified 2026-09-25
# The uploader's OWN close icon. NOT `#close-button`: that id resolves first to the content
# list's invisible ytcp-bulk-actions icon and a click on it times out (seen 2026-09-25).
DIALOG_CLOSE_BUTTON = "#ytcp-uploads-dialog-close-button"   # verified 2026-09-25: matched 1

# --- The uploader, ONLY AFTER a file has been handed over.
# Both boxes are contenteditables, not <textarea>, so fill() cannot set them: the driver
# clicks, selects all, deletes, and inserts. `insert_text` (not `type`) is what reproduces a
# 681-character description with its newlines exactly — verified by reading both back.
TITLE_BOX = "#title-textarea #textbox"           # verified 2026-09-25: matched 1
DESCRIPTION_BOX = "#description-textarea #textbox"   # verified 2026-09-25: matched 1
#: YouTube pre-fills the title from the file name ("day 6"), so the box is always cleared first.
TITLE_MAX = 100          # YouTube's own limit; the driver refuses a longer title, never trims
DESCRIPTION_MAX = 5000   # YouTube's own limit

# "Is this video made for kids? (required)". Until it is answered the form shows "You need to
# answer this question" and Next does not advance — a 2026-09-25 run clicked Next three times
# and stayed on Details because of exactly this. Resolved by ROLE + accessible name: there are
# four tp-yt-paper-radio-button on the Details step (the kids pair and the age-restriction
# pair) and only the name tells them apart.
KIDS_RADIO = "tp-yt-paper-radio-button"          # verified 2026-09-25: matched 4 on Details
KIDS_NO_NAME = "No, it's not made for kids"      # verified 2026-09-25: role=radio matched 1
KIDS_YES_NAME = "Yes, it's made for kids"        # verified 2026-09-25: the one never clicked
#: Shown while the question is unanswered. The driver asserts it is gone before Next.
KIDS_UNANSWERED_TEXT = "You need to answer this question"   # verified 2026-09-25

# The wizard. Four steps, each with a clickable badge whose aria-selected says which is live.
# Waiting on that attribute is the condition wait that replaces "click Next and hope".
NEXT_BUTTON = "#next-button"             # verified 2026-09-25: matched 1, advanced the stepper
BACK_BUTTON = "#back-button"             # verified 2026-09-25: matched 1 on Visibility
#: The submit button. It is the SAME element on every step: it reads "Save" on the Visibility
#: step before a choice is made, and it is what publishes. Never resolved by its text.
DONE_BUTTON = "#done-button"             # verified 2026-09-25: matched 1, text "Save"
STEP_BADGE = "button#step-badge-{n}"     # verified 2026-09-25: 0..3
STEP_NAMES = ("Details", "Video elements", "Initial check", "Visibility")  # verified 2026-09-25
#: Index of each step, so the driver names them rather than counting Next clicks.
STEP_DETAILS, STEP_ELEMENTS, STEP_CHECKS, STEP_VISIBILITY = 0, 1, 2, 3


def step_selected(n: int) -> str:
    """The badge for step `n`, only while it is the live step."""
    return STEP_BADGE.format(n=n) + "[aria-selected='true']"


# The Visibility step.
PRIVACY_RADIOS = "#privacy-radios tp-yt-paper-radio-button"   # verified 2026-09-25: matched 3
#: Resolved by the radio's own `name` attribute — PRIVATE / UNLISTED / PUBLIC — never by the
#: word "Public", which also appears in the row of explanatory copy beside it.
PUBLIC_RADIO = "tp-yt-paper-radio-button[name='PUBLIC']"      # verified 2026-09-25: matched 1
PRIVATE_RADIO = "tp-yt-paper-radio-button[name='PRIVATE']"    # verified 2026-09-25: matched 1
#: YouTube's one-time "Remember that anyone can see what you write / post" notice. It is the
#: same modal that swallows a new channel's first comment (scripts/browser/youtube_pin_comment.py
#: answers it there), and the same backdrop is what makes a plain radio click get intercepted —
#: hence the force-click fallback in the driver.
GOT_IT_BUTTON_TEXT = "Got it"            # verified 2026-09-23 on the comment composer
#: The whole uploader's text carries the video's own link from the moment the upload lands
#: ("Video link https://youtube.com/shorts/<id>"), which is where the driver reads the id from —
#: markup-independent, and available before AND after the Publish click.
VIDEO_LINK_RE = (r"https?://(?:www\.)?youtu(?:be\.com/(?:shorts/|watch\?v=)|\.be/)"
                 r"([A-Za-z0-9_-]{11})")   # verified 2026-09-25: matched "Oxo41KgeVoA"
#: Where a published Short lives. Built from the id the regex above yields.
WATCH_URL = "https://www.youtube.com/shorts/{video_id}"

# --- Deleting a draft (the whole of --dry-run's clean-up, and nothing else ever calls it).
# Closing the uploader saves a draft with no prompt, so the draft is removed from the content
# list: hover the row, open its Options menu, Delete forever, tick the acknowledgement, confirm.
DRAFT_SAVED_TEXT = "has been saved as draft"     # verified 2026-09-25: the toast after closing
ROW_OPTIONS_BUTTON_NAME = "Options"              # verified 2026-09-25: aria-label on the row
DELETE_MENU_ITEM = "tp-yt-paper-item"            # verified 2026-09-25: text-item-0..4
DELETE_MENU_ITEM_TEXT = "Delete forever"         # verified 2026-09-25: text-item-4
DELETE_CONFIRM_CHECKBOX = "#confirm-checkbox"    # verified 2026-09-25: matched 1
DELETE_CONFIRM_BUTTON = "#confirm-button"        # verified 2026-09-25: text "Delete draft video"
DELETE_CANCEL_BUTTON = "#cancel-button"          # verified 2026-09-25: matched 1
#: What the confirm button reads for a DRAFT. Asserted before it is clicked, so the driver can
#: never confirm a dialog that is offering to delete a published video instead.
DELETE_DRAFT_CONFIRM_TEXT = "Delete draft video"  # verified 2026-09-25

# --- Timing envelope. Condition waits only (Chrome rule 6); these are ceilings, not sleeps.
NAV_TIMEOUT_MS = 60_000
ANCHOR_TIMEOUT_MS = 30_000
LIST_TIMEOUT_MS = 45_000
#: An mp4 upload plus YouTube's ingest, not an API ping.
UPLOAD_TIMEOUT_MS = 600_000
#: How long the copyright / "Initial check" step gets before Next is expected to be usable.
CHECKS_TIMEOUT_MS = 300_000
#: How long an optional notice ("Got it") gets to appear before the driver decides it will not.
NOTICE_TIMEOUT_MS = 8_000
#: How long the details form gets to become click-stable before the driver falls back to
#: keyboard focus. Short on purpose: on a page that re-renders while YouTube processes the
#: upload the fallback IS the normal path, and a long wait here only delays the post.
BOX_CLICK_TIMEOUT_MS = 10_000

# Anchors that only exist once a video has been handed to YouTube, so `--check` reports them as
# "post-file only" instead of MISSING. Selecting a file to see them would start a real upload,
# which is exactly what a read-only canary may not do.
POST_FILE_ONLY = (
    "TITLE_BOX",
    "DESCRIPTION_BOX",
    "KIDS_RADIO",
    "KIDS_NO_NAME",
    "NEXT_BUTTON",
    "DONE_BUTTON",
    "STEP_BADGE",
    "PRIVACY_RADIOS",
    "PUBLIC_RADIO",
    "ROW_OPTIONS_BUTTON_NAME",
    "DELETE_MENU_ITEM_TEXT",
    "DELETE_CONFIRM_CHECKBOX",
    "DELETE_CONFIRM_BUTTON",
)

# Anchors that can only be seen by actually publishing a video to the channel. A dry run
# reaches the Visibility step and stops, so these three are the honest remainder.
POST_PUBLISH_ONLY = (
    "GOT_IT_BUTTON_TEXT",
    "WATCH_URL",
    "PUBLIC_VISIBILITY_TEXT",
)

# Every anchor above that has never been confirmed live. `--check` and a dry run are what
# shorten this list: delete a name here in the same commit that confirms it. Everything else
# in this file was counted on the live Studio on 2026-09-25, including the whole post-file
# form and the draft-deletion path.
UNVERIFIED = (
    "ALT_HOSTS",            # nothing has ever redirected off studio.youtube.com
    "LOGIN_MARKER",         # only visible signed out, which is the state we avoid
    "CREATE_BUTTON_NAME",   # the deep link is the path taken; this is the fallback
    "UPLOAD_MENU_ITEM_TEXT",
    "GOT_IT_BUTTON_TEXT",   # the visibility notice was never triggered (no Publish click)
    "WATCH_URL",            # nothing has been published through this driver yet
    "DESCRIPTION_MAX",      # YouTube's documented limit, not one we have hit
)
