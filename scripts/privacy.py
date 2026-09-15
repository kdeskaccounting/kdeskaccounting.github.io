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


def salt() -> str:
    """Read the salt, creating it 0600 on first use."""
    if SALT_FILE.exists():
        existing = SALT_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(SALT_BYTES)
    fd = os.open(SALT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")
    os.chmod(SALT_FILE, 0o600)
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
