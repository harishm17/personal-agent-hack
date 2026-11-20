"""The rules code decides: span match, sums, margins, the pick and the statuses.

Pure functions, no I/O. `build_state` reproduces `fixtures/state.json` from the fixture inputs
(tests/engine/test_rules.py). Nothing in here knows what the sheet is about.
"""

ALIASES = {
    "lb": "lb", "lbs": "lb", "lb.": "lb", "lbs.": "lb", "pound": "lb", "pounds": "lb",
    "in": "in", "in.": "in", "inch": "in", "inches": "in", '"': "in", "”": "in", "″": "in",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm", "mm": "mm", "millimeters": "mm",
    "kg": "kg", "kgs": "kg", "kilograms": "kg", "ft": "ft", "feet": "ft", "foot": "ft",
    "qt": "qt", "qts": "qt", "qt.": "qt", "quart": "qt", "quarts": "qt", "l": "L", "liter": "L", "liters": "L",
    "litre": "L", "litres": "L", "°f": "°F", "f": "°F", "fahrenheit": "°F", "degrees f": "°F",
    "°c": "°C", "c": "°C", "celsius": "°C", "oz": "oz", "ounce": "oz", "ounces": "oz",
    "gpf": "gpf", "gallons per flush": "gpf", "gallon per flush": "gpf", "gal/flush": "gpf", "g.p.f.": "gpf",
    "gpm": "gpm", "gallons per minute": "gpm", "gallon per minute": "gpm", "gal/min": "gpm", "g.p.m.": "gpm",
    "lpf": "Lpf", "l/flush": "Lpf", "liters per flush": "Lpf", "litres per flush": "Lpf",
    "lpm": "Lpm", "l/min": "Lpm", "liters per minute": "Lpm", "litres per minute": "Lpm",
}
TO_BASE = {("cm", "in"): 1 / 2.54, ("mm", "in"): 1 / 25.4, ("ft", "in"): 12.0, ("in", "cm"): 2.54,
           ("kg", "lb"): 2.2046226, ("oz", "lb"): 1 / 16, ("lb", "kg"): 1 / 2.2046226,
           ("L", "qt"): 1.0566882, ("qt", "L"): 1 / 1.0566882,
           ("Lpf", "gpf"): 1 / 3.785411784, ("gpf", "Lpf"): 3.785411784,
           ("Lpm", "gpm"): 1 / 3.785411784, ("gpm", "Lpm"): 3.785411784}
FAMILY = {"lb": "weight", "kg": "weight", "oz": "weight", "in": "length", "cm": "length", "mm": "length",
          "ft": "length", "qt": "volume", "L": "volume", "°F": "temperature", "°C": "temperature",
          "gpf": "volume per flush", "Lpf": "volume per flush", "gpm": "flow", "Lpm": "flow"}
OPS = (">=", "<=", "==")
PICK_RULES = ("cheapest_with_delivery_time", "cheapest")


def validate_sheet(sheet):
    """A sheet the rules cannot run is refused when it is loaded, with the reason: an unknown comparison or an
    unknown pick rule is an error, never quietly treated as something else."""
    for line in sheet["lines"]:
        for limit in line["limits"]:
            if limit.get("op") not in OPS:
                raise ValueError("limit %s has the comparison %r; the rules know %s" % (limit.get("id"), limit.get("op"), ", ".join(OPS)))
    rule = (sheet.get("pick_rule") or {}).get("id")
    if rule not in PICK_RULES:
        raise ValueError("the sheet's pick rule %r is not one the rules know (%s)" % (rule, ", ".join(PICK_RULES)))


def unit_name(unit):
    return ALIASES.get(str(unit or "").strip().lower())


def convert(value, unit, to):
    """A stated value in the limit's unit, or None when the units cannot be compared."""
    unit, to = unit_name(unit), unit_name(to)
    if value is None or unit is None or to is None:
        return None
    if unit == to:
        return value
    if (unit, to) == ("°C", "°F"):
        return round(value * 9 / 5 + 32, 1)
    if (unit, to) == ("°F", "°C"):
        return round((value - 32) * 5 / 9, 1)
    factor = TO_BASE.get((unit, to))
    return None if factor is None else round(value * factor, 2)


def span_found(figure, text):
    """A figure counts only if the quote sits in the store's text at the stated offsets."""
    start, end, quote = figure.get("start"), figure.get("end"), figure.get("quote")
    if not isinstance(start, int) or not isinstance(end, int) or not quote or text is None:
        return False
    return 0 <= start < end <= len(text) and text[start:end] == quote


def sentence_around(text, start, end, most=260):
    """(sentence, a, b): the store's sentence holding the span, and where the span sits inside it.
    A very long sentence is cut at word ends near the span and marked with ellipses."""
    left = max(text.rfind(". ", 0, start) + 2 if text.rfind(". ", 0, start) >= 0 else 0,
               text.rfind("\n", 0, start) + 1, text.rfind("? ", 0, start) + 2 if text.rfind("? ", 0, start) >= 0 else 0)
    stops = [i for i in (text.find(". ", end - 1), text.find("\n", end), text.find("? ", end)) if i >= 0]
    right = min(min(stops) + 1 if stops else len(text), len(text))
    right = max(right, end)
    head, tail = "", ""
    if right - left > most:
        room = max((most - (end - start)) // 2, 20)
        if start - left > room:
            cut = text.find(" ", start - room, start)
            left, head = (cut + 1 if cut >= 0 else start - room), "… "
        if right - end > room:
            cut = text.rfind(" ", end, end + room)
            right, tail = (cut if cut >= 0 else end + room), " …"
    sentence = head + text[left:right].rstrip() + tail
    a = len(head) + start - left
    return sentence, a, a + (end - start)


def deciding(fig, op, bound=None):
    """A spread uses the end that could fail. An adjustable range uses the end that reaches furthest.
    For an equality the end that could fail is the one further from the value to be matched; an adjustable
    range that takes in that value is set to it."""
    if fig["kind"] == "single":
        return fig["value"]
    if op == "==":
        if fig["kind"] == "adjustable" and bound is not None and fig["low"] <= bound <= fig["high"]:
            return bound
        if bound is None:
            return fig["high"]
        return fig["low"] if abs(fig["low"] - bound) >= abs(fig["high"] - bound) else fig["high"]
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
    op = limit["op"]
    if op not in OPS:
        raise ValueError("limit %s has the comparison %r; the rules know %s" % (limit.get("id"), op, ", ".join(OPS)))
    b = limit["bound"]
    if b["source"] == "issuer":
        bound = {"owner": "issuer", "owner_name": sheet["issuer"]["name"], "value": b["value"], "unit": limit["unit"]}
    else:
        f = facts[b["fact"]]
        bound = {"owner": "shopper", "owner_name": sheet["shopper"]["name"], "fact": f["id"], "label": f["short"],
                 "value": f["value"], "unit": f["unit"]}
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
        v = deciding(fig, op, bound["value"] if len(limit["terms"]) == 1 else None)
        if fig["kind"] == "adjustable":
            adjustable = fig
        terms.append({"owner": "store", "owner_name": product["store"], "label": t["figure"].replace("_", " "),
                      "figure": t["figure"], "value": v, "unit": fig["unit"], "kind": fig["kind"],
                      "low": fig["low"], "high": fig["high"], "quote": fig["quote"],
                      "start": fig["start"], "end": fig["end"]})
        if fig.get("sentence"):
            terms[-1].update(sentence=fig["sentence"], quote_in_sentence=fig["quote_in_sentence"])
        lhs += v
    out = {"limit_id": limit["id"], "name": limit["name"], "terms": terms, "op": op, "bound": bound}
    if missing:
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "not_stated",
                    "missing_figure": missing})
        if why_missing != "never stated on the page":
            out["missing_why"] = why_missing
        return out
    shown = " + ".join("%g" % t["value"] for t in terms)
    expr = ("%s = %g %s %g" % (shown, lhs, op, bound["value"])) if len(terms) > 1 else \
        "%g %s %g" % (lhs, op, bound["value"])
    if op == "==":  # a point on the ruler, not a side: 0 when it matches, otherwise how far off, as a negative
        ok = abs(lhs - bound["value"]) < 1e-9
        margin = 0.0 if ok else round(-abs(lhs - bound["value"]), 2)
        out.update({"lhs": round(lhs, 2), "expr": expr, "pass": ok, "margin": margin, "state": "pass" if ok else "fail"})
        return out
    ok = lhs >= bound["value"] if op == ">=" else lhs <= bound["value"]
    margin = round(lhs - bound["value"] if op == ">=" else bound["value"] - lhs, 2)
    if adjustable and ok:  # an adjustable range passes only when the limit lies inside it
        others = lhs - deciding(adjustable, op)
        low, high = adjustable["low"] + others, adjustable["high"] + others
        ok = low <= bound["value"] <= high
        if not ok:  # the range reaches past the limit but cannot be set to it
            expr = "%g within %g to %g" % (bound["value"], low, high)
            margin = round(-abs(low - bound["value"] if op == ">=" else bound["value"] - high), 2)
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
        rule = (sheet.get("pick_rule") or {}).get("id", "cheapest_with_delivery_time")
        if rule not in PICK_RULES:
            raise ValueError("the sheet's pick rule %r is not one the rules know (%s)" % (rule, ", ".join(PICK_RULES)))
        needs_time = rule == "cheapest_with_delivery_time" and not local
        eligible = sorted((c for c in inside if not needs_time or c["arrival"]["status"] == "stated"),
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
                        "text": "matches exactly" if t["op"] == "==" else "nothing to spare" if t["margin"] == 0
                        else "%g %s to spare" % (t["margin"], t["bound"]["unit"])}
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
                      "why": {"total": len(cands), "inside": len(inside),
                              "with_delivery_time": len(eligible) if rule == "cheapest_with_delivery_time" else
                              sum(1 for c in inside if c["arrival"]["status"] == "stated"),
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
