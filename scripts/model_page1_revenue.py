# /// script
# requires-python = ">=3.11"
# dependencies = ["google-auth>=2.30", "google-api-python-client>=2.0"]
# ///
import re, pathlib, datetime as dt, collections
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
creds = Credentials.from_authorized_user_file(str(pathlib.Path.home()/"kdesk-analytics/google-token.json"))
svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
end = dt.date.today() - dt.timedelta(days=2); start = end - dt.timedelta(days=89)
rows = svc.searchanalytics().query(siteUrl="sc-domain:kdeskaccounting.com", body={"startDate": str(start), "endDate": str(end), "dimensions": ["query"], "rowLimit": 5000}).execute().get("rows", [])
COM = re.compile(r"template|excel|spreadsheet|calculator|workbook|xlsx|checklist|schedule format", re.I)
BRAND = re.compile(r"kdesk", re.I)
def vis(p):  # multiplier from today's impressions to page-1 impressions (page-1 users vs. users who paged that deep)
    return 1.0 if p <= 10 else 3.0 if p <= 20 else 6.0 if p <= 30 else 10.0
# our observed CTR on queries where we already sit on page 1 (pos<=10), excluding brand
p1 = [r for r in rows if r["position"] <= 10 and not BRAND.search(r["keys"][0])]
our_ctr = sum(r["clicks"] for r in p1) / max(1, sum(r["impressions"] for r in p1))
p1c = [r for r in p1 if COM.search(r["keys"][0])]
our_ctr_com = sum(r["clicks"] for r in p1c) / max(1, sum(r["impressions"] for r in p1c))
print(f"window {start}..{end}; queries={len(rows)}; total impr/90d={sum(r['impressions'] for r in rows)}")
print(f"our observed CTR on page-1 (pos<=10, non-brand): {our_ctr*100:.1f}% over {sum(r['impressions'] for r in p1)} impr; commercial-only: {our_ctr_com*100:.1f}% over {sum(r['impressions'] for r in p1c)} impr")
buckets = collections.defaultdict(lambda: {"n":0, "impr_now":0.0, "impr_p1":0.0})
for r in rows:
    q = r["keys"][0]
    if BRAND.search(q): continue
    k = "commercial" if COM.search(q) else "informational"
    m = r["impressions"] / 3.0  # per month
    buckets[k]["n"] += 1; buckets[k]["impr_now"] += m; buckets[k]["impr_p1"] += m * vis(r["position"])
AOV = 80.0
scen = {"A our observed page-1 CTR": our_ctr, "B typical page-1 blend (5%)": 0.05, "C top-3 (15%)": 0.15}
print("\nbucket        queries  impr/mo now  impr/mo if all page-1")
for k, b in buckets.items(): print(f"{k:14s} {b['n']:6d} {b['impr_now']:12.0f} {b['impr_p1']:16.0f}")
print("\nRevenue/month if EVERY tracked query is on page 1 (conversion: commercial clicks 1%; informational clicks 1% x 15% reach a product page). AOV $80.")
print(f"{'scenario':32s} {'clicks/mo':>10s} {'sales/mo':>9s} {'revenue/mo':>11s}   (x1.5 long-tail: revenue)")
for name, ctr in scen.items():
    cc = buckets["commercial"]["impr_p1"] * ctr; ic = buckets["informational"]["impr_p1"] * ctr
    sales = cc * 0.01 + ic * 0.01 * 0.15; rev = sales * AOV
    print(f"{name:32s} {cc+ic:10.0f} {sales:9.1f} {rev:11.0f}   {rev*1.5:8.0f}")
# the realistic near-term target set: queries at pos 8-30 today, commercial only
tgt = [r for r in rows if 8 <= r["position"] <= 30 and COM.search(r["keys"][0]) and not BRAND.search(r["keys"][0])]
ti = sum(r["impressions"]/3*vis(r["position"]) for r in tgt)
print(f"\nNear-term target set (commercial, pos 8-30 today): {len(tgt)} queries, {sum(r['impressions'] for r in tgt)/3:.0f} impr/mo now -> ~{ti:.0f} impr/mo on page 1")
for name, ctr in scen.items(): print(f"  {name:32s} clicks {ti*ctr:6.0f}/mo  sales {ti*ctr*0.01:4.1f}/mo  revenue ${ti*ctr*0.01*AOV:5.0f}/mo")
