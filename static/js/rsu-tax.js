/* RSU withholding-gap calculator — pure tax mechanics (ESM, no dependencies).
 * Tested by tests/js/*.test.mjs (node --test). Tax tables are injected; TABLE_2026 is pinned to
 * IRS IR-2025-103 / Rev. Proc. 2025-32 and Publication 15 (2026), verified 2026-09-05.
 * This computes withholding arithmetic on compensation. It is not tax advice and it never
 * recommends buying, selling or holding a security. */

export const SUPPLEMENTAL_FLAT = 0.22;               // IRS optional flat rate on supplemental wages
export const SUPPLEMENTAL_HIGH = 0.37;               // mandatory rate on supplemental wages over $1M in a year
export const SUPPLEMENTAL_HIGH_THRESHOLD = 1_000_000;
export const SS_WAGE_BASE_2026 = 184_500;
export const ADDL_MEDICARE_RATE = 0.009;
export const ADDL_MEDICARE_WITHHOLDING_START = 200_000; // employers withhold above this regardless of filing status

export const TABLE_2026 = {
  year: 2026,
  source: "IRS IR-2025-103 / Rev. Proc. 2025-32; IRS Publication 15 (2026)",
  standardDeduction: { single: 16_100, mfj: 32_200, hoh: 24_150 },
  brackets: {
    single: [{ upTo: 12_400, rate: 0.10 }, { upTo: 50_400, rate: 0.12 }, { upTo: 105_700, rate: 0.22 }, { upTo: 201_775, rate: 0.24 },
             { upTo: 256_225, rate: 0.32 }, { upTo: 640_600, rate: 0.35 }, { upTo: Infinity, rate: 0.37 }],
    mfj:    [{ upTo: 24_800, rate: 0.10 }, { upTo: 100_800, rate: 0.12 }, { upTo: 211_400, rate: 0.22 }, { upTo: 403_550, rate: 0.24 },
             { upTo: 512_450, rate: 0.32 }, { upTo: 768_700, rate: 0.35 }, { upTo: Infinity, rate: 0.37 }],
  },
  addlMedicareThreshold: { single: 200_000, mfj: 250_000, hoh: 200_000 },
};

const round2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

/** Progressive tax on `taxable` under `brackets` ([{upTo, rate}] ascending, last upTo = Infinity). */
export function bracketTax(taxable, brackets) {
  if (!(taxable > 0)) return 0;
  let tax = 0, lower = 0;
  for (const { upTo, rate } of brackets) {
    if (taxable <= lower) break;
    tax += (Math.min(taxable, upTo) - lower) * rate;
    lower = upTo;
  }
  return round2(tax);
}

/** Federal withholding an employer takes on supplemental wages: 22% flat, 37% on the cumulative excess over $1M. */
export function supplementalWithholding(amount, priorSupplementalYtd = 0) {
  const flatRoom = Math.max(0, SUPPLEMENTAL_HIGH_THRESHOLD - priorSupplementalYtd);
  const flat = Math.max(0, Math.min(amount, flatRoom));
  const high = Math.max(0, amount - flat);
  return round2(flat * SUPPLEMENTAL_FLAT + high * SUPPLEMENTAL_HIGH);
}

/** The incremental tax the top `slice` of `totalTaxable` adds. */
export function marginalOnSlice(totalTaxable, slice, brackets) {
  return round2(bracketTax(totalTaxable, brackets) - bracketTax(totalTaxable - slice, brackets));
}

/** How the top `slice` of `totalTaxable` is split across brackets: [{rate, amount}]. */
export function bracketFill(totalTaxable, slice, brackets) {
  const base = Math.max(0, totalTaxable - slice), rows = [];
  let lower = 0;
  for (const { upTo, rate } of brackets) {
    const lo = Math.max(lower, base), hi = Math.min(upTo, totalTaxable);
    if (hi > lo) rows.push({ rate, amount: round2(hi - lo) });
    lower = upTo;
    if (upTo >= totalTaxable) break;
  }
  return rows;
}

/**
 * The April-surprise arithmetic. Assumes the employer's regular-wage withholding covers the tax on
 * salary alone (a standard W-4 with no extra withholding) and that RSU income is withheld at the
 * supplemental flat rate — the two defaults that produce the gap.
 */
export function computeGap(inp, table) {
  const fs = inp.filingStatus || "single";
  const brackets = table.brackets[fs];
  const deduction = Math.max(table.standardDeduction[fs], inp.itemized || 0);
  const pretax = inp.pretaxDeductions || 0;
  const salary = inp.salary || 0, rsu = inp.rsuIncome || 0, wages = salary + rsu;

  const taxableIncome = Math.max(0, round2(wages - pretax - deduction));
  const taxableSalaryOnly = Math.max(0, round2(salary - pretax - deduction));
  const federalTaxTotal = bracketTax(taxableIncome, brackets);
  const salaryWithheldAssumed = bracketTax(taxableSalaryOnly, brackets);
  const rsuWithheld = supplementalWithholding(rsu, inp.priorSupplementalYtd || 0);
  const federalTaxOnRsu = round2(federalTaxTotal - salaryWithheldAssumed);
  const effectiveMarginalOnRsu = rsu > 0 ? Math.round((federalTaxOnRsu / rsu) * 10000) / 10000 : 0;
  const federalGap = round2(federalTaxTotal - salaryWithheldAssumed - rsuWithheld);
  const stateGap = round2(((inp.stateMarginalRate || 0) - (inp.stateSupplementalRate || 0)) * rsu);
  const totalGap = round2(federalGap + stateGap);

  const withheldTotal = round2(salaryWithheldAssumed + rsuWithheld);
  const ninetyPct = round2(0.9 * federalTaxTotal);
  const priorYearPct = inp.priorYearTax != null ? round2(inp.priorYearTax * (inp.priorYearAgiOver150k ? 1.10 : 1.0)) : null;
  const required = priorYearPct != null ? Math.min(ninetyPct, priorYearPct) : ninetyPct;
  const safeHarbor = { ninetyPct, priorYearPct, required: round2(required), requiredPayments: round2(Math.max(0, required - withheldTotal)) };

  const owed = round2(Math.max(0, wages - table.addlMedicareThreshold[fs]) * ADDL_MEDICARE_RATE);
  const withheld = round2(Math.max(0, wages - ADDL_MEDICARE_WITHHOLDING_START) * ADDL_MEDICARE_RATE);
  const addlMedicare = { owed, withheld, gap: round2(owed - withheld) };

  return { filingStatus: fs, wages, deduction, taxableIncome, taxableSalaryOnly, federalTaxTotal, salaryWithheldAssumed, rsuWithheld,
           federalTaxOnRsu, effectiveMarginalOnRsu, federalGap, stateGap, totalGap, withheldTotal, safeHarbor, addlMedicare,
           bracketRows: bracketFill(taxableIncome, taxableIncome - taxableSalaryOnly, brackets), tableYear: table.year };
}
