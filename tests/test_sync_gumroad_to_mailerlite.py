"""scripts/sync_gumroad_to_mailerlite.py — the sync-state writer must never publish a person.

Its state file is the append-only record of who has already been pushed to MailerLite. That
file used to carry plaintext addresses in a PUBLIC repo; it now carries salted digests only.
"""
import json

import privacy
import sync_gumroad_to_mailerlite as sync

SALE = {"email": "Buyer@NorthStar.EXAMPLE", "created_at": "2026-09-11T04:25:17Z"}


def test_a_state_row_carries_a_digest_and_no_address(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    row = sync.state_row(SALE["email"], "ASC 842 lease workbook", SALE["created_at"],
                         now="2026-09-11T08:15-07:00")
    assert row["email_sha256"] == privacy.email_hash("buyer@northstar.example")
    assert "email" not in row, "the address itself must not survive into the row"
    assert row["product"] == "ASC 842 lease workbook"
    assert row["gumroad_sale"] == "2026-09-11T04:25:17Z"


def test_the_serialised_line_contains_no_at_sign(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    line = json.dumps(sync.state_row(SALE["email"], "runway calculator", SALE["created_at"],
                                     now="2026-09-11T08:15-07:00"))
    assert "@" not in line
    assert "northstar" not in line.lower()


def test_synced_hashes_reads_the_sanitised_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    digest = privacy.email_hash("buyer@northstar.example")
    state = tmp_path / "mailerlite-sync.jsonl"
    state.write_text(json.dumps({"email_sha256": digest, "product": "x",
                                 "gumroad_sale": "2026-09-11T04:25:17Z"}) + "\n")
    assert sync.synced_hashes(state) == {digest}


def test_synced_hashes_still_recognises_a_legacy_plaintext_row(tmp_path, monkeypatch):
    """A local file written before containment must not re-sync everyone it already knows."""
    monkeypatch.setattr(privacy, "SALT_FILE", tmp_path / "salt.txt")
    state = tmp_path / "mailerlite-sync.jsonl"
    state.write_text(json.dumps({"email": "Buyer@NorthStar.EXAMPLE", "product": "x"}) + "\n")
    assert sync.synced_hashes(state) == {privacy.email_hash("buyer@northstar.example")}


def test_synced_hashes_tolerates_a_missing_file(tmp_path):
    assert sync.synced_hashes(tmp_path / "nope.jsonl") == set()
