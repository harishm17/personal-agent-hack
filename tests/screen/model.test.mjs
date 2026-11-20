// Run by tests/screen/test_screen_model.py: node --test tests/screen/model.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import * as m from "../../web/screen/model.js";

const state = JSON.parse(readFileSync(new URL("../../fixtures/state.json", import.meta.url)));
const line = (s, id) => s.lines.find((l) => l.line_id === id);

test("numbers are written the way the sums show them", () => {
  assert.equal(m.num(15, "in"), "15.0");
  assert.equal(m.num(27.5, "in"), "27.5");
  assert.equal(m.num(4.25, "in"), "4.25");
  assert.equal(m.num(300, "lb"), "300");
  assert.equal(m.num(null, "lb"), "?");
  assert.equal(m.money(2752), "$27.52");
});

test("the margin is always in words, including nothing to spare", () => {
  const pick = m.pickOf(line(state, "L2"));
  assert.deepEqual(pick.checks.map(m.marginText), ["nothing to spare", "1.0 in to spare"]);
  const outside = line(state, "L2").candidates.find((c) => c.product.product_id === "fx-G");
  assert.equal(m.marginText(outside.checks[1]), "misses by 0.5 in");
  const unknown = line(state, "L2").candidates.find((c) => c.product.product_id === "fx-H");
  assert.equal(m.marginText(unknown.checks[0]), "the page never states weight capacity");
});

test("the figure is found inside the store's sentence", () => {
  const cut = (quote, term) => quote.slice(...m.figureSpan(quote, term));
  assert.equal(cut("Adds 5 to 5.5 inches of height to the toilet seat.", { low: 5, high: 5.5 }), "5 to 5.5 inches");
  assert.equal(cut("Holds up to 300 lb.", { value: 300, low: 300, high: 300 }), "300 lb");
  assert.equal(cut("5” of extra height making it easy", { value: 5 }), "5”");
  assert.equal(cut("a 300-pound weight capacity", { value: 300 }), "300-pound");
  assert.equal(cut("Seat height adjusts from 16 to 21 inches.", { low: 16, high: 21 }), "16 to 21 inches");
  assert.equal(cut("sturdy frame", { value: 300 }), "sturdy frame");
});

test("the line with the most candidates opens first, and both of its limits are axes", () => {
  assert.equal(m.defaultLineId(state), "L2");
  assert.deepEqual(m.plotAxes(line(state, "L2")), [0, 1]);
});

test("an open line shows its limits with the store figure unknown", () => {
  const checks = m.skeletonChecks(state, "L6");
  assert.equal(checks.length, 2);
  assert.equal(checks[0].terms[0].value, null);
  assert.equal(checks[1].bound.owner_name, "Elena");
  assert.equal(checks[1].bound.value, 12);
});

test("axis ranges are round, hold every value and never shrink", () => {
  const d = m.niceDomain([250, 300, 500]);
  assert.ok(d.lo <= 250 && d.hi >= 500);
  assert.equal(d.lo % d.step, 0);
  assert.equal(m.niceDomain([300, 400], d), d);
  assert.ok(m.niceDomain([900], d).hi >= 900);
});

test("sim with nothing moved reproduces the fixture run", () => {
  const sim = m.simulate(state);
  const core = (s) => ({
    counts: s.counts, total: s.total_cents,
    lines: s.lines.map((l) => ({
      status: l.status, reason: l.reason, pick: l.pick, tightest: l.tightest, why: l.why,
      candidates: l.candidates.map((c) => ({
        status: c.status, reason: c.reason, picked: c.picked,
        checks: c.checks.map((ch) => [ch.lhs, ch.expr, ch.pass, ch.margin, ch.state]),
      })),
    })),
  });
  assert.deepEqual(core(sim), core(state));
});

test("sim: raising the capacity limit greys dots and moves the pick to another store", () => {
  const before = m.pickOf(line(state, "L2"));
  const sim = m.simulate(state, { limits: { "L2.capacity": 325 } });
  const after = m.pickOf(line(sim, "L2"));
  assert.equal(before.product.product_id, "fx-A");
  assert.equal(after.product.product_id, "fx-D");
  assert.notEqual(after.product.store, before.product.store);
  assert.equal(line(sim, "L2").candidates.find((c) => c.product.product_id === "fx-A").status, "outside");
  assert.equal(line(sim, "L2").why.inside, 4);
  assert.equal(line(state, "L2").why.inside, 5, "the input state is not changed");
});

test("sim: Elena's measurement shifts every sum that uses it", () => {
  const sim = m.simulate(state, { facts: { toilet_rim_height: 14 } });
  const a = line(sim, "L2").candidates.find((c) => c.product.product_id === "fx-A");
  assert.equal(a.checks[1].lhs, 19);
  assert.equal(a.checks[1].margin, 0);
  assert.equal(line(sim, "L2").candidates.find((c) => c.product.product_id === "fx-E").status, "outside");
});

test("sim: a strike removes the pick and the next candidate takes its place", () => {
  const sim = m.simulate(state, { strikes: [{ line_id: "L2", product_key: "fixture a", reason: "test" }] });
  const l2 = line(sim, "L2");
  assert.equal(l2.candidates.find((c) => c.product.product_id === "fx-A").status, "struck");
  assert.equal(m.pickOf(l2).product.product_id, "fx-D");
  assert.equal(l2.status, "next_candidate");
});

test("an equals limit is a point to hit: no margin, and the sim checks it as equality", () => {
  assert.equal(m.opSymbol("=="), "=");
  assert.equal(m.marginText({ op: "==", pass: true, lhs: 10, bound: { value: 10, unit: "in" }, state: "pass" }), "matches 10.0 in");
  assert.equal(m.marginText({ op: "==", pass: false, lhs: 12, bound: { value: 10, unit: "in" }, state: "fail" }), "12.0 in, not 10.0");
  assert.equal(m.holds("==", 12, 10), false);
  assert.equal(m.num(1.28, "gpf"), "1.28");
  const cut = (quote, term) => quote.slice(...m.figureSpan(quote, term));
  assert.equal(cut("Dual flush: 1.1 to 1.6 GPF.", { low: 1.1, high: 1.6 }), "1.1 to 1.6 GPF");
});

test("the sheet 2 fixture: equality, a spread decided by its high end, and the cheapest rule", () => {
  const s2 = JSON.parse(readFileSync(new URL("../../web/screen/fixture-sheet2.json", import.meta.url)));
  const t1 = s2.lines.find((l) => l.line_id === "T1");
  assert.equal(s2.lines.length, 4);
  const twelve = t1.candidates.find((c) => c.checks[0].lhs === 12);
  assert.equal(twelve.status, "outside");                       // a 12 in rough-in does not equal the measured 10 in
  const dual = t1.candidates.find((c) => c.checks[1].terms[0].kind === "spread" && c.checks[1].terms[0].high === 1.6);
  assert.equal(dual.checks[1].lhs, 1.6);                         // the full flush decides
  assert.equal(dual.status, "outside");
  const pick = m.pickOf(t1), inside = t1.candidates.filter((c) => c.status === "inside");
  assert.equal(pick.product.price_cents, Math.min(...inside.map((c) => c.product.price_cents)));   // cheapest inside, delivery time or not
});
