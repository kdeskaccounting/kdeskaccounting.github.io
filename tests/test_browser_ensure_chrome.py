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


# --- Global constraint: every script has a --dry-run that performs zero writes. For
# ensure_chrome that means reporting the probe and the argv it WOULD launch, launching
# nothing - so Stephen can see what it would do without a second Chrome appearing.

def test_dry_run_lines_report_a_running_chrome_and_launch_nothing():
    launched = []
    lines = ec.dry_run_lines(9222, probe_fn=lambda port, timeout=2.0: {"Browser": "Chrome/141"},
                             launch_fn=lambda: launched.append(1))
    text = "\n".join(lines)
    assert launched == []
    assert "(dry-run)" in text
    assert "Chrome/141" in text
    assert "9222" in text


def test_dry_run_lines_show_the_argv_it_would_launch_when_nothing_answers():
    launched = []
    lines = ec.dry_run_lines(9222, probe_fn=lambda port, timeout=2.0: None,
                             launch_fn=lambda: launched.append(1))
    text = "\n".join(lines)
    assert launched == []
    assert "--remote-debugging-port=9222" in text
    assert "/Applications/Google Chrome.app" in text
    assert "would launch" in text.lower()


# --- 4. dry_run_lines() never touched launch_fn, so asserting `launched == []` proved
# nothing. Drive the real --dry-run branch of main() and assert it launches nothing.

def test_main_dry_run_never_launches_and_prints_the_argv(capsys):
    launched = []
    rc = ec.main(["--dry-run"],
                 probe_fn=lambda port, timeout=2.0: None,
                 launch_fn=lambda: launched.append("LAUNCHED"))
    out = capsys.readouterr().out
    assert rc == 0
    assert launched == [], "--dry-run must not start Chrome"
    assert "--remote-debugging-port=9222" in out
    assert "would launch" in out.lower()


def test_main_dry_run_reports_an_already_running_chrome_without_launching(capsys):
    launched = []
    rc = ec.main(["--dry-run", "--port", "9333"],
                 probe_fn=lambda port, timeout=2.0: {"Browser": "Chrome/141"},
                 launch_fn=lambda: launched.append("LAUNCHED"))
    out = capsys.readouterr().out
    assert rc == 0 and launched == []
    assert "9333" in out and "Chrome/141" in out


def test_main_without_dry_run_does_launch_when_nothing_answers():
    """The mirror image: proves the dry-run assertion above is not vacuous."""
    launched = []
    seq = iter([None, {"Browser": "Chrome/141"}])

    rc = ec.main([], probe_fn=lambda port, timeout=2.0: next(seq),
                 launch_fn=lambda: launched.append("LAUNCHED"),
                 sleep_fn=lambda s: None)
    assert rc == 0
    assert launched == ["LAUNCHED"]
