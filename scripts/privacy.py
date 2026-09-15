#!/usr/bin/env python3
"""Pseudonymise an email address before it touches a tracked file.

This repo is public (github.com/kdeskaccounting/kdeskaccounting.github.io). Scripts still
need to remember "have I already handled this person?" across runs, and that state lives in
git so both machines see it. Storing the address itself publishes a customer list, so state
files store a salted SHA-256 instead: enough to recognise someone we have seen before,
useless to anyone who does not hold the salt.

The salt lives outside the repo at ~/kdesk-analytics/email-hash-salt.txt, mode 0600, and is
created on first use. It is NOT a secret to be rotated casually - rotating it makes every
stored digest unrecognisable, so every past person looks new.

Plain SHA-256 of an email would be trivially reversible: the address space of "people who
bought an accounting template" is small enough to enumerate. The salt is what makes the
digest a pseudonym rather than an encoding.

Stdlib only, so it imports cleanly inside `uv run --with pytest pytest tests/`.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import secrets
from typing import Iterable

SALT_FILE = pathlib.Path.home() / "kdesk-analytics" / "email-hash-salt.txt"
SALT_BYTES = 32

# path -> salt. A sync hashes hundreds of addresses; without this each one re-read the file.
_SALT_CACHE: dict[pathlib.Path, str] = {}


def _read_salt(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def salt() -> str:
    """Read the salt, creating it 0600 on first use.

    Creation is O_EXCL, so two processes starting together cannot each write a salt - the
    loser re-reads the winner's rather than hashing every address under a salt nobody else
    holds, which would silently orphan every digest it wrote.
    """
    path = SALT_FILE
    cached = _SALT_CACHE.get(path)
    if cached:
        return cached
    existing = _read_salt(path)
    if existing:
        _SALT_CACHE[path] = existing
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(SALT_BYTES)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Either a racing process just created it, or a crashed run left it empty.
        existing = _read_salt(path)
        if existing:
            _SALT_CACHE[path] = existing
            return existing
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")
    os.chmod(path, 0o600)
    _SALT_CACHE[path] = value
    return value


def email_hash(email: str | None) -> str:
    """Salted SHA-256 of a normalised address. Empty in, empty out."""
    normalised = (email or "").strip().lower()
    if not normalised:
        return ""
    return hashlib.sha256(f"{salt()}:{normalised}".encode("utf-8")).hexdigest()


def hash_index(emails: Iterable[str | None]) -> dict[str, str]:
    """digest -> address, for joining a pseudonymised state file back to addresses we hold.

    The tracked file never carries an address, but a live API pull does. Hashing what we
    already know is how a hash-only row still enriches the person it belongs to.
    """
    index: dict[str, str] = {}
    for email in emails:
        normalised = (email or "").strip().lower()
        if normalised:
            index[email_hash(normalised)] = normalised
    return index
