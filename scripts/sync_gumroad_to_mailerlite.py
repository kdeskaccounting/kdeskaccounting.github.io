#!/usr/bin/env python3
"""
Sync Gumroad free downloaders into MailerLite so the free->paid automation can run there
(Gumroad Workflows are gated until $100 earned + a payout).

For every Gumroad sale of a FREE product (price 0 or PWYW), upsert the buyer into MailerLite with
custom fields describing the product they took, and add them to the "Gumroad free downloaders" group.
A single MailerLite automation (trigger: joins that group) then sends the 3-email sequence with
merge fields ({$product_name}, {$free_cap}, {$paid_url}, {$page_url}, {$price}, {$full_desc}).

  python3 scripts/sync_gumroad_to_mailerlite.py [--dry-run] [--since-days 3650]
Tokens: ~/kdeskaccountingtemplates/.env (GUMROAD_ACCESS_TOKEN), ~/kdesk-analytics/mailerlite-token.txt
State: marketing/seo-tracking/mailerlite-sync.jsonl (append-only: who was synced when)
"""
import os, sys, json, pathlib, datetime as dt, warnings; warnings.filterwarnings("ignore")
import requests
REPO = pathlib.Path(__file__).resolve().parents[1]; STATE = REPO / "marketing/seo-tracking/mailerlite-sync.jsonl"
ML = "https://connect.mailerlite.com/api"; GR = "https://api.gumroad.com/v2"
GROUP_NAME = "Gumroad free downloaders"
PRODUCTS = {  # gumroad product name prefix -> merge fields
    "ASC 842 Lease Accounting Workbook — Free": dict(product_name="ASC 842 lease workbook", free_cap="3 leases and 36 months", paid_url="https://kdeskaccounting.gumroad.com/l/phxigq", page_url="https://kdeskaccounting.com/templates/asc842/", price="$97", full_desc="20 leases, 120-month schedules, JE Generator with your GL codes, rollforward, maturity analysis and a reconciliation that ties to $0"),
    "ASC 606 Commission Accrual Workbook — Free": dict(product_name="ASC 606 commission workbook", free_cap="5 deals and 24 months", paid_url="https://kdeskaccounting.gumroad.com/l/mwmwpe", page_url="https://kdeskaccounting.com/templates/asc606/", price="$79", full_desc="50 deals, a 60-month waterfall, JE Generator, deferred asset rollforward and a reconciliation that ties to $0"),
    "Free 5-Asset Fixed Asset": dict(product_name="fixed asset workbook", free_cap="5 assets and 36 months", paid_url="https://kdeskaccounting.gumroad.com/l/fixed-asset-rollforward", page_url="https://kdeskaccounting.com/templates/fixed-assets/", price="$79", full_desc="50 assets, four methods, JE Generator with QuickBooks / NetSuite / Sage / Xero presets, disposal log and the five-way reconciliation"),
    "SaaS Metrics & ARR Dashboard — FREE": dict(product_name="SaaS metrics workbook", free_cap="6 months of data", paid_url="https://kdeskaccounting.gumroad.com/l/saas-metrics-dashboard", page_url="https://kdeskaccounting.com/templates/saas-metrics/", price="$67", full_desc="24 months auto-chained, the six-card dashboard, the trend table and the Magic Number"),
    "Startup Runway Calculator — Free": dict(product_name="runway calculator", free_cap="12 months and 5 rows per tab", paid_url="https://kdeskaccounting.gumroad.com/l/runway-calculator", page_url="https://kdeskaccounting.com/templates/runway/", price="$49", full_desc="a 48-month window, 20 rows per tab and Base / Optimistic / Pessimistic scenarios"),
    "Month-End Close Checklist": dict(product_name="month-end close checklist", free_cap="the close scaffolding", paid_url="https://kdeskaccounting.gumroad.com/l/saas-controller-bundle", page_url="https://kdeskaccounting.com/templates/month-end-close/", price="$249 (all five workbooks)", full_desc="the technical workbooks the reconciliation rows tie to: ASC 842, ASC 606, fixed assets, SaaS metrics, runway"),
}
FIELDS = ["product_name", "free_cap", "paid_url", "page_url", "price", "full_desc"]
def gtoken():
    for l in open(os.path.expanduser("~/kdeskaccountingtemplates/.env")):
        if l.startswith("GUMROAD_ACCESS_TOKEN"): return l.split("=", 1)[1].strip().strip('"\'')
def mltoken(): return open(os.path.expanduser("~/kdesk-analytics/mailerlite-token.txt")).read().strip()
def ml(method, path, **kw):
    r = requests.request(method, ML + path, headers={"Authorization": f"Bearer {mltoken()}", "Accept": "application/json", "Content-Type": "application/json"}, timeout=30, **kw)
    if r.status_code >= 300: raise SystemExit(f"MailerLite {method} {path} -> {r.status_code} {r.text[:300]}")
    return r.json() if r.text else {}
def ensure_fields():
    have = {f["key"]: f for f in ml("GET", "/fields?limit=100").get("data", [])}
    for k in FIELDS:
        if k not in have: ml("POST", "/fields", json={"name": k, "type": "text"}); print("created field", k)
def ensure_group():
    for g in ml("GET", "/groups?limit=100").get("data", []):
        if g["name"] == GROUP_NAME: return g["id"]
    return ml("POST", "/groups", json={"name": GROUP_NAME})["data"]["id"]
def gumroad_sales(since_days):
    sales, key = [], None
    while True:
        p = {"access_token": gtoken()}
        if key: p["page_key"] = key
        r = requests.get(f"{GR}/sales", params=p, timeout=30).json(); sales += r.get("sales", []); key = r.get("next_page_key")
        if not key: break
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=since_days)
    return [s for s in sales if dt.datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) >= cutoff]
def main():
    dry = "--dry-run" in sys.argv; since = int(sys.argv[sys.argv.index("--since-days") + 1]) if "--since-days" in sys.argv else 3650
    done = set()
    if STATE.exists():
        for l in STATE.read_text().splitlines():
            if l.strip(): done.add(json.loads(l)["email"].lower())
    if not dry: ensure_fields(); gid = ensure_group()
    synced = 0
    for s in sorted(gumroad_sales(since), key=lambda s: s["created_at"]):
        email = (s.get("email") or "").lower(); name = s.get("product_name", "")
        if not email or email in done or "santiagokdesk" in email or "kdeskaccounting" in email: continue
        if s.get("price", 0) >= 4900: continue  # paid customers get a different treatment
        prod = next((v for k, v in PRODUCTS.items() if name.startswith(k)), None)
        if not prod: continue
        payload = {"email": email, "fields": {**prod, "name": (s.get("full_name") or "").split(" ")[0] if s.get("full_name") else None}, "groups": [gid] if not dry else []}
        payload["fields"] = {k: v for k, v in payload["fields"].items() if v}
        if dry: print("would sync", email, "->", prod["product_name"]); continue
        ml("POST", "/subscribers", json=payload)
        with STATE.open("a") as f: f.write(json.dumps({"email": email, "product": prod["product_name"], "gumroad_sale": s["created_at"], "synced_at": dt.datetime.now().astimezone().isoformat(timespec="minutes")}) + "\n")
        done.add(email); synced += 1; print("synced", email, "->", prod["product_name"])
    print("done:", synced, "new subscriber(s)")
if __name__ == "__main__": main()
