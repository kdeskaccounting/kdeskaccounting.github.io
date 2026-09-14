"""Every Gumroad UI anchor, in one place (spec Chrome rule 6).

When Gumroad changes its editor, this is the only file that changes. Prefer role/label
locators; the XPath below exists because Gumroad's cover and thumbnail panels have no
stable role or test id.
"""

EDITOR_URL = "https://app.gumroad.com/products/{slug}/edit"
WORKFLOWS_URL = "https://app.gumroad.com/workflows"
WORKFLOW_NEW_URL = "https://app.gumroad.com/workflows/new"
WORKFLOW_EDIT_URL = "https://app.gumroad.com/workflows/{wf}/edit"
WORKFLOW_EMAILS_URL = "https://app.gumroad.com/workflows/{wf}/emails"

# Section containing a heading/legend/label with the given text.
SECTION = ("xpath=//*[self::h2 or self::h3 or self::legend or self::label]"
           "[normalize-space(.)='{heading}']/ancestor::*[self::section or self::fieldset][1]")
COVER_HEADING = "Cover"
THUMBNAIL_HEADING = "Thumbnail"

COVER_TABLIST = "[role=tablist][aria-label='Product covers']"
COVER_TABS = f"{COVER_TABLIST} [role=tab]"
ADD_COVER_BUTTON = "button[aria-label='Add cover']"
UPLOAD_BUTTON_TEXT = "Upload images or videos"
THUMBNAIL_REMOVE_BUTTON = "button[aria-label='Remove']"
FILE_INPUT = "input[type=file]"
SAVE_BUTTON = "Save changes"
ALERTS = "[role=alert],[role=status]"

WORKFLOW_LINKS = 'a[href*="/workflows/"][href$="/edit"]'
# The container whose innerText carries a workflow's name. Gumroad renders one <table> per
# workflow with the name in its <caption>; the edit anchor sits in a text-less <div>, and
# Element.closest() returns the NEAREST ancestor matching any listed selector - so a bare
# 'div' or 'li' here silently yields '' and the driver stops recognising its own workflows.
WORKFLOW_ROW_CONTAINER = "table,tr,section"
WORKFLOW_NAME_INPUT = "#name"
WORKFLOW_BOUGHT_INPUT = "#bought"
WORKFLOW_SUBJECT_INPUT = "input[placeholder='Subject']"
WORKFLOW_DELAY_INPUT = "input[placeholder='0']"
WORKFLOW_BODY_EDITOR = "[contenteditable=true]"
WORKFLOW_BLOCK_FOR_SUBJECT = "xpath=ancestor::*[.//input[@placeholder='0']][1]"

# The response whose completion means "Gumroad persisted it" (spec Chrome rule 6:
# wait_for_response instead of a sleep).
SAVE_RESPONSE_FRAGMENTS = ("/products/", "/workflows/")
