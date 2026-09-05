// Pure tax-mechanics core for the RSU withholding-gap calculator (static/js/rsu-tax.js).
// Tax tables are injected so these tests are year-independent; the real 2026 table has its own test.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as T from "../../static/js/rsu-tax.js";

// Synthetic progressive table: 10% to 10k, 20% to 50k, 30% above; standard deduction 10k.
const BR = [{ upTo: 10000, rate: 0.10 }, { upTo: 50000, rate: 0.20 }, { upTo: Infinity, rate: 0.30 }];
const TABLE = { year: 2099, standardDeduction: { single: 10000, mfj: 20000, hoh: 15000 },
                brackets: { single: BR, mfj: BR, hoh: BR },
                addlMedicareThreshold: { single: 200000, mfj: 250000, hoh: 200000 } };

test("bracketTax is progressive and zero at or below zero", () => {
  assert.equal(T.bracketTax(0, BR), 0);
  assert.equal(T.bracketTax(-500, BR), 0);
  assert.equal(T.bracketTax(10000, BR), 1000);
  assert.equal(T.bracketTax(30000, BR), 5000);      // 1,000 + 20% × 20,000
  assert.equal(T.bracketTax(60000, BR), 12000);     // 1,000 + 8,000 + 30% × 10,000
});

test("supplementalWithholding is 22% flat and 37% on the cumulative excess over $1M", () => {
  assert.equal(T.supplementalWithholding(100000), 22000);
  assert.equal(T.supplementalWithholding(1500000), 405000);          // 220,000 + 37% × 500,000
  assert.equal(T.supplementalWithholding(200000, 900000), 59000);    // 22% × 100k + 37% × 100k
});

test("marginalOnSlice is the incremental tax the RSU slice adds on top of everything else", () => {
  assert.equal(T.marginalOnSlice(60000, 20000, BR), 5000);           // tax(60k) − tax(40k)
});

test("bracketFill shows how the slice is taxed bracket by bracket", () => {
  assert.deepEqual(T.bracketFill(60000, 20000, BR), [{ rate: 0.20, amount: 10000 }, { rate: 0.30, amount: 10000 }]);
  assert.deepEqual(T.bracketFill(5000, 5000, BR), [{ rate: 0.10, amount: 5000 }]);
});

test("computeGap: federal shortfall = total tax − assumed salary withholding − 22% RSU withholding", () => {
  const r = T.computeGap({ filingStatus: "single", salary: 50000, rsuIncome: 20000 }, TABLE);
  assert.equal(r.taxableIncome, 60000);
  assert.equal(r.federalTaxTotal, 12000);
  assert.equal(r.salaryWithheldAssumed, 7000);      // tax on 50k − 10k deduction, as if no RSUs
  assert.equal(r.rsuWithheld, 4400);
  assert.equal(r.federalTaxOnRsu, 5000);
  assert.equal(r.effectiveMarginalOnRsu, 0.25);
  assert.equal(r.federalGap, 600);
  assert.equal(r.stateGap, 0);
  assert.equal(r.totalGap, 600);
});

test("computeGap: state gap = (state marginal − state supplemental) × RSU income", () => {
  const r = T.computeGap({ filingStatus: "single", salary: 50000, rsuIncome: 20000,
                           stateSupplementalRate: 0.1023, stateMarginalRate: 0.133 }, TABLE);
  assert.equal(r.stateGap, 614);
  assert.equal(r.totalGap, 1214);
});

test("computeGap: pre-tax deductions reduce taxable income; taxable income never goes negative", () => {
  const r = T.computeGap({ filingStatus: "single", salary: 50000, rsuIncome: 20000, pretaxDeductions: 23000 }, TABLE);
  assert.equal(r.taxableIncome, 37000);
  const z = T.computeGap({ filingStatus: "single", salary: 3000, rsuIncome: 2000 }, TABLE);
  assert.equal(z.taxableIncome, 0);
  assert.equal(z.federalTaxTotal, 0);
});

test("computeGap: safe harbor uses 90% of current-year tax, or the prior-year alternative when given", () => {
  const base = { filingStatus: "single", salary: 50000, rsuIncome: 20000 };
  const a = T.computeGap(base, TABLE);                       // withheld 11,400 ≥ 90% × 12,000 = 10,800
  assert.equal(a.safeHarbor.ninetyPct, 10800);
  assert.equal(a.safeHarbor.requiredPayments, 0);
  const b = T.computeGap({ ...base, rsuIncome: 100000 }, TABLE);   // tax(140k)=36k; withheld 7k+22k=29k; 90%=32.4k
  assert.equal(b.safeHarbor.requiredPayments, 3400);
  const c = T.computeGap({ ...base, rsuIncome: 100000, priorYearTax: 20000 }, TABLE);  // 100% prior = 20k < 29k withheld
  assert.equal(c.safeHarbor.priorYearPct, 20000);
  assert.equal(c.safeHarbor.requiredPayments, 0);
  const d = T.computeGap({ ...base, rsuIncome: 100000, priorYearTax: 30000, priorYearAgiOver150k: true }, TABLE);
  assert.equal(d.safeHarbor.priorYearPct, 33000);   // 110%
  assert.equal(d.safeHarbor.requiredPayments, 3400); // min(32.4k, 33k) − 29k
});

test("computeGap: Additional Medicare is withheld over $200k of wages but owed over the filing-status threshold", () => {
  const s = T.computeGap({ filingStatus: "single", salary: 200000, rsuIncome: 100000 }, TABLE);
  assert.equal(s.addlMedicare.owed, 900);       // 0.9% × 100,000
  assert.equal(s.addlMedicare.withheld, 900);
  assert.equal(s.addlMedicare.gap, 0);
  const m = T.computeGap({ filingStatus: "mfj", salary: 200000, rsuIncome: 100000 }, TABLE);
  assert.equal(m.addlMedicare.owed, 450);       // 0.9% × (300,000 − 250,000)
  assert.equal(m.addlMedicare.withheld, 900);
  assert.equal(m.addlMedicare.gap, -450);       // over-withheld; reported, not clamped
});

test("computeGap rounds money to cents", () => {
  const r = T.computeGap({ filingStatus: "single", salary: 33333.33, rsuIncome: 12345.67 }, TABLE);
  for (const k of ["federalTaxTotal", "rsuWithheld", "federalGap", "totalGap"]) {
    assert.equal(r[k], Math.round(r[k] * 100) / 100, k);
  }
});
