// The real tax-year-2026 table, pinned to IRS IR-2025-103 / Rev. Proc. 2025-32 (verified 2026-09-05)
// and Publication 15 (2026). If any of these change, the calculator's fine print must change too.
import { test } from "node:test";
import assert from "node:assert/strict";
import { TABLE_2026, SUPPLEMENTAL_FLAT, SUPPLEMENTAL_HIGH, SUPPLEMENTAL_HIGH_THRESHOLD, SS_WAGE_BASE_2026, bracketTax } from "../../static/js/rsu-tax.js";

test("2026 standard deductions (Rev. Proc. 2025-32)", () => {
  assert.equal(TABLE_2026.year, 2026);
  assert.deepEqual(TABLE_2026.standardDeduction, { single: 16100, mfj: 32200 });   // HoH/MFS brackets not verified → not offered
});

test("2026 single brackets", () => {
  assert.deepEqual(TABLE_2026.brackets.single.map(b => [b.upTo, b.rate]), [
    [12400, 0.10], [50400, 0.12], [105700, 0.22], [201775, 0.24], [256225, 0.32], [640600, 0.35], [Infinity, 0.37]]);
});

test("2026 married-filing-jointly brackets", () => {
  assert.deepEqual(TABLE_2026.brackets.mfj.map(b => [b.upTo, b.rate]), [
    [24800, 0.10], [100800, 0.12], [211400, 0.22], [403550, 0.24], [512450, 0.32], [768700, 0.35], [Infinity, 0.37]]);
});

test("2026 payroll constants (Publication 15, 2026)", () => {
  assert.equal(SUPPLEMENTAL_FLAT, 0.22);
  assert.equal(SUPPLEMENTAL_HIGH, 0.37);
  assert.equal(SUPPLEMENTAL_HIGH_THRESHOLD, 1000000);
  assert.equal(SS_WAGE_BASE_2026, 184500);
  assert.deepEqual(TABLE_2026.addlMedicareThreshold, { single: 200000, mfj: 250000 });
});

test("sanity: a single filer with $300k taxable owes the sum of the brackets", () => {
  // 1,240 + 4,560 + 12,166 + 23,058 + 17,424 + 35% × (300,000 − 256,225) = 15,321.25
  assert.equal(bracketTax(300000, TABLE_2026.brackets.single), 73769.25);
});

test("the table only declares filing statuses it fully supports (no half-populated keys)", () => {
  assert.deepEqual(Object.keys(TABLE_2026.standardDeduction).sort(), Object.keys(TABLE_2026.brackets).sort());
  assert.deepEqual(Object.keys(TABLE_2026.addlMedicareThreshold).sort(), Object.keys(TABLE_2026.brackets).sort());
});
