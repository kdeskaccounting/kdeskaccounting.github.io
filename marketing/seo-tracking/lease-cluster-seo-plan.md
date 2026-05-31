# Lease-Cluster SEO Plan (ASC 842)

**Created:** 2026-05-31 · **Trigger:** GSC snapshot 2026-05-30 — the lease family is ~64% of all organic impressions (1,558 of 2,433) but ranks position ~35 (page 4) → 0 clicks. Two unrelated pages already sit on page 1, proving the site *can* rank. Goal: move the lease cluster from page 4 toward page 1.

## The cluster (5 posts)

| Post | Topic | Impr (28d) | Avg pos |
|---|---|---|---|
| `operating-vs-finance-lease` | Classification (entry point) | 690 | 39.6 |
| `asc-842-journal-entries` | The journal entries | 519 | 35.0 |
| `asc-842-vs-ifrs-16` | IFRS 16 comparison | 349 | 35.2 |
| `asc-842-amortization-schedule-excel` | Build the schedule | (low/n.r.) | — |
| `right-of-use-asset-calculation-asc-842` | ROU asset at commencement | (low/n.r.) | — |

## Diagnosis (why it's stuck on page 4)

1. **No topical-authority signal.** The cluster is barely interlinked. `asc-842-journal-entries` links to **no** siblings; `right-of-use` and `amortization-schedule` are orphaned. Google can't see this as an authoritative ASC 842 topic cluster.
2. **No schema → CTR ceiling.** Zero FAQ/structured data on any post. The actual bottleneck is CTR (0.04%); FAQ rich results + "People Also Ask" eligibility is the cheapest CTR lever.
3. **Thin-ish + stale signals.** ~1,000 words each; three posts have no `Lastmod`.

## Strategy: hub-and-spoke topic cluster + CTR fixes

Two phases. **Phase 1 is the high-EV core and adds zero new pages** — it's pure on-page/internal work (T0, auto-executable). Phase 2 is optional and heavier.

---

## PHASE 1 — interlink + schema + freshness (do first)

### 1a. Internal interlinking (hub-and-spoke)

Designate **`operating-vs-finance-lease`** as the cluster hub (most impressions; classification is the logical entry to lease accounting). Every spoke links UP to the hub; the hub links DOWN to every spoke; siblings cross-link where contextually natural. Use descriptive, keyword-bearing anchor text in-context (not a bare footer list).

**Links to ADD (from → to · anchor text):**

- `operating-vs-finance-lease` → `right-of-use-asset-calculation` · "how to calculate the right-of-use asset"
- `operating-vs-finance-lease` → `asc-842-amortization-schedule-excel` · "build the lease amortization schedule"
- `operating-vs-finance-lease` → `asc-842-vs-ifrs-16` · "how classification differs under IFRS 16"
- `asc-842-journal-entries` → `operating-vs-finance-lease` · "how to classify a lease (operating vs finance)" **[biggest gap — pillar links to nothing today]**
- `asc-842-journal-entries` → `right-of-use-asset-calculation` · "calculate the ROU asset at commencement"
- `asc-842-journal-entries` → `asc-842-amortization-schedule-excel` · "the amortization schedule these entries pull from"
- `asc-842-vs-ifrs-16` → `operating-vs-finance-lease` · "the ASC 842 classification tests"
- `right-of-use-asset-calculation` → `operating-vs-finance-lease` (hub), `asc-842-amortization-schedule-excel`, `asc-842-journal-entries` (currently orphaned)
- `asc-842-amortization-schedule-excel` → `operating-vs-finance-lease` (hub), `right-of-use-asset-calculation`, `asc-842-journal-entries` (currently orphaned)

Net: every post ends with ≥3 in-context sibling links + the existing workbook CTA. Keep the existing links (don't remove).

### 1b. FAQ schema (CTR lever)

Add a short **FAQ section (3–5 Q&As) + `FAQPage` JSON-LD** to each of the 5 posts. Source the questions from the actual "People Also Ask" / query intent (e.g., operating-vs-finance: "Is a 5-year lease operating or finance?", "Does an operating lease go on the balance sheet under ASC 842?"). Implementation: add a `faqs:` list to post frontmatter + a `layouts/partials/faq_schema.html` partial that emits FAQPage JSON-LD and a visible FAQ block (mirrors how `/templates/` pages already do FAQ + JSON-LD). One partial, reused by all posts.

### 1c. Freshness

Add `Lastmod: 2026-05-31` to every post edited (three lack it). Editing + lastmod re-signals freshness; Google re-crawls.

---

## PHASE 2 — depth + pillar (optional, after Phase 1 is measured)

- **Pull per-page GSC queries** (the query each lease post actually shows for) and expand each post to answer those specific queries — targeted, not blind word-count padding.
- **Consider a dedicated pillar page** "ASC 842 Lease Accounting: The Complete Guide" targeting the head term, summarizing + linking all 5 spokes, with spokes linking up to it. Higher effort / one more page to maintain — only if Phase 1 shows movement.

---

## Measurement & honest expectations

- Re-pull the GSC snapshot weekly (`marketing/seo-tracking/gsc-snapshots.jsonl`); watch **avg position** on the three priority pages, then CTR/clicks.
- Ranking changes take **2–4 weeks** to reflect. Page 4 → page 1 on competitive ASC 842 terms is ambitious; realistic near-term target is **pos ~35 → pos ~15–20**, with clicks following once any page crosses to page 1. The already-page-1 pages (month-end-close pos 8.6, saas-deferred pos 6.2) prove the ceiling is reachable.
- Leading indicator that it's working: impressions hold/rise **and** avg position drops before clicks move.

## Tier / execution note

Phase 1 is T0 (on-page SEO + internal links + meta) — auto-executable, log to `decisions/decisions.jsonl`. Phase 2's pillar page is new content → surface to Stephen first.
