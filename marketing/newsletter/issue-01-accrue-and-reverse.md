---
issue: 1
subject: "The accrual you reverse on day one"
preview: "A $7,500 legal bill with no invoice at month-end, in three entries."
status: draft
fact_check: pending
---

**The situation**

Outside counsel did $7,500 of work in November. It is November 30, the books are closing, and no
invoice has arrived.

**The entries**

November 30, accrue the expense:

```
Dr  Legal expense             7,500
    Cr  Accrued liabilities           7,500
```

December 1, reverse it:

```
Dr  Accrued liabilities       7,500
    Cr  Legal expense                 7,500
```

December 9, the invoice arrives for $7,900 and posts through accounts payable like any other bill:

```
Dr  Legal expense             7,900
    Cr  Accounts payable              7,900
```

**What it does**

November carries the $7,500 it should. December shows $400: the $7,900 invoice less the $7,500
reversal. That $400 is the gap between your estimate and the bill, and it lands in December without
anyone reopening November.

The reversal on day one is the point. Whoever codes the invoice in December does not need to know an
accrual existed. They post the bill as usual and the net comes out right.

**The tie-out**

Before you close November, list every accrual with its amount and what it is for. The total of that
list equals the balance in Accrued liabilities for these items. On December 1, after the reversals,
last month's list is at zero. Anything still sitting there has no reversal and needs a reason.

The month-end close checklist has a tab for that list:
https://kdeskaccounting.com/templates/month-end-close/

Stephen
KDesk Accounting
