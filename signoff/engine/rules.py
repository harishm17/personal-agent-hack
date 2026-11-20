"""The rules code decides: span match, sums, margins, the pick and the statuses.

Pure functions, no I/O. `build_state` reproduces `fixtures/state.json` from the fixture inputs
(tests/engine/test_rules.py). Nothing in here knows what the sheet is about.
"""

ALIASES = {
    "lb": "lb", "lbs": "lb", "lb.": "lb", "lbs.": "lb", "pound": "lb", "pounds": "lb",
    "in": "in", "in.": "in", "inch": "in", "inches": "in", '"': "in", "”": "in", "″": "in",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm", "mm": "mm", "millimeters": "mm",
    "kg": "kg", "kgs": "kg", "kilograms": "kg", "ft": "ft", "feet": "ft", "foot": "ft",
}
TO_BASE = {("cm", "in"): 1 / 2.54, ("mm", "in"): 1 / 25.4, ("ft", "in"): 12.0, ("kg", "lb"): 2.2046226}


def unit_name(unit):
    return ALIASES.get(str(unit or "").strip().lower())


def convert(value, unit, to):
    """A stated value in the limit's unit, or None when the units cannot be compared."""
    unit, to = unit_name(unit), unit_name(to)
    if value is None or unit is None or to is None:
        return None
    if unit == to:
        return value
    factor = TO_BASE.get((unit, to))
    return None if factor is None else round(value * factor, 2)


def span_found(figure, text):
    """A figure counts only if the quote sits in the store's text at the stated offsets."""
    start, end, quote = figure.get("start"), figure.get("end"), figure.get("quote")
    if not isinstance(start, int) or not isinstance(end, int) or not quote or text is None:
        return False
    return 0 <= start < end <= len(text) and text[start:end] == quote


def deciding(fig, op):
    """A spread uses the end that could fail. An adjustable range uses the end that reaches furthest."""
    if fig["kind"] == "single":
        return fig["value"]
    if fig["kind"] == "spread":
        return fig["low"] if op == ">=" else fig["high"]
    return fig["high"] if op == ">=" else fig["low"]


def usable(fig, limit_unit):
    """Why a figure cannot be used in a sum, or None when it can."""
    if not fig:
        return "never stated on the page"
    if not fig.get("span_found_in_text"):
        return "quote not found in the store's text"
    if fig.get("unsure"):
        return "stated, but not clearly for this product: %s" % (fig.get("unsure_reason") or "unclear")
    if fig.get("kind") not in ("single", "spread", "adjustable"):
        return "stated in a form code cannot compare"
    ends = [fig.get("value")] if fig["kind"] == "single" else [fig.get("low"), fig.get("high")]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in ends):
        return "stated without a number"
    if unit_name(fig.get("unit")) != unit_name(limit_unit) or unit_name(limit_unit) is None:
        return "stated in %s, not %s" % (fig.get("unit"), limit_unit)
    return None


def check(limit, product, figs, facts, sheet):
    terms, lhs, missing, why_missing, adjustable = [], 0.0, None, None, None
    for t in limit["terms"]:
        if t["source"] == "shopper":
            f = facts[t["fact"]]
            terms.append({"owner": "shopper", "owner_name": sheet["shopper"]["name"], "label": f["short"],
                          "fact": f["id"], "value": f["value"], "unit": f["unit"]})
            lhs += f["value"]
            continue
        fig = figs.get((product["store"], product["product_id"], t["figure"]))
        problem = usable(fig, limit["unit"])
        if problem:
            missing, why_missing = missing or t["figure"], why_missing or problem
            terms.append({"owner": "store", "owner_name": product["store"], "label": t["figure"].replace("_", " "),
                          "figure": t["figure"], "value": None, "unit": limit["unit"]})
            continue
        v = deciding(fig, limit["op"])
        if fig["kind"] == "adjustable":
            adjustable = fig
        terms.append({"owner": "store", "owner_name": product["store"], "label": t["figure"].replace("_", " "),
                      "figure": t["figure"], "value": v, "unit": fig["unit"], "kind": fig["kind"],
                      "low": fig["low"], "high": fig["high"], "quote": fig["quote"],
                      "start": fig["start"], "end": fig["end"]})
        lhs += v
    b = limit["bound"]
    if b["source"] == "issuer":
        bound = {"owner": "issuer", "owner_name": sheet["issuer"]["name"], "value": b["value"], "unit": limit["unit"]}
    else:
        f = facts[b["fact"]]
        bound = {"owner": "shopper", "owner_name": sheet["shopper"]["name"], "fact": f["id"], "label": f["short"],
                 "value": f["value"], "unit": f["unit"]}
    out = {"limit_id": limit["id"], "name": limit["name"], "terms": terms, "op": limit["op"], "bound": bound}
    if missing:
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "not_stated",
                    "missing_figure": missing})
        if why_missing != "never stated on the page":
            out["missing_why"] = why_missing
        return out
    ok = lhs >= bound["value"] if limit["op"] == ">=" else lhs <= bound["value"]
    margin = round(lhs - bound["value"] if limit["op"] == ">=" else bound["value"] - lhs, 2)
    shown = " + ".join("%g" % t["value"] for t in terms)
    expr = ("%s = %g %s %g" % (shown, lhs, limit["op"], bound["value"])) if len(terms) > 1 else \
        "%g %s %g" % (lhs, limit["op"], bound["value"])
    if adjustable and ok:  # an adjustable range passes only when the limit lies inside it
        others = lhs - deciding(adjustable, limit["op"])
        low, high = adjustable["low"] + others, adjustable["high"] + others
        ok = low <= bound["value"] <= high
        if not ok:  # the range reaches past the limit but cannot be set to it
            expr = "%g within %g to %g" % (bound["value"], low, high)
            margin = round(-abs(low - bound["value"] if limit["op"] == ">=" else bound["value"] - high), 2)
    out.update({"lhs": round(lhs, 2), "expr": expr, "pass": ok, "margin": margin, "state": "pass" if ok else "fail"})
    return out


def figure_index(figures):
    """One figure per (store, product, name): the first whose span is found and that is not marked unsure."""
    figs = {}
    for f in figures:
        key = (f["store"], f["product_id"], f["figure"])
        held = figs.get(key)
        if held is None or (usable_rank(f) < usable_rank(held)):
            figs[key] = f
    return figs


def usable_rank(f):
    return (0 if f.get("span_found_in_text") else 2) + (1 if f.get("unsure") else 0)


def build_state(sheet, pool, figures, answers, strikes, mode="fixture"):
    facts = {f["id"]: f for f in sheet["shopper_facts"]}
    figs = figure_index(figures)
    by_product = {}
    for f in figures:
        by_product.setdefault((f["store"], f["product_id"]), []).append(f)
    ans = {a["store"]: a for a in answers}
    lines, found, every, inside_n, ready = [], len(pool), 0, 0, 0
    for line in sheet["lines"]:
        struck = [s for s in strikes if s["line_id"] == line["id"]]
        struck_by_key = {s["product_key"]: s for s in struck}
        cands = []
        for p in pool:
            if line["id"] not in p["line_ids"]:
                continue
            checks = [check(l, p, figs, facts, sheet) for l in line["limits"]]
            a = ans.get(p["store"], {})
            d = a.get("delivery") or {"stated": False}
            missing = [c for c in checks if c["state"] == "not_stated"]
            strike = struck_by_key.get(p["product_key"])
            if strike:
                status, reason = "struck", strike["reason"]
            elif missing:
                status = "not_stated"
                reason = "%s %s" % (missing[0]["missing_figure"].replace("_", " "),
                                    missing[0].get("missing_why", "never stated on the page"))
            elif all(c["pass"] for c in checks):
                status, reason = "inside", None
            else:
                bad = next(c for c in checks if not c["pass"])
                status, reason = "outside", "%s: %s is false" % (bad["name"], bad["expr"])
            every += 0 if missing else 1
            cands.append({
                "id": "%s:%s:%s" % (line["id"], p["store"], p["product_id"]),
                "order_line": {"id": line["id"], "need": line["need"], "room": line["room"]},
                "product": {k: p[k] for k in ("store", "product_id", "variant_id", "title", "price_cents", "url",
                                              "fetched_at", "product_key")},
                "figures": by_product.get((p["store"], p["product_id"]), []),
                "checks": checks,
                "arrival": {"need_by": sheet["need_by"], "status": "stated" if d.get("stated") else "not stated",
                            "quote": d.get("quote"), "days_low": d.get("days_low"), "days_high": d.get("days_high")},
                "undo": a.get("returns"), "senso": None, "status": status, "reason": reason,
                "strike": strike, "action": None, "picked": False})
        inside = [c for c in cands if c["status"] == "inside"]
        local = line["fulfilment"] == "pick_up_locally"  # nothing is shipped, so no delivery time is needed
        eligible = sorted((c for c in inside if local or c["arrival"]["status"] == "stated"),
                          key=lambda c: (c["product"]["price_cents"], c["id"]))
        pick = eligible[0] if eligible else None
        inside_n += len(inside)
        if pick:
            pick["picked"] = True
            status = "pick_up" if local else ("next_candidate" if struck else "ready")
            reason = line.get("fulfilment_note") if status == "pick_up" else None
            ready += 1 if status in ("ready", "next_candidate") else 0
            t = sorted(pick["checks"], key=lambda c: c["margin"])[0]
            tightest = {"limit_id": t["limit_id"], "name": t["name"], "margin": t["margin"], "unit": t["bound"]["unit"],
                        "text": "nothing to spare" if t["margin"] == 0 else "%g %s to spare" % (t["margin"], t["bound"]["unit"])}
        else:
            status, tightest = "open", None
            if inside:
                reason = "nothing inside the limits states a delivery time"
            elif any(c["status"] == "outside" for c in cands):  # pages that state every figure exist, and all fail
                reason = "nothing inside the limits"
            elif any(c["status"] == "not_stated" for c in cands):
                reason = "no page states every figure"
            else:
                reason = "nothing inside the limits"
        lines.append({"line_id": line["id"], "need": line["need"], "room": line["room"], "status": status,
                      "reason": reason, "pick": pick["id"] if pick else None, "tightest": tightest,
                      "why": {"total": len(cands), "inside": len(inside), "with_delivery_time": len(eligible),
                              "rule": sheet["pick_rule"]["label"],
                              "pick_price_cents": pick["product"]["price_cents"] if pick else None},
                      "struck": struck, "candidates": cands})
    total = sum(c["product"]["price_cents"] for l in lines for c in l["candidates"]
                if c["picked"] and l["status"] in ("ready", "next_candidate"))
    return {"version": 1, "mode": mode, "sheet": sheet,
            "seal": {"signed": False, "text": "Not signed. No cart exists at any store.", "sheet_hash": None,
                     "signature": None, "carts": []},
            "issuer_key": {"enrolled": False, "key_id": None, "persona": None},
            "counts": {"products_found": found, "state_every_figure": every, "inside_limits": inside_n,
                       "lines_ready": ready, "lines_total": len(lines), "hand_checked": False},
            "total_cents": total, "store_answers": answers, "lines": lines}
