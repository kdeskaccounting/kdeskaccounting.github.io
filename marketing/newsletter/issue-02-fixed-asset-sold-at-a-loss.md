---
issue: 2
subject: "Selling a van for less than it is worth on the books"
preview: "Cost $48,000, sold for $12,000 after 42 months. Two entries and a $2,400 loss."
status: draft
fact_check: pending
---

**The situation**

A delivery van cost $48,000 and went into service on January 1, 2023. You depreciate it
straight-line over five years with no salvage value, which is $800 a month. On June 30, 2026 you
sell it for $12,000.

**Step one: depreciate through the sale date**

June's depreciation still has to be booked. Skip it and the loss comes out $800 too high.

```
Dr  Depreciation expense            800
    Cr  Accumulated depreciation          800
```

That makes 42 months: $33,600 of accumulated depreciation and a net book value of $14,400.

**Step two: remove the asset**

```
Dr  Cash                         12,000
Dr  Accumulated depreciation     33,600
Dr  Loss on disposal              2,400
    Cr  Vehicles                         48,000
```

The loss is net book value less proceeds: $14,400 less $12,000.

**The tie-out**

After the entry, the van's cost and its accumulated depreciation are both zero in the fixed asset
register. In the rollforward, disposals show $48,000 of cost and $33,600 of accumulated depreciation,
and the register's ending balances match the general ledger for both accounts.

Sale, retirement, trade-in and write-off, each with its entry:
https://kdeskaccounting.com/posts/fixed-asset-disposal-journal-entries/

Stephen
KDesk Accounting
