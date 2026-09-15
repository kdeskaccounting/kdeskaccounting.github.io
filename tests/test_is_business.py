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
