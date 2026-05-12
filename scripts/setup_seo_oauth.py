#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-auth>=2.30",
#   "google-auth-oauthlib>=1.2",
# ]
# ///
"""
One-time OAuth setup for the SEO snapshot script.

Run this once with the credentials.json downloaded from Google Cloud Console
(OAuth 2.0 client ID, type "Desktop"). It mints a refresh token that
scripts/pull_seo_snapshot.py uses for unattended runs forever after.

Usage:
  python scripts/setup_seo_oauth.py path/to/credentials.json

Output:
  ~/kdesk-analytics/google-token.json   (refresh token, gitignored)
"""
from __future__ import annotations

import pathlib
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]

TOKEN_DIR = pathlib.Path.home() / "kdesk-analytics"
TOKEN_FILE = TOKEN_DIR / "google-token.json"


def main(creds_path: str) -> int:
    creds_file = pathlib.Path(creds_path).expanduser()
    if not creds_file.exists():
        print(f"credentials.json not found at {creds_file}", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    # Use console-mode so this works over SSH/WSL without opening a browser tab
    creds = flow.run_local_server(port=0, open_browser=True)

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Token saved to {TOKEN_FILE}")
    print(
        "You can now run scripts/pull_seo_snapshot.py without further "
        "interaction. Refresh happens automatically."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: setup_seo_oauth.py path/to/credentials.json", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
