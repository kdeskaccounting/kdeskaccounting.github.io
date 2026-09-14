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


def dry_run_lines(port: int = 9222, *, probe_fn=None, launch_fn=None,
                  profile: pathlib.Path = PROFILE_DIR) -> list[str]:
    """What --dry-run prints: the probe result and the argv it would launch.

    Probing is a read; launching is the write, and --dry-run never does it. `launch_fn` is
    accepted only so a test can prove it is never called.
    """
    probe_fn = probe_fn or probe
    info = probe_fn(port)
    if info:
        return [f"(dry-run) debug Chrome already answering on :{port} — "
                f"{info.get('Browser', '?')} (profile {profile})",
                "(dry-run) would launch nothing"]
    return [f"(dry-run) nothing answering on :{port}",
            f"(dry-run) would launch: {' '.join(chrome_argv(profile, port))}",
            f"(dry-run) would create the profile dir if missing: {profile}"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensure the debug Chrome is running.")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--dry-run", action="store_true",
                    help="report the probe and the argv it would launch; launch nothing")
    a = ap.parse_args()
    if a.dry_run:
        for line in dry_run_lines(a.port):
            print(line)
        return 0
    info = ensure(a.port)
    print(f"debug Chrome up on :{a.port} — {info.get('Browser', '?')} (profile {PROFILE_DIR})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
