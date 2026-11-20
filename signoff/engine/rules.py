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
DECLARED = {}  # units a sheet declares itself: {name: [spellings]}; each is its own kind of measure


def declare_units(sheet):
    """A sheet may name its own units and how stores spell them (`"units": {"dB": ["db", "decibels"], ...}`), so a
    new sheet needs no change here. The table above stays as the default for units a sheet does not declare.
    The units of the sheet declared before are taken out first: one sheet's units never linger into another's."""
    for name, spellings in list(DECLARED.items()):
        for spelling in spellings:
            if ALIASES.get(spelling) == name and spelling not in _BUILT_IN:
                ALIASES.pop(spelling, None)
        if name not in _BUILT_IN_FAMILY:
            FAMILY.pop(name, None)
        DECLARED.pop(name, None)
    for name, spellings in (sheet.get("units") or {}).items():
        DECLARED[name] = sorted({str(x).lower() for x in list(spellings) + [name]}, key=len, reverse=True)
        for spelling in DECLARED[name]:
            ALIASES.setdefault(spelling, name) if spelling in _BUILT_IN else ALIASES.__setitem__(spelling, name)
        FAMILY.setdefault(name, name)


_BUILT_IN, _BUILT_IN_FAMILY = frozenset(ALIASES), frozenset(FAMILY)
OPS = (">=", "<=", "==")
PICK_RULES = ("cheapest_with_delivery_time", "cheapest", "best_reviewed", "best_value", "most_popular")
RATING_RULES = ("best_reviewed", "best_value", "most_popular")  # those that order by what reviewers are quoted as saying
WITHIN = 0.3  # stars on a five-star scale: how far under the best quoted rating "best value" still looks


def within_of(sheet):
    w = (sheet.get("pick_rule") or {}).get("within", WITHIN)
    if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
        raise ValueError("the pick rule's `within` is %r; it must be a number of stars, 0 or more" % (w,))
    return w


def pick_rules(within=WITHIN):
    """The orderings a shopper may choose among the products that pass, with the words shown for each."""
    return [{"id": "cheapest", "label": "cheapest inside the limits"},
            {"id": "best_reviewed", "label": "best reviewed among those that pass"},
            {"id": "best_value", "label": "best value: cheapest within %g stars of the best rated" % within},
            {"id": "most_popular", "label": "most reviewed among those that pass"},
            {"id": "cheapest_with_delivery_time", "label": "cheapest that states a delivery time"}]


def stars(quoted):
    """A quoted rating on a five-star scale, or None. A rating is used only as quoted, with the scale it was
    quoted on: one without a scale cannot be compared with the others and is not guessed."""
    if not isinstance(quoted, dict):
        return None
    r, out_of = quoted.get("rating"), quoted.get("out_of")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (r, out_of)) or out_of <= 0 or not 0 <= r <= out_of:
        return None
    return r * 5.0 / out_of


def review_count(quoted):
    """How many reviews were counted, as quoted, or None when no count was quoted."""
    n = quoted.get("review_count") if isinstance(quoted, dict) else None
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None


def pick_order(rule, within, passing, ratings, met):
    """A pick rule is one sort key over the candidates that pass; the first in that order is the pick.
    Returns (key, {candidate id: stars or None}, the best quoted rating or None). More preferences met come
    first under every rule; a product with no quoted rating follows the rated ones, by price."""
    star = {c["id"]: stars(ratings.get(c["id"])) for c in passing}
    best = max((s for s in star.values() if s is not None), default=None)

    def price(c):
        return (c["product"]["price_cents"], c["id"])

    def reviews(c):
        return review_count(ratings.get(c["id"])) or 0

    if rule == "most_popular":
        def by_rule(c):
            n = review_count(ratings.get(c["id"]))
            return ((1, 0, 0) if n is None else (0, -n, -(star[c["id"]] or 0))) + price(c)
    elif rule == "best_reviewed":
        def by_rule(c):
            s = star[c["id"]]
            return ((1, 0, 0) if s is None else (0, -s, -reviews(c))) + price(c)
    elif rule == "best_value":
        def by_rule(c):
            s = star[c["id"]]
            return ((2,) if s is None else (0,) if s >= best - within - 1e-9 else (1,)) + price(c)
    else:
        by_rule = price
    return (lambda c: (-met.get(c["id"], 0),) + by_rule(c)), star, best


def rating_words(quoted):
    r, out_of, n = quoted["rating"], quoted["out_of"], quoted.get("review_count")
    return "rated %g%s%s" % (r, "" if out_of == 5 else " out of %g" % out_of,
                             " from %d review%s" % (n, "" if n == 1 else "s") if isinstance(n, int) and not isinstance(n, bool) else "")


def picked_because(rule, within, pick, passing, ratings, star, best, met, preferences, needs_time):
    """Why the rule's pick is the pick, in one clause the screen can print."""
    s = star.get(pick["id"])
    if rule == "most_popular":
        n = review_count(ratings.get(pick["id"]))
        if n is None:
            clause = "cheapest that passes; %s" % ("it has no quoted review count" if any(
                review_count(ratings.get(c["id"])) is not None for c in passing) else "none of them has a quoted review count")
        else:
            clause = "%d review%s%s, the most that passes" % (n, "" if n == 1 else "s", "" if s is None else
                                                              " (%s)" % rating_words(dict(ratings[pick["id"]], review_count=None)))
    elif rule in RATING_RULES and best is None:
        clause = "cheapest that passes; none of them has a quoted rating"
    elif rule in RATING_RULES and s is None:
        clause = "cheapest that passes; it has no quoted rating"
    elif rule == "best_reviewed":
        clause = "%s, the highest that passes" % rating_words(ratings[pick["id"]])
    elif rule == "best_value" and s >= best - 1e-9:
        clause = "%s, the best rated that passes and the cheapest within %g stars of it" % (rating_words(ratings[pick["id"]]), within)
    elif rule == "best_value" and s >= best - within - 1e-9:
        clause = "cheapest within %g stars of the best rated (%g against %g)" % (within, round(s, 2), round(best, 2))
    elif rule == "best_value":
        clause = "cheapest of those rated (%g against %g)" % (round(s, 2), round(best, 2))
    else:
        clause = "cheapest that passes and states a delivery time" if needs_time else "cheapest that passes"
    mine = met.get(pick["id"], 0)
    if preferences and mine and any(met.get(c["id"], 0) < mine for c in passing):
        clause += ", among those that meet %s" % ("the preference" if len(preferences) == 1 else
                                                 "%d of the %d preferences" % (mine, len(preferences)))
    return clause


PREFERENCE_STATUS = {"pass": "met", "fail": "not_met", "unclear": "unclear", "not_stated": "not_stated"}


def preference(checked):
    """A preference is checked by the same function as a limit; only what is done with the result differs."""
    out = {"id": checked["limit_id"], "label": checked["name"], "status": PREFERENCE_STATUS[checked["state"]],
           "value": checked.get("lhs"), "expr": checked.get("expr"),
           "quote": next((t["quote"] for t in checked["terms"] if t.get("quote")), None)}
    if checked.get("unclear_why"):
        out["why"] = checked["unclear_why"]
    return out


def validate_sheet(sheet):
    """A sheet the rules cannot run is refused when it is loaded, with the reason: an unknown comparison or an
    unknown pick rule is an error, never quietly treated as something else."""
    for line in sheet["lines"]:
        q = line.get("quantity", 1)
        if isinstance(q, bool) or not isinstance(q, int) or q < 1:
            raise ValueError("line %s has the quantity %r; it must be a whole number of at least 1" % (line.get("id"), q))
        for limit in line["limits"] + (line.get("preferences") or []):
            if limit.get("op") not in OPS:
                raise ValueError("limit %s has the comparison %r; the rules know %s" % (limit.get("id"), limit.get("op"), ", ".join(OPS)))
    rule = (sheet.get("pick_rule") or {}).get("id")
    if rule not in PICK_RULES:
        raise ValueError("the sheet's pick rule %r is not one the rules know (%s)" % (rule, ", ".join(PICK_RULES)))
    within_of(sheet)


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


def comparable(fig, limit_unit, unit_required=True):
    """Why a statement's number cannot be put beside the limit, or None when it can. A statement that cannot
    be compared is still a statement: the check is unclear, the figure is not absent."""
    numbers = [fig.get("value")] if fig.get("kind") == "single" else [fig.get("low"), fig.get("high")]
    if fig.get("kind") not in ("single", "spread", "adjustable") or \
            any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in numbers):
        return "stated without a number code can compare"
    if fig.get("disagree"):
        return fig["disagree"]  # the two readers do not report the same value for it
    if fig.get("for_other_option"):
        return fig["for_other_option"]
    if unit_name(fig.get("unit")) is None:
        # a length or a weight without its unit cannot be compared; a count is a bare number, and a sheet says so
        # on the limit with "unit_required": false (the label then says what is counted)
        return None if not unit_required and fig.get("unit") is None else "no unit stated"
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
        needs_unit = limit.get("unit_required", True)
        usable = [f for f in stated if comparable(f, limit["unit"], needs_unit) is None]
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
            unclear = unclear or comparable(stated[0], limit["unit"], needs_unit)
            shown = stated[0].get("value") if stated[0].get("kind") == "single" else stated[0].get("low")
            term.update(value=shown if isinstance(shown, (int, float)) else None, unit=stated[0].get("unit") or limit["unit"])
            terms.append(term)
            continue
        values, source = [], {}
        usable.sort(key=lambda f: bool(f.get("option_name")))  # where the page and the option's name agree, the page's words are shown
        first = usable[0]
        term.update(kind=first.get("kind"), low=first.get("low"), high=first.get("high"), quote=first.get("quote"),
                    start=first.get("start"), end=first.get("end"))
        for f in usable:
            for v in tested_values(f, op, alone):
                if not any(abs(v - w) < 1e-9 for w in values):
                    values.append(v)
                    source[v] = f  # the statement this value was read from: its words are shown beside it
        several = limit.get("several")  # the order may say which of several stated values counts
        if several == "largest":
            values = [max(values)]
        elif several == "smallest":
            values = [min(values)]
        term["_source"] = source
        terms.append(term)
        choices.append((term, values))
    def show(term, value):
        """The term shows the value put to the test with the words of the statement it came from."""
        f = term.pop("_source", {}).get(value)
        term["value"] = value
        if f is not None:
            term.update(kind=f.get("kind"), low=f.get("low"), high=f.get("high"), quote=f.get("quote"),
                        start=f.get("start"), end=f.get("end"), unit=f.get("unit") or term["unit"])
            if f.get("sentence"):
                term.update(sentence=f["sentence"], quote_in_sentence=f["quote_in_sentence"])
            if f.get("option_match"):
                term["option_match"] = f["option_match"]  # which of the page's statements was matched to this option, and why

    out = {"limit_id": limit["id"], "name": limit["name"], "terms": terms, "op": op, "bound": bound}
    if missing:
        for term in terms:
            term.pop("_source", None)
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "not_stated",
                    "missing_figure": missing})
        return out
    if unclear:
        for term, values in choices:
            show(term, values[0])
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
            show(term, v)
        out.update({"lhs": round(total, 2), "expr": expr_of(total, picked), "pass": ok, "margin": margin,
                    "state": "pass" if ok else "fail"})
        return out
    for term, values in choices:  # the stated values differ in outcome: unclear, with what the page states
        show(term, values[0])
        term["values"] = values
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


def build_state(sheet, pool, figures, answers, strikes, mode="fixture", ratings=None):
    facts = {f["id"]: f for f in sheet["shopper_facts"]}
    figs = figure_index(figures, pool)
    several_rows = {}
    for p in pool:
        several_rows[(p["store"], p["product_id"])] = several_rows.get((p["store"], p["product_id"]), 0) + 1
    by_product = {}
    for f in figures:
        by_product.setdefault((f["store"], f["product_id"]), []).append(f)
    quoted = ratings or {}  # {candidate id: {rating, out_of, review_count}}, only what somebody quoted
    ans = {a["store"]: a for a in answers}
    # products found are pages; a product sold in several options is one page and several candidates
    lines, found, every, inside_n, ready = [], len({(p["store"], p["product_id"]) for p in pool}), 0, 0, 0
    for line in sheet["lines"]:
        struck = [s for s in strikes if s["line_id"] == line["id"]]
        struck_by_key = {s["product_key"]: s for s in struck}
        preferences = line.get("preferences") or []
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
            if preferences:  # checked like a limit, shown beside the checks, and never part of the status above
                cands[-1]["preferences"] = [preference(check(wish, p, figs, facts, sheet)) for wish in preferences]
            if stars(quoted.get(cands[-1]["id"])) is not None:
                cands[-1]["rating"] = {k: quoted[cands[-1]["id"]].get(k) for k in ("rating", "out_of", "review_count")}
            if review_count(quoted.get(cands[-1]["id"])) is not None:  # a count is quoted with or without a rating's scale
                cands[-1]["review_count"] = review_count(quoted[cands[-1]["id"]])
        inside = [c for c in cands if c["status"] == "inside"]
        local = line["fulfilment"] == "pick_up_locally"  # nothing is shipped, so no delivery time is needed
        rule = (sheet.get("pick_rule") or {}).get("id", "cheapest_with_delivery_time")
        if rule not in PICK_RULES:
            raise ValueError("the sheet's pick rule %r is not one the rules know (%s)" % (rule, ", ".join(PICK_RULES)))
        needs_time = rule == "cheapest_with_delivery_time" and not local
        eligible = [c for c in inside if not needs_time or c["arrival"]["status"] == "stated"]
        met = {c["id"]: sum(1 for w in c.get("preferences", ()) if w["status"] == "met") for c in eligible}
        order, star, best = pick_order(rule, within_of(sheet), eligible, quoted, met)
        eligible.sort(key=order)
        pick = eligible[0] if eligible else None
        inside_n += len(inside)
        if pick:
            pick["picked"] = True
            if ratings is not None:
                pick["picked_because"] = picked_because(rule, within_of(sheet), pick, eligible, quoted, star, best, met,
                                                        preferences, needs_time)
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
        why = lines[-1]["why"]
        if rule in RATING_RULES:  # the label actually applied: how many of those that pass anyone has rated
            counted = rule == "most_popular"  # this one orders by the count of reviews, the others by the rating
            rated = sum(1 for c in eligible if review_count(quoted.get(c["id"])) is not None) if counted else \
                sum(1 for s in star.values() if s is not None)
            name = "most reviewed" if counted else "best reviewed" if rule == "best_reviewed" else \
                "best value (cheapest within %g stars of the best rated)" % within_of(sheet)
            what = "a quoted review count" if counted else "a quoted rating"
            why["rated"] = rated
            why["rule"] = "%s: nothing passes" % name if not eligible else (
                "%s: %d of %d that pass ha%s %s" % (name, rated, len(eligible), "s" if rated == 1 else "ve", what)
                if rated else "%s: none of the %d that pass has %s, so the cheapest is shown" % (name, len(eligible), what))
        if preferences:
            full = sum(1 for c in eligible if met[c["id"]] == len(preferences))
            why["preferences"] = "%d of %d that pass meet%s %s" % (
                full, len(eligible), "s" if full == 1 else "",
                "the preference" if len(preferences) == 1 else "all %d preferences" % len(preferences))
    quantity = {line["id"]: line.get("quantity", 1) for line in sheet["lines"]}  # how many of the pick the list asks for
    total = sum(c["product"]["price_cents"] * quantity[l["line_id"]] for l in lines for c in l["candidates"]
                if c["picked"] and l["status"] in ("ready", "next_candidate"))
    return {"version": 1, "mode": mode, "sheet": sheet,
            "seal": {"signed": False, "text": "Not signed. No cart exists at any store.", "sheet_hash": None,
                     "signature": None, "carts": []},
            "issuer_key": {"enrolled": False, "key_id": None, "persona": None},
            "counts": {"products_found": found, "state_every_figure": every, "inside_limits": inside_n,
                       "lines_ready": ready, "lines_total": len(lines), "hand_checked": False},
            "total_cents": total, "store_answers": answers, "lines": lines}
