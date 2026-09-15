# KDesk Automation Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the KDesk-site half of Phase 1 — a reusable browser layer, a ledger writer, a pluggable publisher stack on Upload-Post, a guard that stops the dead YouTube Data-API uploads plus a re-upload driver for the 20 locked videos, a `card` scene kind for Shorts, a Google-Sheet CRM sync, the re-engagement sender, the daily digest, and the two GitHub Actions workflows that schedule them.

**Architecture:** Every deliverable is a small Python module under `scripts/` whose *pure* half (string building, diffing, response parsing, record scanning) is importable with the standard library alone and is unit-tested, and whose *impure* half (HTTP, Playwright, `gws`, subprocess) sits behind one injectable seam that tests monkeypatch. Nothing in `tests/` opens a socket or drives a browser. Every script takes `--dry-run`; every live side effect appends one line to `decisions/decisions.jsonl`; every publisher failure produces a paste-ready queue card under `marketing/publish-queue/` instead of a silent error.

**Tech Stack:** Python 3.11+ (the test interpreter is 3.12.13 via `uv`), pytest (`uv run --with pytest pytest tests/`), Playwright over CDP against the debug Chrome on `:9222`, the Upload-Post REST API, the `gws` Google Workspace CLI (authed as `santiagokdesk@gmail.com`), the Gumroad v2 and MailerLite v1 REST APIs, Hugo, GitHub Actions.

**Spec:** `/Users/stephenmichels/.claude/plans/i-just-airdropped-a-ticklish-toucan.md` — read it alongside this plan. The sections this plan implements are "Chrome automation: how it stays repeatable" (rules 1–8), Track 2 rows 3–5, Track 3 (CRM + re-engagement), Track 4 (Actions + digest), and the "Critical finding: the API-uploaded YouTube videos are dead" action.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.11+**, readable, explicit types, modular, local-first, intentional error handling.
- **No secrets in the repo.** Tokens are read from `~/kdeskaccountingtemplates/.env` (`GUMROAD_ACCESS_TOKEN`), `~/kdesk-analytics/mailerlite-token.txt`, `~/kdesk-analytics/google-token.json`, `~/kdesk-analytics/bing-api-key.txt`, or environment variables (`UPLOAD_POST_KEY`). Never commit one, never print one.
- **Every script has `--dry-run`** that performs zero writes — no network write, no file write outside `/tmp`, no ledger append — and prints exactly what it would have done.
- **No network writes in tests.** Tests mock HTTP/browser/`gws` at a module-level seam. A test that would open a socket is a failed test.
- **Ledger entry on every live side effect.** `scripts/ledger.py` appends to `decisions/decisions.jsonl`; the schema is fixed (see Task 1).
- **T3 hard gates — never bypass:** CPA-license claims (Stephen's WA license is inactive); tax/legal advice in content; refunds; IRS/FASB correspondence; claims about CAE before CAE ships; strategic pivots. No generated copy in this plan may assert any of them.
- **"Queues, not silent failures."** Any publisher failure, any missing login, any missing merge field produces a paste-ready card under `marketing/publish-queue/<platform>/` (or `manual/`) with the exact remaining manual step, and a non-zero exit.
- **The test command is exactly `uv run --with pytest pytest tests/`.** That environment has **pytest and the standard library only** — no `requests`, no `yaml`, no `playwright`, no `openpyxl`, no `google-*`. Therefore **every module a test imports must import cleanly with stdlib only**: put `import requests`, `import yaml`, `from playwright... import ...`, `import openpyxl` *inside* the functions that need them, exactly as `scripts/video/youtube_publish.py` already does for the Google libraries.
- `tests/conftest.py` already puts `<repo>/scripts` and `<repo>/scripts/video` on `sys.path`. New packages under `scripts/` are therefore imported as top-level packages: `import ledger`, `from browser import session`, `from publishers import base`, `from sales import crm_sync`.
- **Commit messages end with these two lines, verbatim:**

  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh
  ```

- Run the whole suite (`uv run --with pytest pytest tests/ -q`) before every commit. The baseline at the start of this plan is **18 passing tests**; it must never go down.

---

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `scripts/ledger.py` | Read/append `decisions/decisions.jsonl`; schema, id allocation, veto-window lookup | 1 |
| `scripts/browser/__init__.py` | Package marker | 2 |
| `scripts/browser/ensure_chrome.py` | Probe `:9222`, launch the debug Chrome, wait for the probe | 2 |
| `scripts/browser/session.py` | `connect_over_cdp`, per-site login check, tracing, queue-card writer, `--check` CLI | 2 |
| `scripts/browser/selectors_gumroad.py` | Every Gumroad CSS/XPath/role anchor, in one file | 2 |
| `scripts/browser/selectors_mailerlite.py` | Every MailerLite anchor, in one file | 2 |
| `scripts/video/gumroad_covers_ui.py` | *(modify)* use `session.py`, condition waits, `--check` | 2 |
| `scripts/video/gumroad_workflows_ui.py` | *(modify)* use `session.py`, condition waits, `--check` | 2 |
| `scripts/publishers/__init__.py` | Package marker | 3 |
| `scripts/publishers/base.py` | `PublishResult`, abstract `Publisher`, `queue()` card writer | 3 |
| `scripts/publishers/upload_post.py` | Upload-Post REST client + form builder + response parser | 3 |
| `scripts/publishers/youtube.py` / `tiktok.py` / `instagram.py` | Thin per-platform wrappers | 3 |
| `scripts/publishers/site.py` | Hugo post under `content/shorts/<date>-<slug>.md` | 3 |
| `scripts/publishers/publish.py` | CLI entry point | 3 |
| `scripts/video/youtube_publish.py` | *(modify)* refuse to upload without `--i-understand-locked-private` | 4 |
| `scripts/video/reupload_locked.py` | Scan the 20 `"via": "data-api"` records, re-publish via `publishers/youtube.py` | 4 |
| `scripts/video/cards.py` | Pure 9:16 card HTML for `ranked_list` / `countdown` / `changed` | 5 |
| `scripts/video/render_sheets.py` | *(modify)* `render_card_scene()` wrapper around `cards.card_html` + `screenshot` | 5 |
| `scripts/video/build_video.py` | *(modify)* dispatch `kind: card`; skip the workbook when no scene needs it | 5 |
| `scripts/video/make_short.py` | *(modify)* render a `card` scene full-bleed instead of banding it | 5 |
| `scripts/pull_gumroad_snapshot.py` | *(modify)* extract `is_business()`, make the module stdlib-importable | 6 |
| `scripts/sales/__init__.py` | Package marker | 6 |
| `scripts/sales/crm_sync.py` | Build/upsert the private "KDesk CRM" sheet via `gws` | 6 |
| `scripts/sales/send_reengage.py` | Parse + send the 14-recipient re-engagement email via `gws gmail` | 7 |
| `scripts/digest.py` | Compose (and optionally send / append to the vault) the daily digest | 8 |
| `.github/workflows/data-weekly.yml` | Mondays 08:15 PT: four snapshot pulls + CRM sync, commit results | 9 |
| `.github/workflows/daily-publish.yml` | Daily 07:00 PT: fetch the day's asset, publish each platform, digest | 9 |
| `tests/test_ledger.py` … `tests/test_workflows_yaml.py` | One test module per task | 1–9 |

**Task order is by dependency**, which differs from the order in the brief: the ledger comes first because Task 2's queue-card path and every later script append to it.

---

### Task 1: Ledger writer (`scripts/ledger.py`)

**Files:**
- Create: `scripts/ledger.py`
- Create: `tests/test_ledger.py`
- Read-only reference: `decisions/decisions.jsonl` (68 entries, ids 1–68)

**Interfaces:**
- Consumes: nothing.
- Produces — every later task imports these:
  - `ledger.DEFAULT_PATH: pathlib.Path` — `<repo>/decisions/decisions.jsonl`
  - `ledger.entries(path: Path | None = None) -> list[dict]`
  - `ledger.last_id(path: Path | None = None) -> int`
  - `ledger.find(entry_id: int, path: Path | None = None) -> dict | None`
  - `ledger.veto_close(entry_id: int, path: Path | None = None) -> str | None`
  - `ledger.append(action: str, tier: int, status: str, reasoning: str, files: list[str], veto_window_close: str | None = None, *, path: Path | None = None, now: datetime | None = None) -> dict` — returns the written entry (including its new `id`).

**Schema facts verified from the live file** (do not invent fields): keys are exactly `id` (int), `ts` (str, e.g. `"2026-09-11T09:45:00-0700"`), `tier` (int 0–3), `status` (str: `executed` / `in_progress` / `planned`), `action` (str), `reasoning` (str), `files` (list of str — **but entries 59–63 store a Python-repr *string* instead, so the reader must tolerate both**), `veto_window_close` (str or null), `stephen_reviewed` (bool). New entries always write `files` as a real list and `stephen_reviewed: false`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ledger.py`:

```python
"""scripts/ledger.py — the append-only decision log every autonomous action writes to."""
import datetime as dt
import json

import ledger


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_entries_tolerates_the_repr_string_files_field_used_by_entries_59_to_63(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [
        {"id": 1, "ts": "2026-09-06T09:30:00-0700", "tier": 2, "status": "in_progress",
         "action": "a", "reasoning": "r", "files": "['marketing/outreach/targets.md', 'CLAUDE.md']",
         "veto_window_close": None, "stephen_reviewed": True},
        {"id": 2, "ts": "2026-09-11T09:45:00-0700", "tier": 1, "status": "executed",
         "action": "b", "reasoning": "r", "files": ["CLAUDE.md"],
         "veto_window_close": None, "stephen_reviewed": True},
    ])
    rows = ledger.entries(p)
    assert rows[0]["files"] == ["marketing/outreach/targets.md", "CLAUDE.md"]
    assert rows[1]["files"] == ["CLAUDE.md"]


def test_entries_skips_blank_lines_and_last_id_reads_the_maximum(tmp_path):
    p = tmp_path / "decisions.jsonl"
    p.write_text(json.dumps({"id": 7, "ts": "t", "tier": 0, "status": "executed", "action": "a",
                             "reasoning": "r", "files": [], "veto_window_close": None,
                             "stephen_reviewed": False}) + "\n\n")
    assert len(ledger.entries(p)) == 1
    assert ledger.last_id(p) == 7


def test_last_id_of_a_missing_file_is_zero(tmp_path):
    assert ledger.last_id(tmp_path / "nope.jsonl") == 0


def test_append_allocates_the_next_id_and_writes_one_line_with_the_exact_schema(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 68, "ts": "t", "tier": 1, "status": "executed", "action": "a",
                "reasoning": "r", "files": [], "veto_window_close": None, "stephen_reviewed": True}])
    now = dt.datetime(2026, 9, 14, 8, 30, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
    written = ledger.append("Published a Short", 1, "executed", "Because.",
                            ["marketing/video/asc842/shorts.json"], path=p, now=now)
    assert written["id"] == 69
    assert written["ts"] == "2026-09-14T08:30:00-0700"
    lines = p.read_text().splitlines()
    assert len(lines) == 2
    saved = json.loads(lines[1])
    assert saved == {"id": 69, "ts": "2026-09-14T08:30:00-0700", "tier": 1, "status": "executed",
                     "action": "Published a Short", "reasoning": "Because.",
                     "files": ["marketing/video/asc842/shorts.json"],
                     "veto_window_close": None, "stephen_reviewed": False}


def test_append_creates_the_file_and_its_parent_when_missing(tmp_path):
    p = tmp_path / "decisions" / "decisions.jsonl"
    written = ledger.append("First", 0, "executed", "r", [], path=p)
    assert written["id"] == 1
    assert json.loads(p.read_text().splitlines()[0])["action"] == "First"


def test_append_rejects_an_out_of_range_tier(tmp_path):
    p = tmp_path / "decisions.jsonl"
    try:
        ledger.append("x", 4, "executed", "r", [], path=p)
    except ValueError as e:
        assert "tier" in str(e)
    else:
        raise AssertionError("tier 4 must be rejected")
    assert not p.exists()


def test_find_and_veto_close_read_a_specific_entry(tmp_path):
    p = tmp_path / "decisions.jsonl"
    _write(p, [{"id": 69, "ts": "t", "tier": 2, "status": "in_progress", "action": "T1 loosening",
                "reasoning": "r", "files": [], "veto_window_close": "2026-09-16T09:00:00-0700",
                "stephen_reviewed": False}])
    assert ledger.find(69, p)["action"] == "T1 loosening"
    assert ledger.find(70, p) is None
    assert ledger.veto_close(69, p) == "2026-09-16T09:00:00-0700"
    assert ledger.veto_close(70, p) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_ledger.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ledger'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/ledger.py`:

```python
#!/usr/bin/env python3
"""Append-only decision ledger for KDesk autonomous actions.

Every live side effect in this repo writes exactly one line to decisions/decisions.jsonl.
Schema (fixed, matching entries 1-68): id, ts, tier, status, action, reasoning, files,
veto_window_close, stephen_reviewed.

  python3 scripts/ledger.py --tail 5
Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_PATH = REPO / "decisions" / "decisions.jsonl"
TIERS = (0, 1, 2, 3)
STATUSES = ("executed", "in_progress", "planned", "vetoed")


def _path(path: pathlib.Path | None) -> pathlib.Path:
    return pathlib.Path(path) if path is not None else DEFAULT_PATH


def _norm_files(value: object) -> list[str]:
    """`files` is a list on most rows but a Python-repr string on entries 59-63."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return [value]
        if isinstance(parsed, (list, tuple)):
            return [str(v) for v in parsed]
        return [str(parsed)]
    return []


def entries(path: pathlib.Path | None = None) -> list[dict]:
    p = _path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["files"] = _norm_files(row.get("files"))
        rows.append(row)
    return rows


def last_id(path: pathlib.Path | None = None) -> int:
    return max((int(r.get("id", 0)) for r in entries(path)), default=0)


def find(entry_id: int, path: pathlib.Path | None = None) -> dict | None:
    return next((r for r in entries(path) if int(r.get("id", 0)) == entry_id), None)


def veto_close(entry_id: int, path: pathlib.Path | None = None) -> str | None:
    row = find(entry_id, path)
    return row.get("veto_window_close") if row else None


def append(action: str, tier: int, status: str, reasoning: str, files: list[str],
           veto_window_close: str | None = None, *, path: pathlib.Path | None = None,
           now: dt.datetime | None = None) -> dict:
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}, got {tier!r}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    if not action.strip():
        raise ValueError("action must not be empty")
    p = _path(path)
    stamp = (now or dt.datetime.now().astimezone()).strftime("%Y-%m-%dT%H:%M:%S%z")
    row = {"id": last_id(p) + 1, "ts": stamp, "tier": int(tier), "status": status,
           "action": action, "reasoning": reasoning, "files": [str(f) for f in files],
           "veto_window_close": veto_window_close, "stephen_reviewed": False}
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="Read the KDesk decision ledger.")
    ap.add_argument("--tail", type=int, default=10)
    a = ap.parse_args()
    for row in entries()[-a.tail:]:
        print(f"{row['id']:>3} T{row['tier']} {row['status']:>11} {row['action'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_ledger.py -q`
Expected: PASS, 7 tests.

- [ ] **Step 5: Verify it reads the real ledger without mutating it**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && python3 scripts/ledger.py --tail 3 && git status --porcelain decisions/`
Expected: three lines ending with `68 T1     executed Added Bing to the measurement stack...`, and `git status` prints nothing (the reader does not write).

- [ ] **Step 6: Run the full suite**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 25 passed (18 baseline + 7 new).

- [ ] **Step 7: Commit**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): add scripts/ledger.py append-only decision log writer

Reads and appends decisions/decisions.jsonl with the existing nine-key schema,
tolerating the Python-repr 'files' strings on entries 59-63. Every later
automation script logs its live side effects through ledger.append().

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 2: `scripts/browser/` — Chrome lifecycle, session preflight, selectors, and the two driver refactors

**Files:**
- Create: `scripts/browser/__init__.py`, `scripts/browser/ensure_chrome.py`, `scripts/browser/session.py`, `scripts/browser/selectors_gumroad.py`, `scripts/browser/selectors_mailerlite.py`
- Create: `tests/test_browser_ensure_chrome.py`, `tests/test_browser_session.py`
- Modify: `scripts/video/gumroad_covers_ui.py` (whole file), `scripts/video/gumroad_workflows_ui.py` (whole file)
- Modify: `.gitignore` (add `scripts/browser/runs/` and `marketing/publish-queue/**/*.mp4`)

**Interfaces:**
- Consumes: `ledger.append(...)` from Task 1.
- Produces:
  - `ensure_chrome.CDP_URL: str` = `"http://localhost:9222"`, `ensure_chrome.PROFILE_DIR: pathlib.Path` = `~/.kdesk/chrome-debug`
  - `ensure_chrome.chrome_argv(profile: Path, port: int) -> list[str]`
  - `ensure_chrome.probe(port: int = 9222, timeout: float = 2.0) -> dict | None` — GETs `/json/version`
  - `ensure_chrome.ensure(port=9222, *, probe_fn=None, launch_fn=None, sleep_fn=None, tries=30) -> dict` — raises `RuntimeError` if Chrome never comes up
  - `session.SiteStatus` dataclass: `site: str`, `ok: bool`, `requested_url: str`, `final_url: str`, `detail: str`
  - `session.SITES: dict[str, Site]` with `Site(name, dashboard_url, login_marker, anchor_description)`
  - `session.classify(site: str, requested_url: str, final_url: str) -> SiteStatus`
  - `session.queue_card_markdown(kind: str, title: str, why: str, steps: list[str], now: datetime) -> str`
  - `session.write_queue_card(repo: Path, subdir: str, slug: str, body: str, now: datetime) -> Path`
  - `session.trace_dir(repo: Path, name: str, now: datetime) -> Path`
  - `session.open_page(name: str)` — context manager yielding a Playwright `Page` with tracing on (impure; never imported at test time via a stdlib-only path because the Playwright import is inside the function)
  - `session.check(site: str, *, page=None) -> SiteStatus`
- Later tasks reuse `session.queue_card_markdown` / `write_queue_card` for publisher queue cards.

**Design rules being implemented** (spec "Chrome automation" rules 2, 3, 6, 7, 8): scripts own the browser lifecycle; preflight per site and fail closed with a queue card; condition waits and semantic selectors only (`expect(...).to_be_visible()`, `wait_for_url`, `wait_for_response`) — **no `wait_for_timeout` survives in either driver**; tracing on by default; read-only `--check` mode on every driver.

- [ ] **Step 1: Write the failing tests for `ensure_chrome`**

Create `tests/test_browser_ensure_chrome.py`:

```python
"""scripts/browser/ensure_chrome.py — own the debug-Chrome lifecycle instead of assuming Stephen launched it."""
import pathlib

import pytest

from browser import ensure_chrome as ec


def test_chrome_argv_pins_the_profile_the_port_and_the_app_path():
    argv = ec.chrome_argv(pathlib.Path("/Users/x/.kdesk/chrome-debug"), 9222)
    assert argv[0] == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    assert "--user-data-dir=/Users/x/.kdesk/chrome-debug" in argv
    assert "--remote-debugging-port=9222" in argv
    assert "--no-first-run" in argv


def test_ensure_returns_immediately_when_chrome_is_already_up():
    calls = {"probe": 0, "launch": 0, "sleep": 0}

    def probe(port, timeout=2.0):
        calls["probe"] += 1
        return {"Browser": "Chrome/141.0.0.0", "webSocketDebuggerUrl": "ws://localhost:9222/x"}

    def launch():
        calls["launch"] += 1

    info = ec.ensure(9222, probe_fn=probe, launch_fn=launch, sleep_fn=lambda s: calls.__setitem__("sleep", calls["sleep"] + 1))
    assert info["Browser"].startswith("Chrome/")
    assert calls == {"probe": 1, "launch": 0, "sleep": 0}


def test_ensure_launches_then_polls_until_the_probe_answers():
    state = {"n": 0, "launched": False}

    def probe(port, timeout=2.0):
        state["n"] += 1
        return {"Browser": "Chrome/141"} if state["n"] > 3 else None

    def launch():
        state["launched"] = True

    info = ec.ensure(9222, probe_fn=probe, launch_fn=launch, sleep_fn=lambda s: None, tries=10)
    assert info == {"Browser": "Chrome/141"}
    assert state["launched"] is True
    assert state["n"] == 4


def test_ensure_raises_a_named_error_when_chrome_never_comes_up():
    with pytest.raises(RuntimeError) as e:
        ec.ensure(9222, probe_fn=lambda port, timeout=2.0: None, launch_fn=lambda: None,
                  sleep_fn=lambda s: None, tries=3)
    assert "9222" in str(e.value)
```

- [ ] **Step 2: Write the failing tests for `session`**

Create `tests/test_browser_session.py`:

```python
"""scripts/browser/session.py — per-site preflight, queue cards, trace paths."""
import datetime as dt

import pytest

from browser import session

NOW = dt.datetime(2026, 9, 14, 8, 30, tzinfo=dt.timezone(dt.timedelta(hours=-7)))


def test_sites_cover_gumroad_and_mailerlite_with_dashboard_urls():
    assert set(session.SITES) == {"gumroad", "mailerlite"}
    assert session.SITES["gumroad"].dashboard_url == "https://app.gumroad.com/products"
    assert session.SITES["mailerlite"].dashboard_url == "https://dashboard.mailerlite.com/campaigns"


def test_classify_is_ok_when_the_dashboard_url_holds():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://app.gumroad.com/products")
    assert s.ok is True
    assert s.site == "gumroad"
    assert "logged in" in s.detail


def test_classify_detects_a_redirect_to_the_login_page():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://app.gumroad.com/login?next=%2Fproducts")
    assert s.ok is False
    assert "not logged in" in s.detail
    assert s.final_url.endswith("%2Fproducts")


def test_classify_detects_the_mailerlite_signin_redirect():
    s = session.classify("mailerlite", "https://dashboard.mailerlite.com/campaigns",
                         "https://dashboard.mailerlite.com/login")
    assert s.ok is False


def test_classify_flags_an_unexpected_host_rather_than_calling_it_ok():
    s = session.classify("gumroad", "https://app.gumroad.com/products",
                         "https://accounts.google.com/signin/oauth")
    assert s.ok is False
    assert "unexpected" in s.detail


def test_classify_rejects_an_unknown_site_name():
    with pytest.raises(KeyError):
        session.classify("linkedin", "a", "b")


def test_queue_card_markdown_is_paste_ready_and_dated():
    card = session.queue_card_markdown(
        kind="login",
        title="Log in to Gumroad in the debug Chrome",
        why="session.py --check gumroad was redirected to https://app.gumroad.com/login",
        steps=["Run: python3 scripts/browser/ensure_chrome.py",
               "In the window that opens, sign in to Gumroad",
               "Re-run: python3 scripts/browser/session.py --check gumroad"],
        now=NOW)
    assert card.startswith("# login — Log in to Gumroad in the debug Chrome\n")
    assert "2026-09-14 08:30 -0700" in card
    assert "## Why\n" in card and "## Do this\n" in card
    assert "1. Run: python3 scripts/browser/ensure_chrome.py" in card
    assert "3. Re-run: python3 scripts/browser/session.py --check gumroad" in card


def test_write_queue_card_lands_under_the_dated_manual_folder(tmp_path):
    p = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# body\n", NOW)
    assert p == tmp_path / "marketing" / "publish-queue" / "manual" / "2026-09-14-login-gumroad.md"
    assert p.read_text() == "# body\n"


def test_write_queue_card_never_overwrites_an_existing_card(tmp_path):
    first = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# one\n", NOW)
    second = session.write_queue_card(tmp_path, "manual", "login-gumroad", "# two\n", NOW)
    assert first.read_text() == "# one\n"
    assert second.name == "2026-09-14-login-gumroad-2.md"
    assert second.read_text() == "# two\n"


def test_trace_dir_is_one_folder_per_run_under_the_date(tmp_path):
    d = session.trace_dir(tmp_path, "gumroad-covers", NOW)
    assert d == tmp_path / "scripts" / "browser" / "runs" / "2026-09-14" / "gumroad-covers-083000"
    assert d.is_dir()
    assert session.trace_path(d) == d / "trace.zip"
```

- [ ] **Step 3: Run both test files to verify they fail**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_browser_ensure_chrome.py tests/test_browser_session.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'browser'`.

- [ ] **Step 4: Write `scripts/browser/__init__.py` and `scripts/browser/ensure_chrome.py`**

`scripts/browser/__init__.py`:

```python
"""Shared browser automation for KDesk: Chrome lifecycle, session preflight, site selectors."""
```

`scripts/browser/ensure_chrome.py`:

```python
#!/usr/bin/env python3
"""Own the debug-Chrome lifecycle so no script assumes Stephen launched it.

Probes http://localhost:9222/json/version; if nothing answers, launches
/Applications/Google Chrome.app against the ~/.kdesk/chrome-debug profile (which already
holds the Gumroad / MailerLite / Google logins) and waits for the probe to answer.
Scripts never type passwords and never handle 2FA - login happens once, by Stephen.

  python3 scripts/browser/ensure_chrome.py [--port 9222]
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = pathlib.Path.home() / ".kdesk" / "chrome-debug"
CDP_URL = "http://localhost:9222"


def chrome_argv(profile: pathlib.Path, port: int) -> list[str]:
    return [CHROME_APP, f"--user-data-dir={profile}", f"--remote-debugging-port={port}",
            "--no-first-run", "--no-default-browser-check"]


def probe(port: int = 9222, timeout: float = 2.0) -> dict | None:
    """Return /json/version, or None when nothing is listening."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def launch(port: int = 9222, profile: pathlib.Path = PROFILE_DIR) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(chrome_argv(profile, port), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure(port: int = 9222, *, probe_fn=None, launch_fn=None, sleep_fn=None, tries: int = 30) -> dict:
    """Return the /json/version payload, launching Chrome first if needed."""
    probe_fn = probe_fn or probe
    launch_fn = launch_fn or (lambda: launch(port))
    sleep_fn = sleep_fn or time.sleep
    info = probe_fn(port)
    if info:
        return info
    launch_fn()
    for _ in range(tries):
        sleep_fn(1.0)
        info = probe_fn(port)
        if info:
            return info
    raise RuntimeError(
        f"Chrome did not open a debug port on {port} after {tries}s. "
        f"Try manually: {' '.join(chrome_argv(PROFILE_DIR, port))}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensure the debug Chrome is running.")
    ap.add_argument("--port", type=int, default=9222)
    a = ap.parse_args()
    info = ensure(a.port)
    print(f"debug Chrome up on :{a.port} — {info.get('Browser', '?')} (profile {PROFILE_DIR})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Write `scripts/browser/session.py`**

```python
#!/usr/bin/env python3
"""Connect to the debug Chrome, preflight each site, fail closed with a queue card.

  python3 scripts/browser/session.py --check gumroad mailerlite
  python3 scripts/browser/session.py --check gumroad --dry-run   # prints the plan, opens nothing

Rules implemented (spec "Chrome automation"): scripts own the lifecycle (ensure_chrome);
preflight per site and fail closed; condition waits only; tracing on by default under
scripts/browser/runs/<date>/<name>-<HHMMSS>/trace.zip; a failure writes
marketing/publish-queue/manual/<date>-<slug>.md and logs one ledger line.

Playwright is imported lazily inside open_page() so this module stays importable with
the standard library alone (the test environment has no playwright).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402  (scripts/ledger.py)

REPO = pathlib.Path(__file__).resolve().parents[2]
CDP_URL = "http://localhost:9222"


@dataclasses.dataclass(frozen=True)
class Site:
    name: str
    dashboard_url: str
    login_marker: str
    anchor_description: str


@dataclasses.dataclass(frozen=True)
class SiteStatus:
    site: str
    ok: bool
    requested_url: str
    final_url: str
    detail: str


SITES: dict[str, Site] = {
    "gumroad": Site("gumroad", "https://app.gumroad.com/products", "/login",
                    "the products table"),
    "mailerlite": Site("mailerlite", "https://dashboard.mailerlite.com/campaigns", "/login",
                       "the campaigns list"),
}


def classify(site: str, requested_url: str, final_url: str) -> SiteStatus:
    cfg = SITES[site]
    want_host = urllib.parse.urlsplit(cfg.dashboard_url).netloc
    got = urllib.parse.urlsplit(final_url)
    if got.netloc != want_host:
        return SiteStatus(site, False, requested_url, final_url,
                          f"unexpected host {got.netloc!r} (wanted {want_host!r})")
    if cfg.login_marker in got.path:
        return SiteStatus(site, False, requested_url, final_url,
                          f"not logged in — redirected to {got.path}")
    return SiteStatus(site, True, requested_url, final_url,
                      f"logged in — {cfg.anchor_description} reachable at {got.path}")


def queue_card_markdown(kind: str, title: str, why: str, steps: list[str],
                        now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now().astimezone()
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    return (f"# {kind} — {title}\n\n"
            f"Written {now.strftime('%Y-%m-%d %H:%M %z')} by scripts/browser/session.py\n\n"
            f"## Why\n\n{why}\n\n"
            f"## Do this\n\n{numbered}\n")


def write_queue_card(repo: pathlib.Path, subdir: str, slug: str, body: str,
                     now: dt.datetime | None = None) -> pathlib.Path:
    now = now or dt.datetime.now().astimezone()
    folder = pathlib.Path(repo) / "marketing" / "publish-queue" / subdir
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{now.strftime('%Y-%m-%d')}-{slug}"
    path = folder / f"{stem}.md"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}.md"
        n += 1
    path.write_text(body, encoding="utf-8")
    return path


def trace_dir(repo: pathlib.Path, name: str, now: dt.datetime | None = None) -> pathlib.Path:
    now = now or dt.datetime.now().astimezone()
    d = (pathlib.Path(repo) / "scripts" / "browser" / "runs"
         / now.strftime("%Y-%m-%d") / f"{name}-{now.strftime('%H%M%S')}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def trace_path(directory: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(directory) / "trace.zip"


@contextlib.contextmanager
def open_page(name: str, *, repo: pathlib.Path = REPO, tracing: bool = True):
    """Yield a Page on the logged-in debug Chrome, with a trace.zip per run."""
    from playwright.sync_api import sync_playwright  # lazy: absent in the test env

    from browser import ensure_chrome

    ensure_chrome.ensure()
    out = trace_dir(repo, name)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        if tracing:
            ctx.tracing.start(name=name, screenshots=True, snapshots=True)
        page = ctx.new_page()
        try:
            yield page
        finally:
            if tracing:
                ctx.tracing.stop(path=str(trace_path(out)))
                print(f"trace: {trace_path(out)}", file=sys.stderr)
            page.close()


def check(site: str, *, page=None) -> SiteStatus:
    """Open the site dashboard and report whether the profile is still logged in."""
    cfg = SITES[site]
    if page is not None:
        page.goto(cfg.dashboard_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_load_state("domcontentloaded")
        return classify(site, cfg.dashboard_url, page.url)
    with open_page(f"check-{site}") as pg:
        pg.goto(cfg.dashboard_url, wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_load_state("domcontentloaded")
        return classify(site, cfg.dashboard_url, pg.url)


def report(status: SiteStatus, *, repo: pathlib.Path = REPO, dry_run: bool = False) -> int:
    """Print one line; on failure write a queue card and a ledger entry. Returns an exit code."""
    mark = "OK  " if status.ok else "FAIL"
    print(f"{mark} {status.site:<11} {status.detail}")
    if status.ok or dry_run:
        return 0 if status.ok else 1
    cfg = SITES[status.site]
    body = queue_card_markdown(
        kind="login",
        title=f"Log in to {status.site} in the debug Chrome",
        why=(f"`python3 scripts/browser/session.py --check {status.site}` requested "
             f"{status.requested_url} and landed on {status.final_url}."),
        steps=["Run: python3 scripts/browser/ensure_chrome.py",
               f"In the window that opens, sign in to {status.site} "
               f"({cfg.dashboard_url}) — the profile keeps the session afterwards",
               f"Re-run: python3 scripts/browser/session.py --check {status.site}"])
    card = write_queue_card(repo, "manual", f"login-{status.site}", body)
    ledger.append(
        action=(f"Browser preflight failed for {status.site}: {status.detail}. "
                f"Wrote the manual queue card {card.relative_to(repo)}; no driver ran."),
        tier=0, status="executed",
        reasoning="Fail closed rather than retry blindly (spec Chrome rule 3).",
        files=[str(card.relative_to(repo))])
    print(f"     queued -> {card.relative_to(repo)}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Check the debug Chrome's login state per site.")
    ap.add_argument("--check", nargs="+", choices=sorted(SITES), required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be checked; open nothing, write nothing")
    a = ap.parse_args()
    if a.dry_run:
        for site in a.check:
            print(f"(dry-run) would open {SITES[site].dashboard_url} and assert "
                  f"{SITES[site].anchor_description}")
        return 0
    rc = 0
    for site in a.check:
        rc |= report(check(site))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the two test files to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_browser_ensure_chrome.py tests/test_browser_session.py -q`
Expected: PASS, 14 tests.

- [ ] **Step 7: Write the two selector modules**

`scripts/browser/selectors_gumroad.py` — every Gumroad anchor currently inlined in the two drivers, extracted verbatim so a UI change is a one-file fix:

```python
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
WORKFLOW_NAME_INPUT = "#name"
WORKFLOW_BOUGHT_INPUT = "#bought"
WORKFLOW_SUBJECT_INPUT = "input[placeholder='Subject']"
WORKFLOW_DELAY_INPUT = "input[placeholder='0']"
WORKFLOW_BODY_EDITOR = "[contenteditable=true]"
WORKFLOW_BLOCK_FOR_SUBJECT = "xpath=ancestor::*[.//input[@placeholder='0']][1]"

# The response whose completion means "Gumroad persisted it" (spec Chrome rule 6:
# wait_for_response instead of a sleep).
SAVE_RESPONSE_FRAGMENTS = ("/products/", "/workflows/")
```

`scripts/browser/selectors_mailerlite.py`:

```python
"""Every MailerLite UI anchor, in one place (spec Chrome rule 6).

Only the read-only anchors needed by the weekly selector canary exist today; the campaign
editor driver (spec Track 2) lands in a later phase and adds its anchors here.
"""

DASHBOARD_URL = "https://dashboard.mailerlite.com/campaigns"
SUBSCRIBERS_URL = "https://dashboard.mailerlite.com/subscribers"
AUTOMATIONS_URL = "https://dashboard.mailerlite.com/automations"

CAMPAIGNS_HEADING = "Campaigns"
CREATE_CAMPAIGN_BUTTON = "Create campaign"
```

- [ ] **Step 8: Rewrite `scripts/video/gumroad_covers_ui.py`**

Same behaviour (same `LISTINGS` map, same cover-then-thumbnail-then-save order, same API verification) with the lifecycle, waits, tracing and `--check` from `session.py`. Replace the whole file with:

```python
#!/usr/bin/env python3
"""
Upload covers + thumbnails to Gumroad listings through the logged-in debug Chrome (CDP :9222).
The Gumroad API silently ignores cover params, so this drives the product editor UI.

  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py [--only slug] [--skip a,b]
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check      # read-only
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --dry-run    # plan only

Behaviour is unchanged from the 2026-09-02 version; the browser lifecycle, login preflight,
condition waits (no wait_for_timeout), tracing and queue cards come from scripts/browser/.
"""
import argparse
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from browser import selectors_gumroad as S  # noqa: E402
from browser import session  # noqa: E402

IMG = (REPO / "static" / "images" / "products").resolve()
LISTINGS = {  # Gumroad EDITOR permalink -> (cover, thumb, api product id or None)
    "phxigq": ("asc842-cover.png", "asc842-thumb.png", "Gp9nwTmverZnmQqvQe_afg=="),
    "gljxc": ("asc842-free-cover.png", "asc842-free-thumb.png", "OYv6bQLI2pyKl7xnr-qzTA=="),
    "mwmwpe": ("asc606-cover.png", "asc606-thumb.png", None),
    "cjexre": ("asc606-free-cover.png", "asc606-free-thumb.png", "XW7TqzwvQ8MuwsiMOUq-ng=="),
    "xsezh": ("fixed-assets-cover.png", "fixed-assets-thumb.png", "SAuqdvLmzgT_nUKj99lpZw=="),
    "pdnpy": ("fixed-assets-free-cover.png", "fixed-assets-free-thumb.png", "T9PHkG-s1Hz_tHIlgoyf_A=="),
    "qmgnitm": ("saas-metrics-cover.png", "saas-metrics-thumb.png", "5b3Dn9UXPPDSu_gJs1gVhA=="),
    "feqoy": ("saas-metrics-free-cover.png", "saas-metrics-free-thumb.png", "oEIj8s_0_Kk9qHDuPT6Y1Q=="),
    "bujdfg": ("runway-cover.png", "runway-thumb.png", "tDj5H9JMTOTNHlr8JLqOWg=="),
    "onxlfg": ("runway-free-cover.png", "runway-free-thumb.png", "ZkFjfA6mjAV6ogPNTqkJjw=="),
    "sjftml": ("month-end-close-cover.png", "month-end-close-thumb.png", "tvxqT2fwquibDUr1V4rJEg=="),
    "shccc": ("bundle-cover.png", "bundle-thumb.png", "WAKdGcEmy476e-5fWioVsQ=="),
}


def token() -> str:
    env = pathlib.Path(os.path.expanduser("~/kdeskaccountingtemplates/.env"))
    for line in env.read_text().splitlines():
        if line.startswith("GUMROAD_ACCESS_TOKEN"):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"No GUMROAD_ACCESS_TOKEN in {env}")


def open_editor(pg, slug: str):
    from playwright.sync_api import expect
    pg.goto(S.EDITOR_URL.format(slug=slug), wait_until="domcontentloaded", timeout=60_000)
    status = session.classify("gumroad", S.EDITOR_URL.format(slug=slug), pg.url)
    if not status.ok:
        raise SystemExit(session.report(status, repo=REPO) and f"gumroad preflight: {status.detail}")
    cover = pg.locator(S.SECTION.format(heading=S.COVER_HEADING)).first
    expect(cover).to_be_visible(timeout=30_000)
    return cover


def check_listing(pg, slug: str) -> str:
    """Read-only: assert the two anchors this driver depends on still resolve."""
    from playwright.sync_api import expect
    cover = open_editor(pg, slug)
    thumb = pg.locator(S.SECTION.format(heading=S.THUMBNAIL_HEADING)).first
    expect(thumb).to_be_visible(timeout=30_000)
    tabs = cover.locator(S.COVER_TABS).count()
    return f"cover section ok (tiles={tabs}) · thumbnail section ok"


def do_listing(pg, slug: str, cover_png: str, thumb_png: str):
    from playwright.sync_api import expect
    cov = open_editor(pg, slug)
    pg.evaluate(
        "() => { window.__fi=[]; const mo=new MutationObserver(ms=>ms.forEach(m=>m.addedNodes"
        ".forEach(n=>{ if(n.nodeType===1){ if(n.matches&&n.matches('input[type=file]'))"
        " window.__fi.push(n); n.querySelectorAll&&n.querySelectorAll('input[type=file]')"
        ".forEach(i=>window.__fi.push(i)); } }))); mo.observe(document.documentElement,"
        "{childList:true,subtree:true}); }")
    cov.scroll_into_view_if_needed()
    tiles = cov.locator(S.COVER_TABS)
    before = tiles.count()
    if cov.locator(S.ADD_COVER_BUTTON).count():
        cov.locator(S.ADD_COVER_BUTTON).first.click()
        dialog = pg.locator("[role=dialog]")
        expect(dialog).to_be_visible(timeout=15_000)
        dialog.locator("button", has_text=S.UPLOAD_BUTTON_TEXT).first.click()
    else:
        cov.locator("button", has_text=S.UPLOAD_BUTTON_TEXT).first.click()
    pg.wait_for_function("() => window.__fi && window.__fi.length > 0", timeout=15_000)
    handle = pg.evaluate_handle("() => window.__fi[window.__fi.length-1]")
    element = handle.as_element()
    if element is None:
        raise RuntimeError("no file input created by 'Upload images or videos'")
    element.set_input_files(str(IMG / cover_png))
    pg.keyboard.press("Escape")
    pg.wait_for_function("n => document.querySelectorAll("
                         "\"[role=tablist][aria-label='Product covers'] [role=tab]\").length > n",
                         arg=before, timeout=120_000)
    if before > 0:  # drag the new (last) tile to the front so it becomes the main cover
        src = tiles.nth(tiles.count() - 1).bounding_box()
        dst = tiles.nth(0).bounding_box()
        pg.mouse.move(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2)
        pg.mouse.down()
        for i in range(1, 12):
            pg.mouse.move(src["x"] + src["width"] / 2 + (dst["x"] - src["x"]) * i / 11,
                          src["y"] + src["height"] / 2)
        pg.mouse.move(dst["x"] + 5, dst["y"] + dst["height"] / 2)
        pg.mouse.up()
        expect(tiles.nth(0)).to_be_visible(timeout=15_000)
    th = pg.locator(S.SECTION.format(heading=S.THUMBNAIL_HEADING)).first
    th.scroll_into_view_if_needed()
    rm = th.locator(S.THUMBNAIL_REMOVE_BUTTON)
    if rm.count():
        rm.first.click()
        expect(th.locator("img")).to_have_count(0, timeout=15_000)
    th.locator(S.FILE_INPUT).first.set_input_files(str(IMG / thumb_png))
    expect(th.locator("img").first).to_be_visible(timeout=120_000)
    with pg.expect_response(lambda r: "/products/" in r.url and r.request.method in ("PUT", "POST"),
                            timeout=60_000):
        pg.get_by_role("button", name=S.SAVE_BUTTON).first.click()
    alerts = [a for a in pg.locator(S.ALERTS).all_inner_texts() if a.strip()][:2]
    return before, alerts


def verify_via_api(pid: str | None) -> str:
    if not pid:
        return ""
    import requests
    g = requests.get(f"https://api.gumroad.com/v2/products/{pid}",
                     params={"access_token": token()}, timeout=30).json()["product"]
    covers = g.get("covers") or []
    return (f"covers={len(covers)} "
            f"main_is_new={(covers[0].get('id') if covers else None) == g.get('main_cover_id')} "
            f"thumb={bool(g.get('thumbnail_url'))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--skip", default="")
    ap.add_argument("--check", action="store_true", help="read-only anchor assertion; changes nothing")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; open nothing")
    a = ap.parse_args()
    skip = {s for s in a.skip.split(",") if s}
    targets = [(s, v) for s, v in LISTINGS.items() if (not a.only or s == a.only) and s not in skip]
    if a.dry_run:
        for slug, (cover, thumb, _pid) in targets:
            print(f"(dry-run) {slug:<10} cover={cover} thumb={thumb}")
        return 0
    rc = 0
    with session.open_page("gumroad-covers", repo=REPO) as pg:
        for slug, (cover, thumb, pid) in targets:
            try:
                if a.check:
                    print(f"{slug:<10} CHECK {check_listing(pg, slug)}", flush=True)
                    continue
                before, alerts = do_listing(pg, slug, cover, thumb)
                print(f"{slug:<10} ok  old_covers={before} {verify_via_api(pid)} {alerts}", flush=True)
            except Exception as exc:  # noqa: BLE001 — one retry max, then a queue card (rule 7)
                rc = 1
                shot = session.trace_dir(REPO, f"gumroad-covers-fail-{slug}") / "fail.png"
                pg.screenshot(path=str(shot))
                card = session.write_queue_card(
                    REPO, "manual", f"gumroad-cover-{slug}",
                    session.queue_card_markdown(
                        kind="gumroad-cover",
                        title=f"Set the cover and thumbnail on Gumroad listing {slug} by hand",
                        why=f"gumroad_covers_ui.py failed: {str(exc)[:300]}\n\nScreenshot: {shot}",
                        steps=[f"Open {S.EDITOR_URL.format(slug=slug)}",
                               f"Cover → Upload images or videos → static/images/products/{cover}",
                               "Drag the new tile to the first position",
                               f"Thumbnail → replace with static/images/products/{thumb}",
                               "Save changes"]))
                print(f"{slug:<10} FAILED {str(exc)[:120]} -> {card.relative_to(REPO)}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9: Rewrite `scripts/video/gumroad_workflows_ui.py`**

Keep the existing declarative shape (`read_state → diff → apply → re-read → assert`, spec Chrome rule 4) and the `JS_STATE` reader; replace every `wait_for_timeout` with a condition wait, route the browser through `session.open_page`, and add `--check` / `--dry-run`. Replace the whole file with:

```python
#!/usr/bin/env python3
"""Create + publish the free->paid follow-up workflows on Gumroad (UI via CDP :9222).
Copy from marketing/email-sequences/workflows.json.

  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py [--only slug]
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check    # read-only
  scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --dry-run  # plan only

Declarative and idempotent: read the live state, apply only what is missing, re-read and
assert. Re-running with nothing to do prints the verified state and changes nothing.
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from browser import selectors_gumroad as S  # noqa: E402
from browser import session  # noqa: E402

W = json.load(open(REPO / "marketing/email-sequences/workflows.json"))
PRODUCT = {
    "asc842": "ASC 842 Lease Accounting Workbook — Free Excel Template (3-Lease Version)",
    "asc606": "ASC 606 Commission Accrual Workbook — Free Excel Template (5-Deal Version)",
    "fixed-assets": "Free 5-Asset Fixed Asset Depreciation Workbook (Excel)",
    "saas-metrics": "SaaS Metrics & ARR Dashboard — FREE 6-Month Excel Template",
    "runway": "Startup Runway Calculator — Free Excel Template (12-Month)",
}
NAME = {
    "asc842": "Free → full: ASC 842 (3-email follow-up)",
    "asc606": "Free → full: ASC 606 (3-email follow-up)",
    "fixed-assets": "Free → full: Fixed Assets (3-email follow-up)",
    "saas-metrics": "Free → full: SaaS Metrics (3-email follow-up)",
    "runway": "Free → full: Runway (3-email follow-up)",
}
JS_STATE = (
    "() => [...document.querySelectorAll('input[placeholder=\"Subject\"]')].map(s=>{let n=s;"
    " for(let i=0;i<12;i++){ n=n.parentElement; if(n.querySelector('[contenteditable=true]')"
    "&&n.querySelector('input[placeholder=\"0\"]')) break;}"
    " const ce=n.querySelector('[contenteditable=true]');"
    " return {subj:s.value.slice(0,16), delay:n.querySelector('input[placeholder=\"0\"]').value,"
    " body:(ce?ce.innerText:'').trim().length}})")
DELAY_LABELS = ("0 days after purchase", "3 days after purchase", "7 days after purchase")


def alerts(pg):
    return [a for a in pg.locator(S.ALERTS).all_inner_texts() if a.strip()][:2]


def block(pg, i):
    s = pg.locator(S.WORKFLOW_SUBJECT_INPUT).nth(i)
    return s, s.locator(S.WORKFLOW_BLOCK_FOR_SUBJECT)


def type_body(pg, blk, text):
    from playwright.sync_api import expect
    body = blk.locator(S.WORKFLOW_BODY_EDITOR).first
    body.scroll_into_view_if_needed()
    body.click()
    expect(body).to_be_focused(timeout=10_000)
    for line in text.split("\n"):
        pg.keyboard.type(line)
        pg.keyboard.press("Enter")


def goto(pg, url):
    from playwright.sync_api import expect
    pg.goto(url, wait_until="domcontentloaded", timeout=60_000)
    status = session.classify("gumroad", url, pg.url)
    if not status.ok:
        session.report(status, repo=REPO)
        raise SystemExit(f"gumroad preflight: {status.detail}")
    expect(pg.locator("body")).to_be_visible(timeout=30_000)


def existing(pg):
    goto(pg, S.WORKFLOWS_URL)
    pg.wait_for_selector(S.WORKFLOW_LINKS, state="attached", timeout=30_000)
    return pg.evaluate(
        f"() => [...document.querySelectorAll('{S.WORKFLOW_LINKS}')].map(a=>({{"
        "href:a.getAttribute('href'),"
        "text:(a.closest('tr,li,section,div')?.innerText||'').replace(/\\s+/g,' ').slice(0,120)}}))")


def read_state(pg, slug):
    """Live state for one workflow: id, product filter, subjects present, delays, published."""
    wf = next((e["href"].split("/")[2] for e in existing(pg) if NAME[slug][:22] in e["text"]), None)
    if wf is None:
        return {"wf": None, "filter_ok": False, "emails": 0, "delays": 0, "published": False}
    goto(pg, S.WORKFLOW_EDIT_URL.format(wf=wf))
    filter_ok = PRODUCT[slug][:20] in pg.inner_text("body")
    goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=wf))
    text = pg.inner_text("body")
    return {"wf": wf, "filter_ok": filter_ok,
            "emails": sum(1 for e in W[slug] if e["subject"] in text),
            "delays": sum(1 for d in DELAY_LABELS if d in text),
            "published": pg.get_by_role("button", name="Unpublish").count() > 0}


def save(pg):
    from playwright.sync_api import expect
    with pg.expect_response(lambda r: "/workflows/" in r.url and r.request.method in ("PUT", "POST"),
                            timeout=60_000):
        pg.get_by_role("button", name=S.SAVE_BUTTON).first.click(force=True)
    expect(pg.locator(S.ALERTS).first).to_be_visible(timeout=30_000)


def apply_emails(pg, slug):
    from playwright.sync_api import expect
    emails = W[slug]
    for _ in range(8):
        d = pg.locator("button[aria-label='Delete']")
        if not d.count():
            break
        d.first.click(force=True)
        confirm = pg.get_by_role("button", name="Yes, delete")
        if confirm.count():
            confirm.first.click(force=True)
        expect(pg.locator("button[aria-label='Delete']")).to_have_count(
            max(0, d.count() - 1), timeout=15_000)
    pg.get_by_role("button", name="Create email").first.click(force=True)
    expect(pg.locator(S.WORKFLOW_SUBJECT_INPUT)).to_have_count(1, timeout=30_000)
    for n in (2, 3):
        pg.get_by_role("button", name="Add email").last.click(force=True)
        expect(pg.locator(S.WORKFLOW_SUBJECT_INPUT)).to_have_count(n, timeout=30_000)
    for i, e in enumerate(emails):
        s, blk = block(pg, i)
        delay = blk.locator(S.WORKFLOW_DELAY_INPUT).first
        delay.click()
        pg.keyboard.press("Meta+A")
        pg.keyboard.type(str(e["delay_days"]))
        blk.locator("select").first.select_option(label="days after purchase")
        s.click()
        s.fill(e["subject"])
        type_body(pg, blk, e["body"])
    for i, e in enumerate(emails):
        if pg.evaluate(JS_STATE)[i]["body"] < 50:
            _s, blk = block(pg, i)
            type_body(pg, blk, e["body"])
    save(pg)


def build(pg, slug, check_only=False):
    from playwright.sync_api import expect
    state = read_state(pg, slug)
    if check_only:
        return (f"wf={str(state['wf'])[:10]} filter={state['filter_ok']} "
                f"emails={state['emails']}/3 delays={state['delays']}/3 "
                f"published={state['published']}")
    if state["wf"] is None:
        goto(pg, S.WORKFLOW_NEW_URL)
        pg.locator(S.WORKFLOW_NAME_INPUT).fill(NAME[slug])
        pg.get_by_text("Purchase", exact=True).first.click()
        pg.locator(S.WORKFLOW_BOUGHT_INPUT).click()
        pg.keyboard.type(PRODUCT[slug][:24])
        option = pg.get_by_text(PRODUCT[slug], exact=True).first
        expect(option).to_be_visible(timeout=15_000)
        option.click()
        with pg.expect_navigation(timeout=60_000):
            pg.get_by_role("button", name="Save and continue").first.click(force=True)
        state = read_state(pg, slug)
    if not state["filter_ok"]:
        goto(pg, S.WORKFLOW_EDIT_URL.format(wf=state["wf"]))
        pg.locator(S.WORKFLOW_BOUGHT_INPUT).click()
        pg.keyboard.type(PRODUCT[slug][:24])
        option = pg.get_by_text(PRODUCT[slug], exact=True).first
        expect(option).to_be_visible(timeout=15_000)
        option.click()
        save(pg)
        state = read_state(pg, slug)
    if state["emails"] < 3:
        goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=state["wf"]))
        apply_emails(pg, slug)
        state = read_state(pg, slug)
    if state["emails"] == 3 and state["delays"] == 3 and state["filter_ok"] and not state["published"]:
        goto(pg, S.WORKFLOW_EMAILS_URL.format(wf=state["wf"]))
        with pg.expect_response(lambda r: "/workflows/" in r.url, timeout=60_000):
            pg.get_by_role("button", name="Publish").first.click(force=True)
        state = read_state(pg, slug)
    return (f"wf={str(state['wf'])[:10]} filter={state['filter_ok']} "
            f"emails={state['emails']}/3 delays={state['delays']}/3 published={state['published']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--check", action="store_true", help="read-only state report; changes nothing")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; open nothing")
    a = ap.parse_args()
    slugs = [s for s in W if not a.only or s == a.only]
    if a.dry_run:
        for slug in slugs:
            print(f"(dry-run) {slug:<13} would ensure '{NAME[slug]}' has "
                  f"{len(W[slug])} emails filtered to {PRODUCT[slug][:40]}…")
        return 0
    rc = 0
    with session.open_page("gumroad-workflows", repo=REPO) as pg:
        for slug in slugs:
            try:
                print(f"{slug:<13} {build(pg, slug, check_only=a.check)}", flush=True)
            except Exception as exc:  # noqa: BLE001
                rc = 1
                shot = session.trace_dir(REPO, f"gumroad-workflows-fail-{slug}") / "fail.png"
                pg.screenshot(path=str(shot))
                card = session.write_queue_card(
                    REPO, "manual", f"gumroad-workflow-{slug}",
                    session.queue_card_markdown(
                        kind="gumroad-workflow",
                        title=f"Finish the free→paid workflow for {slug} in the Gumroad editor",
                        why=f"gumroad_workflows_ui.py failed: {str(exc)[:300]}\n\nScreenshot: {shot}",
                        steps=[f"Open {S.WORKFLOWS_URL}",
                               f"Open or create '{NAME[slug]}' filtered to '{PRODUCT[slug]}'",
                               "Paste the three emails from marketing/email-sequences/workflows.json "
                               f"under key '{slug}' with delays 0/3/7 days after purchase",
                               "Save changes, then Publish"]))
                print(f"{slug:<13} FAILED {str(exc)[:120]} -> {card.relative_to(REPO)}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 10: Assert no fixed sleeps survive**

Run:

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
grep -rn "wait_for_timeout" scripts/video/gumroad_covers_ui.py scripts/video/gumroad_workflows_ui.py scripts/browser/ ; echo "exit=$?"
```

Expected: no matches, `exit=1` (grep found nothing). If anything matches, replace it with an `expect(...)`, `wait_for_function`, `expect_response` or `expect_navigation` condition before continuing.

- [ ] **Step 11: Update `.gitignore`**

Append to `.gitignore`:

```
# Playwright traces + failure screenshots from scripts/browser (local evidence, not source)
scripts/browser/runs/

# Queued video assets are linked/copied from the build dir, never committed
marketing/publish-queue/**/*.mp4
```

- [ ] **Step 12: Run the full suite**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 39 passed (25 + 14).

- [ ] **Step 13: Live verification on the Mac (spec's own check for this section)**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 scripts/browser/ensure_chrome.py
python3 scripts/browser/session.py --check gumroad mailerlite
scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check
scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check
scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check   # twice
```

Expected: `ensure_chrome` prints `debug Chrome up on :9222`; `session.py` prints one `OK` line per site (or `FAIL` plus a card under `marketing/publish-queue/manual/` — then log in and re-run); `--check` on both drivers exits 0, prints one line per listing/slug, and the second workflows run prints **identical** output with no new ledger line (`tail -1 decisions/decisions.jsonl` unchanged).

- [ ] **Step 14: Commit**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/browser tests/test_browser_ensure_chrome.py tests/test_browser_session.py \
        scripts/video/gumroad_covers_ui.py scripts/video/gumroad_workflows_ui.py .gitignore
git commit -m "feat(browser): shared Chrome lifecycle, per-site preflight, selectors, --check

scripts/browser/ owns launching the debug Chrome, detects a login redirect per site and
fails closed with a queue card plus a ledger line, keeps one trace.zip per run, and holds
every Gumroad/MailerLite anchor in one file. The two Gumroad drivers now use it, wait on
conditions instead of fixed sleeps, and gain a read-only --check for the weekly canary.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 3: `scripts/publishers/` — pluggable publishers on Upload-Post, with a queue fallback

**Files:**
- Create: `scripts/publishers/__init__.py`, `base.py`, `upload_post.py`, `youtube.py`, `tiktok.py`, `instagram.py`, `site.py`, `publish.py`
- Create: `tests/test_publishers_base.py`, `tests/test_publishers_upload_post.py`, `tests/test_publishers_site.py`
- Create: `marketing/publish-queue/.gitkeep`
- Create: `content/shorts/_index.md`

**Interfaces:**
- Consumes: `ledger.append(...)` (Task 1); `session.queue_card_markdown(...)` and `session.write_queue_card(...)` (Task 2).
- Produces:
  - `base.PublishResult` dataclass: `platform: str`, `ok: bool`, `url: str | None`, `queued_path: str | None`, `detail: str`
  - `base.Publisher` ABC: `platform: str` (class attr), `capabilities() -> dict`, `preflight() -> PublishResult | None`, `publish(asset: Path, meta: dict, dry_run: bool) -> PublishResult`, `queue(asset: Path, meta: dict, detail: str) -> PublishResult`
  - `base.queue_card_body(platform: str, meta: dict, detail: str, asset_name: str, now) -> str`
  - `base.link_or_copy(asset: Path, dest: Path) -> str` (returns `"symlink"` or `"copy"`)
  - `upload_post.API_URL = "https://api.upload-post.com/api/upload"`
  - `upload_post.build_form(platform: str, meta: dict) -> list[tuple[str, str]]`
  - `upload_post.parse_response(platform: str, status: int, payload: dict) -> PublishResult`
  - `upload_post.UploadPostPublisher(platform, *, repo, api_key=None, profile=None)` — subclass of `base.Publisher`; the single HTTP seam is the module function `upload_post._http_post(url, headers, fields, file_field, file_path) -> tuple[int, dict]`
  - `youtube.YouTubePublisher`, `tiktok.TikTokPublisher`, `instagram.InstagramPublisher`
  - `site.SitePublisher` + `site.post_markdown(date, slug, meta) -> str` + `site.post_path(repo, date, slug) -> Path`
  - `publish.PUBLISHERS: dict[str, type]` and `publish.main() -> int`
- Later tasks: Task 4 drives `youtube.YouTubePublisher`; Task 9's workflow calls `publish.py`.

**Upload-Post API facts, researched 2026-09-14 from `https://docs.upload-post.com/api/upload-video/` and `/api/reference/`** — encode exactly these:

| Item | Value |
|---|---|
| Endpoint | `POST https://api.upload-post.com/api/upload` |
| Content type | `multipart/form-data` |
| Auth header | `Authorization: Apikey <UPLOAD_POST_KEY>` |
| Video file field | `video` |
| Platform field | `platform[]`, repeated once per platform |
| Always-sent fields | `user` (profile username), `title`, `description` |
| YouTube extras | `privacyStatus` (`public`/`unlisted`/`private`), `tags`, `categoryId`, `selfDeclaredMadeForKids` |
| TikTok extras | `privacy_level` (`PUBLIC_TO_EVERYONE`/`MUTUAL_FOLLOW_FRIENDS`/`FOLLOWER_OF_CREATOR`/`SELF_ONLY`), `post_mode` (`DIRECT_POST`) |
| Instagram extras | `media_type` (`REELS`/`STORIES`), `share_to_feed` |
| Success body | `{"success": true, "results": {"<platform>": {"success": true, "url": "...", "video_id": "..."}}, "usage": {...}}` |
| Errors | 400 `Username required in form data` · 401 `Invalid or expired token` · 403 `TikTok uploads not available on Free plan.` · 429 `This upload would exceed your monthly limit.` — all with `{"success": false, "message": "..."}` |
| Profile listing | `GET https://api.upload-post.com/api/uploadposts/users` |
| Free tier | 10 uploads/month; TikTok needs a paid plan |

> **Doc conflict (resolved):** the docs landing page shows `file=@video.mp4` + `platforms=tiktok,instagram,youtube`; the API reference page shows `video=@video.mp4` + repeated `platform[]=tiktok`. This plan encodes the **reference page** form (`video` + `platform[]`), because it is the page that also documents every platform-specific field. `capabilities()` records `"form_variant": "platform[]"` so a future fix is one constant.

- [ ] **Step 1: Write the failing test for `base`**

Create `tests/test_publishers_base.py`:

```python
"""scripts/publishers/base.py — the queue-card fallback every publisher shares."""
import datetime as dt
import pathlib

import pytest

from publishers import base

NOW = dt.datetime(2026, 9, 14, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))
META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel #Shorts",
        "description": "PV of the remaining payments.\nFree: https://kdeskaccounting.com/",
        "privacy": "public", "tags": ["ASC 842", "Excel"]}


def test_publish_result_carries_either_a_url_or_a_queued_path():
    ok = base.PublishResult(platform="youtube", ok=True, url="https://youtu.be/x",
                            queued_path=None, detail="uploaded")
    queued = base.PublishResult(platform="tiktok", ok=False, url=None,
                                queued_path="marketing/publish-queue/tiktok/x.md", detail="403")
    assert ok.url and ok.queued_path is None
    assert queued.queued_path and queued.url is None


def test_queue_card_body_is_paste_ready_with_title_description_and_the_asset():
    body = base.queue_card_body("tiktok", META, "HTTP 403 TikTok uploads not available on Free plan.",
                                "asc842-short-liability.mp4", NOW)
    assert body.startswith("# tiktok — ASC 842 Lease Liability in Excel #Shorts\n")
    assert "2026-09-14 07:00 -0700" in body
    assert "HTTP 403 TikTok uploads not available on Free plan." in body
    assert "asc842-short-liability.mp4" in body
    assert "PV of the remaining payments." in body
    assert "## Caption (copy this)" in body


def test_link_or_copy_symlinks_when_it_can(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video")
    dest = tmp_path / "queue" / "a.mp4"
    dest.parent.mkdir()
    how = base.link_or_copy(src, dest)
    assert how == "symlink"
    assert dest.read_bytes() == b"video"


def test_link_or_copy_falls_back_to_a_real_copy(tmp_path, monkeypatch):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video")
    dest = tmp_path / "a-copy.mp4"

    def boom(self, target, target_is_directory=False):
        raise OSError("cross-device link")

    monkeypatch.setattr(pathlib.Path, "symlink_to", boom)
    assert base.link_or_copy(src, dest) == "copy"
    assert dest.read_bytes() == b"video"
    assert not dest.is_symlink()


class _Stub(base.Publisher):
    platform = "stub"

    def capabilities(self):
        return {"video": True}

    def _do_publish(self, asset, meta):
        raise RuntimeError("upstream exploded")


def test_queue_writes_the_card_and_the_asset_and_returns_a_not_ok_result(tmp_path):
    asset = tmp_path / "asc842-short-liability.mp4"
    asset.write_bytes(b"video")
    pub = _Stub(repo=tmp_path)
    res = pub.queue(asset, META, "upstream exploded")
    assert res.ok is False
    assert res.platform == "stub"
    assert res.url is None
    card = tmp_path / res.queued_path
    assert card.exists()
    assert "upstream exploded" in card.read_text()
    assert (card.parent / asset.name).exists()


def test_publish_dry_run_touches_nothing_and_reports_the_plan(tmp_path, capsys):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"video")
    pub = _Stub(repo=tmp_path)
    res = pub.publish(asset, META, dry_run=True)
    assert res.ok is True
    assert res.url is None and res.queued_path is None
    assert "dry-run" in res.detail
    assert not (tmp_path / "marketing").exists()


def test_publish_falls_back_to_the_queue_when_the_platform_call_raises(tmp_path):
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"video")
    res = _Stub(repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert res.queued_path is not None
    assert "upstream exploded" in res.detail


def test_publish_refuses_a_missing_asset_without_touching_the_network(tmp_path):
    with pytest.raises(FileNotFoundError):
        _Stub(repo=tmp_path).publish(tmp_path / "gone.mp4", META, dry_run=False)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_publishers_base.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'publishers'`.

- [ ] **Step 3: Write `scripts/publishers/__init__.py` and `scripts/publishers/base.py`**

`scripts/publishers/__init__.py`:

```python
"""Pluggable publishers: every one implements --dry-run and a queue() fallback."""
```

`scripts/publishers/base.py`:

```python
#!/usr/bin/env python3
"""Publisher contract: dry-run everywhere, queue cards instead of silent failures.

A publisher either returns a url (it published) or a queued_path (it wrote a paste-ready
card plus the asset under marketing/publish-queue/<platform>/ for Stephen). It never
raises past publish() for an upstream problem, and never swallows one either.
Stdlib only at import time.
"""
from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import pathlib
import shutil

REPO = pathlib.Path(__file__).resolve().parents[2]


@dataclasses.dataclass(frozen=True)
class PublishResult:
    platform: str
    ok: bool
    url: str | None
    queued_path: str | None
    detail: str


def queue_card_body(platform: str, meta: dict, detail: str, asset_name: str,
                    now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now().astimezone()
    tags = " ".join(f"#{t.replace(' ', '')}" for t in meta.get("tags", []))
    return (f"# {platform} — {meta.get('title', meta.get('slug', 'untitled'))}\n\n"
            f"Queued {now.strftime('%Y-%m-%d %H:%M %z')} by scripts/publishers/{platform}.py\n\n"
            f"## Why it is here\n\n{detail}\n\n"
            f"## Asset\n\n`{asset_name}` — sitting next to this card in the same folder.\n\n"
            f"## Title (copy this)\n\n{meta.get('title', '')}\n\n"
            f"## Caption (copy this)\n\n{meta.get('description', '')}\n\n"
            f"## Tags\n\n{tags or '(none)'}\n\n"
            f"## Privacy\n\n{meta.get('privacy', 'public')}\n")


def link_or_copy(asset: pathlib.Path, dest: pathlib.Path) -> str:
    """Symlink the mp4 next to its card; fall back to a real copy across filesystems."""
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    try:
        dest.symlink_to(asset.resolve())
        return "symlink"
    except OSError:
        shutil.copy2(asset, dest)
        return "copy"


class Publisher(abc.ABC):
    platform: str = "base"

    def __init__(self, *, repo: pathlib.Path = REPO) -> None:
        self.repo = pathlib.Path(repo)

    @abc.abstractmethod
    def capabilities(self) -> dict:
        """What this publisher can do right now (credentials present, limits, form variant)."""

    def preflight(self) -> PublishResult | None:
        """Return a not-ok PublishResult to abort before touching the asset, or None to proceed."""
        return None

    @abc.abstractmethod
    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        """Platform-specific publish. Raise or return a not-ok result to trigger queue()."""

    def queue(self, asset: pathlib.Path, meta: dict, detail: str) -> PublishResult:
        folder = self.repo / "marketing" / "publish-queue" / self.platform
        folder.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now().astimezone()
        slug = meta.get("slug", asset.stem)
        card = folder / f"{now.strftime('%Y-%m-%d')}-{slug}.md"
        n = 2
        while card.exists():
            card = folder / f"{now.strftime('%Y-%m-%d')}-{slug}-{n}.md"
            n += 1
        card.write_text(queue_card_body(self.platform, meta, detail, asset.name, now),
                        encoding="utf-8")
        link_or_copy(asset, folder / asset.name)
        return PublishResult(platform=self.platform, ok=False, url=None,
                             queued_path=str(card.relative_to(self.repo)), detail=detail)

    def publish(self, asset: pathlib.Path, meta: dict, dry_run: bool) -> PublishResult:
        asset = pathlib.Path(asset)
        if not asset.exists():
            raise FileNotFoundError(f"asset not found: {asset}")
        if dry_run:
            return PublishResult(platform=self.platform, ok=True, url=None, queued_path=None,
                                 detail=(f"dry-run: would publish {asset.name} to {self.platform} "
                                         f"as {meta.get('title', '')!r} "
                                         f"[{meta.get('privacy', 'public')}]"))
        blocked = self.preflight()
        if blocked is not None:
            return self.queue(asset, meta, blocked.detail)
        try:
            result = self._do_publish(asset, meta)
        except Exception as exc:  # noqa: BLE001 — queues, not silent failures
            return self.queue(asset, meta, f"{type(exc).__name__}: {exc}")
        if not result.ok:
            return self.queue(asset, meta, result.detail)
        return result
```

- [ ] **Step 4: Run the base test to verify it passes**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_publishers_base.py -q`
Expected: PASS, 8 tests.

- [ ] **Step 5: Write the failing test for the Upload-Post client**

Create `tests/test_publishers_upload_post.py`:

```python
"""scripts/publishers/upload_post.py — the REST client, its form, and its failure modes."""
import pathlib

from publishers import upload_post as up

META = {"slug": "asc842-liability", "title": "ASC 842 Lease Liability in Excel #Shorts",
        "description": "PV of the remaining payments.", "privacy": "public",
        "tags": ["ASC 842", "Excel"]}


def _fields(platform, meta=META):
    return dict(up.build_form(platform, meta))


def test_endpoint_and_auth_header_match_the_documented_api():
    assert up.API_URL == "https://api.upload-post.com/api/upload"
    assert up.auth_header("abc123") == {"Authorization": "Apikey abc123"}
    assert up.FILE_FIELD == "video"
    assert up.PLATFORM_FIELD == "platform[]"


def test_build_form_always_sends_user_platform_title_and_description():
    pairs = up.build_form("youtube", META)
    assert ("platform[]", "youtube") in pairs
    f = dict(pairs)
    assert f["user"] == up.DEFAULT_PROFILE
    assert f["title"] == "ASC 842 Lease Liability in Excel #Shorts"
    assert f["description"] == "PV of the remaining payments."


def test_build_form_maps_youtube_privacy_tags_and_category():
    f = _fields("youtube")
    assert f["privacyStatus"] == "public"
    assert f["categoryId"] == "27"                  # Education, same as youtube_publish.py
    assert f["selfDeclaredMadeForKids"] == "false"
    assert dict(up.build_form("youtube", {**META, "privacy": "unlisted"}))["privacyStatus"] == "unlisted"


def test_build_form_maps_tiktok_privacy_level_and_direct_post():
    f = _fields("tiktok")
    assert f["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert f["post_mode"] == "DIRECT_POST"
    assert dict(up.build_form("tiktok", {**META, "privacy": "private"}))["privacy_level"] == "SELF_ONLY"


def test_build_form_maps_instagram_to_reels_shared_to_feed():
    f = _fields("instagram")
    assert f["media_type"] == "REELS"
    assert f["share_to_feed"] == "true"


def test_build_form_truncates_the_title_to_the_youtube_limit():
    f = dict(up.build_form("youtube", {**META, "title": "A" * 150}))
    assert len(f["title"]) == 100


def test_parse_response_reads_the_per_platform_url():
    res = up.parse_response("youtube", 200, {
        "success": True,
        "results": {"youtube": {"success": True, "url": "https://youtube.com/watch?v=VID",
                                "video_id": "VID"}},
        "usage": {"count": 12, "limit": 100}})
    assert res.ok is True
    assert res.url == "https://youtube.com/watch?v=VID"
    assert "12/100" in res.detail


def test_parse_response_reports_a_per_platform_failure_inside_a_200():
    res = up.parse_response("tiktok", 200, {
        "success": True,
        "results": {"tiktok": {"success": False, "error": "account not connected"}}})
    assert res.ok is False
    assert "account not connected" in res.detail


def test_parse_response_surfaces_the_http_error_message():
    res = up.parse_response("tiktok", 403, {
        "success": False, "message": "TikTok uploads not available on Free plan."})
    assert res.ok is False
    assert "403" in res.detail
    assert "Free plan" in res.detail


def test_parse_response_handles_an_async_accepted_upload():
    res = up.parse_response("youtube", 200, {
        "success": True, "message": "Upload initiated successfully in background.",
        "request_id": "1a2b3c", "total_platforms": 1})
    assert res.ok is False                       # no url yet -> queue it rather than claim success
    assert "1a2b3c" in res.detail


def test_publisher_without_an_api_key_queues_instead_of_calling_the_network(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")

    def explode(*a, **k):
        raise AssertionError("no HTTP call may happen without a key")

    monkeypatch.setattr(up, "_http_post", explode)
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert res.queued_path is not None
    assert "UPLOAD_POST_KEY" in res.detail
    assert (tmp_path / res.queued_path).exists()


def test_publisher_with_a_key_posts_the_multipart_form_and_returns_the_url(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    seen = {}

    def fake_post(url, headers, fields, file_field, file_path):
        seen.update(url=url, headers=headers, fields=fields,
                    file_field=file_field, file_path=str(file_path))
        return 200, {"success": True,
                     "results": {"youtube": {"success": True, "url": "https://youtu.be/VID",
                                             "video_id": "VID"}}}

    monkeypatch.setattr(up, "_http_post", fake_post)
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is True
    assert res.url == "https://youtu.be/VID"
    assert seen["url"] == up.API_URL
    assert seen["headers"]["Authorization"] == "Apikey k-123"
    assert seen["file_field"] == "video"
    assert ("platform[]", "youtube") in seen["fields"]


def test_publisher_queues_on_an_http_error(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (
        429, {"success": False, "message": "This upload would exceed your monthly limit."}))
    res = up.UploadPostPublisher("tiktok", repo=tmp_path).publish(asset, META, dry_run=False)
    assert res.ok is False
    assert "monthly limit" in res.detail
    card = tmp_path / res.queued_path
    assert card.exists()
    assert (card.parent / "x.mp4").exists()


def test_dry_run_makes_no_call_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_POST_KEY", "k-123")
    asset = tmp_path / "x.mp4"
    asset.write_bytes(b"v")
    monkeypatch.setattr(up, "_http_post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no")))
    res = up.UploadPostPublisher("youtube", repo=tmp_path).publish(asset, META, dry_run=True)
    assert res.ok is True and res.url is None
    assert not (tmp_path / "marketing").exists()


def test_capabilities_reports_the_key_state_and_the_form_variant(tmp_path, monkeypatch):
    monkeypatch.delenv("UPLOAD_POST_KEY", raising=False)
    caps = up.UploadPostPublisher("tiktok", repo=tmp_path).capabilities()
    assert caps["platform"] == "tiktok"
    assert caps["has_key"] is False
    assert caps["form_variant"] == "platform[]"
    assert caps["needs_paid_plan"] is True          # TikTok is not on the free tier
    assert pathlib.Path(caps["queue_dir"]).name == "tiktok"
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_publishers_upload_post.py -q`
Expected: FAIL — `ImportError: cannot import name 'upload_post'`.

- [ ] **Step 7: Write `scripts/publishers/upload_post.py`**

```python
#!/usr/bin/env python3
"""Upload-Post REST client (https://docs.upload-post.com/api/upload-video/, read 2026-09-14).

Upload-Post holds audited YouTube / TikTok / Meta credentials, which is why it exists here:
KDesk's own Google Cloud project is un-audited, so its Data-API uploads land locked-private
and cannot be appealed (see marketing plan, "Critical finding").

  POST https://api.upload-post.com/api/upload   multipart/form-data
  Authorization: Apikey <UPLOAD_POST_KEY>
  video=@file.mp4   platform[]=youtube   user=<profile>   title=...   description=...

Free tier: 10 uploads/month, YouTube + Instagram. TikTok needs the paid plan.
Key from env UPLOAD_POST_KEY; profile from env UPLOAD_POST_PROFILE (default "kdesk").
No key, or any non-2xx, or a per-platform failure -> queue() (never a silent failure).
requests is imported lazily so this module stays stdlib-importable for tests.
"""
from __future__ import annotations

import json
import os
import pathlib

from publishers.base import Publisher, PublishResult

API_URL = "https://api.upload-post.com/api/upload"
USERS_URL = "https://api.upload-post.com/api/uploadposts/users"
FILE_FIELD = "video"
PLATFORM_FIELD = "platform[]"
DEFAULT_PROFILE = "kdesk"
TITLE_MAX = 100          # YouTube's limit; the shortest of the three, so it is the safe cap
FREE_TIER_PLATFORMS = ("youtube", "instagram")

# privacy (our vocabulary) -> per-platform value
TIKTOK_PRIVACY = {"public": "PUBLIC_TO_EVERYONE", "unlisted": "SELF_ONLY", "private": "SELF_ONLY"}


def auth_header(api_key: str) -> dict:
    return {"Authorization": f"Apikey {api_key}"}


def profile() -> str:
    return os.environ.get("UPLOAD_POST_PROFILE", DEFAULT_PROFILE)


def build_form(platform: str, meta: dict) -> list[tuple[str, str]]:
    """Every non-file multipart field, in a stable order, for one platform."""
    privacy = meta.get("privacy", "public")
    fields: list[tuple[str, str]] = [
        (PLATFORM_FIELD, platform),
        ("user", profile()),
        ("title", str(meta.get("title", ""))[:TITLE_MAX]),
        ("description", str(meta.get("description", ""))),
    ]
    if platform == "youtube":
        fields += [("privacyStatus", privacy),
                   ("categoryId", str(meta.get("category_id", "27"))),
                   ("selfDeclaredMadeForKids", "false")]
        for tag in meta.get("tags", []):
            fields.append(("tags", str(tag)))
    elif platform == "tiktok":
        fields += [("privacy_level", TIKTOK_PRIVACY.get(privacy, "SELF_ONLY")),
                   ("post_mode", "DIRECT_POST")]
    elif platform == "instagram":
        fields += [("media_type", meta.get("media_type", "REELS")),
                   ("share_to_feed", "true")]
    return fields


def parse_response(platform: str, status: int, payload: dict) -> PublishResult:
    def fail(detail: str) -> PublishResult:
        return PublishResult(platform=platform, ok=False, url=None, queued_path=None, detail=detail)

    if status >= 300 or not payload.get("success"):
        return fail(f"Upload-Post HTTP {status}: "
                    f"{payload.get('message') or payload.get('error') or json.dumps(payload)[:200]}")
    results = payload.get("results") or {}
    if platform not in results:
        if payload.get("request_id"):
            return fail(f"Upload-Post accepted the upload asynchronously "
                        f"(request_id {payload['request_id']}); no url yet — "
                        f"check GET /api/uploadposts/status?request_id={payload['request_id']}")
        if payload.get("job_id"):
            return fail(f"Upload-Post scheduled the upload (job_id {payload['job_id']}); no url yet")
        return fail(f"Upload-Post returned no result for {platform}: {json.dumps(payload)[:200]}")
    entry = results[platform]
    if not entry.get("success"):
        return fail(f"Upload-Post {platform} failed: "
                    f"{entry.get('error') or entry.get('message') or json.dumps(entry)[:200]}")
    url = entry.get("url")
    if not url:
        pid = entry.get("post_id") or entry.get("video_id")
        return fail(f"Upload-Post {platform} succeeded but returned no url (post_id {pid})")
    usage = payload.get("usage") or {}
    used = f" · usage {usage.get('count')}/{usage.get('limit')}" if usage else ""
    return PublishResult(platform=platform, ok=True, url=url, queued_path=None,
                         detail=f"published via Upload-Post{used}")


def _http_post(url: str, headers: dict, fields: list[tuple[str, str]],
               file_field: str, file_path: pathlib.Path) -> tuple[int, dict]:
    """The one network seam. Tests monkeypatch this; nothing else does I/O."""
    import requests  # lazy: absent in the test environment
    with open(file_path, "rb") as fh:
        resp = requests.post(url, headers=headers, data=fields,
                             files={file_field: (file_path.name, fh, "video/mp4")}, timeout=600)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, {"success": False, "message": resp.text[:500]}


class UploadPostPublisher(Publisher):
    def __init__(self, platform: str, *, repo: pathlib.Path | None = None,
                 api_key: str | None = None) -> None:
        from publishers.base import REPO
        super().__init__(repo=repo if repo is not None else REPO)
        self.platform = platform
        self._api_key = api_key

    def api_key(self) -> str | None:
        return self._api_key or os.environ.get("UPLOAD_POST_KEY")

    def capabilities(self) -> dict:
        return {"platform": self.platform,
                "transport": "upload-post",
                "endpoint": API_URL,
                "form_variant": PLATFORM_FIELD,
                "has_key": bool(self.api_key()),
                "profile": profile(),
                "needs_paid_plan": self.platform not in FREE_TIER_PLATFORMS,
                "queue_dir": str(self.repo / "marketing" / "publish-queue" / self.platform)}

    def preflight(self) -> PublishResult | None:
        if not self.api_key():
            return PublishResult(
                platform=self.platform, ok=False, url=None, queued_path=None,
                detail=("No UPLOAD_POST_KEY in the environment. Set it "
                        "(export UPLOAD_POST_KEY=...) after connecting the account at "
                        "https://www.upload-post.com/, or post this card by hand."))
        return None

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        status, payload = _http_post(API_URL, auth_header(self.api_key()),
                                     build_form(self.platform, meta), FILE_FIELD, asset)
        return parse_response(self.platform, status, payload)
```

- [ ] **Step 8: Run the Upload-Post test to verify it passes**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_publishers_upload_post.py -q`
Expected: PASS, 15 tests.

- [ ] **Step 9: Write the three thin wrappers**

`scripts/publishers/youtube.py`:

```python
#!/usr/bin/env python3
"""YouTube Shorts via Upload-Post (NOT the Data API — see scripts/video/youtube_publish.py)."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class YouTubePublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("youtube", **kw)
```

`scripts/publishers/tiktok.py`:

```python
#!/usr/bin/env python3
"""TikTok via Upload-Post. Needs the paid plan; on the free tier this queues a card."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class TikTokPublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("tiktok", **kw)
```

`scripts/publishers/instagram.py`:

```python
#!/usr/bin/env python3
"""Instagram Reels via Upload-Post (media_type=REELS, shared to feed)."""
from __future__ import annotations

from publishers.upload_post import UploadPostPublisher


class InstagramPublisher(UploadPostPublisher):
    def __init__(self, **kw):
        super().__init__("instagram", **kw)
```

- [ ] **Step 10: Write the failing test for the site publisher**

Create `tests/test_publishers_site.py`:

```python
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
```

- [ ] **Step 11: Write `scripts/publishers/site.py`**

```python
#!/usr/bin/env python3
"""Cross-post a published Short to the Hugo site as content/shorts/<date>-<slug>.md.

Runs after a video publisher returns a url: the post embeds that url. With no video_url
there is nothing to embed, so it queues rather than publishing an empty page.
Hugo resolves layouts by `type`, so the frontmatter sets type: "shorts" explicitly
(see CLAUDE.md: `layout:` alone silently falls back to _default/single.html).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

from publishers.base import Publisher, PublishResult

SITE_BASE = "https://kdeskaccounting.com"


def video_id(url: str) -> str | None:
    url = url.split("?")[0].rstrip("/")
    for marker in ("/shorts/", "/embed/", "youtu.be/", "watch?v="):
        if marker in url:
            return url.rsplit("/", 1)[-1]
    return None


def post_path(repo: pathlib.Path, date: dt.date, slug: str) -> pathlib.Path:
    return pathlib.Path(repo) / "content" / "shorts" / f"{date.isoformat()}-{slug}.md"


def post_markdown(date: dt.date, slug: str, meta: dict) -> str:
    vid = video_id(meta.get("video_url", "")) or ""
    embed = (f'<div class="kd-short-embed">\n'
             f'  <iframe src="https://www.youtube.com/embed/{vid}" title='
             f'{json.dumps(meta.get("title", ""))} frameborder="0" allowfullscreen '
             f'loading="lazy"></iframe>\n</div>')
    tags = ", ".join(json.dumps(t) for t in meta.get("tags", []))
    front = "\n".join([
        "---",
        f"title: {json.dumps(meta.get('title', slug))}",
        f"date: {date.isoformat()}",
        'type: "shorts"',
        f"description: {json.dumps(meta.get('description', '').splitlines()[0] if meta.get('description') else '')}",
        f"tags: [{tags}]",
        f"product: {json.dumps(meta.get('product', ''))}",
        f"video_url: {json.dumps(meta.get('video_url', ''))}",
        'author: "KDesk Accounting"',
        "ShowToc: false",
        "---",
        "",
    ])
    return f"{front}{embed}\n\n{meta.get('description', '')}\n"


class SitePublisher(Publisher):
    platform = "site"

    def __init__(self, *, repo: pathlib.Path | None = None, today: dt.date | None = None) -> None:
        from publishers.base import REPO
        super().__init__(repo=repo if repo is not None else REPO)
        self.today = today or dt.date.today()

    def capabilities(self) -> dict:
        return {"platform": "site", "transport": "filesystem",
                "content_dir": str(self.repo / "content" / "shorts"),
                "base_url": SITE_BASE}

    def preflight(self) -> PublishResult | None:
        return None

    def _do_publish(self, asset: pathlib.Path, meta: dict) -> PublishResult:
        if not meta.get("video_url"):
            return PublishResult(platform="site", ok=False, url=None, queued_path=None,
                                 detail="meta has no video_url — publish the video first, "
                                        "then re-run publish.py --platform site")
        slug = meta.get("slug", asset.stem)
        path = post_path(self.repo, self.today, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(post_markdown(self.today, slug, meta), encoding="utf-8")
        return PublishResult(platform="site", ok=True,
                             url=f"{SITE_BASE}/shorts/{self.today.isoformat()}-{slug}/",
                             queued_path=None, detail=f"wrote {path.relative_to(self.repo)}")
```

- [ ] **Step 12: Create the Hugo section index**

`content/shorts/_index.md`:

```markdown
---
title: "Shorts"
description: "Short videos from the KDesk Accounting workbooks — one idea, under a minute."
type: "shorts"
---

Every Short published from the KDesk workbooks. One idea each, under a minute.
```

Also create `marketing/publish-queue/.gitkeep` (empty file) so the queue folder exists in a fresh clone.

- [ ] **Step 13: Write `scripts/publishers/publish.py`**

```python
#!/usr/bin/env python3
"""One entry point for every publisher.

  python3 scripts/publishers/publish.py --platform youtube --asset X.mp4 --meta meta.json [--dry-run]
  python3 scripts/publishers/publish.py --platform youtube,instagram,site --asset X.mp4 --meta meta.json
  python3 scripts/publishers/publish.py --capabilities

meta.json: {"slug": "...", "title": "...", "description": "...", "privacy": "public",
            "tags": ["..."], "product": "asc842", "video_url": "(filled by a video publisher)"}

Exit code 0 only when every requested platform published. A queued card is a non-zero exit
on purpose: the daily job must surface it in the digest.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ledger  # noqa: E402

from publishers.base import REPO  # noqa: E402
from publishers.instagram import InstagramPublisher  # noqa: E402
from publishers.site import SitePublisher  # noqa: E402
from publishers.tiktok import TikTokPublisher  # noqa: E402
from publishers.youtube import YouTubePublisher  # noqa: E402

PUBLISHERS = {"youtube": YouTubePublisher, "tiktok": TikTokPublisher,
              "instagram": InstagramPublisher, "site": SitePublisher}


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish one asset to one or more platforms.")
    ap.add_argument("--platform", help="comma-separated: " + ", ".join(PUBLISHERS))
    ap.add_argument("--asset", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--capabilities", action="store_true", help="print each publisher's state and exit")
    a = ap.parse_args()

    if a.capabilities:
        for name, cls in PUBLISHERS.items():
            print(f"{name:<10} {json.dumps(cls().capabilities(), sort_keys=True)}")
        return 0
    if not (a.platform and a.asset and a.meta):
        ap.error("--platform, --asset and --meta are required unless --capabilities is given")

    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    rc = 0
    for name in [p.strip() for p in a.platform.split(",") if p.strip()]:
        if name not in PUBLISHERS:
            print(f"unknown platform {name!r}; known: {', '.join(PUBLISHERS)}", file=sys.stderr)
            rc = 2
            continue
        result = PUBLISHERS[name]().publish(a.asset, meta, a.dry_run)
        target = result.url or result.queued_path or "(dry-run)"
        print(f"{name:<10} {'ok  ' if result.ok else 'QUEUED'} {target}  {result.detail}")
        if result.url and name in ("youtube", "tiktok", "instagram"):
            meta["video_url"] = meta.get("video_url") or result.url
        if a.dry_run:
            continue
        ledger.append(
            action=(f"Published {a.asset.name} to {name}: "
                    f"{result.url or 'QUEUED ' + str(result.queued_path)}. {result.detail}"),
            tier=1, status="executed",
            reasoning=("T1 auto-publish after the fact-check gate (2026-09-14 autonomy decision); "
                       "a failure queues a paste-ready card instead of dropping the post."),
            files=[str(result.queued_path)] if result.queued_path else [])
        if not result.ok:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 14: Run the three new test files**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_publishers_base.py tests/test_publishers_upload_post.py tests/test_publishers_site.py -q`
Expected: PASS, 30 tests.

- [ ] **Step 15: Verify the CLI end to end with a dry run (no network, no key needed)**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 scripts/publishers/publish.py --capabilities
cat > /tmp/meta.json <<'JSON'
{"slug": "asc842-liability",
 "title": "ASC 842 Lease Liability Calculation in Excel #Shorts",
 "description": "Lease liability = present value of the remaining payments.",
 "privacy": "public", "tags": ["ASC 842", "Excel"], "product": "asc842"}
JSON
python3 scripts/publishers/publish.py --platform youtube,instagram,site \
  --asset scripts/video/build/asc842/asc842-short-liability.mp4 --meta /tmp/meta.json --dry-run
git status --porcelain
```

Expected: `--capabilities` prints four JSON lines (`has_key` false until `UPLOAD_POST_KEY` is exported); the dry run prints three `ok` lines starting `dry-run: would publish`; `git status` is clean — a dry run writes nothing and appends no ledger line.

- [ ] **Step 16: Run the full suite and commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 69 passed (39 + 30).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/publishers content/shorts/_index.md marketing/publish-queue/.gitkeep \
        tests/test_publishers_base.py tests/test_publishers_upload_post.py tests/test_publishers_site.py
git commit -m "feat(publishers): Upload-Post video publishing with a queue-card fallback

Adds scripts/publishers/: an abstract Publisher whose publish() always dry-runs, always
queues a paste-ready card plus the mp4 on failure, and never raises past the caller; an
Upload-Post REST client encoding the documented multipart form (video + platform[],
Authorization: Apikey) and its per-platform privacy fields; youtube/tiktok/instagram
wrappers; a site publisher writing content/shorts/<date>-<slug>.md; and a publish.py CLI
that logs one ledger line per live publish.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 4: Stop the Data-API uploads and re-upload the 20 locked videos

**Files:**
- Modify: `scripts/video/youtube_publish.py` (module docstring, `main()`, plus three new pure helpers)
- Modify: `tests/test_youtube_publish.py` (add four tests; the existing eight stay green)
- Create: `scripts/video/reupload_locked.py`
- Create: `tests/test_reupload_locked.py`
- Modify: `CLAUDE.md` (the two paragraphs that still tell a future session to "flip in Studio")

**Interfaces:**
- Consumes: `publishers.youtube.YouTubePublisher` and `base.PublishResult` (Task 3); `ledger.append` (Task 1).
- Produces:
  - `youtube_publish.LOCK_FINDING: str` — the one-paragraph finding printed on refusal
  - `youtube_publish.refuse_reason(acknowledged: bool) -> str | None` — `None` only when `acknowledged` is True
  - `reupload_locked.LockedVideo` dataclass: `rec_path: Path`, `key: str | None`, `slug: str`, `kind: str`, `title: str`, `description: str`, `old_url: str`, `video_id: str`
  - `reupload_locked.scan(repo: Path) -> list[LockedVideo]`
  - `reupload_locked.resolve_mp4(repo: Path, item: LockedVideo) -> Path | None`
  - `reupload_locked.update_record(rec_path, key, new_url, payload_loader, payload_writer) -> dict`

**The finding, verified 2026-09-14:** all **20** records across `marketing/video/*/{youtube,short,shorts}.json` carry `"via": "data-api"` and were uploaded 2026-09-04 22:21 → 2026-09-07 07:40. Google's policy (support.google.com/youtube/answer/7300965) is that locked-private uploads from an unverified API project cannot be appealed and must be re-uploaded; passing the audit only unlocks *future* uploads. Verify the count before starting:

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
grep -c '"via": "data-api"' marketing/video/*/*.json | awk -F: '{s+=$2} END {print s}'   # -> 20
```

- [ ] **Step 1: Write the failing tests for the guard**

Append to `tests/test_youtube_publish.py`:

```python
def test_refuse_reason_blocks_an_unacknowledged_upload_and_names_the_replacement():
    reason = yp.refuse_reason(False)
    assert reason is not None
    assert "locked" in reason.lower()
    assert "scripts/publishers/youtube.py" in reason
    assert "--i-understand-locked-private" in reason


def test_refuse_reason_is_none_once_the_flag_is_passed():
    assert yp.refuse_reason(True) is None


def test_lock_finding_states_the_20_videos_and_that_reupload_is_the_only_fix():
    assert "20" in yp.LOCK_FINDING
    assert "re-upload" in yp.LOCK_FINDING.lower()
    assert "cannot be appealed" in yp.LOCK_FINDING.lower()


def test_run_refuses_a_live_upload_without_the_flag_and_never_calls_upload(tmp_path, capsys):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 10)
    job = dict(mp4=mp4, body=yp.video_body("t", "d", []), thumb=None, playlist=None,
               rec_path=tmp_path / "youtube.json", rec={}, key=None, url_fmt="https://youtu.be/{}")

    class _Boom:
        def videos(self):
            raise AssertionError("no upload may be attempted without the acknowledgement flag")

    assert yp.run(job, dry_run=False, yt=_Boom(), acknowledged=False) == 2
    out = capsys.readouterr()
    assert "--i-understand-locked-private" in out.err
    assert not (tmp_path / "youtube.json").exists()


def test_run_still_works_in_dry_run_without_the_flag(tmp_path, capsys):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"0" * 10)
    job = dict(mp4=mp4, body=yp.video_body("t", "d", []), thumb=None, playlist=None,
               rec_path=tmp_path / "youtube.json", rec={}, key=None, url_fmt="https://youtu.be/{}")
    assert yp.run(job, dry_run=True, acknowledged=False) == 0
    assert "(dry-run)" in capsys.readouterr().out
```

The existing `test_run_records_the_url_even_when_the_thumbnail_step_is_forbidden` must also be updated to pass the flag — change its call to:

```python
    assert yp.run(job, dry_run=False, yt=fake, acknowledged=True) == 0
```

- [ ] **Step 2: Run the file to verify the new tests fail**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_youtube_publish.py -q`
Expected: FAIL — `AttributeError: module 'youtube_publish' has no attribute 'refuse_reason'`.

- [ ] **Step 3: Add the guard to `scripts/video/youtube_publish.py`**

Replace the "Note:" paragraph at the end of the module docstring with:

```
DO NOT USE THIS TO UPLOAD. Verified 2026-09-14: every video this script uploaded is locked
private with 0 views and cannot be appealed. Route new uploads through
scripts/publishers/youtube.py (Upload-Post), which holds audited credentials. The pure
helpers here (chapters, descriptions, video_body) are still the source of the metadata.
```

Add, directly under the `TAGS = {...}` block:

```python
LOCK_FINDING = (
    "FINDING (verified 2026-09-14 against support.google.com/youtube/answer/7300965 and the\n"
    "2026-09-07 snapshot in marketing/seo-tracking/youtube-snapshots.jsonl): all 20 videos this\n"
    "script uploaded via the YouTube Data API are locked PRIVATE with 0 views. Google: an upload\n"
    "locked private by an unverified API project cannot be appealed and must be re-uploaded.\n"
    "Passing the compliance audit only unlocks FUTURE uploads. The 10 videos uploaded through\n"
    "Chrome on 2026-09-02 are public and getting views. The 'flip in Studio' step that used to be\n"
    "in CLAUDE.md never worked.")

REPLACEMENT_PATH = (
    "Use Upload-Post instead — it holds audited YouTube credentials:\n"
    "  python3 scripts/publishers/publish.py --platform youtube --asset <mp4> --meta <meta.json>\n"
    "To re-publish the 20 locked videos with their original titles and descriptions:\n"
    "  python3 scripts/video/reupload_locked.py --dry-run     # list what it would do\n"
    "  python3 scripts/video/reupload_locked.py")


def refuse_reason(acknowledged: bool) -> str | None:
    """None when the caller passed --i-understand-locked-private; the refusal text otherwise."""
    if acknowledged:
        return None
    return (f"{LOCK_FINDING}\n\n{REPLACEMENT_PATH}\n\n"
            "If you have a reason to upload through the Data API anyway (for example the audit has\n"
            "passed and you verified a test upload is public), re-run with "
            "--i-understand-locked-private.")
```

Change `run(...)` to take the flag and refuse before any API work — replace its first three lines:

```python
def run(job: dict, dry_run: bool, yt=None, *, acknowledged: bool = False) -> int:
    if not needs_upload(job["rec"]):
        print(f"already published: {job['rec']['url']}"); return 0
    print(f"{job['mp4'].name}: {job['body']['snippet']['title']}  [{job['body']['status']['privacyStatus']}]")
    if dry_run:
        print("  (dry-run) exists:", job["mp4"].exists(), "| thumb:", job["thumb"], "| playlist:", job["playlist"])
        print("  description:\n   ", job["body"]["snippet"]["description"].replace("\n", "\n    ")[:600]); return 0
    reason = refuse_reason(acknowledged)
    if reason is not None:
        print(reason, file=sys.stderr)
        return 2
    if not job["mp4"].exists(): raise SystemExit(f"missing {job['mp4']} — render it first")
```

Add the flag in `main()` — after the `--dry-run` argument line, insert:

```python
    ap.add_argument("--i-understand-locked-private", dest="acknowledged", action="store_true",
                    help="acknowledge that Data-API uploads land locked-private and upload anyway")
```

and change the last line of `main()` to:

```python
    return run(job, a.dry_run, acknowledged=a.acknowledged)
```

- [ ] **Step 4: Run the youtube_publish tests to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_youtube_publish.py -q`
Expected: PASS, 13 tests (8 existing + 5 new).

- [ ] **Step 5: Verify the guard refuses from the command line**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
uv run scripts/video/youtube_publish.py --kind short --slug asc842 --variant liability --dry-run; echo "rc=$?"
```

Expected: the dry-run path still prints the title and description, `rc=0`. (A live run would print the finding and exit 2; do not run one.)

- [ ] **Step 6: Write the failing test for `reupload_locked`**

Create `tests/test_reupload_locked.py`:

```python
"""scripts/video/reupload_locked.py — re-publish the 20 locked-private Data-API uploads."""
import json
import pathlib

import reupload_locked as rl


def _repo(tmp_path):
    mv = tmp_path / "marketing" / "video"
    (mv / "asc842").mkdir(parents=True)
    (mv / "rsu-planner").mkdir(parents=True)
    (mv / "asc842" / "shorts.json").write_text(json.dumps({
        "liability": {"title": "Lease liability #Shorts", "description": "PV of payments.",
                      "url": "https://youtube.com/shorts/n1BlUeme0k4", "video_id": "n1BlUeme0k4",
                      "uploaded": "2026-09-04 22:21", "via": "data-api"},
        "rollforward": {"title": "Rollforward #Shorts", "description": "Opening + additions.",
                        "url": "https://youtube.com/shorts/nHSki3m6fRI", "video_id": "nHSki3m6fRI",
                        "uploaded": "2026-09-04 22:21", "via": "upload-post"}}))
    (mv / "asc842" / "short.json").write_text(json.dumps({
        "title": "Legacy short", "description": "d", "url": "https://youtube.com/shorts/OrgGKSkFHoY",
        "video_id": "OrgGKSkFHoY"}))                                   # no "via" -> Chrome-era, skip
    (mv / "rsu-planner" / "youtube.json").write_text(json.dumps({
        "title": "RSU walkthrough", "description": "d", "url": "https://youtu.be/-rfZDelJQMY",
        "video_id": "-rfZDelJQMY", "uploaded": "2026-09-05 09:11", "via": "data-api"}))
    return tmp_path


def test_scan_finds_only_the_data_api_records(tmp_path):
    items = rl.scan(_repo(tmp_path))
    assert [(i.slug, i.kind, i.key) for i in items] == [
        ("asc842", "shorts", "liability"), ("rsu-planner", "youtube", None)]


def test_scan_carries_the_original_title_description_and_old_url(tmp_path):
    item = rl.scan(_repo(tmp_path))[0]
    assert item.title == "Lease liability #Shorts"
    assert item.description == "PV of payments."
    assert item.old_url == "https://youtube.com/shorts/n1BlUeme0k4"
    assert item.video_id == "n1BlUeme0k4"


def test_resolve_mp4_prefers_the_named_short_variant_in_the_build_dir(tmp_path):
    repo = _repo(tmp_path)
    build = repo / "scripts" / "video" / "build" / "asc842"
    build.mkdir(parents=True)
    (build / "asc842-short-liability.mp4").write_bytes(b"v")
    item = rl.scan(repo)[0]
    assert rl.resolve_mp4(repo, item) == build / "asc842-short-liability.mp4"


def test_resolve_mp4_finds_the_walkthrough_by_slug(tmp_path):
    repo = _repo(tmp_path)
    build = repo / "scripts" / "video" / "build" / "rsu-planner"
    build.mkdir(parents=True)
    (build / "rsu-planner.mp4").write_bytes(b"v")
    item = rl.scan(repo)[1]
    assert rl.resolve_mp4(repo, item) == build / "rsu-planner.mp4"


def test_resolve_mp4_returns_none_when_nothing_is_on_disk(tmp_path):
    repo = _repo(tmp_path)
    assert rl.resolve_mp4(repo, rl.scan(repo)[0]) is None


def test_expected_mp4_names_cover_both_legacy_and_named_shorts():
    assert rl.expected_mp4_name("asc842", "shorts", "liability") == "asc842-short-liability.mp4"
    assert rl.expected_mp4_name("asc842", "short", None) == "asc842-short.mp4"
    assert rl.expected_mp4_name("asc842", "youtube", None) == "asc842.mp4"


def test_update_record_rewrites_the_url_and_flips_via_for_a_named_variant(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[0]
    rl.update_record(item, "https://youtube.com/shorts/NEW111")
    saved = json.loads((repo / "marketing/video/asc842/shorts.json").read_text())
    assert saved["liability"]["url"] == "https://youtube.com/shorts/NEW111"
    assert saved["liability"]["via"] == "upload-post"
    assert saved["liability"]["replaced_url"] == "https://youtube.com/shorts/n1BlUeme0k4"
    assert saved["rollforward"]["url"] == "https://youtube.com/shorts/nHSki3m6fRI"   # untouched


def test_update_record_rewrites_a_flat_record(tmp_path):
    repo = _repo(tmp_path)
    item = rl.scan(repo)[1]
    rl.update_record(item, "https://youtu.be/NEW222")
    saved = json.loads((repo / "marketing/video/rsu-planner/youtube.json").read_text())
    assert saved["url"] == "https://youtu.be/NEW222"
    assert saved["via"] == "upload-post"
    assert saved["replaced_url"] == "https://youtu.be/-rfZDelJQMY"


def test_meta_for_builds_the_publisher_payload(tmp_path):
    item = rl.scan(_repo(tmp_path))[0]
    meta = rl.meta_for(item)
    assert meta == {"slug": "asc842-liability", "title": "Lease liability #Shorts",
                    "description": "PV of payments.", "privacy": "public", "product": "asc842",
                    "tags": []}
```

- [ ] **Step 7: Write `scripts/video/reupload_locked.py`**

```python
#!/usr/bin/env python3
"""Re-publish, through Upload-Post, every video that the YouTube Data API locked private.

Verified 2026-09-14: 20 records across marketing/video/*/{youtube,short,shorts}.json carry
"via": "data-api". Those uploads are locked private with 0 views and cannot be appealed
(support.google.com/youtube/answer/7300965) — they have to be re-uploaded by a scheduler
holding audited credentials. This drives scripts/publishers/youtube.py for each one with
the original title and description, then rewrites the record with the new url and
"via": "upload-post", keeping the old url under "replaced_url".

  python3 scripts/video/reupload_locked.py --dry-run          # list every item and its mp4
  python3 scripts/video/reupload_locked.py [--slug asc842] [--limit 5]

mp4 resolution order: scripts/video/build/<slug>/<name>.mp4 (local renders), then any mp4
downloaded from the GitHub release media-2026-09 into that same folder:
  gh release download media-2026-09 --pattern '<slug>.mp4' --dir scripts/video/build/<slug>
Stdlib only at import time.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402

RECORD_FILES = ("youtube.json", "short.json", "shorts.json")
RELEASE_TAG = "media-2026-09"


@dataclasses.dataclass(frozen=True)
class LockedVideo:
    rec_path: pathlib.Path
    key: str | None          # variant name inside shorts.json, else None
    slug: str
    kind: str                # "youtube" | "short" | "shorts"
    title: str
    description: str
    old_url: str
    video_id: str


def _locked(entry: dict) -> bool:
    return isinstance(entry, dict) and entry.get("via") == "data-api" and bool(entry.get("url"))


def scan(repo: pathlib.Path = REPO) -> list[LockedVideo]:
    out: list[LockedVideo] = []
    base = pathlib.Path(repo) / "marketing" / "video"
    for slug_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for name in RECORD_FILES:
            path = slug_dir / name
            if not path.exists():
                continue
            kind = name.removesuffix(".json")
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.items() if kind == "shorts" else [(None, data)]
            for key, entry in items:
                if not _locked(entry):
                    continue
                out.append(LockedVideo(
                    rec_path=path, key=key, slug=slug_dir.name, kind=kind,
                    title=entry.get("title", ""), description=entry.get("description", ""),
                    old_url=entry["url"], video_id=entry.get("video_id", "")))
    return out


def expected_mp4_name(slug: str, kind: str, key: str | None) -> str:
    if kind == "youtube":
        return f"{slug}.mp4"
    if kind == "short":
        return f"{slug}-short.mp4"
    return f"{slug}-short-{key}.mp4"


def resolve_mp4(repo: pathlib.Path, item: LockedVideo) -> pathlib.Path | None:
    candidate = (pathlib.Path(repo) / "scripts" / "video" / "build" / item.slug
                 / expected_mp4_name(item.slug, item.kind, item.key))
    return candidate if candidate.exists() else None


def meta_for(item: LockedVideo) -> dict:
    slug = f"{item.slug}-{item.key}" if item.key else item.slug
    return {"slug": slug, "title": item.title, "description": item.description,
            "privacy": "public", "product": item.slug, "tags": []}


def update_record(item: LockedVideo, new_url: str) -> dict:
    data = json.loads(item.rec_path.read_text(encoding="utf-8"))
    entry = data[item.key] if item.key else data
    entry["replaced_url"] = entry.get("url")
    entry["url"] = new_url
    entry["via"] = "upload-post"
    entry["video_id"] = new_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    item.rec_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-upload the locked-private Data-API videos.")
    ap.add_argument("--slug", help="only this product slug")
    ap.add_argument("--limit", type=int, help="stop after N uploads (Upload-Post free tier is 10/mo)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = [i for i in scan(REPO) if not a.slug or i.slug == a.slug]
    print(f"{len(items)} locked-private record(s) with via=data-api")
    if a.dry_run:
        for item in items:
            mp4 = resolve_mp4(REPO, item)
            where = str(mp4.relative_to(REPO)) if mp4 else (
                f"MISSING — gh release download {RELEASE_TAG} --pattern "
                f"'{expected_mp4_name(item.slug, item.kind, item.key)}' "
                f"--dir scripts/video/build/{item.slug}")
            print(f"  {item.slug:<15} {item.kind:<8} {str(item.key):<12} {item.old_url}\n"
                  f"      -> {where}\n      title: {item.title[:80]}")
        return 0

    from publishers.youtube import YouTubePublisher
    pub = YouTubePublisher(repo=REPO)
    done = failed = 0
    for item in items:
        if a.limit is not None and done >= a.limit:
            print(f"stopping at --limit {a.limit}")
            break
        mp4 = resolve_mp4(REPO, item)
        if mp4 is None:
            failed += 1
            print(f"  {item.slug}/{item.key or item.kind}: no local mp4 — "
                  f"gh release download {RELEASE_TAG} --pattern "
                  f"'{expected_mp4_name(item.slug, item.kind, item.key)}' "
                  f"--dir scripts/video/build/{item.slug}")
            continue
        result = pub.publish(mp4, meta_for(item), dry_run=False)
        if result.ok and result.url:
            update_record(item, result.url)
            done += 1
            print(f"  {item.slug}/{item.key or item.kind}: {item.old_url} -> {result.url}")
        else:
            failed += 1
            print(f"  {item.slug}/{item.key or item.kind}: QUEUED {result.queued_path} "
                  f"({result.detail})")
    ledger.append(
        action=(f"Re-uploaded {done} of {len(items)} locked-private YouTube videos through "
                f"Upload-Post ({failed} queued or missing an mp4). The Data-API uploads were "
                f"locked private with 0 views and cannot be appealed; the records now carry "
                f'"via": "upload-post" with the old url under "replaced_url".'),
        tier=1, status="executed",
        reasoning=("Google: a locked-private upload from an unverified API project must be "
                   "re-uploaded. Upload-Post holds audited credentials, so its uploads are public."),
        files=sorted({str(i.rec_path.relative_to(REPO)) for i in items}))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run the reupload tests to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_reupload_locked.py -q`
Expected: PASS, 9 tests.

- [ ] **Step 9: Verify the dry run against the real repo**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 scripts/video/reupload_locked.py --dry-run | head -30
python3 scripts/video/reupload_locked.py --dry-run | grep -c '^  '
git status --porcelain
```

Expected: the first line reads `20 locked-private record(s) with via=data-api`; every item resolves to a path under `scripts/video/build/` (all 20 mp4s were confirmed present on 2026-09-14) rather than `MISSING`; `git status` is clean.

- [ ] **Step 10: Correct `CLAUDE.md`**

Two places still tell a future session that flipping in Studio works. Replace them:

1. In the "Useful commands" block, replace the comment line
   `# Publish to YouTube via the Data API (lands PRIVATE until the GCP project passes YouTube's API audit — flip in Studio)`
   and the `youtube_publish.py` line beneath it with:

   ```bash
   # DO NOT publish through the Data API — those uploads are locked private and cannot be appealed.
   python3 scripts/publishers/publish.py --platform youtube --asset <mp4> --meta <meta.json> [--dry-run]
   python3 scripts/video/reupload_locked.py --dry-run     # the 20 locked videos and their mp4s
   ```

2. In "Mac-side notes", replace the sentence
   `**Gotcha:** API uploads from this un-audited GCP project are forced PRIVATE until the YouTube API compliance audit passes — flip to public in Studio meanwhile.`
   with:

   ```
   **CORRECTED 2026-09-14:** API uploads from this un-audited GCP project are locked PRIVATE
   permanently — Google does not allow an appeal and the "flip in Studio" step never worked
   (support.google.com/youtube/answer/7300965). All 20 Data-API uploads sit at 0 views. New
   uploads go through Upload-Post (`scripts/publishers/youtube.py`); the 20 are re-published by
   `scripts/video/reupload_locked.py`. `youtube_publish.py` now refuses to upload without
   `--i-understand-locked-private`. Submitting the audit form is still worth doing — it unlocks
   future direct uploads — but it does not rescue the existing 20.
   ```

3. In "Waiting on Stephen", replace item 1 ("Flip the 12 new Shorts to public…") with:

   ```
   1. **Connect YouTube, TikTok and Instagram to Upload-Post** (https://www.upload-post.com/) and
      export `UPLOAD_POST_KEY`. The 20 locked-private Data-API uploads cannot be flipped; they are
      re-published by `scripts/video/reupload_locked.py` once the key exists.
   ```

- [ ] **Step 11: Log the finding to the ledger**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 - <<'PY'
import pathlib, sys
sys.path.insert(0, str(pathlib.Path.cwd() / "scripts"))
import ledger
row = ledger.append(
    action=("YouTube Data-API uploads disabled. FINDING (verified 2026-09-14 against "
            "support.google.com/youtube/answer/7300965 and marketing/seo-tracking/"
            "youtube-snapshots.jsonl): all 20 videos uploaded via the Data API are locked "
            "PRIVATE with 0 views and cannot be appealed — a locked-private upload from an "
            "unverified API project must be re-uploaded, and passing the compliance audit only "
            "unlocks future uploads. The 10 videos uploaded through Chrome on 2026-09-02 are "
            "public and getting views; the 'flip in Studio' step in CLAUDE.md never worked. "
            "scripts/video/youtube_publish.py now refuses to upload without "
            "--i-understand-locked-private and prints the finding plus the Upload-Post path; "
            "scripts/video/reupload_locked.py re-publishes all 20 through Upload-Post with their "
            "original titles and descriptions; CLAUDE.md corrected in three places."),
    tier=0, status="executed",
    reasoning=("A measurement error that cost three weeks of Shorts output. Recording it as T0 "
               "because it stops a broken path rather than starting a new one."),
    files=["scripts/video/youtube_publish.py", "scripts/video/reupload_locked.py", "CLAUDE.md"])
print(row["id"], row["ts"])
PY
tail -1 decisions/decisions.jsonl | python3 -m json.tool | head -5
```

Expected: the new entry prints `69` (the first free id) and the tail shows it.

- [ ] **Step 12: Run the full suite and commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 83 passed (69 + 5 new youtube_publish + 9 reupload).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/video/youtube_publish.py scripts/video/reupload_locked.py \
        tests/test_youtube_publish.py tests/test_reupload_locked.py CLAUDE.md decisions/decisions.jsonl
git commit -m "fix(youtube): refuse Data-API uploads; add reupload_locked.py for the 20 locked videos

Uploads from the un-audited GCP project are locked private permanently and cannot be
appealed, so youtube_publish.py now prints the finding and the Upload-Post path and exits 2
unless --i-understand-locked-private is passed. reupload_locked.py scans every
marketing/video record with via=data-api, resolves its mp4 under scripts/video/build/,
re-publishes it through publishers/youtube.py with the original title and description, and
rewrites the record with the new url, via=upload-post and replaced_url. CLAUDE.md's three
'flip in Studio' claims corrected; finding logged to the ledger.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 5: `card` scene kind for Shorts (`ranked_list` / `countdown` / `changed`)

**Files:**
- Create: `scripts/video/cards.py`
- Create: `tests/test_cards.py`, `tests/test_card_scene_e2e.py`
- Create: `tests/golden/` (three generated `.html` files, committed)
- Create: `marketing/video/card-demo/scenes.yaml`
- Modify: `scripts/video/render_sheets.py` (add `render_card_scene`)
- Modify: `scripts/video/build_video.py` (dispatch `kind: card`; skip the workbook when nothing needs it)
- Modify: `scripts/video/make_short.py` (render a `card` scene full-bleed)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `cards.TEMPLATES = ("ranked_list", "countdown", "changed")`
  - `cards.DEFAULT_BRAND: dict` — brand-neutral tokens: `{"name", "url", "bg", "bg_alt", "fg", "muted", "accent", "accent_fg", "font"}`
  - `cards.brand_tokens(spec_brand: dict | None) -> dict` — `DEFAULT_BRAND` overlaid with the spec's `brand:` block
  - `cards.card_html(template: str, data: dict, brand: dict, width: int = 1296, height: int = 2304) -> str`
  - `cards.is_card(scene: dict) -> bool`
  - `render_sheets.render_card_scene(out_png, template, data, brand, width, height, html_dir=None) -> dict` — returns the same `{"fx","fy","static"}` shape as `render_card` so `focus.json` stays uniform
- `make_short.py` and `build_video.py` both branch on `cards.is_card(scene)`.

**Spec shape** — a `card` scene in `marketing/video/<slug>/scenes.yaml`:

```yaml
brand:                       # optional; brand-neutral defaults when absent
  name: KDesk Accounting
  url: kdeskaccounting.com
  bg: "#1F3864"
  bg_alt: "#2E75B6"
  fg: "#FFFFFF"
  muted: "#DBE7F7"
  accent: "#FFD966"
  accent_fg: "#0D1A33"
scenes:
  - kind: card
    template: ranked_list
    data:
      title: Shortest waits right now
      subtitle: Magic Kingdom · 2026-09-14
      items:
        - {label: "Tomorrowland Speedway", value: "5 min"}
        - {label: "The Barnstormer", value: "10 min"}
    narration: >
      Right now at Magic Kingdom the five shortest waits are ...
```

`countdown` takes the same `items` but numbers them downward (`#5 … #1`); `changed` takes `rows: [{label, from, to, direction}]` where `direction` is `up` / `down` / `flat`.

- [ ] **Step 1: Write the failing test for `cards.py`**

Create `tests/test_cards.py`:

```python
"""scripts/video/cards.py — 9:16 HTML cards for the `card` scene kind."""
import os
import pathlib
import re

import pytest

import cards

GOLDEN = pathlib.Path(__file__).parent / "golden"

RANKED = {"title": "Shortest waits right now", "subtitle": "Magic Kingdom · 2026-09-14",
          "items": [{"label": "Tomorrowland Speedway", "value": "5 min"},
                    {"label": "The Barnstormer", "value": "10 min"},
                    {"label": "Dumbo the Flying Elephant", "value": "15 min"}]}
COUNTDOWN = {"title": "Worst days to go in March", "subtitle": "Crowd score, 1-10",
             "items": [{"label": "Mar 14 — Sat", "value": "9.4"},
                       {"label": "Mar 15 — Sun", "value": "9.1"},
                       {"label": "Mar 16 — Mon", "value": "8.7"}]}
CHANGED = {"title": "3 rides closing next week", "subtitle": "Refurbishment calendar",
           "rows": [{"label": "Space Mountain", "from": "Open", "to": "Refurb", "direction": "down"},
                    {"label": "Test Track", "from": "Refurb", "to": "Open", "direction": "up"},
                    {"label": "Haunted Mansion", "from": "Open", "to": "Open", "direction": "flat"}]}
BRAND = {"name": "Demo Brand", "url": "example.com"}


def test_templates_are_the_three_the_spec_names():
    assert cards.TEMPLATES == ("ranked_list", "countdown", "changed")


def test_default_brand_is_neutral_and_complete():
    for key in ("name", "url", "bg", "bg_alt", "fg", "muted", "accent", "accent_fg", "font"):
        assert key in cards.DEFAULT_BRAND
    assert "KDesk" not in cards.DEFAULT_BRAND["name"]


def test_brand_tokens_overlays_the_spec_block_onto_the_defaults():
    tokens = cards.brand_tokens({"name": "Demo Brand", "accent": "#00FF00"})
    assert tokens["name"] == "Demo Brand"
    assert tokens["accent"] == "#00FF00"
    assert tokens["bg"] == cards.DEFAULT_BRAND["bg"]


def test_brand_tokens_of_none_is_the_default_set():
    assert cards.brand_tokens(None) == cards.DEFAULT_BRAND


def test_brand_tokens_rejects_an_unknown_key_instead_of_ignoring_it():
    with pytest.raises(KeyError) as e:
        cards.brand_tokens({"colour": "#fff"})
    assert "colour" in str(e.value)


def test_is_card_detects_the_kind():
    assert cards.is_card({"kind": "card", "template": "ranked_list"}) is True
    assert cards.is_card({"kind": "title"}) is False
    assert cards.is_card({"sheet": "Setup", "range": "A1:B2"}) is False


def test_card_html_sizes_the_page_to_the_requested_canvas():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 1296, 2304)
    assert "width:1296px" in html and "height:2304px" in html
    portrait = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND), 2400, 1350)
    assert "width:2400px" in portrait and "height:1350px" in portrait


def test_card_html_escapes_untrusted_data():
    html = cards.card_html("ranked_list", {"title": "5 < 10 & \"quoted\"", "subtitle": "",
                                           "items": [{"label": "<script>x</script>", "value": "1"}]},
                           cards.brand_tokens(BRAND))
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "5 &lt; 10 &amp; &quot;quoted&quot;" in html


def test_ranked_list_numbers_items_upward_from_one():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND))
    ranks = re.findall(r'<div class="rank">([^<]+)</div>', html)
    assert ranks == ["1", "2", "3"]
    assert "Tomorrowland Speedway" in html and "5 min" in html


def test_countdown_numbers_items_downward_to_one():
    html = cards.card_html("countdown", COUNTDOWN, cards.brand_tokens(BRAND))
    ranks = re.findall(r'<div class="rank">([^<]+)</div>', html)
    assert ranks == ["#3", "#2", "#1"]


def test_changed_shows_from_to_and_a_direction_class_per_row():
    html = cards.card_html("changed", CHANGED, cards.brand_tokens(BRAND))
    assert html.count('class="row down"') == 1
    assert html.count('class="row up"') == 1
    assert html.count('class="row flat"') == 1
    assert "Space Mountain" in html
    assert "Refurb" in html
    assert "→" in html


def test_card_html_carries_the_brand_name_and_url():
    html = cards.card_html("ranked_list", RANKED, cards.brand_tokens(BRAND))
    assert "Demo Brand" in html
    assert "example.com" in html


def test_card_html_rejects_an_unknown_template():
    with pytest.raises(ValueError) as e:
        cards.card_html("bar_chart", RANKED, cards.brand_tokens(BRAND))
    assert "ranked_list" in str(e.value)


def test_card_html_rejects_a_ranked_list_with_no_items():
    with pytest.raises(ValueError):
        cards.card_html("ranked_list", {"title": "t", "items": []}, cards.brand_tokens(BRAND))


@pytest.mark.parametrize("template,data", [("ranked_list", RANKED), ("countdown", COUNTDOWN),
                                           ("changed", CHANGED)])
def test_card_html_matches_its_golden_file(template, data):
    """Regenerate after an intentional design change:
       KDESK_UPDATE_GOLDEN=1 uv run --with pytest pytest tests/test_cards.py -q
    then open the rendered PNG before committing."""
    html = cards.card_html(template, data, cards.brand_tokens(BRAND), 1296, 2304)
    path = GOLDEN / f"card_{template}.html"
    if os.environ.get("KDESK_UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    assert path.exists(), f"missing golden {path}; regenerate with KDESK_UPDATE_GOLDEN=1"
    assert html == path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_cards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cards'`.

- [ ] **Step 3: Write `scripts/video/cards.py`**

```python
#!/usr/bin/env python3
"""HTML cards for the `card` scene kind: data straight from a weekly diff into a 9:16 frame.

Three templates, all driven by one `data:` block in the scene:
  ranked_list  {title, subtitle, items: [{label, value}]}         numbered 1..N
  countdown    {title, subtitle, items: [{label, value}]}         numbered #N..#1
  changed      {title, subtitle, rows: [{label, from, to, direction}]}  direction: up|down|flat

Colours come from the spec's optional `brand:` block; the defaults are brand-neutral so the
same renderer serves a second venture without carrying KDesk's palette. Pure string
building - no I/O, stdlib only - so the golden tests run in the plain pytest environment.
"""
from __future__ import annotations

import html as _html

TEMPLATES = ("ranked_list", "countdown", "changed")

DEFAULT_BRAND: dict = {
    "name": "Your Brand",
    "url": "example.com",
    "bg": "#101418",
    "bg_alt": "#1B2430",
    "fg": "#FFFFFF",
    "muted": "#AAB6C4",
    "accent": "#F2C14E",
    "accent_fg": "#101418",
    "font": "Carlito, Arial, Helvetica, sans-serif",
}

DIRECTION_MARK = {"up": "▲", "down": "▼", "flat": "•"}


def brand_tokens(spec_brand: dict | None) -> dict:
    tokens = dict(DEFAULT_BRAND)
    for key, value in (spec_brand or {}).items():
        if key not in DEFAULT_BRAND:
            raise KeyError(f"unknown brand token {key!r}; known: {', '.join(sorted(DEFAULT_BRAND))}")
        tokens[key] = value
    return tokens


def is_card(scene: dict) -> bool:
    return scene.get("kind") == "card"


def _e(value: object) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def _rows_ranked(items: list[dict], countdown: bool) -> str:
    n = len(items)
    out = []
    for i, item in enumerate(items):
        rank = f"#{n - i}" if countdown else str(i + 1)
        out.append(f'<li class="row"><div class="rank">{_e(rank)}</div>'
                   f'<div class="label">{_e(item.get("label"))}</div>'
                   f'<div class="value">{_e(item.get("value"))}</div></li>')
    return "\n    ".join(out)


def _rows_changed(rows: list[dict]) -> str:
    out = []
    for row in rows:
        direction = str(row.get("direction", "flat")).lower()
        if direction not in DIRECTION_MARK:
            raise ValueError(f"direction must be one of {sorted(DIRECTION_MARK)}, got {direction!r}")
        out.append(f'<li class="row {direction}"><div class="mark">{DIRECTION_MARK[direction]}</div>'
                   f'<div class="label">{_e(row.get("label"))}</div>'
                   f'<div class="value"><span class="from">{_e(row.get("from"))}</span>'
                   f' <span class="arrow">→</span> '
                   f'<span class="to">{_e(row.get("to"))}</span></div></li>')
    return "\n    ".join(out)


def card_html(template: str, data: dict, brand: dict, width: int = 1296, height: int = 2304) -> str:
    if template not in TEMPLATES:
        raise ValueError(f"unknown card template {template!r}; known: {', '.join(TEMPLATES)}")
    if template == "changed":
        rows = data.get("rows") or []
        if not rows:
            raise ValueError("card template 'changed' needs a non-empty data.rows")
        body = _rows_changed(rows)
    else:
        items = data.get("items") or []
        if not items:
            raise ValueError(f"card template {template!r} needs a non-empty data.items")
        body = _rows_ranked(items, countdown=(template == "countdown"))
    subtitle = (f'<p class="sub">{_e(data.get("subtitle"))}</p>' if data.get("subtitle") else "")
    unit = height / 100.0          # every size scales with the canvas, so 9:16 and 16:9 both fit
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden;
  background:radial-gradient(120% 60% at 20% 8%, {brand['bg_alt']} 0%, {brand['bg']} 60%, {brand['bg']} 100%);
  color:{brand['fg']};font-family:{brand['font']}}}
.wrap{{width:{width}px;height:{height}px;display:flex;flex-direction:column;
  justify-content:center;padding:{unit * 5:.0f}px {unit * 4:.0f}px}}
.brand{{position:absolute;top:{unit * 5:.0f}px;left:{unit * 4:.0f}px;
  font-size:{unit * 1.5:.1f}px;letter-spacing:.06em;text-transform:uppercase;color:{brand['muted']}}}
h1{{font-size:{unit * 4.6:.1f}px;line-height:1.06;font-weight:700;margin-bottom:{unit * 1.2:.0f}px}}
.sub{{font-size:{unit * 2.1:.1f}px;color:{brand['muted']};margin-bottom:{unit * 3:.0f}px}}
ul{{list-style:none;display:flex;flex-direction:column;gap:{unit * 1.2:.0f}px}}
.row{{display:flex;align-items:center;gap:{unit * 1.6:.0f}px;background:rgba(255,255,255,.06);
  border-radius:{unit * 1.2:.0f}px;padding:{unit * 1.6:.0f}px {unit * 2:.0f}px}}
.rank{{min-width:{unit * 6:.0f}px;font-size:{unit * 3:.1f}px;font-weight:700;color:{brand['accent']}}}
.mark{{min-width:{unit * 4:.0f}px;font-size:{unit * 2.4:.1f}px;text-align:center}}
.label{{flex:1;font-size:{unit * 2.3:.1f}px;line-height:1.2}}
.value{{font-size:{unit * 2.3:.1f}px;font-weight:700;white-space:nowrap}}
.row.up .mark{{color:#57C878}} .row.down .mark{{color:#E2725B}} .row.flat .mark{{color:{brand['muted']}}}
.from{{color:{brand['muted']};font-weight:400}} .arrow{{color:{brand['muted']}}}
.foot{{position:absolute;bottom:{unit * 4:.0f}px;left:{unit * 4:.0f}px;
  font-size:{unit * 1.7:.1f}px;color:{brand['accent']}}}
</style></head><body>
<div class="brand">{_e(brand['name'])}</div>
<div class="wrap">
  <h1>{_e(data.get('title'))}</h1>
  {subtitle}
  <ul>
    {body}
  </ul>
</div>
<div class="foot">{_e(brand['url'])}</div>
</body></html>"""
```

- [ ] **Step 4: Generate the goldens, then lock them**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
KDESK_UPDATE_GOLDEN=1 uv run --with pytest pytest tests/test_cards.py -q
uv run --with pytest pytest tests/test_cards.py -q
ls tests/golden/
```

Expected: the first run creates `tests/golden/card_ranked_list.html`, `card_countdown.html`, `card_changed.html` and passes; the second run passes without the flag (goldens now locked). 17 tests collected — 15 test
functions, one of them parametrized over the three templates.

- [ ] **Step 5: Eyeball one rendered card before trusting the goldens**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
mkdir -p /tmp/cardcheck && cp tests/golden/card_ranked_list.html /tmp/cardcheck/
scripts/video/.venv-tts/bin/python -c "
import sys; sys.path.insert(0, 'scripts/video')
import render_sheets as R
R.screenshot('/tmp/cardcheck/card_ranked_list.html', '/tmp/cardcheck/card.png', 1296, 2304)
print('wrote /tmp/cardcheck/card.png')"
open /tmp/cardcheck/card.png
```

Expected: a 1296×2304 card — brand name top-left, headline, subtitle, three numbered rows with values right-aligned, the url bottom-left in the accent colour, nothing clipped. If anything overflows, fix `cards.py`, re-run Step 4 to regenerate the goldens, and look again.

- [ ] **Step 6: Add `render_card_scene` to `scripts/video/render_sheets.py`**

Append at the end of the file (it reuses the module's existing `screenshot`, and `cards` sits next to it in `scripts/video/`):

```python
def render_card_scene(out_png, template, data, brand, width=W, height=H, html_dir=None):
    """Render a `kind: card` scene to PNG. Returns the same focus shape as render_card()."""
    import cards
    doc = cards.card_html(template, data, cards.brand_tokens(brand), width, height)
    hp = pathlib.Path(html_dir or pathlib.Path(out_png).parent) / (pathlib.Path(out_png).stem + ".html")
    hp.write_text(doc)
    screenshot(hp, out_png, width, height)
    return {"fx": 0.5, "fy": 0.5, "static": True}
```

- [ ] **Step 7: Dispatch `card` in `scripts/video/build_video.py`**

Two edits.

(a) Replace the workbook-loading block — everything from `src = pathlib.Path(spec["source"]).expanduser()` down to `wbv = openpyxl.load_workbook(rec, data_only=True); wbf = openpyxl.load_workbook(rec)` — with:

```python
    import cards
    needs_workbook = any(sc.get("kind", "sheet") not in ("title", "outro", "card")
                         for sc in spec["scenes"])
    wbv = wbf = None
    wbname = spec.get("workbook_name", "")
    if needs_workbook:
        src = pathlib.Path(spec["source"]).expanduser()
        if not src.is_absolute(): src = REPO / src
        staged = build / "src.xlsx"
        if not a.skip_recalc or not (build / "recalc" / "src.xlsx").exists():
            shutil.copy(src, staged)
            presets = spec.get("presets") or {}
            if presets:
                wb = openpyxl.load_workbook(staged)
                for sheet, cells in presets.items():
                    for addr, val in cells.items():
                        wb[sheet][addr] = val
                wb.save(staged)
            rec = recalc(staged, build / "recalc")
            print(f"recalc ok -> {rec}")
        rec = build / "recalc" / "src.xlsx"
        wbv = openpyxl.load_workbook(rec, data_only=True); wbf = openpyxl.load_workbook(rec)
        wbname = spec.get("workbook_name", src.name)
```

(This makes a card-only spec render with no workbook and no LibreOffice — which is what the venture's weekly-diff Shorts need, and what makes the end-to-end test below fast.)

(b) In the scene loop, insert a `card` branch before the `title`/`outro` branch:

```python
        if cards.is_card(sc):
            focus[str(i)] = R.render_card_scene(out, sc["template"], sc.get("data", {}),
                                                spec.get("brand"))
        elif kind in ("title", "outro"):
```

- [ ] **Step 8: Render a `card` scene full-bleed in `scripts/video/make_short.py`**

(a) Add `import cards` next to the existing `from short_variants import ...` line.

(b) In the scene loop, replace the line

```python
        sc = spec["scenes"][idx]; mode = "cover"; fx = fy = 0.5; pan = None
```

with:

```python
        sc = spec["scenes"][idx]; mode = "cover"; fx = fy = 0.5; pan = None
        if cards.is_card(sc):
            # A card is already 9:16 — use it as the whole frame, no top/bottom banding.
            png = work / f"scene_{k}.png"
            R.render_card_scene(png, sc["template"], sc.get("data", {}), spec.get("brand"),
                                RW, RH, html_dir=work)
            wav = build / "audio" / f"scene_{idx:02d}.wav"
            adur = float(durs.get(str(idx), 0) or dur_of(wav)); dur = adur + 0.6
            n = math.ceil(dur * FPS); zmax = 1.06; dz = (zmax - 1.0) / n
            vf = (f"scale={RW}:{RH}:flags=lanczos,zoompan=z='min(zoom+{dz:.7f},{zmax})':"
                  f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},"
                  f"fade=t=in:st=0:d=0.3,fade=t=out:st={max(0.0, dur-0.3):.3f}:d=0.3,format=yuv420p")
            out = work / f"scene_{k}.mp4"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-i", str(wav),
                 "-filter_complex",
                 f"[0:v]{vf}[v];[1:a]apad=pad_dur=2,afade=t=in:d=0.05,"
                 f"aformat=sample_rates=48000:channel_layouts=stereo[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "libx264",
                 "-preset", "medium", "-crf", str(a.crf), "-r", str(FPS), "-c:a", "aac",
                 "-b:a", "128k", str(out)])
            parts.append(out); print(f"scene {idx:02d}: card {dur:.1f}s -> {out.name}", flush=True)
            continue
```

(c) `make_short.py` loads `focus.json` and the recalculated workbook up front. Make both tolerant of a card-only build — replace

```python
    focus = json.load(open(build / "frames/focus.json")); durs = json.load(open(build / "audio/durations.json"))
```

with:

```python
    fj = build / "frames/focus.json"
    focus = json.load(open(fj)) if fj.exists() else {}
    durs = json.load(open(build / "audio/durations.json"))
```

- [ ] **Step 9: Write the demo spec used by the end-to-end test**

Create `marketing/video/card-demo/scenes.yaml`:

```yaml
# Card-scene smoke spec: three card kinds, no workbook, no LibreOffice.
# Render: scripts/video/.venv-tts/bin/python scripts/video/build_video.py \
#           --spec marketing/video/card-demo/scenes.yaml --frames-only
product: Card scene demo
slug: card-demo
workbook_name: (none)
voice: am_michael
brand:
  name: KDesk Accounting
  url: kdeskaccounting.com
  bg: "#1F3864"
  bg_alt: "#2E75B6"
  fg: "#FFFFFF"
  muted: "#DBE7F7"
  accent: "#FFD966"
  accent_fg: "#0D1A33"
scenes:
  - kind: card
    template: ranked_list
    data:
      title: Three reconciliations that fail most often
      subtitle: From the month-end close checklist
      items:
        - {label: "Accrued commissions", value: "Deal-level"}
        - {label: "Prepaid expenses", value: "Schedule"}
        - {label: "Deferred revenue", value: "Waterfall"}
    narration: >
      Three reconciliations fail more often than the rest: accrued commissions, prepaid expenses,
      and deferred revenue.
  - kind: card
    template: countdown
    data:
      title: Close-day order of operations
      subtitle: Last three steps
      items:
        - {label: "Post the final accruals", value: "Day 3"}
        - {label: "Tie every subledger", value: "Day 4"}
        - {label: "Sign off", value: "Day 5"}
    narration: >
      The last three steps of the close, in order: post the final accruals, tie every subledger,
      then sign off.
  - kind: card
    template: changed
    data:
      title: What moved this month
      subtitle: Rollforward summary
      rows:
        - {label: "Lease liability", from: "$264,954", to: "$261,058", direction: "down"}
        - {label: "Deferred commissions", from: "$16,000", to: "$12,557", direction: "down"}
        - {label: "Fixed asset register", from: "50 assets", to: "50 assets", direction: "flat"}
    narration: >
      This month the lease liability came down, deferred commissions amortized, and the fixed
      asset register was unchanged.
```

- [ ] **Step 10: Write the end-to-end `--frames-only` test**

Create `tests/test_card_scene_e2e.py`:

```python
"""End-to-end: a card-only spec renders three PNGs through build_video.py --frames-only.

Needs the render venv (playwright/yaml/openpyxl) and a headless Chrome, so it skips in a bare
pytest environment and on CI runners. It is the test that proves the card kind is actually
wired into the pipeline, not just into cards.py.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = REPO / "scripts" / "video" / ".venv-tts" / "bin" / "python"
SPEC = REPO / "marketing" / "video" / "card-demo" / "scenes.yaml"


@pytest.mark.skipif(not VENV_PY.exists(), reason="render venv scripts/video/.venv-tts is absent")
def test_build_video_frames_only_renders_every_card_scene():
    build = REPO / "scripts" / "video" / "build" / "card-demo"
    if build.exists():
        shutil.rmtree(build)
    proc = subprocess.run([str(VENV_PY), str(REPO / "scripts/video/build_video.py"),
                           "--spec", str(SPEC), "--frames-only"],
                          capture_output=True, text=True, timeout=600, cwd=REPO)
    assert proc.returncode == 0, proc.stderr[-2000:]
    frames = build / "frames"
    for i in range(3):
        png = frames / f"scene_{i:02d}.png"
        assert png.exists(), f"{png} missing\n{proc.stdout}"
        assert png.stat().st_size > 10_000, f"{png} is suspiciously small"
    focus = json.loads((frames / "focus.json").read_text())
    assert all(focus[str(i)]["static"] is True for i in range(3))
    assert "card" in proc.stdout
```

- [ ] **Step 11: Run the end-to-end test**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_card_scene_e2e.py -q -s`
Expected: PASS (1 test). It must complete without LibreOffice running — the spec has no `source:` key, and Step 7(a) skips the workbook path entirely.

- [ ] **Step 12: Confirm the existing pipeline is unchanged**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
scripts/video/.venv-tts/bin/python scripts/video/build_video.py \
  --spec marketing/video/asc842/scenes.yaml --frames-only --skip-recalc --scenes 0,1
```

Expected: `scene 00: title` and `scene 01: sheet Setup A4:D12 …` render exactly as before (the workbook path still runs because scene 1 is a sheet scene).

- [ ] **Step 13: Run the full suite and commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 101 passed (83 + 17 cards + 1 e2e).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/video/cards.py scripts/video/render_sheets.py scripts/video/build_video.py \
        scripts/video/make_short.py marketing/video/card-demo/scenes.yaml \
        tests/test_cards.py tests/test_card_scene_e2e.py tests/golden
git commit -m "feat(video): add the card scene kind (ranked_list, countdown, changed)

cards.py builds a 9:16 HTML card from a scene's data block with brand-neutral tokens the
spec's brand: block overrides, so the same renderer serves a second venture. render_sheets
gains render_card_scene(); build_video dispatches kind: card and now skips the workbook
entirely when no scene needs one (a card-only spec renders with no LibreOffice); make_short
uses a card as the full frame instead of banding it. Golden HTML per template plus an
end-to-end --frames-only test.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 6: `scripts/sales/crm_sync.py` — the private "KDesk CRM" Google Sheet

**Files:**
- Modify: `scripts/pull_gumroad_snapshot.py` (extract `is_business()`, make the module stdlib-importable)
- Create: `scripts/sales/__init__.py`, `scripts/sales/crm_sync.py`
- Create: `tests/test_is_business.py`, `tests/test_crm_sync.py`

**Interfaces:**
- Consumes: `ledger.append(...)` (Task 1).
- Produces:
  - `pull_gumroad_snapshot.FREEMAIL: set[str]` (already exists) and **new** `pull_gumroad_snapshot.is_business(email: str) -> bool`
  - `crm_sync.COLUMNS: tuple[str, ...]` = `("email", "first_seen", "source", "domain", "is_business", "interest", "stage", "mrr", "last_touch", "next_action")`
  - `crm_sync.TABS: tuple[str, ...]` = `("People", "Events", "Pipeline", "Scoreboard")`
  - `crm_sync.Person` dataclass mirroring `COLUMNS`
  - `crm_sync.from_gumroad(sales: list[dict]) -> dict[str, Person]`
  - `crm_sync.from_mailerlite(subscribers: list[dict]) -> dict[str, Person]`
  - `crm_sync.from_seo_tracking(repo: Path) -> dict[str, Person]`
  - `crm_sync.merge(*sources) -> dict[str, Person]`
  - `crm_sync.diff(existing_rows: list[list[str]], wanted: dict[str, Person]) -> tuple[list[tuple[int, Person]], list[Person]]` → `(updates, appends)`
  - `crm_sync.a1(tab: str, row: int) -> str`
  - `crm_sync._gws(argv: list[str], body: dict | None = None) -> dict` — the single subprocess seam every test monkeypatches
  - `crm_sync.SHEET_ID_FILE: Path` = `~/kdesk-analytics/crm-sheet-id.txt`

**`gws` invocations, verified 2026-09-14 against the installed CLI** (`gws sheets spreadsheets --help`, `gws schema sheets.spreadsheets.values.batchUpdate`, `gws gmail users getProfile` → `santiagokdesk@gmail.com`). Path parameters go in `--params`, request bodies in `--json`:

```bash
gws sheets spreadsheets create --json '{"properties":{"title":"KDesk CRM"},
  "sheets":[{"properties":{"title":"People"}},{"properties":{"title":"Events"}},
            {"properties":{"title":"Pipeline"}},{"properties":{"title":"Scoreboard"}}]}'
gws sheets spreadsheets values get --params '{"spreadsheetId":"<id>","range":"People!A1:J2000"}'
gws sheets spreadsheets values batchUpdate --params '{"spreadsheetId":"<id>"}' \
  --json '{"valueInputOption":"RAW","data":[{"range":"People!A2","values":[["a@example.com", ...]]}]}'
gws sheets spreadsheets values append --params '{"spreadsheetId":"<id>","range":"People!A1",
  "valueInputOption":"RAW","insertDataOption":"INSERT_ROWS"}' --json '{"values":[[...]]}'
```

> **Blocker to record, not to solve here:** `gws` is a local Homebrew binary and `~/kdesk-analytics/google-token.json` currently carries only `webmasters.readonly` + `analytics.readonly` (see ledger entry 68). Writing a Sheet needs `https://www.googleapis.com/auth/spreadsheets`, and the `gws` CLI carries its own credentials at `~/.config/gws/`. So `crm_sync.py` runs **live on the Mac** (where `gws` is authed as santiagokdesk) and **`--dry-run` only on Actions** (Task 9). The first live run will prompt for whatever consent `gws` needs; that is Stephen's one-time step, noted in the task's verification.

- [ ] **Step 1: Write the failing test for `is_business`**

Create `tests/test_is_business.py`:

```python
"""The freemail rule lives once, in pull_gumroad_snapshot.py, and is imported everywhere else."""
import pull_gumroad_snapshot as pg


def test_business_domains_are_business():
    assert pg.is_business("buyer@northstar.example") is True
    assert pg.is_business("ap@acmeholdings.example") is True
    assert pg.is_business("Operations@Vendorworks.EXAMPLE") is True


def test_the_freemail_set_is_not_business():
    """Addresses are built from FREEMAIL itself: the rule and the set cannot drift apart, and
    this file carries no address literal for tests/test_no_third_party_emails.py to trip on."""
    for domain in sorted(pg.FREEMAIL):
        assert pg.is_business(f"someone@{domain}") is False, domain


def test_the_freemail_set_still_covers_every_consumer_host_we_listed():
    assert {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "naver.com",
            "proton.me", "protonmail.com", "aol.com", "live.com", "me.com"} <= pg.FREEMAIL


def test_malformed_addresses_are_not_business():
    assert pg.is_business("") is False
    assert pg.is_business("no-at-sign") is False
    assert pg.is_business("trailing@") is False


def test_summarize_still_reports_the_same_business_domains():
    sales = [{"email": "buyer@northstar.example", "price": 0, "product_name": "X",
              "created_at": "2026-09-01T00:00:00Z"},
             {"email": "a@gmail.com", "price": 0, "product_name": "X",
              "created_at": "2026-09-01T00:00:00Z"}]
    assert pg.summarize(sales)["business_domains"] == ["northstar.example"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_is_business.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'requests'` (the module imports it at the top today).

- [ ] **Step 3: Refactor `scripts/pull_gumroad_snapshot.py`**

Three edits, behaviour unchanged.

(a) Replace the import line

```python
import datetime as dt, json, os, pathlib, sys, warnings
warnings.filterwarnings("ignore")
import requests
```

with

```python
import datetime as dt, json, os, pathlib, sys, warnings
warnings.filterwarnings("ignore")
```

(b) Add, directly under the `FREEMAIL = {...}` line:

```python
def is_business(email: str) -> bool:
    """True when the address is on a company domain (not one of the free consumer hosts).

    The single definition of "business lead" for this repo — crm_sync.py imports it.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1]
    return bool(domain) and domain not in FREEMAIL
```

(c) In `pull()`, add `import requests` as the first line of the function body; in `summarize()`, replace

```python
    biz = sorted({e.split("@")[1] for e in emails if "@" in e and e.split("@")[1] not in FREEMAIL})
```

with

```python
    biz = sorted({e.rsplit("@", 1)[1] for e in emails if is_business(e)})
```

- [ ] **Step 4: Run the test and the script to confirm nothing changed**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
uv run --with pytest pytest tests/test_is_business.py -q
python3 scripts/pull_gumroad_snapshot.py --dry-run | head -20
```

Expected: 4 tests pass; the dry run still prints the same JSON shape (`all_time`, `last_28d`, `last_7d`) and appends nothing.

- [ ] **Step 5: Write the failing test for `crm_sync`**

Create `tests/test_crm_sync.py`:

```python
"""scripts/sales/crm_sync.py — build and upsert the private KDesk CRM sheet through gws."""
import json

from sales import crm_sync as cs

GUMROAD = [
    {"email": "Buyer@NorthStar.EXAMPLE", "price": 0, "product_name": "ASC 842 — Free",
     "created_at": "2026-08-01T10:00:00Z"},
    {"email": "buyer@northstar.example", "price": 24900, "product_name": "ASC 842",
     "created_at": "2026-09-02T10:00:00Z"},
    {"email": "a@gmail.com", "price": 0, "product_name": "Month-End Close",
     "created_at": "2026-09-05T10:00:00Z"},
]
MAILERLITE = [
    {"email": "a@gmail.com", "subscribed_at": "2026-09-06 12:00:00",
     "fields": {"interest": "rsu-planner"}},
    {"email": "new@acme.example", "subscribed_at": "2026-09-10 12:00:00", "fields": {"interest": None}},
]


def test_columns_and_tabs_match_the_plan_of_record():
    assert cs.COLUMNS == ("email", "first_seen", "source", "domain", "is_business",
                          "interest", "stage", "mrr", "last_touch", "next_action")
    assert cs.TABS == ("People", "Events", "Pipeline", "Scoreboard")


def test_a1_is_one_based_and_spans_every_column():
    assert cs.a1("People", 2) == "People!A2:J2"


def test_from_gumroad_lowercases_the_email_and_keeps_the_earliest_first_seen():
    people = cs.from_gumroad(GUMROAD)
    buyer = people["buyer@northstar.example"]
    assert buyer.first_seen == "2026-08-01"
    assert buyer.last_touch == "2026-09-02"
    assert buyer.domain == "northstar.example"
    assert buyer.is_business == "TRUE"


def test_from_gumroad_marks_a_paid_buyer_and_a_free_downloader_differently():
    people = cs.from_gumroad(GUMROAD)
    assert people["buyer@northstar.example"].source == "gumroad-paid"
    assert people["buyer@northstar.example"].stage == "customer"
    assert people["a@gmail.com"].source == "gumroad-free"
    assert people["a@gmail.com"].stage == "lead"
    assert people["a@gmail.com"].is_business == "FALSE"


def test_from_mailerlite_carries_the_interest_field():
    people = cs.from_mailerlite(MAILERLITE)
    assert people["a@gmail.com"].interest == "rsu-planner"
    assert people["new@acme.example"].interest == ""
    assert people["new@acme.example"].source == "mailerlite"
    assert people["new@acme.example"].first_seen == "2026-09-10"


def test_from_seo_tracking_reads_the_mailerlite_sync_log(tmp_path):
    d = tmp_path / "marketing" / "seo-tracking"
    d.mkdir(parents=True)
    (d / "mailerlite-sync.jsonl").write_text(
        json.dumps({"email": "info@northwind.example", "product": "ASC 842 lease workbook",
                    "gumroad_sale": "2026-09-11T04:25:17Z",
                    "synced_at": "2026-09-11T08:15-07:00"}) + "\n")
    people = cs.from_seo_tracking(tmp_path)
    assert people["info@northwind.example"].first_seen == "2026-09-11"
    assert people["info@northwind.example"].interest == "ASC 842 lease workbook"
    assert people["info@northwind.example"].is_business == "TRUE"


def test_merge_prefers_the_strongest_source_and_the_earliest_first_seen():
    merged = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    assert merged["a@gmail.com"].source == "gumroad-free"       # gumroad outranks mailerlite
    assert merged["a@gmail.com"].interest == "rsu-planner"      # but the interest is filled in
    assert merged["a@gmail.com"].first_seen == "2026-09-05"     # the earlier of the two
    assert merged["a@gmail.com"].last_touch == "2026-09-06"     # the later of the two
    assert set(merged) == {"buyer@northstar.example", "a@gmail.com", "new@acme.example"}


def test_diff_appends_new_people_and_updates_changed_ones():
    header = list(cs.COLUMNS)
    existing = [header,
                ["a@gmail.com", "2026-09-05", "gumroad-free", "gmail.com", "FALSE", "",
                 "lead", "0", "2026-09-05", ""]]
    wanted = cs.merge(cs.from_gumroad(GUMROAD), cs.from_mailerlite(MAILERLITE))
    updates, appends = cs.diff(existing, wanted)
    assert [row for _i, row in updates] == [wanted["a@gmail.com"]]
    assert updates[0][0] == 2                                   # sheet row number, 1-based
    assert {p.email for p in appends} == {"buyer@northstar.example", "new@acme.example"}


def test_diff_is_a_noop_when_the_sheet_already_matches():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    person = wanted["new@acme.example"]
    existing = [list(cs.COLUMNS), person.as_row()]
    assert cs.diff(existing, wanted) == ([], [])


def test_diff_tolerates_an_empty_sheet():
    wanted = cs.from_mailerlite([MAILERLITE[1]])
    updates, appends = cs.diff([], wanted)
    assert updates == []
    assert [p.email for p in appends] == ["new@acme.example"]


def test_sync_dry_run_prints_the_diff_and_makes_no_gws_call(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no gws call in --dry-run")))
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=[list(cs.COLUMNS)], dry_run=True)
    out = capsys.readouterr().out
    assert "+ buyer@northstar.example" in out
    assert "2 to append" in out


def test_sync_batch_updates_then_appends_through_one_seam(tmp_path, monkeypatch):
    calls = []

    def fake_gws(argv, body=None):
        calls.append((argv, body))
        return {"spreadsheetId": "SHEET1"}

    monkeypatch.setattr(cs, "_gws", fake_gws)
    wanted = cs.merge(cs.from_gumroad(GUMROAD))
    header = list(cs.COLUMNS)
    existing = [header, ["a@gmail.com", "2026-01-01", "mailerlite", "gmail.com", "FALSE", "",
                         "lead", "0", "2026-01-01", ""]]
    cs.sync(sheet_id="SHEET1", wanted=wanted, existing=existing, dry_run=False)
    kinds = [argv[3] for argv, _ in calls]
    assert kinds == ["batchUpdate", "append"]
    update_body = calls[0][1]
    assert update_body["valueInputOption"] == "RAW"
    assert update_body["data"][0]["range"] == "People!A2:J2"
    append_body = calls[1][1]
    assert [row[0] for row in append_body["values"]] == ["buyer@northstar.example"]


def test_ensure_sheet_reuses_the_recorded_id(tmp_path, monkeypatch):
    idfile = tmp_path / "crm-sheet-id.txt"
    idfile.write_text("EXISTING-ID\n")
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    monkeypatch.setattr(cs, "_gws", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not create a second sheet")))
    assert cs.ensure_sheet(dry_run=False) == "EXISTING-ID"


def test_ensure_sheet_creates_all_four_tabs_and_records_the_id(tmp_path, monkeypatch):
    idfile = tmp_path / "crm-sheet-id.txt"
    monkeypatch.setattr(cs, "SHEET_ID_FILE", idfile)
    seen = {}

    def fake_gws(argv, body=None):
        seen.update(argv=argv, body=body)
        return {"spreadsheetId": "NEW-ID"}

    monkeypatch.setattr(cs, "_gws", fake_gws)
    assert cs.ensure_sheet(dry_run=False) == "NEW-ID"
    assert idfile.read_text().strip() == "NEW-ID"
    assert seen["body"]["properties"]["title"] == "KDesk CRM"
    assert [s["properties"]["title"] for s in seen["body"]["sheets"]] == list(cs.TABS)
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_crm_sync.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sales'`.

- [ ] **Step 7: Write `scripts/sales/__init__.py` and `scripts/sales/crm_sync.py`**

`scripts/sales/__init__.py`:

```python
"""Sales automation: the CRM sheet, the re-engagement sender."""
```

`scripts/sales/crm_sync.py`:

```python
#!/usr/bin/env python3
"""Build and upsert the private "KDesk CRM" Google Sheet from Gumroad + MailerLite + the
append-only JSONL trackers. Never in the public repo — the sheet lives in Drive, owned by
santiagokdesk@gmail.com, and only its id is stored locally.

  python3 scripts/sales/crm_sync.py --dry-run     # print the diff, write nothing
  python3 scripts/sales/crm_sync.py               # create-or-upsert, then log to the ledger

Row (tab "People"): email · first_seen · source · domain · is_business · interest · stage ·
mrr · last_touch · next_action. Upserts are keyed on the lowercased email, so re-running is
idempotent: a run with nothing to change makes zero write calls.

Transport is the `gws` CLI, which carries its own santiagokdesk credentials
(~/.config/gws/). That binary is local to the Mac, so live runs happen on the Mac; CI runs
--dry-run only. Sheet id: ~/kdesk-analytics/crm-sheet-id.txt.
requests is imported lazily so this module is importable with the standard library alone.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402
from pull_gumroad_snapshot import is_business  # noqa: E402  (single definition of the rule)

SHEET_TITLE = "KDesk CRM"
SHEET_ID_FILE = pathlib.Path.home() / "kdesk-analytics" / "crm-sheet-id.txt"
TABS = ("People", "Events", "Pipeline", "Scoreboard")
COLUMNS = ("email", "first_seen", "source", "domain", "is_business", "interest",
           "stage", "mrr", "last_touch", "next_action")
LAST_COL = chr(ord("A") + len(COLUMNS) - 1)          # "J"
SOURCE_RANK = {"gumroad-paid": 3, "gumroad-free": 2, "calculator": 2, "mailerlite": 1, "": 0}
PAID_CENTS = 1                                        # any non-zero price is a purchase


@dataclasses.dataclass
class Person:
    email: str
    first_seen: str = ""
    source: str = ""
    domain: str = ""
    is_business: str = "FALSE"
    interest: str = ""
    stage: str = "lead"
    mrr: str = "0"
    last_touch: str = ""
    next_action: str = ""

    def as_row(self) -> list[str]:
        return [str(getattr(self, c)) for c in COLUMNS]

    @classmethod
    def from_row(cls, row: list[str]) -> "Person":
        padded = list(row) + [""] * (len(COLUMNS) - len(row))
        return cls(**dict(zip(COLUMNS, padded[:len(COLUMNS)])))


def a1(tab: str, row: int) -> str:
    return f"{tab}!A{row}:{LAST_COL}{row}"


def _date(value: str) -> str:
    """Normalise every timestamp shape these APIs return to YYYY-MM-DD."""
    text = (value or "").strip().replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        return dt.datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return text[:10]


def _person(email: str, **kw) -> Person:
    email = (email or "").strip().lower()
    domain = email.rsplit("@", 1)[1] if "@" in email else ""
    return Person(email=email, domain=domain,
                  is_business="TRUE" if is_business(email) else "FALSE", **kw)


def from_gumroad(sales: list[dict]) -> dict[str, Person]:
    out: dict[str, Person] = {}
    for sale in sorted(sales, key=lambda s: s.get("created_at", "")):
        email = (sale.get("email") or "").strip().lower()
        if not email:
            continue
        day = _date(sale.get("created_at", ""))
        paid = int(sale.get("price", 0) or 0) >= PAID_CENTS
        person = out.get(email) or _person(email, first_seen=day)
        person.last_touch = day
        if paid or person.source != "gumroad-paid":
            person.source = "gumroad-paid" if paid else (person.source or "gumroad-free")
        if paid:
            person.stage = "customer"
        person.interest = person.interest or str(sale.get("product_name", ""))[:60]
        out[email] = person
    return out


def from_mailerlite(subscribers: list[dict]) -> dict[str, Person]:
    out: dict[str, Person] = {}
    for sub in subscribers:
        email = (sub.get("email") or "").strip().lower()
        if not email:
            continue
        day = _date(sub.get("subscribed_at") or sub.get("created_at") or "")
        person = _person(email, first_seen=day, source="mailerlite")
        person.last_touch = day
        person.interest = str((sub.get("fields") or {}).get("interest") or "")
        out[email] = person
    return out


def from_seo_tracking(repo: pathlib.Path) -> dict[str, Person]:
    """The append-only sync log is the record of who took a free file and when."""
    out: dict[str, Person] = {}
    path = pathlib.Path(repo) / "marketing" / "seo-tracking" / "mailerlite-sync.jsonl"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        day = _date(row.get("gumroad_sale", ""))
        person = _person(email, first_seen=day, source="gumroad-free")
        person.last_touch = _date(row.get("synced_at", "")) or day
        person.interest = str(row.get("product", ""))
        out[email] = person
    return out


def merge(*sources: dict[str, Person]) -> dict[str, Person]:
    merged: dict[str, Person] = {}
    for source in sources:
        for email, person in source.items():
            current = merged.get(email)
            if current is None:
                merged[email] = dataclasses.replace(person)
                continue
            if SOURCE_RANK.get(person.source, 0) > SOURCE_RANK.get(current.source, 0):
                current.source = person.source
            if person.first_seen and (not current.first_seen or person.first_seen < current.first_seen):
                current.first_seen = person.first_seen
            if person.last_touch and person.last_touch > current.last_touch:
                current.last_touch = person.last_touch
            current.interest = current.interest or person.interest
            if person.stage == "customer":
                current.stage = "customer"
    return merged


def diff(existing_rows: list[list[str]], wanted: dict[str, Person]):
    """Return (updates, appends). updates are (1-based sheet row, Person)."""
    index: dict[str, tuple[int, Person]] = {}
    for offset, row in enumerate(existing_rows[1:], start=2):   # row 1 is the header
        if row and row[0].strip():
            index[row[0].strip().lower()] = (offset, Person.from_row(row))
    updates, appends = [], []
    for email, person in wanted.items():
        found = index.get(email)
        if found is None:
            appends.append(person)
        elif found[1].as_row() != person.as_row():
            updates.append((found[0], person))
    return updates, appends


def _gws(argv: list[str], body: dict | None = None) -> dict:
    """The one subprocess seam. Tests monkeypatch this; nothing else shells out."""
    cmd = ["gws", *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"gws {' '.join(argv[:4])} failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def ensure_sheet(dry_run: bool) -> str:
    if SHEET_ID_FILE.exists() and SHEET_ID_FILE.read_text().strip():
        return SHEET_ID_FILE.read_text().strip()
    if dry_run:
        return "(would create a new spreadsheet)"
    created = _gws(["sheets", "spreadsheets", "create"],
                   {"properties": {"title": SHEET_TITLE},
                    "sheets": [{"properties": {"title": t}} for t in TABS]})
    sheet_id = created["spreadsheetId"]
    SHEET_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHEET_ID_FILE.write_text(sheet_id + "\n")
    _gws(["sheets", "spreadsheets", "values", "batchUpdate",
          "--params", json.dumps({"spreadsheetId": sheet_id})],
         {"valueInputOption": "RAW",
          "data": [{"range": a1("People", 1), "values": [list(COLUMNS)]}]})
    return sheet_id


def read_people(sheet_id: str) -> list[list[str]]:
    payload = _gws(["sheets", "spreadsheets", "values", "get", "--params",
                    json.dumps({"spreadsheetId": sheet_id, "range": f"People!A1:{LAST_COL}2000"})])
    return payload.get("values", [])


def sync(sheet_id: str, wanted: dict[str, Person], existing: list[list[str]], dry_run: bool) -> tuple[int, int]:
    updates, appends = diff(existing, wanted)
    for _row, person in updates:
        print(f"  ~ {person.email:<40} {person.source:<13} {person.stage}")
    for person in appends:
        print(f"  + {person.email:<40} {person.source:<13} {person.stage}")
    print(f"{len(updates)} to update, {len(appends)} to append")
    if dry_run or not (updates or appends):
        return len(updates), len(appends)
    if updates:
        _gws(["sheets", "spreadsheets", "values", "batchUpdate", "--params",
              json.dumps({"spreadsheetId": sheet_id})],
             {"valueInputOption": "RAW",
              "data": [{"range": a1("People", row), "values": [person.as_row()]}
                       for row, person in updates]})
    if appends:
        _gws(["sheets", "spreadsheets", "values", "append", "--params",
              json.dumps({"spreadsheetId": sheet_id, "range": "People!A1",
                          "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})],
             {"values": [person.as_row() for person in appends]})
    return len(updates), len(appends)


def fetch_gumroad() -> list[dict]:
    import requests
    from pull_gumroad_snapshot import token
    sales, key = [], None
    while True:
        params = {"access_token": token()}
        if key:
            params["page_key"] = key
        payload = requests.get("https://api.gumroad.com/v2/sales", params=params, timeout=30).json()
        sales += payload.get("sales", [])
        key = payload.get("next_page_key")
        if not key:
            return sales


def fetch_mailerlite() -> list[dict]:
    import requests
    token = (pathlib.Path.home() / "kdesk-analytics" / "mailerlite-token.txt").read_text().strip()
    out, cursor = [], None
    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = requests.get("https://connect.mailerlite.com/api/subscribers",
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                         params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        out += payload.get("data", [])
        cursor = (payload.get("meta") or {}).get("next_cursor")
        if not cursor:
            return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync the private KDesk CRM sheet.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    wanted = merge(from_seo_tracking(REPO), from_mailerlite(fetch_mailerlite()),
                   from_gumroad(fetch_gumroad()))
    sheet_id = ensure_sheet(a.dry_run)
    existing = [] if a.dry_run and not SHEET_ID_FILE.exists() else read_people(sheet_id)
    print(f"{SHEET_TITLE} ({sheet_id}) — {len(wanted)} people from Gumroad + MailerLite + trackers")
    updated, appended = sync(sheet_id, wanted, existing, a.dry_run)
    if a.dry_run or not (updated or appended):
        return 0
    ledger.append(
        action=(f"CRM sync: updated {updated} and appended {appended} rows on the private "
                f"'{SHEET_TITLE}' Google Sheet ({sheet_id}) from Gumroad sales, MailerLite "
                f"subscribers and marketing/seo-tracking/mailerlite-sync.jsonl. "
                f"{len(wanted)} people total; keyed on lowercased email, so the run is idempotent."),
        tier=0, status="executed",
        reasoning="Track 3: the CRM is a private sheet, never the public repo.",
        files=[])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run the crm tests to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_crm_sync.py -q`
Expected: PASS, 14 tests.

- [ ] **Step 9: Live verification on the Mac**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
gws gmail users getProfile --params '{"userId":"me"}'          # must print santiagokdesk@gmail.com
python3 scripts/sales/crm_sync.py --dry-run
python3 scripts/sales/crm_sync.py
cat ~/kdesk-analytics/crm-sheet-id.txt
gws sheets spreadsheets values get --params "{\"spreadsheetId\":\"$(cat ~/kdesk-analytics/crm-sheet-id.txt)\",\"range\":\"People!A1:J5\"}"
python3 scripts/sales/crm_sync.py                               # idempotence check
git status --porcelain
```

Expected: the dry run lists every person with `+`, writes nothing and appends no ledger line; the live run creates the sheet, records its id, and appends one ledger entry; the `values get` shows the header plus rows; the **second** live run prints `0 to update, 0 to append` and appends **no** second ledger line; `git status` shows only `decisions/decisions.jsonl`. If `gws sheets spreadsheets create` fails with a scope error, that is Stephen's one-time consent — run `gws auth login -s gmail,drive,calendar,docs,sheets,slides` as santiagokdesk and retry.

- [ ] **Step 10: Run the full suite and commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 119 passed (101 + 4 + 14).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/pull_gumroad_snapshot.py scripts/sales tests/test_is_business.py \
        tests/test_crm_sync.py decisions/decisions.jsonl
git commit -m "feat(sales): crm_sync.py builds the private KDesk CRM sheet via gws

Merges Gumroad sales, MailerLite subscribers and marketing/seo-tracking/mailerlite-sync.jsonl
into one People tab keyed on lowercased email, so a re-run with nothing to change makes zero
write calls. --dry-run prints the diff and touches nothing. The freemail rule is now a single
is_business() in pull_gumroad_snapshot.py that crm_sync imports rather than copies, and that
module no longer imports requests at module scope so it is testable.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 7: `scripts/sales/send_reengage.py` — the 14-recipient re-engagement send

**Files:**
- Create: `scripts/sales/send_reengage.py`
- Create: `tests/test_send_reengage.py`
- Read-only input: `marketing/email-sequences/re-engage-2026-09.md`

**Interfaces:**
- Consumes: `ledger.veto_close(...)` and `ledger.append(...)` (Task 1); `crm_sync._gws` pattern (a private `_gws` seam of its own, so the two scripts fail independently).
- Produces:
  - `send_reengage.Recipient` dataclass: `subscriber_id: str`, `email: str`, `product: str`
  - `send_reengage.parse(markdown: str) -> tuple[str, str, list[Recipient]]` → `(subject, body, recipients)`
  - `send_reengage.MERGE_FIELDS: tuple[str, ...]` = `("product_name", "page_url", "paid_url", "price", "free_cap")`
  - `send_reengage.render(template: str, fields: dict) -> str` — substitutes `{$key}`; raises `KeyError` naming every field it could not fill
  - `send_reengage.rfc822(to: str, subject: str, body: str, sender: str) -> str` — base64url of the MIME message
  - `send_reengage.veto_ok(close_iso: str | None, now: datetime) -> tuple[bool, str]`
  - `send_reengage.VETO_ENTRY_DEFAULT = 69`

**Source file facts** (`marketing/email-sequences/re-engage-2026-09.md`, read 2026-09-14): `## Subject` holds one line; `## Body` holds the markdown body; `## Recipients (14 — …)` holds a pipe table whose columns are `id | email | product | domain`, with a header row and a `|---|---|---|---|` separator. Merge fields present in the copy are `{$product_name}`, `{$page_url}`, `{$paid_url}`. The sender is `santiagokdesk@gmail.com`.

> **Spec conflict, resolved here:** the brief says to refuse "before the veto close in ledger entry 69". At the time of writing the ledger's highest id is **68** — entry 69 does not exist yet; it is the Phase-0 T1-loosening entry (and Task 4 Step 11 of this plan writes an entry that will take id 69 if Phase 0 has not run first). `send_reengage.py` therefore takes `--veto-entry N` (default 69) and **refuses with a clear message when that entry is missing, when it is not a T2 entry, or when its `veto_window_close` has not passed.** Confirm which entry actually carries the window before the first live send: `python3 scripts/ledger.py --tail 5`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_send_reengage.py`:

```python
"""scripts/sales/send_reengage.py — parse the drafted campaign, gate on the veto, send one by one."""
import base64
import datetime as dt
import email
import json

import pytest

from sales import send_reengage as sr

MD = """# Re-engagement email — the 14 downloaders the nurture skipped

**Sender:** KDesk Accounting · santiagokdesk@gmail.com

## Subject
Quick question about the {$product_name} you downloaded

## Body
Hi —

Earlier this year you grabbed the free **{$product_name}** from KDesk.

1. The product page: {$page_url}
2. 20% off with **UPGRADE20**: {$paid_url}/UPGRADE20

— Stephen

## Recipients (2 — MailerLite subscriber id · email · product)
| id | email | product | domain |
|---|---|---|---|
| 197511900414608737 | buyer@northstar.example | ASC 842 lease workbook | **accounting firm** |
| 197511899790705978 | kaley@example.net | month-end close checklist | individual |

## Also noted while here
- Nothing relevant to the sender.
"""
TZ = dt.timezone(dt.timedelta(hours=-7))


def test_parse_reads_the_subject_line():
    subject, _body, _rcpts = sr.parse(MD)
    assert subject == "Quick question about the {$product_name} you downloaded"


def test_parse_reads_the_body_and_stops_at_the_next_heading():
    _s, body, _r = sr.parse(MD)
    assert body.startswith("Hi —")
    assert "UPGRADE20" in body
    assert body.rstrip().endswith("— Stephen")
    assert "Recipients" not in body


def test_parse_reads_the_recipient_table_without_the_header_or_separator():
    _s, _b, rcpts = sr.parse(MD)
    assert [r.email for r in rcpts] == ["buyer@northstar.example",
                                        "kaley@example.net"]
    assert rcpts[0].subscriber_id == "197511900414608737"
    assert rcpts[0].product == "ASC 842 lease workbook"


def test_parse_rejects_a_file_with_no_recipients():
    with pytest.raises(ValueError) as e:
        sr.parse("## Subject\nx\n\n## Body\ny\n")
    assert "Recipients" in str(e.value)


def test_render_substitutes_every_merge_field():
    out = sr.render("Hi, the {$product_name} at {$page_url}",
                    {"product_name": "ASC 842 workbook", "page_url": "https://x/"})
    assert out == "Hi, the ASC 842 workbook at https://x/"


def test_render_names_every_field_it_could_not_fill():
    with pytest.raises(KeyError) as e:
        sr.render("{$product_name} {$paid_url} {$price}", {"product_name": "x"})
    message = str(e.value)
    assert "paid_url" in message and "price" in message
    assert "product_name" not in message


def test_veto_ok_is_false_before_the_window_closes():
    ok, why = sr.veto_ok("2026-09-16T09:00:00-0700", dt.datetime(2026, 9, 14, 8, 0, tzinfo=TZ))
    assert ok is False
    assert "2026-09-16" in why


def test_veto_ok_is_true_after_the_window_closes():
    ok, _why = sr.veto_ok("2026-09-16T09:00:00-0700", dt.datetime(2026, 9, 17, 8, 0, tzinfo=TZ))
    assert ok is True


def test_veto_ok_refuses_when_the_entry_has_no_window():
    ok, why = sr.veto_ok(None, dt.datetime(2026, 9, 17, 8, 0, tzinfo=TZ))
    assert ok is False
    assert "no veto_window_close" in why


def test_rfc822_round_trips_to_and_subject_and_body():
    raw = sr.rfc822("a@example.com", "Subject line", "Body line\nSecond", "santiagokdesk@gmail.com")
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert msg["To"] == "a@example.com"
    assert msg["From"] == "santiagokdesk@gmail.com"
    assert msg["Subject"] == "Subject line"
    assert "Second" in msg.get_payload(decode=True).decode()


def test_dry_run_renders_every_email_and_makes_no_gws_call_and_no_sleep(capsys, monkeypatch):
    monkeypatch.setattr(sr, "_gws", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    monkeypatch.setattr(sr, "_sleep", lambda s: (_ for _ in ()).throw(AssertionError("no sleep")))
    monkeypatch.setattr(sr, "merge_fields_for", lambda email, product: {
        "product_name": product, "page_url": "https://kdeskaccounting.com/templates/asc842/",
        "paid_url": "https://kdeskaccounting.gumroad.com/l/phxigq", "price": "$249",
        "free_cap": "3 leases"})
    sent, failed = sr.send_all(MD, dry_run=True, repo=None)
    out = capsys.readouterr().out
    assert sent == 2 and failed == 0
    assert "buyer@northstar.example" in out
    assert "Quick question about the ASC 842 lease workbook you downloaded" in out


def test_live_send_waits_two_seconds_between_recipients(monkeypatch, tmp_path):
    calls, sleeps = [], []
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: calls.append(body) or {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", sleeps.append)
    monkeypatch.setattr(sr, "merge_fields_for", lambda email, product: {
        "product_name": product, "page_url": "u", "paid_url": "p", "price": "$1", "free_cap": "c"})
    logged = []
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: logged.append(kw) or {"id": 1})
    sent, failed = sr.send_all(MD, dry_run=False, repo=tmp_path)
    assert (sent, failed) == (2, 0)
    assert len(calls) == 2
    assert sleeps == [sr.GAP_SECONDS, sr.GAP_SECONDS]
    assert len(logged) == 2                                  # one ledger line per send
    assert "buyer@northstar.example" in logged[0]["action"]


def test_a_missing_merge_field_queues_a_card_instead_of_sending(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, "_gws", lambda argv, body=None: {"id": "m1"})
    monkeypatch.setattr(sr, "_sleep", lambda s: None)
    monkeypatch.setattr(sr.ledger, "append", lambda **kw: {"id": 1})
    monkeypatch.setattr(sr, "merge_fields_for",
                        lambda email, product: {} if "kaley@example.net" in email else {
                            "product_name": product, "page_url": "u", "paid_url": "p",
                            "price": "$1", "free_cap": "c"})
    sent, failed = sr.send_all(MD, dry_run=False, repo=tmp_path)
    assert (sent, failed) == (1, 1)
    cards = list((tmp_path / "marketing" / "publish-queue" / "manual").glob("*.md"))
    assert len(cards) == 1
    assert "kaley@example.net" in cards[0].read_text()


def test_main_refuses_when_the_veto_entry_is_missing(monkeypatch, capsys, tmp_path):
    empty = tmp_path / "decisions.jsonl"
    empty.write_text("")
    monkeypatch.setattr(sr, "LEDGER_PATH", empty)
    monkeypatch.setattr(sr, "_gws", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    monkeypatch.setattr("sys.argv", ["send_reengage.py"])
    assert sr.main() == 2
    assert "entry 69" in capsys.readouterr().err


def test_main_refuses_before_the_window_closes(monkeypatch, capsys, tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text(json.dumps({"id": 69, "ts": "t", "tier": 2, "status": "in_progress",
                                "action": "T1 loosening", "reasoning": "r", "files": [],
                                "veto_window_close": "2099-01-01T00:00:00-0800",
                                "stephen_reviewed": False}) + "\n")
    monkeypatch.setattr(sr, "LEDGER_PATH", path)
    monkeypatch.setattr(sr, "_gws", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    monkeypatch.setattr("sys.argv", ["send_reengage.py"])
    assert sr.main() == 2
    assert "2099-01-01" in capsys.readouterr().err
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_send_reengage.py -q`
Expected: FAIL — `ImportError: cannot import name 'send_reengage'`.

- [ ] **Step 3: Write `scripts/sales/send_reengage.py`**

```python
#!/usr/bin/env python3
"""Send the drafted re-engagement email to the 14 downloaders the nurture skipped.

Copy, merge fields and recipients all come from marketing/email-sequences/re-engage-2026-09.md
— this script never writes copy. One message per recipient through
`gws gmail users messages send` as santiagokdesk@gmail.com, two seconds apart, one ledger
line each. Merge values are read from MailerLite (the store the copy was written against);
a recipient whose fields cannot be filled gets a queue card instead of a half-rendered email.

  python3 scripts/sales/send_reengage.py --dry-run              # render every email, send none
  python3 scripts/sales/send_reengage.py [--veto-entry 69] [--limit 2]

Refuses to run until the T2 veto window in the named ledger entry has closed. Confirm which
entry carries it first:  python3 scripts/ledger.py --tail 5
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import time
from email.message import EmailMessage

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402
from browser.session import queue_card_markdown, write_queue_card  # noqa: E402

LEDGER_PATH = ledger.DEFAULT_PATH
SOURCE = REPO / "marketing" / "email-sequences" / "re-engage-2026-09.md"
SENDER = "santiagokdesk@gmail.com"
GAP_SECONDS = 2.0
VETO_ENTRY_DEFAULT = 69
MERGE_FIELDS = ("product_name", "page_url", "paid_url", "price", "free_cap")
MERGE_RE = re.compile(r"\{\$([a-z_]+)\}")


@dataclasses.dataclass(frozen=True)
class Recipient:
    subscriber_id: str
    email: str
    product: str


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{heading}.*?$\n(.*?)(?=^##\s|\Z)", re.S | re.M)
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def parse(markdown: str) -> tuple[str, str, list[Recipient]]:
    subject = _section(markdown, "Subject").strip()
    body = _section(markdown, "Body")
    table = _section(markdown, r"Recipients")
    recipients: list[Recipient] = []
    for line in table.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() == "id" or "@" not in cells[1]:
            continue
        recipients.append(Recipient(cells[0], cells[1].lower(), cells[2]))
    if not subject or not body:
        raise ValueError(f"{SOURCE.name}: both '## Subject' and '## Body' are required")
    if not recipients:
        raise ValueError(f"{SOURCE.name}: no rows found under '## Recipients'")
    return subject, body, recipients


def render(template: str, fields: dict) -> str:
    missing = sorted({m for m in MERGE_RE.findall(template) if not fields.get(m)})
    if missing:
        raise KeyError(f"unfilled merge fields: {', '.join(missing)}")
    return MERGE_RE.sub(lambda m: str(fields[m.group(1)]), template)


def rfc822(to: str, subject: str, body: str, sender: str = SENDER) -> str:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = f"KDesk Accounting <{sender}>" if "<" not in sender else sender
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")


def veto_ok(close_iso: str | None, now: dt.datetime) -> tuple[bool, str]:
    if not close_iso:
        return False, "the ledger entry has no veto_window_close — nothing authorises this send"
    closes = dt.datetime.fromisoformat(close_iso)
    if now < closes:
        return False, f"the veto window closes {close_iso}; it is {now.isoformat(timespec='minutes')}"
    return True, f"veto window closed {close_iso}"


def _gws(argv: list[str], body: dict | None = None) -> dict:
    """The one send seam. Tests monkeypatch this; nothing else shells out."""
    cmd = ["gws", *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"gws send failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def merge_fields_for(email: str, product: str) -> dict:
    """Read the subscriber's merge values from MailerLite — the store the copy was written for."""
    import requests
    token = (pathlib.Path.home() / "kdesk-analytics" / "mailerlite-token.txt").read_text().strip()
    r = requests.get(f"https://connect.mailerlite.com/api/subscribers/{email}",
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                     timeout=30)
    if r.status_code >= 300:
        return {}
    fields = (r.json().get("data") or {}).get("fields") or {}
    return {k: fields.get(k) for k in MERGE_FIELDS}


def send_all(markdown: str, dry_run: bool, repo: pathlib.Path | None, limit: int | None = None):
    subject_tpl, body_tpl, recipients = parse(markdown)
    sent = failed = 0
    for rcpt in recipients[:limit]:
        fields = merge_fields_for(rcpt.email, rcpt.product)
        try:
            subject = render(subject_tpl, fields)
            body = render(body_tpl, fields)
        except KeyError as exc:
            failed += 1
            print(f"  SKIP {rcpt.email:<40} {exc}")
            if not dry_run and repo is not None:
                card = write_queue_card(repo, "manual", f"reengage-{rcpt.email.replace('@', '-at-')}",
                                        queue_card_markdown(
                                            kind="email",
                                            title=f"Send the re-engagement email to {rcpt.email} by hand",
                                            why=(f"send_reengage.py could not fill its merge fields "
                                                 f"from MailerLite: {exc}"),
                                            steps=[f"Open {SOURCE.relative_to(REPO)}",
                                                   f"Fill {', '.join(MERGE_FIELDS)} for "
                                                   f"'{rcpt.product}' by hand",
                                                   f"Send from {SENDER} to {rcpt.email}"]))
                print(f"       queued -> {card.relative_to(repo)}")
            continue
        if dry_run:
            sent += 1
            print(f"\n--- would send to {rcpt.email} (MailerLite id {rcpt.subscriber_id})")
            print(f"Subject: {subject}\n{body}")
            continue
        _gws(["gmail", "users", "messages", "send", "--params", json.dumps({"userId": "me"})],
             {"raw": rfc822(rcpt.email, subject, body)})
        sent += 1
        print(f"  sent {rcpt.email}")
        ledger.append(
            action=(f"Sent the 2026-09 re-engagement email to {rcpt.email} (MailerLite subscriber "
                    f"{rcpt.subscriber_id}, took the free {rcpt.product}) from {SENDER}. "
                    f"Subject: {subject}. Copy verbatim from "
                    f"{SOURCE.relative_to(REPO)}; merge fields from MailerLite."),
            tier=1, status="executed",
            reasoning=("Decision 35 activated the free→paid automation as 'new subscribers only', "
                       "so these downloaders never received any email. The send is gated on the "
                       "T1-loosening veto window."),
            files=[str(SOURCE.relative_to(REPO))])
        _sleep(GAP_SECONDS)
    return sent, failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Send the 2026-09 re-engagement email.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--veto-entry", type=int, default=VETO_ENTRY_DEFAULT)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    markdown = SOURCE.read_text(encoding="utf-8")
    if a.dry_run:
        sent, failed = send_all(markdown, dry_run=True, repo=None, limit=a.limit)
        print(f"\n(dry-run) {sent} rendered, {failed} could not be filled — nothing sent")
        return 0
    entry = ledger.find(a.veto_entry, LEDGER_PATH)
    if entry is None:
        print(f"REFUSING: ledger entry {a.veto_entry} does not exist. The T1-loosening entry that "
              f"authorises autonomous sends has not been written yet — run Phase 0 first, or pass "
              f"--veto-entry with the id that carries the window "
              f"(python3 scripts/ledger.py --tail 5).", file=sys.stderr)
        return 2
    ok, why = veto_ok(entry.get("veto_window_close"), dt.datetime.now().astimezone())
    if not ok:
        print(f"REFUSING: entry {a.veto_entry} — {why}", file=sys.stderr)
        return 2
    print(f"entry {a.veto_entry}: {why}")
    sent, failed = send_all(markdown, dry_run=False, repo=REPO, limit=a.limit)
    print(f"{sent} sent, {failed} queued")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_send_reengage.py -q`
Expected: PASS, 15 tests.

- [ ] **Step 5: Verify against the real draft**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 scripts/sales/send_reengage.py --dry-run 2>&1 | head -40
python3 scripts/sales/send_reengage.py --dry-run 2>&1 | grep -c '^--- would send to'
python3 scripts/sales/send_reengage.py; echo "rc=$?"
git status --porcelain
```

Expected: the dry run renders each recipient's subject and body (the grep counts the 14 rows minus any whose MailerLite fields are empty, which print `SKIP` instead); the live run **refuses** with `REFUSING: ledger entry 69 …` and `rc=2` until the Phase-0 veto entry exists and its window has closed; `git status` is clean.

- [ ] **Step 6: Commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q` — expected 134 passed (119 + 15).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/sales/send_reengage.py tests/test_send_reengage.py
git commit -m "feat(sales): send_reengage.py sends the drafted re-engagement email via gws

Parses subject, body and the recipient table straight out of
marketing/email-sequences/re-engage-2026-09.md (the script never writes copy), fills merge
fields from MailerLite, and sends one Gmail per recipient two seconds apart with a ledger
line each. A recipient whose merge fields cannot be filled gets a queue card, not a
half-rendered email. Refuses to send until the T2 veto window in the named ledger entry has
closed, and says so clearly when that entry does not exist yet.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 8: `scripts/digest.py` — the daily digest

**Files:**
- Create: `scripts/digest.py`
- Create: `tests/test_digest.py`

**Interfaces:**
- Consumes: `ledger.entries(...)` and `ledger.append(...)` (Task 1); the queue folders written by Tasks 2, 3 and 7.
- Produces:
  - `digest.Section` dataclass: `heading: str`, `lines: list[str]`
  - `digest.recent_entries(entries, now, hours=24) -> list[dict]`
  - `digest.open_veto_windows(entries, now) -> list[dict]`
  - `digest.queue_cards(repo) -> list[pathlib.Path]`
  - `digest.snapshot_delta(path, keys) -> dict` — last row minus the previous row for each dotted key
  - `digest.compose(now, recent, veto, cards, deltas) -> str`
  - `digest.vault_path(now) -> pathlib.Path` — `~/CommandCenter/01-Daily/YYYY-MM-DD.md`
  - `digest.append_to_vault(markdown, now, *, root=None) -> pathlib.Path` — idempotent under a `## KDesk digest` heading
  - `digest.SNAPSHOTS: tuple[tuple[str, tuple[str, ...]], ...]` — which JSONL and which dotted keys

**Snapshot keys, from the real files:** `gumroad-snapshots.jsonl` → `all_time.paid_full_price`, `all_time.download_events`, `all_time.unique_people`, `all_time.revenue_usd`; `youtube-snapshots.jsonl` and `ga4-snapshots.jsonl` / `gsc-snapshots.jsonl` are read the same way but only for keys that exist in the last two rows — `snapshot_delta` skips a key that is missing rather than crashing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_digest.py`:

```python
"""scripts/digest.py — the 07:30 summary: what happened, what is queued, what moved."""
import datetime as dt
import json

import digest

TZ = dt.timezone(dt.timedelta(hours=-7))
NOW = dt.datetime(2026, 9, 14, 7, 30, tzinfo=TZ)
ENTRIES = [
    {"id": 66, "ts": "2026-09-10T10:55:00-0700", "tier": 0, "status": "executed",
     "action": "Old thing", "reasoning": "r", "files": [], "veto_window_close": None,
     "stephen_reviewed": True},
    {"id": 69, "ts": "2026-09-13T20:00:00-0700", "tier": 1, "status": "executed",
     "action": "Published asc842-short-liability.mp4 to youtube: https://youtu.be/NEW",
     "reasoning": "r", "files": [], "veto_window_close": None, "stephen_reviewed": False},
    {"id": 70, "ts": "2026-09-14T06:00:00-0700", "tier": 2, "status": "in_progress",
     "action": "T1 loosening", "reasoning": "r", "files": [],
     "veto_window_close": "2026-09-16T09:00:00-0700", "stephen_reviewed": False},
    {"id": 71, "ts": "2026-09-14T06:05:00-0700", "tier": 2, "status": "executed",
     "action": "Closed window", "reasoning": "r", "files": [],
     "veto_window_close": "2026-09-01T09:00:00-0700", "stephen_reviewed": True},
]


def test_recent_entries_keeps_only_the_last_24_hours():
    recent = digest.recent_entries(ENTRIES, NOW, hours=24)
    assert [e["id"] for e in recent] == [69, 70, 71]


def test_open_veto_windows_lists_only_windows_still_in_the_future():
    assert [e["id"] for e in digest.open_veto_windows(ENTRIES, NOW)] == [70]


def test_queue_cards_lists_every_card_across_every_platform_folder(tmp_path):
    for sub, name in (("manual", "2026-09-14-login-gumroad.md"),
                      ("tiktok", "2026-09-14-asc842-liability.md")):
        d = tmp_path / "marketing" / "publish-queue" / sub
        d.mkdir(parents=True)
        (d / name).write_text("# card\n")
        (d / "asset.mp4").write_bytes(b"v")            # mp4s are not cards
    cards = digest.queue_cards(tmp_path)
    assert sorted(p.name for p in cards) == ["2026-09-14-asc842-liability.md",
                                             "2026-09-14-login-gumroad.md"]


def test_queue_cards_is_empty_when_the_folder_does_not_exist(tmp_path):
    assert digest.queue_cards(tmp_path) == []


def test_snapshot_delta_subtracts_the_previous_row(tmp_path):
    p = tmp_path / "gumroad-snapshots.jsonl"
    p.write_text("\n".join([
        json.dumps({"all_time": {"paid_full_price": 0, "download_events": 15, "revenue_usd": 16.99}}),
        json.dumps({"all_time": {"paid_full_price": 0, "download_events": 17, "revenue_usd": 16.99}}),
    ]) + "\n")
    delta = digest.snapshot_delta(p, ("all_time.paid_full_price", "all_time.download_events",
                                      "all_time.revenue_usd"))
    assert delta == {"all_time.paid_full_price": (0, 0.0),
                     "all_time.download_events": (17, 2.0),
                     "all_time.revenue_usd": (16.99, 0.0)}


def test_snapshot_delta_skips_a_key_absent_from_the_rows(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"a": 1}) + "\n" + json.dumps({"a": 3}) + "\n")
    assert digest.snapshot_delta(p, ("a", "missing.key")) == {"a": (3, 2.0)}


def test_snapshot_delta_of_a_single_row_reports_the_value_with_no_delta(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"a": 5}) + "\n")
    assert digest.snapshot_delta(p, ("a",)) == {"a": (5, None)}


def test_snapshot_delta_of_a_missing_file_is_empty(tmp_path):
    assert digest.snapshot_delta(tmp_path / "nope.jsonl", ("a",)) == {}


def test_compose_has_every_section_and_names_the_open_window(tmp_path):
    md = digest.compose(NOW, digest.recent_entries(ENTRIES, NOW),
                        digest.open_veto_windows(ENTRIES, NOW),
                        [tmp_path / "marketing/publish-queue/tiktok/2026-09-14-x.md"],
                        {"gumroad-snapshots.jsonl": {"all_time.download_events": (17, 2.0)}})
    assert md.startswith("## KDesk digest — 2026-09-14\n")
    for heading in ("### Shipped in the last 24 h", "### Waiting on Stephen",
                    "### Open veto windows", "### Numbers"):
        assert heading in md
    assert "https://youtu.be/NEW" in md
    assert "2026-09-14-x.md" in md
    assert "closes 2026-09-16T09:00:00-0700" in md
    assert "all_time.download_events" in md and "+2" in md


def test_compose_says_so_plainly_when_nothing_happened():
    md = digest.compose(NOW, [], [], [], {})
    assert "Nothing logged in the last 24 h." in md
    assert "Queue is empty." in md
    assert "No open veto windows." in md


def test_vault_path_is_todays_daily_note(tmp_path):
    assert digest.vault_path(NOW, root=tmp_path) == tmp_path / "01-Daily" / "2026-09-14.md"


def test_append_to_vault_creates_the_note_when_it_is_missing(tmp_path):
    p = digest.append_to_vault("## KDesk digest — 2026-09-14\n\nbody\n", NOW, root=tmp_path)
    assert p.read_text().startswith("## KDesk digest — 2026-09-14")


def test_append_to_vault_replaces_an_earlier_digest_rather_than_stacking(tmp_path):
    note = tmp_path / "01-Daily" / "2026-09-14.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Tuesday\n\nMorning pages.\n\n## KDesk digest — 2026-09-14\n\nold\n\n## Later\n\nkeep me\n")
    digest.append_to_vault("## KDesk digest — 2026-09-14\n\nnew\n", NOW, root=tmp_path)
    text = note.read_text()
    assert text.count("## KDesk digest") == 1
    assert "new" in text and "old" not in text
    assert "Morning pages." in text and "keep me" in text


def test_send_builds_a_gmail_to_stephen_through_the_seam(monkeypatch):
    calls = []
    monkeypatch.setattr(digest, "_gws", lambda argv, body=None: calls.append((argv, body)) or {"id": "m"})
    digest.send("## KDesk digest — 2026-09-14\n\nbody\n", NOW)
    argv, body = calls[0]
    assert argv[:4] == ["gmail", "users", "messages", "send"]
    assert "raw" in body


def test_main_dry_run_prints_and_neither_sends_nor_writes(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(digest, "REPO", tmp_path)
    monkeypatch.setattr(digest, "_gws", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    monkeypatch.setattr(digest.ledger, "entries", lambda path=None: ENTRIES)
    monkeypatch.setattr("sys.argv", ["digest.py", "--dry-run", "--send", "--vault"])
    assert digest.main() == 0
    assert "## KDesk digest" in capsys.readouterr().out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_digest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'digest'`.

- [ ] **Step 3: Write `scripts/digest.py`**

```python
#!/usr/bin/env python3
"""The daily digest: what published, what is queued for Stephen, what moved, what is open.

  python3 scripts/digest.py                       # print the markdown
  python3 scripts/digest.py --send                # + email it to Stephen via gws
  python3 scripts/digest.py --vault               # + append it to today's ~/CommandCenter note
  python3 scripts/digest.py --send --vault --dry-run   # compose only, no send, no write
  python3 scripts/digest.py --out "$GITHUB_STEP_SUMMARY"

Sections: ledger entries in the last 24 h · queue cards outstanding · snapshot deltas from the
JSONL trackers · open veto windows. Appending to the vault is idempotent — a second run the
same day replaces its own "## KDesk digest" section rather than stacking another copy.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from email.message import EmailMessage

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ledger  # noqa: E402

VAULT_ROOT = pathlib.Path.home() / "CommandCenter"
VAULT_HEADING = "## KDesk digest"
SENDER = "santiagokdesk@gmail.com"
RECIPIENT = "santiagokdesk@gmail.com"
TRACKING = REPO / "marketing" / "seo-tracking"
SNAPSHOTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gumroad-snapshots.jsonl", ("all_time.paid_full_price", "all_time.download_events",
                                 "all_time.unique_people", "all_time.revenue_usd")),
    ("youtube-snapshots.jsonl", ("totals.views", "totals.subscribers")),
    ("mailerlite-sync.jsonl", ()),
)


@dataclasses.dataclass(frozen=True)
class Section:
    heading: str
    lines: list[str]

    def render(self) -> str:
        body = "\n".join(self.lines) if self.lines else "_(nothing)_"
        return f"{self.heading}\n\n{body}\n"


def recent_entries(entries: list[dict], now: dt.datetime, hours: int = 24) -> list[dict]:
    cutoff = now - dt.timedelta(hours=hours)
    out = []
    for row in entries:
        try:
            stamp = dt.datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if stamp >= cutoff:
            out.append(row)
    return out


def open_veto_windows(entries: list[dict], now: dt.datetime) -> list[dict]:
    out = []
    for row in entries:
        close = row.get("veto_window_close")
        if not close:
            continue
        try:
            if dt.datetime.fromisoformat(close) > now:
                out.append(row)
        except ValueError:
            continue
    return out


def queue_cards(repo: pathlib.Path) -> list[pathlib.Path]:
    root = pathlib.Path(repo) / "marketing" / "publish-queue"
    return sorted(root.rglob("*.md")) if root.exists() else []


def _dig(row: dict, dotted: str):
    node = row
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, (int, float)) else None


def snapshot_delta(path: pathlib.Path, keys: tuple[str, ...]) -> dict:
    path = pathlib.Path(path)
    if not path.exists() or not keys:
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {}
    last, previous = rows[-1], (rows[-2] if len(rows) > 1 else None)
    out = {}
    for key in keys:
        now_value = _dig(last, key)
        if now_value is None:
            continue
        if previous is None:
            out[key] = (now_value, None)
            continue
        before = _dig(previous, key)
        out[key] = (now_value, None if before is None else round(float(now_value) - float(before), 2))
    return out


def _fmt_delta(delta) -> str:
    if delta is None:
        return "(first row)"
    if delta == 0:
        return "±0"
    return f"{'+' if delta > 0 else ''}{delta:g}"


def compose(now: dt.datetime, recent: list[dict], veto: list[dict],
            cards: list[pathlib.Path], deltas: dict) -> str:
    shipped = Section("### Shipped in the last 24 h",
                      [f"- **{r['id']}** T{r['tier']} {r['action'][:220]}" for r in recent]
                      or ["Nothing logged in the last 24 h."])
    waiting = Section("### Waiting on Stephen",
                      [f"- `{p.parent.name}/{p.name}`" for p in cards] or ["Queue is empty."])
    windows = Section("### Open veto windows",
                      [f"- **{r['id']}** closes {r['veto_window_close']} — {r['action'][:160]}"
                       for r in veto] or ["No open veto windows."])
    number_lines = []
    for filename, values in deltas.items():
        for key, (value, delta) in values.items():
            number_lines.append(f"- `{filename}` **{key}** = {value} ({_fmt_delta(delta)})")
    numbers = Section("### Numbers", number_lines or ["No snapshot rows yet."])
    parts = "\n".join(s.render() for s in (shipped, waiting, windows, numbers))
    return f"{VAULT_HEADING} — {now.strftime('%Y-%m-%d')}\n\n{parts}"


def vault_path(now: dt.datetime, *, root: pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(root or VAULT_ROOT) / "01-Daily" / f"{now.strftime('%Y-%m-%d')}.md"


def append_to_vault(markdown: str, now: dt.datetime, *, root: pathlib.Path | None = None):
    path = vault_path(now, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = markdown if markdown.endswith("\n") else markdown + "\n"
    if not path.exists():
        path.write_text(body, encoding="utf-8")
        return path
    existing = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(VAULT_HEADING)}.*?$\n.*?(?=^## (?!KDesk digest)|\Z)",
                         re.S | re.M)
    if pattern.search(existing):
        path.write_text(pattern.sub(lambda _m: body + "\n", existing, count=1), encoding="utf-8")
    else:
        path.write_text(existing.rstrip("\n") + "\n\n" + body, encoding="utf-8")
    return path


def _gws(argv: list[str], body: dict | None = None) -> dict:
    cmd = ["gws", *argv]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"gws send failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def send(markdown: str, now: dt.datetime) -> dict:
    msg = EmailMessage()
    msg["To"] = RECIPIENT
    msg["From"] = f"KDesk digest <{SENDER}>"
    msg["Subject"] = f"KDesk digest — {now.strftime('%Y-%m-%d')}"
    msg.set_content(markdown)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
    return _gws(["gmail", "users", "messages", "send", "--params", json.dumps({"userId": "me"})],
                {"raw": raw})


def main() -> int:
    ap = argparse.ArgumentParser(description="Compose (and optionally send) the daily digest.")
    ap.add_argument("--send", action="store_true", help="email it to Stephen via gws")
    ap.add_argument("--vault", action="store_true",
                    help="append it to ~/CommandCenter/01-Daily/YYYY-MM-DD.md (local only)")
    ap.add_argument("--out", type=pathlib.Path, help="also write the markdown to this file")
    ap.add_argument("--dry-run", action="store_true", help="compose only; never send or write")
    a = ap.parse_args()
    now = dt.datetime.now().astimezone()
    entries = ledger.entries()
    deltas = {name: snapshot_delta(TRACKING / name, keys) for name, keys in SNAPSHOTS}
    deltas = {name: values for name, values in deltas.items() if values}
    markdown = compose(now, recent_entries(entries, now), open_veto_windows(entries, now),
                       queue_cards(REPO), deltas)
    print(markdown)
    if a.dry_run:
        return 0
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    if a.vault:
        print(f"vault -> {append_to_vault(markdown, now)}", file=sys.stderr)
    if a.send:
        send(markdown, now)
        print("emailed to " + RECIPIENT, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_digest.py -q`
Expected: PASS, 15 tests.

- [ ] **Step 5: Verify against the real repo and vault**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
python3 scripts/digest.py --dry-run
python3 scripts/digest.py --vault
grep -c '^## KDesk digest' ~/CommandCenter/01-Daily/$(date +%F).md
python3 scripts/digest.py --vault
grep -c '^## KDesk digest' ~/CommandCenter/01-Daily/$(date +%F).md
python3 scripts/digest.py --send
```

Expected: the digest lists the entries written by Tasks 4, 6 and 7 plus the real Gumroad numbers; both `grep -c` runs print `1` (the second run replaced its own section, it did not stack); `--send` puts one message in `santiagokdesk@gmail.com`. Then commit the vault change:

```bash
cd ~/CommandCenter && git add 01-Daily && git commit -m "KDesk digest $(date +%F)" && git push
```

- [ ] **Step 6: Commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q` — expected 149 passed (134 + 15).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add scripts/digest.py tests/test_digest.py
git commit -m "feat(digest): daily digest of ledger, queue, snapshot deltas and open vetoes

Composes one markdown digest from the last 24 h of decisions/decisions.jsonl, every
outstanding card under marketing/publish-queue/, the deltas between the last two rows of
each seo-tracking JSONL, and every veto window still in the future. --send emails it to
Stephen through gws; --vault appends it idempotently under '## KDesk digest' in today's
~/CommandCenter daily note, replacing its own earlier section instead of stacking.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

### Task 9: GitHub Actions — `data-weekly.yml` and `daily-publish.yml`

**Files:**
- Create: `.github/workflows/data-weekly.yml`, `.github/workflows/daily-publish.yml`
- Create: `tests/test_workflows.py`
- Create: `marketing/runbooks/automation-2026-09.md`

**Interfaces:**
- Consumes: every script from Tasks 1–8 (each must already work with `--dry-run` from a clean checkout).
- Produces: two scheduled workflows plus a runbook documenting the `gh secret set` commands.

**Cron, in UTC** (Actions has no local time zone): 08:15 PT is **15:15 UTC** during PDT and 16:15 UTC during PST; 07:00 PT is **14:00 UTC** during PDT. This plan pins the PDT values and the runbook records that both jobs run an hour early between the November and March changeovers — acceptable for a data pull and a morning publish.

> **Two Actions limits, recorded rather than papered over.** (1) `gws` is a local Homebrew binary carrying credentials at `~/.config/gws/`; it does not exist on a runner. So `crm_sync.py` runs **`--dry-run` on Actions** (proving the Gumroad and MailerLite pulls work from CI) and live **on the Mac**. (2) For the same reason `digest.py --send` cannot run on a runner, and `--vault` never can — the vault is local. `daily-publish.yml` therefore writes the digest into the job summary, and a `send_digest` input lets a future run switch on the email once a non-`gws` Gmail path exists. The Mac keeps sending the real one. Both limits are stated in the workflow comments so nobody re-discovers them.

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows.py`:

```python
"""The two scheduled workflows: pinned crons, the right secrets, dry_run everywhere it matters."""
import pathlib
import re

import pytest

WF = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
WEEKLY = WF / "data-weekly.yml"
DAILY = WF / "daily-publish.yml"


@pytest.mark.parametrize("path", [WEEKLY, DAILY])
def test_the_workflow_exists_and_offers_manual_dispatch_with_a_dry_run_input(path):
    text = path.read_text()
    assert "workflow_dispatch:" in text
    assert "dry_run:" in text
    assert "default: 'true'" in text


def test_weekly_runs_monday_at_0815_pt():
    text = WEEKLY.read_text()
    assert re.search(r"- cron: '15 15 \* \* 1'", text), "Mon 15:15 UTC == 08:15 PDT"


def test_daily_runs_at_0700_pt():
    assert re.search(r"- cron: '0 14 \* \* \*'", DAILY.read_text()), "14:00 UTC == 07:00 PDT"


def test_weekly_runs_all_four_pullers_and_the_crm_sync():
    text = WEEKLY.read_text()
    for script in ("pull_seo_snapshot.py", "pull_gumroad_snapshot.py",
                   "pull_youtube_snapshot.py", "pull_bing_snapshot.py",
                   "sales/crm_sync.py"):
        assert script in text, script


def test_weekly_wires_every_documented_secret():
    text = WEEKLY.read_text()
    for secret in ("GUMROAD_ACCESS_TOKEN", "MAILERLITE_TOKEN", "GOOGLE_TOKEN_JSON", "BING_API_KEY"):
        assert f"secrets.{secret}" in text, secret


def test_weekly_commits_the_snapshot_files_only():
    text = WEEKLY.read_text()
    assert "git add marketing/seo-tracking/*.jsonl" in text
    assert "contents: write" in text


def test_daily_downloads_the_weekly_media_release_and_publishes_each_platform():
    text = DAILY.read_text()
    assert "media-daily-" in text
    assert "gh release download" in text
    assert "scripts/publishers/publish.py" in text
    assert "--platform youtube" in text and "--platform tiktok" in text \
        and "--platform instagram" in text


def test_daily_passes_the_upload_post_key_and_runs_the_digest():
    text = DAILY.read_text()
    assert "secrets.UPLOAD_POST_KEY" in text
    assert "scripts/digest.py" in text
    assert "GITHUB_STEP_SUMMARY" in text


def test_daily_documents_that_the_vault_append_cannot_run_on_actions():
    assert "--vault" in DAILY.read_text()
    assert "vault is local" in DAILY.read_text().lower()


def test_neither_workflow_hardcodes_a_secret():
    for path in (WEEKLY, DAILY):
        text = path.read_text()
        assert "Apikey " not in text
        assert not re.search(r"(?i)token\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", text), path.name
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_workflows.py -q`
Expected: FAIL — `FileNotFoundError: .github/workflows/data-weekly.yml`.

- [ ] **Step 3: Write `.github/workflows/data-weekly.yml`**

```yaml
name: Weekly data pulls

# Mondays 15:15 UTC = 08:15 PDT (16:15 UTC would be 08:15 PST; the job runs an hour early
# between the November and March changeovers, which is fine for a data pull).
# This replaces the Monday block of ~/kdesk-analytics/kdesk-daily.sh so the pulls happen
# whether or not the Mac is awake. Local files stay authoritative for credentials.
on:
  schedule:
    - cron: '15 15 * * 1'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Pull and print, but commit nothing'
        type: boolean
        required: false
        default: 'true'

permissions:
  contents: write

concurrency:
  group: data-weekly
  cancel-in-progress: false

jobs:
  pull:
    runs-on: ubuntu-latest
    env:
      GUMROAD_ACCESS_TOKEN: ${{ secrets.GUMROAD_ACCESS_TOKEN }}
      MAILERLITE_TOKEN: ${{ secrets.MAILERLITE_TOKEN }}
      BING_API_KEY: ${{ secrets.BING_API_KEY }}
      KDESK_SEO_SKIP_COMMIT: '1'
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5

      - name: Restore the credential files the scripts read by path
        run: |
          mkdir -p ~/kdesk-analytics ~/kdeskaccountingtemplates
          printf '%s' "$GOOGLE_TOKEN_JSON" > ~/kdesk-analytics/google-token.json
          printf '%s\n' "$MAILERLITE_TOKEN" > ~/kdesk-analytics/mailerlite-token.txt
          printf '%s\n' "$BING_API_KEY" > ~/kdesk-analytics/bing-api-key.txt
          printf 'GUMROAD_ACCESS_TOKEN=%s\n' "$GUMROAD_ACCESS_TOKEN" > ~/kdeskaccountingtemplates/.env
          chmod 600 ~/kdesk-analytics/* ~/kdeskaccountingtemplates/.env
        env:
          GOOGLE_TOKEN_JSON: ${{ secrets.GOOGLE_TOKEN_JSON }}

      - name: GSC + GA4 + target queries
        run: uv run scripts/pull_seo_snapshot.py

      - name: Gumroad
        run: uv run --with requests scripts/pull_gumroad_snapshot.py

      - name: YouTube
        continue-on-error: true   # the token lost youtube.force-ssl on 2026-09-11 (ledger 68)
        run: uv run scripts/pull_youtube_snapshot.py --print

      - name: Bing
        continue-on-error: true   # exits with setup instructions until the API key exists
        run: uv run scripts/pull_bing_snapshot.py --print

      # gws is a local Homebrew binary holding santiagokdesk credentials under ~/.config/gws,
      # so the CRM sheet can only be written from the Mac. CI proves the pulls and the diff.
      - name: CRM sync (dry run — gws is not available on a runner)
        run: uv run --with requests scripts/sales/crm_sync.py --dry-run

      - name: Commit the snapshot rows
        if: ${{ github.event_name == 'schedule' || inputs.dry_run != true }}
        run: |
          git config user.name  'kdesk-bot'
          git config user.email 'santiagokdesk@gmail.com'
          git add marketing/seo-tracking/*.jsonl
          git diff --cached --quiet || git commit -m "Weekly data snapshots $(date +%F)"
          git push
```

- [ ] **Step 4: Write `.github/workflows/daily-publish.yml`**

```yaml
name: Daily publish

# 14:00 UTC = 07:00 PDT. Reads the week's rendered asset from the GitHub release
# media-daily-YYYY-WW (the Mac renders on Saturday and pushes the release), so a sleeping
# Mac never breaks the daily cadence.
on:
  schedule:
    - cron: '0 14 * * *'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Compose and print, but publish nothing'
        type: boolean
        required: false
        default: 'true'
      slug:
        description: "Asset slug to publish (default: today's date)"
        type: string
        required: false
        default: ''
      send_digest:
        description: 'Email the digest (needs a non-gws Gmail path; off by default)'
        type: boolean
        required: false
        default: 'false'

permissions:
  contents: read

concurrency:
  group: daily-publish
  cancel-in-progress: false

jobs:
  publish:
    runs-on: ubuntu-latest
    env:
      UPLOAD_POST_KEY: ${{ secrets.UPLOAD_POST_KEY }}
      UPLOAD_POST_PROFILE: kdesk
      GH_TOKEN: ${{ github.token }}
      DRY: ${{ (github.event_name == 'workflow_dispatch' && inputs.dry_run == true) && '--dry-run' || '' }}
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5

      - name: Work out today's release and slug
        id: today
        run: |
          echo "release=media-daily-$(date -u +%Y-%V)" >> "$GITHUB_OUTPUT"
          echo "slug=${SLUG:-$(date -u +%Y-%m-%d)}" >> "$GITHUB_OUTPUT"
        env:
          SLUG: ${{ inputs.slug }}

      - name: Download the day's asset and its meta
        run: |
          mkdir -p build
          gh release download "${{ steps.today.outputs.release }}" \
            --pattern "${{ steps.today.outputs.slug }}.mp4" --dir build --clobber
          gh release download "${{ steps.today.outputs.release }}" \
            --pattern "${{ steps.today.outputs.slug }}.json" --dir build --clobber

      - name: Publish to YouTube
        run: uv run --with requests scripts/publishers/publish.py --platform youtube
             --asset "build/${{ steps.today.outputs.slug }}.mp4"
             --meta "build/${{ steps.today.outputs.slug }}.json" $DRY

      - name: Publish to TikTok
        run: uv run --with requests scripts/publishers/publish.py --platform tiktok
             --asset "build/${{ steps.today.outputs.slug }}.mp4"
             --meta "build/${{ steps.today.outputs.slug }}.json" $DRY

      - name: Publish to Instagram
        run: uv run --with requests scripts/publishers/publish.py --platform instagram
             --asset "build/${{ steps.today.outputs.slug }}.mp4"
             --meta "build/${{ steps.today.outputs.slug }}.json" $DRY

      # digest.py --send needs the gws CLI (local, santiagokdesk credentials) and --vault
      # needs ~/CommandCenter, which is local too — the vault is local, so neither runs here.
      # The Mac's 07:30 job sends the real digest; this writes it into the run summary and
      # only emails when send_digest is switched on and a non-gws Gmail path exists.
      - name: Digest into the run summary
        run: uv run scripts/digest.py --out "$GITHUB_STEP_SUMMARY"

      - name: Digest by email (opt-in)
        if: ${{ github.event_name == 'workflow_dispatch' && inputs.send_digest == true }}
        run: uv run scripts/digest.py --send

      - name: Surface anything that queued
        run: |
          shopt -s nullglob
          cards=(marketing/publish-queue/*/*.md)
          if [ ${#cards[@]} -gt 0 ]; then
            printf '### Queued for Stephen\n' >> "$GITHUB_STEP_SUMMARY"
            for c in "${cards[@]}"; do printf -- '- %s\n' "$c" >> "$GITHUB_STEP_SUMMARY"; done
          fi
```

- [ ] **Step 5: Run the workflow test to verify it passes**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/test_workflows.py -q`
Expected: PASS, 11 tests.

- [ ] **Step 6: Prove the YAML actually parses**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
uv run --with pyyaml python -c "
import yaml, pathlib
for p in sorted(pathlib.Path('.github/workflows').glob('*.yml')):
    d = yaml.safe_load(p.read_text())
    print(p.name, '->', list(d.get('jobs', {})))
"
```

Expected: `data-weekly.yml -> ['pull']`, `daily-publish.yml -> ['publish']`, `deploy.yml -> ['build', 'deploy']` — no parse error. (YAML reads the `on:` key as the boolean `True`; that is normal and harmless.)

- [ ] **Step 7: Write the runbook with the exact `gh secret set` commands**

Create `marketing/runbooks/automation-2026-09.md`:

````markdown
# Automation runbook — Phase 1 (2026-09)

Read this with `docs/superpowers/plans/2026-09-14-kdesk-automation-phase1.md`.

## Set the Actions secrets (one time, from the Mac)

Every value already exists locally; nothing here is committed.

```bash
R=kdeskaccounting/kdeskaccounting.github.io

gh secret set GUMROAD_ACCESS_TOKEN --repo "$R" \
  --body "$(grep '^GUMROAD_ACCESS_TOKEN' ~/kdeskaccountingtemplates/.env | cut -d= -f2- | tr -d '"'"'"'')"

gh secret set MAILERLITE_TOKEN --repo "$R" --body "$(cat ~/kdesk-analytics/mailerlite-token.txt)"

gh secret set GOOGLE_TOKEN_JSON --repo "$R" < ~/kdesk-analytics/google-token.json

# Stephen creates this key first: bing.com/webmasters -> Settings -> API Access -> API Key
gh secret set BING_API_KEY --repo "$R" --body "$(cat ~/kdesk-analytics/bing-api-key.txt)"

# From https://www.upload-post.com/ after connecting YouTube, TikTok and Instagram
gh secret set UPLOAD_POST_KEY --repo "$R"        # prompts, so the key never hits the shell history

gh secret list --repo "$R"
```

## Schedules

| Workflow | Cron (UTC) | Local | Does |
|---|---|---|---|
| `data-weekly.yml` | `15 15 * * 1` | Mon 08:15 PDT | GSC/GA4 + Gumroad + YouTube + Bing pulls, CRM dry run, commits the JSONL rows |
| `daily-publish.yml` | `0 14 * * *` | 07:00 PDT | Downloads the day's asset from `media-daily-YYYY-WW`, publishes YouTube/TikTok/Instagram, writes the digest to the run summary |

Both take `workflow_dispatch` with `dry_run` defaulting to **true**, so a manual run never
publishes by accident:

```bash
gh workflow run data-weekly.yml -f dry_run=true
gh workflow run daily-publish.yml -f dry_run=true -f slug=2026-09-15
gh run list --limit 5
gh run view --log-failed
```

## What still only runs on the Mac, and why

- **`scripts/sales/crm_sync.py`** (live) — needs the `gws` CLI and its santiagokdesk
  credentials under `~/.config/gws/`. CI runs `--dry-run`.
- **`scripts/digest.py --send --vault`** — `--send` needs `gws`; `--vault` needs
  `~/CommandCenter`. CI writes the digest into the run summary instead.
- **Rendering** (`build_video.py`, `make_short.py`) — LibreOffice, Kokoro TTS and the
  Playwright Chromium shell. The Mac renders on Saturday and pushes the release the daily
  job reads.
- **Every Chrome driver** (`scripts/browser/`, the two Gumroad UI scripts) — spec Chrome
  rule 1: Chrome is never on the recurring path.

## Turning off the old launchd Monday block

Once `data-weekly.yml` has committed two consecutive Mondays, remove the Monday branch from
`~/kdesk-analytics/kdesk-daily.sh` (keep the daily MailerLite sync) so the pulls do not run
twice and race on the same JSONL files. Back the file up first —
`cp ~/kdesk-analytics/kdesk-daily.sh ~/kdesk-analytics/kdesk-daily.sh.bak-$(date +%F)` — and
check the result with `zsh -n ~/kdesk-analytics/kdesk-daily.sh`.

## Weekly selector canary (spec Chrome rule 8)

While the debug Chrome is up on a Monday:

```bash
python3 scripts/browser/ensure_chrome.py
python3 scripts/browser/session.py --check gumroad mailerlite
scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check
scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check
```

Any drift shows up here, in the digest, before a driver is actually needed.
````

- [ ] **Step 8: Add the runbook to the "read first" list in `CLAUDE.md`**

Under "Read first, every session", insert a new item after the runbooks entry:

```
5. **`marketing/runbooks/automation-2026-09.md`** — Phase 1 automation: what runs on Actions,
   what only runs on the Mac and why, the `gh secret set` commands, the weekly selector canary.
```

(and renumber "The **Currently working on** section below." to 6).

- [ ] **Step 9: Dry-run both workflows once they are on `main`**

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
gh workflow list
gh workflow run data-weekly.yml -f dry_run=true && sleep 30 && gh run list --workflow data-weekly.yml --limit 1
gh workflow run daily-publish.yml -f dry_run=true && sleep 30 && gh run list --workflow daily-publish.yml --limit 1
gh run view --log-failed
```

Expected: `data-weekly` completes with the four pull steps green (YouTube and Bing may be yellow — both are `continue-on-error` with known causes) and commits nothing; `daily-publish` fails at the `gh release download` step until the first `media-daily-YYYY-WW` release exists, which is the correct, legible failure. Record that in the runbook rather than faking a release.

- [ ] **Step 10: Run the full suite and commit**

Run: `cd /Users/stephenmichels/kdeskaccounting.github.io && uv run --with pytest pytest tests/ -q`
Expected: 160 passed (149 + 11).

```bash
cd /Users/stephenmichels/kdeskaccounting.github.io
git add .github/workflows/data-weekly.yml .github/workflows/daily-publish.yml \
        tests/test_workflows.py marketing/runbooks/automation-2026-09.md CLAUDE.md
git commit -m "ci: weekly data pulls and daily publish on GitHub Actions

data-weekly.yml (Mon 15:15 UTC = 08:15 PDT) runs the four snapshot pullers plus a CRM dry
run from repo secrets and commits the JSONL rows, moving the Monday block off launchd so it
happens whether or not the Mac is awake. daily-publish.yml (14:00 UTC = 07:00 PDT) pulls the
day's asset from the media-daily-YYYY-WW release and runs publish.py per platform with
UPLOAD_POST_KEY, then writes the digest into the run summary. Both take workflow_dispatch
with dry_run defaulting to true. The runbook records the gh secret set commands and exactly
which steps can only run on the Mac (gws and the vault are local).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FpQS7CbmJhdugQKVRLPpdh"
```

---

## Verification (whole plan)

Run from `/Users/stephenmichels/kdeskaccounting.github.io` after every task is done:

```bash
uv run --with pytest pytest tests/ -q                      # 160 passed

python3 scripts/ledger.py --tail 5
python3 scripts/browser/ensure_chrome.py && python3 scripts/browser/session.py --check gumroad mailerlite
scripts/video/.venv-tts/bin/python scripts/video/gumroad_covers_ui.py --check
scripts/video/.venv-tts/bin/python scripts/video/gumroad_workflows_ui.py --check
python3 scripts/publishers/publish.py --capabilities
python3 scripts/video/reupload_locked.py --dry-run          # 20 records, every mp4 resolved
scripts/video/.venv-tts/bin/python scripts/video/build_video.py \
  --spec marketing/video/card-demo/scenes.yaml --frames-only
python3 scripts/sales/crm_sync.py --dry-run
python3 scripts/sales/send_reengage.py --dry-run
python3 scripts/digest.py --dry-run
gh workflow run data-weekly.yml -f dry_run=true && gh run list --limit 3
git status --porcelain                                     # clean: no dry run writes anything
```

**Live proofs for Phase 1** (each needs Stephen's one-time step first): the 20 re-uploaded
videos show `public` in the next `youtube-snapshots.jsonl` row; the CRM sheet's People tab
holds every Gumroad and MailerLite address; the 14 re-engagement emails appear in the
santiagokdesk Sent folder with 14 matching ledger entries; the digest arrives at 07:30.

---

## Self-Review

**1. Spec coverage.** Every Phase-1 item that lives in this repo has a task: Chrome rules 2/3/6/7/8 → Task 2 (rules 1 and 4 are honoured by design — no Chrome in either workflow, and both drivers keep the read/diff/apply/re-read shape; rule 5, driving the app's own JSON endpoints, is the MailerLite campaign work deferred to Phase 2 and is named in `selectors_mailerlite.py`). Track 2 row 3 (`card` scene kind) → Task 5; row 4 (Upload-Post publishing) → Task 3; row 5 (site cross-post) → Task 3's `site.py`. The YouTube-lock finding → Task 4. Track 3's CRM and re-engagement → Tasks 6 and 7. Track 4's `data-weekly.yml`, `daily-publish.yml` and the digest → Tasks 8 and 9. The ledger requirement → Task 1, used by Tasks 2, 3, 4, 6, 7 and 8.

**Deliberately out of scope**, because they are not Phase 1 or not this repo: `make product` and `product_pipeline.py` (they live in `~/kdeskaccountingtemplates`); everything under Track 1B (the venture's own repo); `plan_week.py` / `factcheck.py` (the cloud Claude routine, Phase 2); `linkedin.py` / `reddit.py` queue-only publishers (Phase 2 — the queue-card machinery they need is built here); `membership-sync.yml` and the Cloudflare Worker (Phase 4); `emit_pages.py` and `weekly_digest.py` to the list (Phase 3); `affiliate_links.py` (Phase 3). `run_daily.py` is not built here either — Task 3's `publish.py` is the piece of it Phase 1 needs.

**2. Placeholder scan.** No "TBD", no "similar to Task N", no "add error handling". Every code step carries the real code; every test step carries real assertions; the one deliberately generated artefact (the three golden HTML files) has an explicit generate-then-lock procedure with a visual check, because inventing 200 lines of exact HTML by hand would be a worse plan, not a better one.

**3. Type consistency.** `PublishResult(platform, ok, url, queued_path, detail)` is constructed identically in `base.py`, `upload_post.py`, `site.py` and consumed with the same field names in `publish.py`, `reupload_locked.py` and the tests. `ledger.append(action, tier, status, reasoning, files, veto_window_close=None, *, path, now)` is called with keyword arguments everywhere. `session.queue_card_markdown(kind, title, why, steps, now=None)` / `write_queue_card(repo, subdir, slug, body, now=None)` keep the same signature in `session.py`, both Gumroad drivers and `send_reengage.py`. `cards.card_html(template, data, brand, width, height)` matches its one caller, `render_sheets.render_card_scene`, which returns the `{"fx","fy","static"}` shape `focus.json` already uses. `crm_sync.Person.as_row()` and `Person.from_row()` are inverse over `COLUMNS`, and `a1()` spans exactly `len(COLUMNS)` columns.

**4. Conflicts found and how this plan resolves them.**

| Conflict | Resolution |
|---|---|
| Brief: "the veto close in ledger entry 69". The ledger's highest id is **68** — entry 69 does not exist. | `send_reengage.py` takes `--veto-entry` (default 69) and refuses with an explicit message when the entry is missing, is not a T2 window, or has not closed. Task 4 Step 11 writes a T0 finding that will itself take id 69 if Phase 0 has not run — so confirm the id with `scripts/ledger.py --tail 5` before the first live send. |
| Upload-Post docs disagree with themselves: landing page `file` + `platforms`, reference page `video` + `platform[]`. | Encode the reference page (`video` + `platform[]`), record it in `capabilities()["form_variant"]` so a fix is one constant, and note it in Task 3. |
| Brief: `data-weekly.yml` runs `crm_sync.py` on Actions. `gws` is a local Homebrew binary and the repo's Google token carries read-only GSC/GA4 scopes. | Actions runs `crm_sync.py --dry-run`; live writes stay on the Mac. Stated in the workflow comment, the runbook and Task 6. |
| Brief: `daily-publish.yml` runs `digest.py --send`. `--send` also needs `gws`. | The workflow writes the digest into `$GITHUB_STEP_SUMMARY` and gates `--send` behind a `send_digest` dispatch input; the Mac keeps sending the real one. Stated in Task 9. |
| Spec: "the four `pull_*_snapshot.py`". Ledger 68 records that `pull_youtube_snapshot.py` has been failing since 2026-09-07 (the token lost `youtube.force-ssl`) and `pull_bing_snapshot.py` exits with setup instructions because `~/kdesk-analytics/bing-api-key.txt` does not exist. | Both steps are `continue-on-error` with the reason in a comment, so a known-broken puller does not fail the whole weekly job. Fixing the scopes and creating the Bing key stay on Stephen's list. |
| Spec: re-upload "from GitHub release `media-2026-09` or `scripts/video/build/`". That release holds only the seven walkthrough mp4s and six posters — none of the Shorts. | `resolve_mp4()` looks in `scripts/video/build/<slug>/` (all 20 mp4s were verified present there on 2026-09-14) and prints the exact `gh release download` command when a file is missing, rather than pretending the release is a complete source. |
| `scripts/video/build/` is gitignored, so the mp4s exist only on the Mac. | `reupload_locked.py` is a Mac script by design; the Actions job reads assets from the `media-daily-YYYY-WW` release instead. |
| The test command `uv run --with pytest pytest tests/` installs pytest only — no `requests`, `yaml`, `playwright` or `openpyxl`. | Every module under test imports those lazily; Task 6 Step 3 fixes `pull_gumroad_snapshot.py`, which imports `requests` at module scope today and would otherwise be untestable. |
