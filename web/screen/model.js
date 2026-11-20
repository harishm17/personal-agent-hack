// Pure functions over the /api/state shape. No DOM here, so tests/screen can run this file under node.

const LENGTH_UNITS = new Set(["in", "cm", "mm", "ft", "m"]);

export function num(value, unit) {
  if (value === null || value === undefined) return "?";
  const places = unit === "in" ? 1 : 0;
  const fixed = value.toFixed(places);
  return Math.abs(parseFloat(fixed) - value) < 1e-9 ? fixed : String(+value.toFixed(2));
}

export function money(cents) {
  return cents === null || cents === undefined ? "?" : "$" + (cents / 100).toFixed(2);
}

export function opSymbol(op) {
  return op === ">=" ? "≥" : "≤";
}

export function opWords(op) {
  return op === ">=" ? "at least" : "at most";
}

/** Who owns a term or a bound, as the words shown above its number. */
export function ownerWords(part) {
  if (part.owner === "issuer") return part.owner_name + " set";
  if (part.owner === "shopper") return part.owner_name + (LENGTH_UNITS.has(part.unit) ? " measured" : " stated");
  return part.owner_name + " states";
}

/** What a store term's number is, including which end of a stated range the code used. */
export function termNote(term, op) {
  const label = term.label || (term.figure || "").replace(/_/g, " ");
  if (term.value === null || term.value === undefined) return label + ": not stated";
  if (term.kind === "spread") {
    const end = op === ">=" ? "low" : "high";
    return `${label}: ${end} end of ${num(term.low, term.unit)} to ${num(term.high, term.unit)}`;
  }
  if (term.kind === "adjustable") return `${label}: adjusts ${num(term.low, term.unit)} to ${num(term.high, term.unit)}`;
  return label;
}

/** The margin of one check in words. The tightest one is always shown, including "nothing to spare". */
export function marginText(check) {
  const unit = check.bound.unit;
  if (check.state === "not_stated") {
    return "the page never states " + (check.missing_figure || "this figure").replace(/_/g, " ");
  }
  if (check.pass) return check.margin === 0 ? "nothing to spare" : `${num(check.margin, unit)} ${unit} to spare`;
  if (check.margin < 0) return `misses by ${num(-check.margin, unit)} ${unit}`;
  return "the limit is outside its adjustable range";
}

/** Where the figure sits inside the store's quote: [start, end) offsets into `quote`. Whole quote if not found. */
export function figureSpan(quote, term) {
  const whole = [0, quote.length];
  const low = term.low ?? term.value, high = term.high ?? term.value;
  if (low === null || low === undefined) return whole;
  const found = [...quote.matchAll(/\d+(?:\.\d+)?/g)].map((m) => ({ v: parseFloat(m[0]), s: m.index, e: m.index + m[0].length }));
  const first = found.find((t) => t.v === low);
  if (!first) return whole;
  const last = high !== low ? found.find((t) => t.s >= first.e && t.v === high) || first : first;
  const unit = /^\s?-?\s?(?:inches|inch|in\b|”|"|''|lbs?\b|pounds?|cm\b|mm\b|°\s?F\b)/i.exec(quote.slice(last.e));
  return [first.s, last.e + (unit ? unit[0].length : 0)];
}

export function pickOf(line) {
  return line.candidates.find((c) => c.picked) || null;
}

/** The line opened when the page has no #hash: the one with the most candidates. */
export function defaultLineId(state) {
  let best = state.lines[0];
  for (const line of state.lines) if (line.candidates.length > best.candidates.length) best = line;
  return best ? best.line_id : null;
}

/** For a line nothing is proposed for: the limits as sums with every store figure unknown. */
export function skeletonChecks(state, lineId) {
  const sheetLine = state.sheet.lines.find((l) => l.id === lineId);
  const facts = Object.fromEntries(state.sheet.shopper_facts.map((f) => [f.id, f]));
  const fact = (id) => ({ owner: "shopper", owner_name: state.sheet.shopper.name, fact: id, label: facts[id].short, value: facts[id].value, unit: facts[id].unit });
  return sheetLine.limits.map((limit) => ({
    limit_id: limit.id, name: limit.name, op: limit.op,
    terms: limit.terms.map((t) => t.source === "shopper" ? fact(t.fact)
      : { owner: "store", owner_name: "no store", label: t.figure.replace(/_/g, " "), figure: t.figure, value: null, unit: limit.unit }),
    bound: limit.bound.source === "issuer"
      ? { owner: "issuer", owner_name: state.sheet.issuer.name, value: limit.bound.value, unit: limit.unit }
      : fact(limit.bound.fact),
    lhs: null, expr: null, pass: false, margin: null, state: "not_stated",
    missing_figure: (limit.terms.find((t) => t.source === "store") || {}).figure,
  }));
}

/** Which limits are the plot's axes: indexes into checks[]. Two for a box, one for a strip. */
export function plotAxes(line) {
  const sample = pickOf(line) || line.candidates[0];
  if (!sample) return [];
  const withStore = sample.checks.map((c, i) => i).filter((i) => sample.checks[i].terms.some((t) => t.owner === "store"));
  if (withStore.length <= 2) return withStore;
  const tight = (i) => {
    const c = sample.checks[i];
    return c.margin === null || !c.bound.value ? Infinity : Math.abs(c.margin) / Math.abs(c.bound.value);
  };
  return [...withStore].sort((a, b) => tight(a) - tight(b)).slice(0, 2).sort((a, b) => a - b);
}

/** A round axis range that holds every value, with about four steps. Never shrinks below `keep`. */
export function niceDomain(values, keep) {
  let lo = Math.min(...values), hi = Math.max(...values);
  if (keep) { lo = Math.min(lo, keep.lo); hi = Math.max(hi, keep.hi); }
  if (keep && lo >= keep.lo && hi <= keep.hi) return keep;
  const span = hi - lo || Math.abs(hi) || 1;
  lo -= span * 0.12; hi += span * 0.12;
  const raw = (hi - lo) / 4, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step };
}

const round2 = (v) => Math.round(v * 100) / 100;
const g = (v) => String(+v.toPrecision(6));

/**
 * ?sim=1 only: works the checks and the pick out again in the page for a moved limit or measurement,
 * following fixtures/make_state.py. The real screen never calls this; the engine decides.
 * overrides: { limits: {limit_id: value}, facts: {fact_id: value} }
 */
export function simulate(state, overrides = {}) {
  const s = structuredClone(state);
  const facts = Object.fromEntries(s.sheet.shopper_facts.map((f) => [f.id, f]));
  for (const [id, v] of Object.entries(overrides.facts || {})) if (facts[id]) facts[id].value = v;
  const limits = {};
  for (const sheetLine of s.sheet.lines) {
    for (const limit of sheetLine.limits) {
      limits[limit.id] = limit;
      const v = (overrides.limits || {})[limit.id];
      if (v !== undefined && limit.bound.source === "issuer") limit.bound.value = v;
    }
  }
  let insideCount = 0, ready = 0, total = 0;
  for (const line of s.lines) {
    const sheetLine = s.sheet.lines.find((l) => l.id === line.line_id);
    for (const c of line.candidates) {
      for (const ch of c.checks) {
        for (const t of ch.terms) if (t.owner === "shopper") t.value = facts[t.fact].value;
        ch.bound.value = ch.bound.owner === "issuer" ? limits[ch.limit_id].bound.value : facts[ch.bound.fact].value;
        if (ch.state === "not_stated") continue;
        const lhs = ch.terms.reduce((sum, t) => sum + t.value, 0), b = ch.bound.value;
        let ok = ch.op === ">=" ? lhs >= b : lhs <= b;
        const adj = ch.terms.find((t) => t.kind === "adjustable");
        if (adj && ok) {
          const others = lhs - adj.value;
          ok = adj.low + others <= b && b <= adj.high + others;
        }
        const shown = ch.terms.map((t) => g(t.value)).join(" + ");
        ch.lhs = round2(lhs);
        ch.margin = round2(ch.op === ">=" ? lhs - b : b - lhs);
        ch.pass = ok;
        ch.state = ok ? "pass" : "fail";
        ch.expr = ch.terms.length > 1 ? `${shown} = ${g(lhs)} ${ch.op} ${g(b)}` : `${g(lhs)} ${ch.op} ${g(b)}`;
      }
      c.picked = false;
      if (c.status === "struck") continue;
      const missing = c.checks.find((ch) => ch.state === "not_stated");
      const bad = c.checks.find((ch) => !ch.pass);
      if (missing) {
        c.status = "not_stated"; c.reason = `${missing.missing_figure.replace(/_/g, " ")} never stated on the page`;
      } else if (!bad) {
        c.status = "inside"; c.reason = null;
      } else {
        c.status = "outside"; c.reason = `${bad.name}: ${bad.expr} is false`;
      }
    }
    const inside = line.candidates.filter((c) => c.status === "inside");
    const local = sheetLine.fulfilment === "pick_up_locally";
    const eligible = inside.filter((c) => local || c.arrival.status === "stated")
      .sort((a, b) => a.product.price_cents - b.product.price_cents || (a.id < b.id ? -1 : 1));
    const pick = eligible[0] || null;
    insideCount += inside.length;
    if (pick) {
      pick.picked = true;
      line.status = local ? "pick_up" : line.struck.length ? "next_candidate" : "ready";
      line.reason = local ? sheetLine.fulfilment_note || null : null;
      if (line.status !== "pick_up") { ready += 1; total += pick.product.price_cents; }
      const t = [...pick.checks].sort((a, b) => a.margin - b.margin)[0];
      line.tightest = { limit_id: t.limit_id, name: t.name, margin: t.margin, unit: t.bound.unit,
        text: t.margin === 0 ? "nothing to spare" : `${g(t.margin)} ${t.bound.unit} to spare` };
    } else {
      line.status = "open"; line.tightest = null;
      line.reason = !inside.length && line.candidates.some((c) => c.status === "not_stated") ? "no page states every figure"
        : !inside.length ? "nothing inside the limits" : "nothing inside the limits states a delivery time";
    }
    line.pick = pick ? pick.id : null;
    line.why = { ...line.why, total: line.candidates.length, inside: inside.length, with_delivery_time: eligible.length,
      pick_price_cents: pick ? pick.product.price_cents : null };
  }
  s.counts = { ...s.counts, inside_limits: insideCount, lines_ready: ready };
  s.total_cents = total;
  return s;
}
