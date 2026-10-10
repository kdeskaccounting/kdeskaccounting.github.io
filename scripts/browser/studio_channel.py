"""Switch the YouTube Studio channel within ONE Google account, and put it back afterwards.

The debug Chrome profile is signed in to two Google accounts. santiagokdesk@gmail.com owns
KDeskAccounting, ParkSheet, Court of Inquiry and KDesk Games; smichels1@gmail.com owns
"Stephen is Acting" and booshigotyou. Studio opens on whichever channel was used last, and
Stephen works in Court of Inquiry by hand in the same profile.

So a driver that needs ParkSheet:

  * stays put when Studio already reads ParkSheet;
  * SWITCHES (avatar -> Switch account -> the channel) when Studio is on another channel of the
    santiagokdesk account — the "Accounts" section of that menu, headed by the account email;
  * REFUSES when the active account is anything else (the channel it would need sits under
    "Other accounts", and switching there is a Google sign-in, possibly a passkey prompt).
    Credentials are never entered;
  * after the run, success or failure, switches BACK to the channel it found (best-effort,
    logged), so Stephen's session is left as it was.

`plan_switch` is the decision and is pure; everything else is the browser half.
Seen live 2026-10-10 (Studio on Court of Inquiry): the Switch account panel is a list of
`ytd-account-section-list-renderer`; the active account's section carries a
`ytd-google-account-header-renderer` whose `#email` reads santiagokdesk@gmail.com, other
accounts' sections a `ytd-account-item-section-header-renderer` with their email, and each
channel is a `ytd-account-item-renderer` with a `#channel-title`.
"""
from __future__ import annotations

import json
import re
import sys

from browser import selectors_youtube as S

STAY, SWITCH, REFUSE = "stay", "switch", "refuse"


class ChannelRefused(RuntimeError):
    """Studio is not on a channel this driver may switch away from. Never worked around."""


def _norm(text) -> str:
    return " ".join(str(text or "").split()).casefold()


def _say(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- the decision

def plan_switch(current: str, target: str, sections, *,
                account_email: str = S.ACCOUNT_EMAIL) -> tuple[str, str]:
    """(STAY | SWITCH | REFUSE, why). Pure: `sections` is what `accounts_js` read.

    `sections` is a list of {"active": bool, "email": str, "channels": [str, ...]}. SWITCH needs
    all of: exactly one active section, its email is `account_email`, and both the channel
    Studio is on now and the target are listed in it. Anything less is a refusal, because the
    only safe switch is one that changes nothing but which of the SAME account's channels the
    header shows.
    """
    if _norm(current) == _norm(target):
        return STAY, f"Studio already reads {target!r}"
    active = [s for s in (sections or []) if s.get("active")]
    if len(active) != 1:
        return REFUSE, (f"Studio reads {current!r}; could not tell which Google account is "
                        f"active from the Switch account menu ({len(active)} active sections)")
    sec = active[0]
    email = _norm(sec.get("email"))
    if email != _norm(account_email):
        return REFUSE, (f"Studio reads {current!r} on the Google account {sec.get('email')!r}, "
                        f"not {account_email!r}. Switching would be a Google sign-in, which "
                        f"this driver never does")
    channels = {_norm(c) for c in sec.get("channels") or []}
    if _norm(target) not in channels:
        return REFUSE, (f"{target!r} is not among the {account_email} channels the menu lists "
                        f"({sorted(sec.get('channels') or [])})")
    if _norm(current) not in channels:
        return REFUSE, (f"Studio reads {current!r}, which is not among the {account_email} "
                        f"channels the menu lists ({sorted(sec.get('channels') or [])})")
    return SWITCH, f"{current!r} and {target!r} are both channels of {account_email}"


# --------------------------------------------------------------------------- the browser half

def accounts_js() -> str:
    """Every section of the open Switch account panel: is it the active account, its email,
    its channel titles."""
    return ("() => Array.from(document.querySelectorAll(" + json.dumps(S.SWITCH_SECTION) + "))"
            ".map(sec => {"
            " const act = sec.querySelector(" + json.dumps(S.ACTIVE_ACCOUNT_EMAIL) + ");"
            " const other = sec.querySelector(" + json.dumps(S.OTHER_ACCOUNT_HEADER) + ");"
            " return {active: !!act,"
            "  email: ((act || other || {}).textContent || '').trim(),"
            "  channels: Array.from(sec.querySelectorAll(" + json.dumps(S.SWITCH_CHANNEL_TITLE)
            + ")).map(e => (e.textContent || '').trim())}; })")


def click_channel(page, name: str) -> bool:
    """Click the ACTIVE account's channel titled exactly `name`; False if it is not there.

    Scoped to the active section on purpose: a channel of the same name under "Other accounts"
    would be a Google sign-in. A real (Playwright) click, as the 2026-10-10 hand switch used.
    """
    items = (page.locator(f"{S.SWITCH_SECTION}:has({S.ACTIVE_ACCOUNT_EMAIL}) "
                          f"{S.SWITCH_CHANNEL_TITLE}")
             .filter(has_text=re.compile(rf"^\s*{re.escape(name.strip())}\s*$", re.I)))
    if not items.count():
        return False
    items.first.click()
    return True


def header_is_js(name: str) -> str:
    return ("() => { const e = document.querySelector(" + json.dumps(S.CHANNEL_NAME_TEXT) + ");"
            " return !!e && e.textContent.trim().toLowerCase() === "
            + json.dumps(name.strip().lower()) + "; }")


def current_channel(page) -> str:
    page.locator(S.CHANNEL_NAME_TEXT).first.wait_for(state="visible",
                                                     timeout=S.ANCHOR_TIMEOUT_MS)
    return (page.locator(S.CHANNEL_NAME_TEXT).first.text_content() or "").strip()


def read_accounts(page) -> list:
    """Open avatar -> Switch account and read the panel. Changes nothing."""
    page.locator(S.AVATAR_BUTTON).first.click()
    page.get_by_text(S.SWITCH_ACCOUNT_TEXT, exact=False).first.click()
    page.locator(S.SWITCH_CHANNEL_TITLE).first.wait_for(state="visible",
                                                        timeout=S.ANCHOR_TIMEOUT_MS)
    sections = page.evaluate(accounts_js())
    return sections if isinstance(sections, list) else []


def close_menu(page) -> None:
    try:
        page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001 — a menu left open is cosmetic
        pass


def switch_to(page, current: str, target: str, *,
              account_email: str = S.ACCOUNT_EMAIL) -> str:
    """Make Studio read `target`, if the decision allows it. Returns STAY or SWITCH.

    `page` must already be on Studio with the header rendered. Raises ChannelRefused rather
    than switching across Google accounts or typing anything into a sign-in page.
    """
    if _norm(current) == _norm(target):
        return STAY
    sections = read_accounts(page)
    decision, why = plan_switch(current, target, sections, account_email=account_email)
    if decision != SWITCH:
        close_menu(page)
        raise ChannelRefused(why)
    if not click_channel(page, target):
        close_menu(page)
        raise ChannelRefused(f"{target!r} is listed under {account_email} but could not be "
                             f"clicked in the Switch account menu")
    try:
        page.wait_for_function(header_is_js(target), timeout=S.NAV_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001 — re-raised as a refusal with the landing url
        if S.SIGN_IN_HOST in (page.url or ""):
            raise ChannelRefused(f"switching to {target!r} landed on a Google sign-in page "
                                 f"({page.url}); no credentials are ever entered") from exc
        raise
    return SWITCH


def restore(page, original: str | None, *, label: str = "youtube") -> bool:
    """Best-effort: put Studio back on `original`. Logs and returns False on any failure.

    `page` should be a fresh tab (the run's own page may be mid-dialog); it is navigated to
    Studio. Never raises: the run's own result matters more than the courtesy.
    """
    if not original:
        return True
    try:
        page.goto(S.STUDIO_URL, wait_until="domcontentloaded", timeout=S.NAV_TIMEOUT_MS)
        now = current_channel(page)
        if _norm(now) == _norm(original):
            _say(f"{label}: Studio already back on {original!r}")
            return True
        switch_to(page, now, original)
        _say(f"{label}: switched Studio back to {original!r}")
        return True
    except Exception as exc:  # noqa: BLE001 — logged, never raised
        _say(f"{label}: COULD NOT switch Studio back to {original!r} "
             f"({type(exc).__name__}: {exc}). Switch by hand: avatar -> Switch account -> "
             f"{original}.")
        return False


def restore_in_new_tab(context, original: str | None, *, label: str = "youtube") -> bool:
    """`restore` in a tab of its own, closed afterwards."""
    if not original:
        return True
    try:
        page = context.new_page()
    except Exception as exc:  # noqa: BLE001
        _say(f"{label}: COULD NOT open a tab to switch Studio back to {original!r} "
             f"({type(exc).__name__}: {exc}). Switch by hand: avatar -> Switch account -> "
             f"{original}.")
        return False
    try:
        return restore(page, original, label=label)
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001
            pass
