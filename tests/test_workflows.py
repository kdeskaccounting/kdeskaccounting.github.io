"""The two scheduled workflows: pinned crons, the right secrets, dry_run everywhere it matters.

These assertions are parse-level, not substring soup: the workflow is read into a dict and
the steps are inspected as objects. That matters because the bugs worth catching here -- a
boolean input compared against a string, an input interpolated straight into a shell, a
`git add` on a file pathspec that .gitignore covers, a pipe that swallows an exit code --
all live in the *structure* of a step, not in whether some string appears somewhere.

The mandated test environment is `uv run --with pytest pytest tests/`: pytest and the
standard library, no PyYAML. So this module carries a small block-YAML reader covering the
subset GitHub workflow files use, and `test_the_lite_reader_agrees_with_pyyaml` pins it to
the real thing in any environment that does have PyYAML (`uv run --with pytest --with
pyyaml pytest tests/test_workflows.py`). If the two ever disagree, that test says so
instead of these assertions quietly drifting into fiction.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
WEEKLY = WF / "data-weekly.yml"
DAILY = WF / "daily-publish.yml"
DEPLOY = WF / "deploy.yml"


# --------------------------------------------------------------------------------------
# A block-YAML reader for the subset these workflows use (see the module docstring).
# --------------------------------------------------------------------------------------
_BLOCK_MARKERS = ("|", "|-", "|+", ">", ">-", ">+")


def _strip_comment(text: str) -> str:
    """Drop a trailing `# ...` comment, respecting quotes. Never used on block scalars."""
    out: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(token: str):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        return [] if not inner else [_scalar(part) for part in inner.split(",")]
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if token in ("", "null", "~"):
        return None
    try:
        return int(token)
    except ValueError:
        return token


def _indent_of(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _next_content(lines: list[str], i: int) -> int:
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i += 1
    return i


def _block_scalar(lines: list[str], i: int, parent_indent: int, marker: str) -> tuple[str, int]:
    body: list[str] = []
    block_indent: int | None = None
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            body.append("")
            i += 1
            continue
        if _indent_of(raw) <= parent_indent:
            break
        if block_indent is None:
            block_indent = _indent_of(raw)
        body.append(raw[block_indent:])
        i += 1
    while body and body[-1] == "":
        body.pop()
    text = " ".join(line.strip() for line in body) if marker[0] == ">" else "\n".join(body)
    if marker.endswith("-"):
        return text, i
    return (text + "\n") if text else text, i


def _parse_map(lines: list[str], i: int, indent: int) -> tuple[dict, int]:
    out: dict = {}
    while True:
        i = _next_content(lines, i)
        if i >= len(lines):
            break
        here = _indent_of(lines[i])
        content = lines[i].lstrip(" ")
        if here < indent or content.startswith("- "):
            break
        if here > indent:
            raise ValueError(f"unexpected indent at line {i + 1}: {lines[i]!r}")
        key, sep, rest = content.partition(":")
        if not sep:
            raise ValueError(f"not a mapping entry at line {i + 1}: {content!r}")
        value = _strip_comment(rest).strip()
        if value in _BLOCK_MARKERS:
            out[key.strip()], i = _block_scalar(lines, i + 1, indent, value)
            continue
        if value:
            out[key.strip()] = _scalar(value)
            i += 1
            continue
        nxt = _next_content(lines, i + 1)
        deeper = nxt < len(lines) and _indent_of(lines[nxt]) > indent
        sibling_seq = (nxt < len(lines) and _indent_of(lines[nxt]) == indent
                       and lines[nxt].lstrip().startswith("- "))
        if deeper or sibling_seq:
            out[key.strip()], i = _parse_node(lines, i + 1, indent if sibling_seq else indent + 1)
        else:
            out[key.strip()] = None
            i += 1
    return out, i


def _parse_seq(lines: list[str], i: int, indent: int) -> tuple[list, int]:
    out: list = []
    while True:
        i = _next_content(lines, i)
        if i >= len(lines):
            break
        content = lines[i].lstrip(" ")
        if _indent_of(lines[i]) != indent or not content.startswith("- "):
            break
        item, item_indent = content[2:], indent + 2
        head = item.partition(":")
        if head[1] and not head[0].strip().startswith(("'", '"')):
            shifted = list(lines)
            shifted[i] = " " * item_indent + item
            value, i = _parse_map(shifted, i, item_indent)
            out.append(value)
        else:
            out.append(_scalar(_strip_comment(item)))
            i += 1
    return out, i


def _parse_node(lines: list[str], i: int, min_indent: int):
    i = _next_content(lines, i)
    if i >= len(lines) or _indent_of(lines[i]) < min_indent:
        return None, i
    indent = _indent_of(lines[i])
    if lines[i].lstrip().startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def lite_load(text: str) -> dict:
    value, _ = _parse_node(text.splitlines(), 0, 0)
    return value or {}


def load(path: pathlib.Path) -> dict:
    return lite_load(path.read_text())


def steps_of(path: pathlib.Path) -> list[dict]:
    jobs = load(path)["jobs"]
    (job,) = jobs.values()
    return job["steps"]


def run_blocks(path: pathlib.Path) -> list[tuple[str, str]]:
    """(step name, run script) for every step that runs a shell."""
    return [(step.get("name", step.get("uses", "?")), step["run"])
            for step in steps_of(path) if "run" in step]


def commands_only(script: str) -> str:
    """The run block with its `#` comment lines removed.

    A comment is allowed — is in fact the point — to name the thing a command must never
    do. Assertions about what a step *does* have to read what the shell executes.
    """
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def has_shell_pipe(script: str) -> bool:
    """A `|` the shell would act on: not inside quotes, not a `||`, not in a comment.

    jq programs are full of pipes (`.[]|select(...)`) and they are single-quoted
    arguments, not pipelines. Treating those as pipelines demanded pipefail from a step
    that has no pipeline at all.
    """
    for line in commands_only(script).splitlines():
        quote: str | None = None
        index = 0
        while index < len(line):
            char = line[index]
            if quote:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "|":
                if line[index + 1:index + 2] == "|":
                    index += 1
                else:
                    return True
            index += 1
    return False


# --------------------------------------------------------------------------------------
# Which flags each workflow hands to which script.
# --------------------------------------------------------------------------------------
_SCRIPT = re.compile(r"^scripts/[\w/]+\.py$")


def script_flags(path: pathlib.Path) -> dict[str, set[str]]:
    """{'scripts/x.py': {'--flag', ...}} for every literal flag passed after the script."""
    found: dict[str, set[str]] = {}
    for _name, script in run_blocks(path):
        for command in re.split(r"\|\||&&|[|;\n]", script.replace("\\\n", " ")):
            tokens = command.split()
            for index, token in enumerate(tokens):
                if _SCRIPT.match(token):
                    flags = {t for t in tokens[index + 1:] if t.startswith("--")}
                    found.setdefault(token, set()).update(flags)
    return found


def script_help(script: str) -> subprocess.CompletedProcess:
    """Ask a script what flags it takes. Only ever called for a script the workflow
    passes at least one flag to — see `_flag_check`.

    A script with no argparse does not answer --help, it *ignores* it and runs. Two belts
    on top of never calling this for a flagless script: KDESK_SEO_SKIP_COMMIT=1, so the
    one script that git-commits on its own cannot, and a 10 s timeout, so a network call
    that does start becomes a loud failure rather than a hung suite.
    """
    return subprocess.run([sys.executable, str(ROOT / script), "--help"],
                          cwd=ROOT, capture_output=True, text=True, timeout=10,
                          env={**os.environ, "KDESK_SEO_SKIP_COMMIT": "1"})


# --------------------------------------------------------------------------------------
# Shape: the files exist, parse, and offer a safe manual dispatch.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_the_workflow_exists_and_offers_manual_dispatch_with_a_dry_run_input(path):
    workflow = load(path)
    dispatch = workflow["on"]["workflow_dispatch"]
    dry_run = dispatch["inputs"]["dry_run"]

    assert dry_run["type"] == "boolean"
    # A real boolean, not the string 'true': every guard below compares `!= true`, and a
    # quoted default is the first half of the string-versus-boolean bug that comparison
    # exists to avoid.
    assert dry_run["default"] is True
    assert dry_run["description"]


def test_the_hugo_deploy_workflow_is_still_there_and_untouched_by_this_work():
    workflow = load(DEPLOY)

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert sorted(workflow["jobs"]) == ["build", "deploy"]
    assert sorted(p.name for p in WF.glob("*.yml")) == [
        "daily-publish.yml", "data-weekly.yml", "deploy.yml"]


def test_weekly_runs_monday_at_0815_pt():
    # 15:15 UTC == 08:15 PDT. 16:15 UTC would be 08:15 PST, so between the November and
    # March changeovers this runs an hour early -- fine for a data pull.
    assert load(WEEKLY)["on"]["schedule"] == [{"cron": "15 15 * * 1"}]


def test_daily_runs_at_0700_pt():
    assert load(DAILY)["on"]["schedule"] == [{"cron": "0 14 * * *"}]


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_both_workflows_serialise_rather_than_cancel(path):
    concurrency = load(path)["concurrency"]

    assert concurrency["group"]
    # A cancelled run can leave a commit, a push or an upload half done. Queue behind the
    # run in flight; never cancel it.
    assert concurrency["cancel-in-progress"] is False


# --------------------------------------------------------------------------------------
# data-weekly.yml
# --------------------------------------------------------------------------------------
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


def test_weekly_restores_the_google_token_at_the_path_the_scripts_read_and_locks_it_down():
    restore = next(run for name, run in run_blocks(WEEKLY) if "google-token.json" in run)

    # pull_seo_snapshot.py and pull_youtube_snapshot.py both open this exact path.
    assert "~/kdesk-analytics/google-token.json" in restore
    assert "~/kdesk-analytics/mailerlite-token.txt" in restore
    assert "umask 077" in restore
    assert "chmod 600" in restore
    # A credential must never be echoed. printf '%s' is the whole write.
    assert "cat ~/kdesk-analytics" not in restore


def test_weekly_binds_the_google_refresh_token_to_only_the_steps_that_need_it():
    """A long-lived OAuth refresh token in job-level env is handed to every step in the
    job, including actions/checkout and setup-uv, which are pinned by moving tag rather
    than by SHA. Two steps need it; two steps get it."""
    job = load(WEEKLY)["jobs"]["pull"]
    assert "GOOGLE_TOKEN_JSON" not in job["env"]

    bound = [s for s in job["steps"] if "GOOGLE_TOKEN_JSON" in (s.get("env") or {})]
    assert [s["name"] for s in bound] == ["Preflight the secrets",
                                          "Restore the credential files the scripts read by path"]


def test_weekly_skips_bing_cleanly_when_its_key_is_not_minted_yet():
    workflow_steps = steps_of(WEEKLY)
    bing = next(s for s in workflow_steps if "pull_bing_snapshot.py" in s.get("run", ""))
    preflight = next(s for s in workflow_steps if s.get("id") == "preflight")

    # Skipped, not failed: Stephen has not created the Bing key yet (ledger 68), and a
    # yellow-or-red step every Monday for a known-absent optional key trains everyone to
    # stop reading the run.
    assert bing["if"] == "steps.preflight.outputs.bing != ''"
    assert "BING_API_KEY" in preflight["run"]
    assert workflow_steps.index(preflight) < workflow_steps.index(bing)


def test_weekly_crm_sync_is_a_dry_run_because_gws_is_not_on_a_runner():
    crm = next(run for _n, run in run_blocks(WEEKLY) if "crm_sync.py" in run)

    assert "--dry-run" in crm
    assert "gws" in WEEKLY.read_text()


def test_weekly_commits_the_snapshot_directory_not_a_file_pathspec():
    commit = next(run for name, run in run_blocks(WEEKLY) if "git commit" in run)

    assert load(WEEKLY)["permissions"]["contents"] == "write"
    # mkdir -p first so the pathspec exists on a from-scratch checkout, then a DIRECTORY
    # pathspec. `git add marketing/seo-tracking/*.jsonl` would be expanded by the shell
    # into an explicit list that names the gitignored mailerlite-sync.jsonl, and `git add`
    # on an explicitly named ignored file fails the step.
    assert "mkdir -p marketing/seo-tracking" in commit
    assert "git add -A marketing/seo-tracking" in commit
    for line in commit.splitlines():
        if line.strip().startswith("git add"):
            assert "*.jsonl" not in line, f"file pathspec: {line.strip()}"


def test_weekly_never_commits_the_gitignored_mailerlite_sync_log():
    """It is untracked on purpose -- it is the free-file sync state and it used to carry
    real addresses (ledger 76). Nothing in this workflow may name it."""
    assert "marketing/seo-tracking/mailerlite-sync.jsonl" in (ROOT / ".gitignore").read_text()
    tracked = subprocess.run(["git", "ls-files", "marketing/seo-tracking/mailerlite-sync.jsonl"],
                             cwd=ROOT, capture_output=True, text=True)
    assert tracked.stdout.strip() == "", "mailerlite-sync.jsonl must stay untracked"
    # Named in a comment is how the next reader learns why the pathspec is a directory;
    # named in a command is the bug.
    for name, script in run_blocks(WEEKLY):
        assert "mailerlite-sync" not in commands_only(script), name


def test_weekly_does_not_let_pull_seo_snapshot_commit_and_push_on_its_own():
    """pull_seo_snapshot.py git-commits by itself unless KDESK_SEO_SKIP_COMMIT=1. One
    commit step at the bottom of the job is the only place this workflow touches git."""
    assert load(WEEKLY)["jobs"]["pull"]["env"]["KDESK_SEO_SKIP_COMMIT"] == "1"


def test_weekly_commits_what_it_already_pulled_even_if_a_later_step_failed():
    commit = next(s for s in steps_of(WEEKLY) if "git commit" in s.get("run", ""))

    # !cancelled(), not always(): a cancelled job should stop, not race to commit into a
    # checkout whose steps were killed part-way. always() would have run it anyway.
    assert "!cancelled()" in commit["if"]
    assert "always()" not in commit["if"]
    assert "inputs.dry_run != true" in commit["if"]


# --------------------------------------------------------------------------------------
# daily-publish.yml
# --------------------------------------------------------------------------------------
def test_daily_downloads_the_weekly_media_release_and_publishes_each_platform():
    text = DAILY.read_text()

    assert "media-daily-" in text
    assert "gh release download" in text
    assert "scripts/publishers/publish.py" in text
    assert "--platform youtube" in text and "--platform tiktok" in text \
        and "--platform instagram" in text


def test_daily_resolves_the_newest_media_daily_release_not_todays_week():
    """The Mac batch renders on Saturday and tags the release with that week. Recomputing
    the tag from today's date matches only on the day the batch ran: `date -u +%G-W%V` on
    a Monday already reads as the *next* week. Resolve from the releases that exist."""
    workflow_steps = steps_of(DAILY)
    for step in workflow_steps:
        assert "%G-W%V" not in step.get("run", ""), \
            f"{step.get('name')}: the tag must come from the releases that exist"

    resolve = next(s for s in workflow_steps if "gh release list" in s.get("run", ""))
    # By --clobber, not by "gh release download": the resolve step's own comment quotes
    # `gh release download null` as the thing the `// empty` guard prevents.
    download = next(s for s in workflow_steps if "--clobber" in s.get("run", ""))

    assert 'startswith("media-daily-")' in resolve["run"]
    assert "// empty" in resolve["run"], "a null tagName would stringify to 'null'"
    assert workflow_steps.index(resolve) < workflow_steps.index(download)


def test_daily_refuses_a_missing_or_stale_media_release():
    resolve = next(s for s in steps_of(DAILY) if "gh release list" in s.get("run", ""))
    run = resolve["run"]

    assert 'gh release view "$TAG" --json createdAt' in run
    # The batch runs Saturday and this runs daily, so the oldest legitimate release is 7
    # days old; 8 leaves a day of slack. Past that, nobody rendered this week and
    # re-publishing last week's assets as new would be silent.
    assert "-gt 8" in run
    assert run.count("exit 2") >= 2, "missing and stale both fail closed"


def test_daily_passes_the_upload_post_key_and_runs_the_digest():
    text = DAILY.read_text()

    assert "secrets.UPLOAD_POST_KEY" in text
    assert "scripts/digest.py" in text
    assert "GITHUB_STEP_SUMMARY" in text


def test_daily_documents_that_the_vault_append_cannot_run_on_actions():
    assert "--vault" in DAILY.read_text()
    assert "vault is local" in DAILY.read_text().lower()


def test_daily_writes_the_digest_into_the_summary_without_the_script_writing_anything():
    digest = next(s for s in steps_of(DAILY)
                  if "digest.py --dry-run" in s.get("run", ""))

    # --dry-run composes and prints and returns before it writes or sends anything; the
    # shell, not the script, is what appends to the summary.
    assert 'tee -a "$GITHUB_STEP_SUMMARY"' in digest["run"]
    assert digest["run"].strip().splitlines()[0].strip() == "set -o pipefail"


def test_daily_never_commits_and_has_no_write_permission():
    """For KDesk the ledger is committed by the Mac. Actions publishes and reports; it
    has nothing to write back, so it does not get the permission to."""
    text = DAILY.read_text()

    assert load(DAILY)["permissions"]["contents"] == "read"
    assert "git commit" not in text
    assert "git push" not in text


def test_daily_uploads_the_publish_log_and_any_queue_cards_as_an_artifact():
    """A queued platform's paste-ready card lands in the ephemeral checkout. Without the
    artifact, a QUEUED line in the log would point at a path nobody can ever read."""
    upload = next(s for s in steps_of(DAILY) if s.get("uses", "").startswith("actions/upload-artifact"))

    assert "publish-stdout.txt" in upload["with"]["path"]
    assert "marketing/publish-queue/" in upload["with"]["path"]
    assert "${{ github.run_id }}" in upload["with"]["name"], "a same-day retry must not collide"
    assert upload["if"].startswith("always()")


def test_daily_uploads_the_ledger_rows_it_wrote_in_the_ephemeral_checkout():
    """This job deliberately never commits (contents: read), so every ledger line a publish
    appends is written into a checkout that is deleted when the job ends. Without the file
    in the artifact, the audit trail for anything Actions published simply does not exist -
    the publish happened, the row proving it was thrown away."""
    upload = next(s for s in steps_of(DAILY)
                  if s.get("uses", "").startswith("actions/upload-artifact"))
    assert "decisions/decisions.jsonl" in upload["with"]["path"]


def test_daily_publish_steps_tee_without_masking_the_exit_code():
    publish = [s for s in steps_of(DAILY) if "publishers/publish.py" in s.get("run", "")]

    assert len(publish) == 3, "one step per platform, so the log says which one queued"
    for step in publish:
        # publish.py exits 1 for a queued platform. tiktok and instagram are not connected
        # yet, so that is every run; a red schedule every morning trains everyone to stop
        # reading it. The stdout artifact and the queue card are the record of truth.
        assert step["continue-on-error"] is True
        lines = [line.strip() for line in step["run"].splitlines() if line.strip()]
        assert lines[0] == "set -o pipefail", f"{step['name']}: pipefail before the pipe"
        assert "| tee -a publish-stdout.txt" in step["run"]


# --------------------------------------------------------------------------------------
# The lessons shared with the sibling ParkSheet repo's workflows.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_every_pipe_is_preceded_by_pipefail(path):
    for name, script in run_blocks(path):
        if not has_shell_pipe(script):
            assert "set -o pipefail" not in script, f"{name}: pipefail with nothing to guard"
            continue
        assert "set -o pipefail" in script, f"{name}: a pipe hides the left side's exit code"
        assert not has_shell_pipe(script.split("set -o pipefail", 1)[0]), \
            f"{name}: pipefail must come before the first pipe"


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_dry_run_guards_compare_a_boolean_never_a_string(path):
    text = path.read_text()

    assert "inputs.dry_run != 'true'" not in text
    assert "inputs.dry_run == 'true'" not in text
    assert re.search(r"inputs\.dry_run (==|!=) true", text), "compare the boolean"


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_inputs_reach_the_shell_through_env_never_inline(path):
    """`${{ inputs.slug }}` pasted into a run body is a shell injection and a quoting bug
    at once. Bind it to an env var and let the shell expand it."""
    for name, script in run_blocks(path):
        assert "${{ inputs." not in script, f"{name}: bind the input with env:"
        assert "${{ secrets." not in script, f"{name}: bind the secret with env:"


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_each_workflow_preflights_its_required_secrets_and_exits_2(path):
    preflight = next(s for s in steps_of(path) if "missing required repository secret" in s.get("run", ""))

    assert "exit 2" in preflight["run"]
    assert "gh secret set" in preflight["run"], "say how to fix it, in the failure itself"
    # First real step, so an absent secret costs one line instead of a stack trace from
    # inside a Google token refresh four steps later.
    assert steps_of(path).index(preflight) <= 3


def test_the_weekly_push_retries_a_racing_push():
    """Both halves of the retry have to sit inside one `if … && …` guard.

    GitHub runs every `run` body as `bash -e`. An unguarded `git pull --rebase` that loses
    the race therefore kills the step on attempt 1 and the loop never reaches attempt 2 —
    a retry loop that cannot retry. Putting pull and push inside the `if` condition
    suppresses -e for both.
    """
    commit = next(run for _n, run in run_blocks(WEEKLY) if "git push" in run)

    assert "for attempt in 1 2 3" in commit
    assert 'if git pull --rebase --autostash origin "$GITHUB_REF_NAME" \\' in commit
    assert '&& git push origin "HEAD:$GITHUB_REF_NAME"; then' in commit
    # A rebase that stopped on a conflict leaves the tree mid-rebase; the next attempt's
    # pull would refuse to start until it is cleared.
    assert "git rebase --abort" in commit
    assert "exit 1" in commit, "give up loudly after three attempts"

    for line in commit.splitlines():
        stripped = line.strip()
        if stripped.startswith(("git pull", "git push")):
            raise AssertionError(f"unguarded under bash -e: {stripped}")


def test_weekly_checks_out_the_full_history_the_seo_pull_annotates_from():
    """pull_seo_snapshot.py's git_changes_since() runs `git log --since=<last pull>`. The
    default shallow checkout has one commit, so every row's annotation would be empty."""
    checkout = next(s for s in steps_of(WEEKLY) if s.get("uses", "").startswith("actions/checkout"))

    assert checkout["with"]["fetch-depth"] == 0


def test_weekly_restore_reuses_the_preflight_answer_about_bing():
    """One place decides whether a Bing key exists. The restore step asks the preflight
    rather than re-testing the secret, so the two can never disagree."""
    restore = next(s for s in steps_of(WEEKLY) if "google-token.json" in s.get("run", ""))

    assert restore["env"]["HAVE_BING"] == "${{ steps.preflight.outputs.bing }}"
    assert '[ -n "$HAVE_BING" ]' in restore["run"]
    # It still writes the key's value — it just does not re-decide whether there is one.
    assert '[ -n "$BING_API_KEY" ]' not in restore["run"]


def test_daily_fails_the_run_when_nothing_published_and_nothing_queued():
    """Every publish step is continue-on-error, so without this a morning on which all
    three platforms hard-failed is green with an empty summary. A queued platform is a
    legitimate outcome — it leaves a paste-ready card. Zero of both is a silent drop."""
    guard = next(s for s in steps_of(DAILY) if "nothing was queued" in s.get("run", ""))
    workflow_steps = steps_of(DAILY)

    assert "inputs.dry_run != true" in guard["if"]
    assert "publish-stdout.txt" in guard["run"]
    assert "marketing/publish-queue/" in guard["run"]
    assert "exit 1" in guard["run"]
    # After all three publish steps, so it sees every outcome.
    last_publish = max(i for i, s in enumerate(workflow_steps)
                       if "publishers/publish.py" in s.get("run", ""))
    assert workflow_steps.index(guard) > last_publish


def test_daily_release_lookup_scans_enough_releases_and_names_an_unusable_timestamp():
    resolve = next(s for s in steps_of(DAILY) if "gh release list" in s.get("run", ""))
    run = resolve["run"]

    # 20 is one week of daily tags away from missing a media-daily-* behind a run of
    # unrelated releases.
    assert "--limit 50" in run
    # An empty or unparseable createdAt would otherwise become a bash arithmetic syntax
    # error — a failure whose message says nothing about releases.
    assert 'has no createdAt' in run
    assert "cannot parse createdAt" in run
    assert run.count("exit 2") >= 4


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_neither_workflow_hardcodes_a_secret(path):
    text = path.read_text()

    assert "Apikey " not in text
    assert "ya29." not in text and "AIza" not in text
    assert not re.search(r"(?i)token\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", text), path.name


# --------------------------------------------------------------------------------------
# Every flag a workflow passes must be a flag the script actually accepts.
# --------------------------------------------------------------------------------------
def _flag_check(path: pathlib.Path, probe) -> None:
    calls = script_flags(path)
    assert calls, f"{path.name} runs no repo script?"
    for script, flags in sorted(calls.items()):
        assert (ROOT / script).exists(), f"{path.name} calls a script that is not here: {script}"
        if not flags:
            # Nothing to verify — and verifying it would be actively harmful. Three of
            # these scripts (pull_seo_snapshot.py, pull_gumroad_snapshot.py,
            # pull_youtube_snapshot.py) have no argparse, so `--help` is not a question to
            # them, it is an ignored argument: they would pull live data for real, and
            # pull_seo_snapshot.py would git-commit and push. Never execute them.
            continue
        helped = probe(script)
        if helped.returncode != 0:
            # A script with no argparse cannot accept a flag, so passing it one is a bug
            # in the workflow, not in this test.
            assert not flags, f"{script} has no argparse; it cannot accept {sorted(flags)}"
            continue
        for flag in sorted(flags):
            assert flag in helped.stdout, f"{script} --help does not list {flag}"


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_every_flag_the_workflow_passes_is_a_flag_the_script_accepts(path):
    _flag_check(path, script_help)


@pytest.mark.parametrize("path", [WEEKLY, DAILY], ids=["weekly", "daily"])
def test_a_script_the_workflow_passes_no_flags_to_is_never_executed(path):
    """The check above must not become a way to run production scripts for real."""
    probed: list[str] = []

    def recording_probe(script: str) -> subprocess.CompletedProcess:
        probed.append(script)
        return script_help(script)

    _flag_check(path, recording_probe)

    for script, flags in script_flags(path).items():
        assert (script in probed) is bool(flags), script
    for flagless in ("scripts/pull_seo_snapshot.py", "scripts/pull_gumroad_snapshot.py",
                     "scripts/pull_youtube_snapshot.py"):
        assert flagless not in probed


def test_publish_py_accepts_the_dry_run_flag_the_daily_job_injects_through_a_variable():
    """The daily job's --dry-run arrives via the job-level DRY env var, so the flag scan
    above cannot see it as a literal argument. Check it directly."""
    assert "'--dry-run'" in DAILY.read_text()
    assert "--dry-run" in script_help("scripts/publishers/publish.py").stdout


# --------------------------------------------------------------------------------------
# The runbook is the operator-facing half of this task.
# --------------------------------------------------------------------------------------
def test_the_runbook_documents_the_secrets_the_schedules_and_the_launchd_handover():
    runbook = (ROOT / "marketing" / "runbooks" / "automation-2026-09.md").read_text()

    for secret in ("GUMROAD_ACCESS_TOKEN", "MAILERLITE_TOKEN", "GOOGLE_TOKEN_JSON",
                   "BING_API_KEY", "UPLOAD_POST_KEY"):
        assert f"gh secret set {secret}" in runbook, secret
    assert "data-weekly.yml" in runbook and "daily-publish.yml" in runbook
    assert "15 15 * * 1" in runbook and "0 14 * * *" in runbook
    # The double-append hazard: launchd and Actions both appending to the same JSONL.
    assert "kdesk-daily.sh" in runbook
    assert "media-daily-" in runbook
    # The two limits that are recorded rather than papered over.
    assert "gws" in runbook and "vault" in runbook


def test_the_runbook_names_the_ledger_owner_for_the_daily_publish():
    runbook = (ROOT / "marketing" / "runbooks" / "automation-2026-09.md").read_text()

    assert "the Mac commits the ledger" in runbook


# --------------------------------------------------------------------------------------
# The lite reader, pinned to PyYAML wherever PyYAML exists.
# --------------------------------------------------------------------------------------
def test_the_lite_reader_agrees_with_pyyaml():
    yaml = pytest.importorskip("yaml", reason="the mandated test env is pytest + stdlib only")

    for path in sorted(WF.glob("*.yml")):
        real = yaml.safe_load(path.read_text())
        if True in real:  # PyYAML reads the `on:` key as the boolean True
            real["on"] = real.pop(True)
        assert lite_load(path.read_text()) == real, path.name


# --------------------------------------------------------------------------------------
# Chrome is never on the recurring path (spec Chrome rule 1), and for TikTok there is a
# second reason: driving a logged-in web session is a ToS grey area that stays
# semi-supervised on the Mac. Both facts live in prose today, which is exactly the kind of
# rule that erodes the first time a scheduled job "just needs" one more step. A workflow
# file is where that erosion would land, so this is the assertion that catches it.
# --------------------------------------------------------------------------------------

CHROME_ONLY_SCRIPTS = ("scripts/publishers/tiktok_web.py", "scripts/publishers/schedule_week.py",
                       "scripts/browser/session.py", "scripts/browser/ensure_chrome.py")


@pytest.mark.parametrize("workflow", sorted(WF.glob("*.yml")), ids=lambda p: p.name)
def test_no_workflow_drives_chrome_or_schedules_tiktok(workflow):
    text = workflow.read_text()
    for script in CHROME_ONLY_SCRIPTS:
        assert script not in text, (
            f"{workflow.name} references {script}. Chrome drivers run beside Stephen on the "
            f"Mac, never in Actions — the runner has no logged-in profile, and for TikTok "
            f"automating a logged-in session is a ToS grey area kept semi-supervised.")
    # The basename alone would catch an invocation through a variable or a different path.
    for name in ("tiktok_web.py", "schedule_week.py", "ensure_chrome.py"):
        assert name not in text, f"{workflow.name} names {name}"


def test_the_guard_covers_every_workflow_that_exists():
    """A new workflow file must be swept too, not just the two named schedules."""
    assert set(WF.glob("*.yml")) >= {WEEKLY, DAILY, DEPLOY}
