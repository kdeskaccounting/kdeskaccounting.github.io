import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (ROOT / "scripts", ROOT / "scripts" / "video"):
    sys.path.insert(0, str(p))

from browser import session  # noqa: E402  (needs scripts/ on sys.path first)


@pytest.fixture(autouse=True)
def hide_ambient_credentials(monkeypatch):
    """Remove every credential-named variable from os.environ for the duration of a test.

    session._env_secrets() reads the live environment, so a real GITHUB_PERSONAL_ACCESS_TOKEN
    or UPLOAD_POST_KEY on a developer's machine (or in CI) would change what a test masks -
    a test could pass here and fail there, or worse, pass for the wrong reason. Tests that
    need a key set one explicitly; monkeypatch restores everything afterwards.

    The rule comes from session.is_credential_name so it cannot drift from the sweep it
    is isolating.
    """
    for name in list(os.environ):
        if session.is_credential_name(name):
            monkeypatch.delenv(name, raising=False)
