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
    """The one value of a statement that is put to the test when only one can be shown: for a single number,
    itself; for a range of settings, the setting that best meets the comparison (rule 3); for a spread, the
    end that could fail."""
    if fig["kind"] == "single":
        return fig["value"]
    if fig["kind"] == "adjustable":
        if op == "==":
            if bound is not None and fig["low"] <= bound <= fig["high"]:
                return bound
            if bound is None:
                return fig["high"]
            return fig["low"] if abs(fig["low"] - bound) <= abs(fig["high"] - bound) else fig["high"]
        return fig["high"] if op == ">=" else fig["low"]
    if op == "==":
        if bound is None:
            return fig["high"]
        return fig["low"] if abs(fig["low"] - bound) >= abs(fig["high"] - bound) else fig["high"]
    return fig["low"] if op == ">=" else fig["high"]


def tested_values(fig, op, bound):
    """Every value one statement puts to the test (rule 1), in the statement's own unit.
    - a single number: that number, and any other number in its quote that the text does not rule out;
    - a spread (one size given loosely, or several values given together): both ends;
    - a range the user can set (rule 3): the setting that meets the comparison if one does, so "at least"
      and "at most" pass when the product can be set to meet them, and an equality needs the value in range."""
    if fig["kind"] == "adjustable":
        values = [deciding(fig, op, bound)]
    elif fig["kind"] == "spread":
        values = [fig["low"], fig["high"]]
    else:
        values = [fig["value"]]
    for other in fig.get("possible") or []:
        if isinstance(other, (int, float)) and not any(abs(other - v) < 1e-9 for v in values):
            values.append(other)
    return values


def comparable(fig, limit_unit):
    """Why a statement's number cannot be put beside the limit, or None when it can. A statement that cannot
    be compared is still a statement: the check is unclear, the figure is not absent."""
    numbers = [fig.get("value")] if fig.get("kind") == "single" else [fig.get("low"), fig.get("high")]
    if fig.get("kind") not in ("single", "spread", "adjustable") or \
            any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in numbers):
        return "stated without a number code can compare"
    if fig.get("for_other_option"):
        return fig["for_other_option"]
    if unit_name(fig.get("unit")) is None:
        return "no unit stated"
    if unit_name(fig.get("unit")) != unit_name(limit_unit):
        return "stated in %s, not %s" % (fig.get("unit"), limit_unit)
    return None


def holds(lhs, op, bound):
    if op == "==":
        return abs(lhs - bound) < 1e-9
    return lhs >= bound if op == ">=" else lhs <= bound


def margin_of(lhs, op, bound):
    if op == "==":
        return 0.0 if abs(lhs - bound) < 1e-9 else round(-abs(lhs - bound), 2)
    return round(lhs - bound if op == ">=" else bound - lhs, 2)


def check(limit, product, figs, facts, sheet):
    """One limit against one candidate. Every value the page states for the figure is tested: all pass, the
    check passes; all fail, it fails; they differ, or a statement cannot be compared, it is unclear. Only a
    figure with no statement at all is not stated."""
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
    home = 0.0 + sum(facts[t["fact"]]["value"] for t in limit["terms"] if t["source"] == "shopper")
    store_terms = [t for t in limit["terms"] if t["source"] == "store"]
    alone = bound["value"] - home if len(store_terms) == 1 else None  # what one store figure is compared with
    terms, missing, unclear, choices = [], None, None, []
    for t in limit["terms"]:
        if t["source"] == "shopper":
            f = facts[t["fact"]]
            terms.append({"owner": "shopper", "owner_name": sheet["shopper"]["name"], "label": f["short"],
                          "fact": f["id"], "value": f["value"], "unit": f["unit"]})
            continue
        label = t["figure"].replace("_", " ")
        stated = [f for f in figs.get((product["store"], product["product_id"], product.get("variant_id"), t["figure"]), [])
                  if f.get("span_found_in_text") and f.get("number_in_quote") is not False]
        if not stated:
            missing = missing or t["figure"]
            terms.append({"owner": "store", "owner_name": product["store"], "label": label,
                          "figure": t["figure"], "value": None, "unit": limit["unit"]})
            continue
        usable = [f for f in stated if comparable(f, limit["unit"]) is None]
        first = (usable or stated)[0]
        term = {"owner": "store", "owner_name": product["store"], "label": label, "figure": t["figure"],
                "value": None, "unit": first.get("unit") or limit["unit"], "kind": first.get("kind"),
                "low": first.get("low"), "high": first.get("high"), "quote": first.get("quote"),
                "start": first.get("start"), "end": first.get("end")}
        if first.get("sentence"):
            term.update(sentence=first["sentence"], quote_in_sentence=first["quote_in_sentence"])
        if len(stated) > 1:
            term["statements"] = len(stated)
        if not usable:
            unclear = unclear or comparable(stated[0], limit["unit"])
            shown = stated[0].get("value") if stated[0].get("kind") == "single" else stated[0].get("low")
            term.update(value=shown if isinstance(shown, (int, float)) else None, unit=stated[0].get("unit") or limit["unit"])
            terms.append(term)
            continue
        values = []
        for f in usable:
            for v in tested_values(f, op, alone):
                if not any(abs(v - w) < 1e-9 for w in values):
                    values.append(v)
        several = limit.get("several")  # the order may say which of several stated values counts
        if several == "largest":
            values = [max(values)]
        elif several == "smallest":
            values = [min(values)]
        terms.append(term)
        choices.append((term, values))
    out = {"limit_id": limit["id"], "name": limit["name"], "terms": terms, "op": op, "bound": bound}
    if missing:
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "not_stated",
                    "missing_figure": missing})
        return out
    if unclear:
        for term, values in choices:
            term["value"] = values[0]
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "unclear", "unclear_why": unclear})
        return out
    combos = [(home, [])]
    for term, values in choices:
        combos = [(total + v, picked + [v]) for total, picked in combos for v in values][:64]
    results = [(total, holds(total, op, bound["value"]), margin_of(total, op, bound["value"]), picked)
               for total, picked in combos]
    passed = [r for r in results if r[1]]

    def expr_of(total, picked):
        position, shown = 0, []
        for t in terms:
            if t["owner"] == "shopper":
                shown.append("%g" % t["value"])
            else:
                shown.append("%g" % picked[position])
                position += 1
        return ("%s = %g %s %g" % (" + ".join(shown), total, op, bound["value"])) if len(terms) > 1 else \
            "%g %s %g" % (total, op, bound["value"])

    if len(passed) in (0, len(results)):
        # every stated value agrees. A pass is shown on the value nearest to failing; a failure on the value
        # nearest to passing, so the line reads "even the best stated value fails".
        total, ok, margin, picked = (min if passed else max)(results, key=lambda r: r[2])
        for (term, values), v in zip(choices, picked):
            term["value"] = v
        out.update({"lhs": round(total, 2), "expr": expr_of(total, picked), "pass": ok, "margin": margin,
                    "state": "pass" if ok else "fail"})
        return out
    for term, values in choices:  # the stated values differ in outcome: unclear, with what the page states
        term["value"], term["values"] = values[0], values
    stated_all = sorted({v for _, values in choices for v in values})
    unit = next((t["unit"] for t in terms if t["owner"] == "store"), limit["unit"])
    out.update({"lhs": None, "pass": False, "margin": None, "state": "unclear",
                "expr": "%s %s %g" % (" or ".join("%g" % r[0] for r in results), op, bound["value"]),
                "unclear_why": "page states both %s %s" % (" and ".join("%g" % v for v in stated_all), unit),
                "values": [{"lhs": round(r[0], 2), "pass": r[1]} for r in results]})
    return out


def figure_index(figures, pool=()):
    """{(store, product_id, variant_id, figure): [statements]}: every statement of a figure for each candidate.
    A statement read for one option belongs to that option; one read for the product belongs to all its rows."""
    rows = {}
    for p in pool:
        rows.setdefault((p["store"], p["product_id"]), []).append(p.get("variant_id"))
    figs = {}
    for f in figures:
        own = f.get("variant_id")
        every = rows.get((f["store"], f["product_id"]), [own])
        for variant in ([own] if own is not None and own in every else every):
            figs.setdefault((f["store"], f["product_id"], variant, f["figure"]), []).append(f)
    return figs


def usable_rank(f):
    return (0 if f.get("span_found_in_text") else 2) + (1 if f.get("unsure") else 0)


def build_state(sheet, pool, figures, answers, strikes, mode="fixture"):
    facts = {f["id"]: f for f in sheet["shopper_facts"]}
    figs = figure_index(figures, pool)
    several_rows = {}
    for p in pool:
        several_rows[(p["store"], p["product_id"])] = several_rows.get((p["store"], p["product_id"]), 0) + 1
    by_product = {}
    for f in figures:
        by_product.setdefault((f["store"], f["product_id"]), []).append(f)
    ans = {a["store"]: a for a in answers}
    # products found are pages; a product sold in several options is one page and several candidates
    lines, found, every, inside_n, ready = [], len({(p["store"], p["product_id"]) for p in pool}), 0, 0, 0
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
            failed = [c for c in checks if c["state"] == "fail"]
            unclear = [c for c in checks if c["state"] == "unclear"]
            strike = struck_by_key.get(p["product_key"])
            if strike:
                status, reason = "struck", strike["reason"]
            elif failed:  # a stated value that fails decides, whatever else the page leaves out
                status, reason = "outside", "%s: %s is false" % (failed[0]["name"], failed[0]["expr"])
            elif missing:
                status = "not_stated"
                reason = "%s never stated on the page" % missing[0]["missing_figure"].replace("_", " ")
            elif unclear:
                status, reason = "unclear", "%s: %s" % (unclear[0]["name"], unclear[0]["unclear_why"])
            else:
                status, reason = "inside", None
            every += 0 if missing else 1
            cands.append({
                "id": "%s:%s:%s" % (line["id"], p["store"], p["product_id"]) + (
                    ":%s" % p.get("variant_id") if several_rows[(p["store"], p["product_id"])] > 1 else ""),
                "order_line": {"id": line["id"], "need": line["need"], "room": line["room"]},
                "product": {k: p[k] for k in ("store", "product_id", "variant_id", "title", "price_cents", "url",
                                              "fetched_at", "product_key")},
                "figures": [f for f in by_product.get((p["store"], p["product_id"]), [])
                            if f.get("variant_id") in (None, p.get("variant_id")) or several_rows[(p["store"], p["product_id"])] == 1],
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
            elif any(c["status"] == "unclear" for c in cands):
                reason = "no page states every figure clearly"
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
