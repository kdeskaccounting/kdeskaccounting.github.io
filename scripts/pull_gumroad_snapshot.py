#!/usr/bin/env python3
"""
Weekly Gumroad snapshot: pulls products + all sales via the Gumroad API and
appends one JSON row to marketing/seo-tracking/gumroad-snapshots.jsonl.

This is THE money metric for the funnel (paid sales, free downloads, unique
people, business-domain leads). Runs from the Mac; the token lives in
~/kdeskaccountingtemplates/.env as GUMROAD_ACCESS_TOKEN (never in this repo).

Usage:
  python3 scripts/pull_gumroad_snapshot.py            # append row + print summary
  python3 scripts/pull_gumroad_snapshot.py --dry-run  # print only, no append
"""
from __future__ import annotations
import datetime as dt, json, os, pathlib, sys, warnings
warnings.filterwarnings("ignore")
import requests

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "marketing" / "seo-tracking" / "gumroad-snapshots.jsonl"
ENV = pathlib.Path(os.environ.get("KDESK_GUMROAD_ENV", "~/kdeskaccountingtemplates/.env")).expanduser()
B = "https://api.gumroad.com/v2"
FREEMAIL = {"gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","naver.com","proton.me","protonmail.com","aol.com","live.com","me.com"}

def token() -> str:
    t = os.environ.get("GUMROAD_ACCESS_TOKEN")
    if not t and ENV.exists():
        for l in ENV.read_text().splitlines():
            if l.startswith("GUMROAD_ACCESS_TOKEN"):
                t = l.split("=", 1)[1].strip().strip('"\'')
    if not t:
        sys.exit(f"No GUMROAD_ACCESS_TOKEN (env or {ENV})")
    return t

def pull(tok: str):
    prods = requests.get(f"{B}/products", params={"access_token": tok}, timeout=30).json().get("products", [])
    sales, key = [], None
    while True:
        p = {"access_token": tok}
        if key: p["page_key"] = key
        r = requests.get(f"{B}/sales", params=p, timeout=30).json()
        sales += r.get("sales", [])
        key = r.get("next_page_key")
        if not key: break
    return prods, sales

def window(sales, days):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    return [s for s in sales if dt.datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) >= cutoff]

def summarize(sales):
    emails = {s.get("email", "").lower() for s in sales if s.get("email")}
    paid = [s for s in sales if s.get("price", 0) > 0]
    biz = sorted({e.split("@")[1] for e in emails if "@" in e and e.split("@")[1] not in FREEMAIL})
    by_product = {}
    for s in sales:
        by_product[s.get("product_name", "?")[:60]] = by_product.get(s.get("product_name", "?")[:60], 0) + 1
    refs = {}
    for s in sales:
        r = (s.get("referrer") or "direct").split("?")[0]
        refs[r] = refs.get(r, 0) + 1
    return {
        "download_events": len(sales),
        "unique_people": len(emails),
        "paid_transactions": len(paid),
        "paid_full_price": len([s for s in paid if s.get("price", 0) >= 4900]),
        "revenue_usd": round(sum(s.get("price", 0) for s in sales) / 100, 2),
        "business_domains": biz,
        "by_product": by_product,
        "referrers": refs,
    }

def main():
    dry = "--dry-run" in sys.argv
    prods, sales = pull(token())
    row = {
        "pulled_at": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
        "source": "Gumroad API v2 (products + sales), scripts/pull_gumroad_snapshot.py",
        "products_listed": len(prods),
        "products_paid": len([p for p in prods if p.get("price", 0) > 0]),
        "all_time": summarize(sales),
        "last_28d": summarize(window(sales, 28)),
        "last_7d": summarize(window(sales, 7)),
    }
    print(json.dumps(row, indent=1))
    if not dry:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"\nappended -> {OUT.relative_to(REPO)}")

if __name__ == "__main__":
    main()
