"""scripts/privacy.py — the one place an email becomes a pseudonym for a tracked file.

Tracked files in this repo are public. Anything that needs to remember "have I already
handled this person?" stores a salted SHA-256 instead of the address.
"""
import re
import stat

import privacy


def test_the_salt_is_created_once_and_kept_private(tmp_path, monkeypatch):
    saltfile = tmp_path / "email-hash-salt.txt"
    monkeypatch.setattr(privacy, "SALT_FILE", saltfile)
    first = privacy.salt()
    assert saltfile.exists()
    assert stat.S_IMODE(saltfile.stat().st_mode) == 0o600
    assert len(first) >= 32
    assert privacy.salt() == first, "a second call must reuse the salt, not roll it"


def test_the_hash_is_hex_carries_no_address_and_is_stable(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "email-hash-salt.txt")
    digest = privacy.email_hash("Person@Example.COM")
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert "@" not in digest
    assert "person" not in digest and "example" not in digest
    assert digest == privacy.email_hash("  person@example.com  "), "normalise case and space"
    assert digest != privacy.email_hash("other@example.com")


def test_an_empty_address_hashes_to_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "email-hash-salt.txt")
    assert privacy.email_hash("") == ""
    assert privacy.email_hash(None) == ""


def test_a_different_salt_gives_a_different_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "a.txt")
    one = privacy.email_hash("person@example.com")
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "b.txt")
    two = privacy.email_hash("person@example.com")
    assert one != two, "the salt must actually salt - otherwise the digest is a rainbow lookup"


def test_index_maps_known_addresses_back_to_their_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "email-hash-salt.txt")
    index = privacy.hash_index(["A@example.com", "b@example.com", "", None])
    assert index[privacy.email_hash("a@example.com")] == "a@example.com"
    assert len(index) == 2, "blank addresses contribute nothing"


def test_the_salt_is_cached_in_process(tmp_path, monkeypatch):
    """Every hashed address would otherwise re-read the file; a sync hashes hundreds."""
    saltfile = tmp_path / "email-hash-salt.txt"
    monkeypatch.setattr(privacy, "SALT_FILE", saltfile)
    first = privacy.salt()
    saltfile.unlink()
    assert privacy.salt() == first, "served from the in-process cache"
    assert not saltfile.exists(), "a cache hit must not touch the disk at all"


def test_a_concurrent_creator_wins_and_its_salt_is_reused(tmp_path, monkeypatch):
    """Two processes starting at once must not each write a salt - the loser would hash
    every address under a salt nobody else uses."""
    import os
    saltfile = tmp_path / "email-hash-salt.txt"
    monkeypatch.setattr(privacy, "SALT_FILE", saltfile)
    privacy._SALT_CACHE.clear()
    real_open = os.open

    def racing_open(path, flags, mode=0o777):
        if flags & os.O_EXCL:                       # someone beat us to the create
            fd = real_open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.write(fd, b"the-winners-salt\n")
            os.close(fd)
            raise FileExistsError(path)
        return real_open(path, flags, mode)

    monkeypatch.setattr(privacy.os, "open", racing_open)
    assert privacy.salt() == "the-winners-salt"


def test_an_empty_salt_file_is_replaced(tmp_path, monkeypatch):
    saltfile = tmp_path / "email-hash-salt.txt"
    saltfile.write_text("\n")
    monkeypatch.setattr(privacy, "SALT_FILE", saltfile)
    privacy._SALT_CACHE.clear()
    assert len(privacy.salt()) >= 32
